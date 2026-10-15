"""
Supabase JWT verification via JWKS.

This is ADR 0002, pulled forward from S02 because the alternative does not work.

Supabase now signs access tokens with **asymmetric** keys by default. A token
from this project has header `{"alg":"ES256", "kid": "..."}`, and the project
publishes the matching public key at
`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`:

    {"keys":[{"alg":"ES256","kty":"EC","crv":"P-256","kid":"...","x":"...","y":"..."}]}

`security.py` previously called `jwt.decode(token, JWT_SECRET_KEY,
algorithms=["HS256"])`, which failed with *"The specified alg value is not
allowed"* on every authenticated request. No value of `JWT_SECRET_KEY` could
have fixed that: HS256 is a symmetric MAC and the token is an ECDSA signature.
The secret was never the problem.

Verifying against the published public key is also better than the shared
secret it replaces:

* The backend never holds a credential capable of *minting* tokens, only of
  checking them. A leaked JWKS cache is worthless to an attacker.
* Supabase can rotate signing keys without a coordinated backend deploy — a new
  `kid` simply triggers a refetch.

HS256 remains supported for projects still on a legacy shared secret, chosen per
token by its own `alg` header, so this works on either configuration.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# Supabase issues access tokens with this audience.
_EXPECTED_AUDIENCE = "authenticated"

# Asymmetric only, deliberately. ADR 0002: a symmetric algorithm means the
# verifier holds a key that can also *mint*, and this project's `.env` — which
# carries `JWT_SECRET_KEY` — is committed on purpose. ES256 is what Supabase
# issues here; RS256 is kept because it is the other asymmetric algorithm a
# Supabase project can be configured for, and it has the same property.
_ALLOWED_ALGORITHMS = frozenset({"ES256", "RS256"})

# Clock skew tolerance between this host and Supabase, in seconds.
_LEEWAY = 10

# How long a fetched key set is trusted before refetching. Short enough to pick
# up a rotation promptly, long enough that normal traffic is not making an
# outbound request per API call.
_CACHE_TTL_SECONDS = 600

# Refetching on *every* unknown kid would let an attacker drive outbound
# requests by sending junk tokens, so a forced refresh is rate limited.
_MIN_REFETCH_INTERVAL_SECONDS = 30


class _JwksCache:
    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0
        self._last_attempt: float = 0.0

    @property
    def _url(self) -> str:
        base = (settings.SUPABASE_URL or "").rstrip("/")
        if not base:
            raise RuntimeError(
                "SUPABASE_URL is not set, so JWT signing keys cannot be fetched. "
                "Add it to backend/.env (see backend/migrations/supabase/README.md)."
            )
        return f"{base}/auth/v1/.well-known/jwks.json"

    async def _fetch(self) -> None:
        url = self._url
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            document = response.json()

        keys = {k["kid"]: k for k in document.get("keys", []) if "kid" in k}
        if not keys:
            raise RuntimeError(f"{url} returned no usable signing keys")

        self._keys = keys
        self._fetched_at = time.monotonic()
        logger.info(
            "Loaded %d Supabase signing key(s): %s",
            len(keys),
            ", ".join(f"{k[:8]}…({v.get('alg')})" for k, v in keys.items()),
        )

    async def get(self, kid: str) -> dict[str, Any]:
        """Return the JWK for `kid`, refetching if it is unknown or stale."""
        now = time.monotonic()
        expired = (now - self._fetched_at) > _CACHE_TTL_SECONDS

        if not self._keys or expired or kid not in self._keys:
            may_attempt = (now - self._last_attempt) > _MIN_REFETCH_INTERVAL_SECONDS
            if may_attempt or not self._keys:
                self._last_attempt = now
                try:
                    await self._fetch()
                except Exception as exc:  # noqa: BLE001 - surfaced as 401 below
                    logger.warning("Could not refresh Supabase signing keys: %s", exc)

        if kid not in self._keys:
            raise JWTError(f"No signing key published for kid {kid!r}")
        return self._keys[kid]


_cache = _JwksCache()


async def verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verify a Supabase access token and return its claims.

    Raises `JWTError` on anything invalid — expired, wrong audience, unknown
    key, bad signature, or a missing `aud`. Callers turn that into a 401.

    **Asymmetric only.** See ADR 0002's finding of 2026-10-15: the HS256 branch
    that used to be here was a legacy accommodation this project never needed,
    and it was what made a forged token verify. `endpoints/auth.py` minted
    `{"sub": "user_id"}` tokens with `JWT_SECRET_KEY` for anyone who asked, and
    this function accepted them. The endpoint is gone, the minting helpers are
    gone, and so is the branch that trusted a shared secret — three faults, any
    one of which was sufficient, so all three were removed rather than the
    cheapest one.

    If a Supabase project on a genuinely legacy symmetric secret ever has to be
    supported, that is a deliberate change here with a test alongside it, not a
    fallback that happens to be reachable.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"Malformed token header: {exc}") from exc

    algorithm = header.get("alg")
    if not algorithm:
        raise JWTError("Token header has no 'alg'")

    if algorithm not in _ALLOWED_ALGORITHMS:
        raise JWTError(
            f"Unsupported token algorithm: {algorithm}. This project's tokens are "
            "ES256; symmetric algorithms are refused (ADR 0002)."
        )

    kid = header.get("kid")
    if not kid:
        raise JWTError(f"{algorithm} token has no 'kid', cannot select a key")
    key: Any = await _cache.get(kid)

    # `require` is the part that matters, and it is not implied by `verify_aud`.
    # A token carrying no `aud` claim at all was *accepted* under
    # `{"verify_aud": True}` alone — measured, and the single fault that would
    # have blocked the bypass on its own. Every genuine Supabase access token
    # carries `aud: "authenticated"`, so requiring it rejects nothing real.
    #
    # `leeway` tolerates small clock differences between this host and Supabase;
    # without it a correctly-issued token can be rejected as not-yet-valid.
    options = {
        "verify_aud": True,
        "leeway": _LEEWAY,
        "require": ["exp", "aud", "sub"],
    }

    return jwt.decode(
        token,
        key,
        algorithms=[algorithm],
        audience=_EXPECTED_AUDIENCE,
        options=options,
    )
