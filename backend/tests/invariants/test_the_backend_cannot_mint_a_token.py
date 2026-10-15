"""
This backend verifies tokens. It must never be able to issue one. ADR 0002.

## The failure this exists for, which was live until 2026-10-15

`POST /api/v1/auth/login` was registered, unauthenticated, and returned a
**signed, accepted** token for any email posted to it:

    access_token = create_access_token({"sub": "user_id", "email": request.email})

`verify_password` was imported in that file and never called. Measured before
removal:

    verify_supabase_token(forged)  -> ACCEPTED
    get_current_user(forged)       -> {'user_id': 'user_id', 'email': 'attacker@...'}

So every endpoint behind `get_current_user` was reachable without credentials,
including `/sos/trigger` — which emails a police station — and `/ai/*` and
`/casework/*`, which spend LLM budget on each call.

Three faults stacked, and this file has a test for each, because any one of them
coming back is sufficient on its own:

1. **the backend could mint** — `create_access_token`/`create_refresh_token`
   signed with `JWT_SECRET_KEY`;
2. **the verifier accepted HS256** whenever that secret was set, so what the
   backend minted, the backend trusted — and `.env` is committed on purpose
   here, so the secret is not secret;
3. **the `aud` claim was not required.** `options={"verify_aud": True}` with
   `audience="authenticated"` accepted a token carrying no `aud` at all. This
   one would have blocked the bypass by itself.

## Why a source scan and not just an import check

The bypass did not survive because anyone decided it should. It survived because
**nothing exercised it** — the same reason defect 31's unconditional police
routing went unnoticed. An endpoint nobody calls and a helper nobody imports are
invisible to every other kind of test, so the check has to be structural: does a
minting primitive exist anywhere under `app/`, and is `/auth` routable? Those
are questions about the shape of the codebase, not about its behaviour, and they
are the only ones that fail *before* somebody is relying on the answer.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from jose import JWTError, jwt

from app.api.v1.api import api_router
from app.core.jwks import _ALLOWED_ALGORITHMS, verify_supabase_token

pytestmark = pytest.mark.invariant

APP = Path(__file__).resolve().parent.parent.parent / "app"

# `jwt.encode(...)`, however it is spelled. Also catches `jose.jwt.encode` and a
# bare `encode(` on an imported name, which is how somebody would reintroduce
# this without the obvious string appearing.
_ENCODE = re.compile(r"\bjwt\s*\.\s*encode\s*\(|\bfrom\s+jose\s+import\s+[^\n]*\bencode\b")

# `app/agents/report_corroboration.py` uses JWT_SECRET_KEY as an HMAC key for
# reporter pseudonyms (B13), which is not token minting and is allowed. Named
# explicitly so that "it is fine, it is just HMAC" has to be argued once rather
# than assumed per file.
_MAY_READ_THE_SECRET = {"agents/report_corroboration.py", "core/config.py"}


def _python_sources() -> list[Path]:
    return [path for path in APP.rglob("*.py") if "__pycache__" not in path.parts]


# ---------------------------------------------------------------------------
# Fault 1 — nothing under app/ may sign a token
# ---------------------------------------------------------------------------


def test_no_module_signs_a_jwt() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in _python_sources()
        if _ENCODE.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        f"these modules can mint a token: {offenders}. ADR 0002 — Supabase Auth "
        "is the only identity provider, and a backend that can sign a token can "
        "leak the ability to. If a genuine need appears, it changes that ADR "
        "first."
    )


def test_the_minting_helpers_are_gone() -> None:
    """
    Named individually, because these four are what `endpoints/auth.py` used and
    re-adding one with its old name is the likeliest way back in.
    """
    import app.core.security as security

    for name in (
        "create_access_token",
        "create_refresh_token",
        "verify_password",
        "get_password_hash",
    ):
        assert not hasattr(security, name), (
            f"core.security.{name} is back. It was removed on 15 Oct with the "
            "endpoint that called it; see ADR 0002's finding."
        )


def test_only_two_files_read_the_shared_secret() -> None:
    """
    `JWT_SECRET_KEY` survives as B13's reporter-pseudonym HMAC key and nothing
    else. A third reader is either token signing or symmetric verification
    coming back under a new name.

    **Parsed, not grepped.** A text scan counted `core/security.py`, whose
    docstring *explains* that the deleted helpers used to sign with this secret.
    Prose about a credential is not use of it, and a check that cannot tell the
    difference gets suppressed rather than fixed. `ast` ignores docstrings and
    comments for free, and it also catches `from app.core.config import
    settings as s; s.JWT_SECRET_KEY`, which a fixed string would miss.
    """
    readers: set[str] = set()
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "JWT_SECRET_KEY":
                readers.add(str(path.relative_to(APP)).replace("\\", "/"))

    assert readers <= _MAY_READ_THE_SECRET, (
        f"unexpected readers of JWT_SECRET_KEY: {sorted(readers - _MAY_READ_THE_SECRET)}. "
        "It is an HMAC key for reporter pseudonyms, not an auth credential."
    )


# ---------------------------------------------------------------------------
# Fault 2 — no symmetric algorithm is accepted
# ---------------------------------------------------------------------------


def test_only_asymmetric_algorithms_are_accepted() -> None:
    assert _ALLOWED_ALGORITHMS == frozenset({"ES256", "RS256"}), (
        f"the accepted algorithm set is {set(_ALLOWED_ALGORITHMS)}. A symmetric "
        "algorithm means the verifying key is also a signing key."
    )
    assert "HS256" not in _ALLOWED_ALGORITHMS


@pytest.mark.asyncio
async def test_an_hs256_token_is_refused_before_any_key_lookup() -> None:
    """
    The exact forgery that worked: HS256, signed with a secret, `sub` set.

    It must be refused on the algorithm alone — no network, no JWKS fetch — so
    this passes whether or not Supabase is reachable.
    """
    forged = jwt.encode(
        {"sub": "user_id", "email": "attacker@example.com", "aud": "authenticated"},
        "any-secret-at-all",
        algorithm="HS256",
    )
    with pytest.raises(JWTError, match="Unsupported token algorithm"):
        await verify_supabase_token(forged)


@pytest.mark.asyncio
async def test_the_none_algorithm_is_refused() -> None:
    """
    `alg: none` is the other classic. Refused by the same allowlist, which is
    why an allowlist rather than a denylist.
    """
    unsigned = jwt.encode({"sub": "x", "aud": "authenticated"}, "", algorithm="HS256")
    header, payload, _ = unsigned.split(".")
    import base64
    import json

    none_header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(JWTError):
        await verify_supabase_token(f"{none_header}.{payload}.")


# ---------------------------------------------------------------------------
# Fault 3 — required claims
# ---------------------------------------------------------------------------


def test_the_verifier_requires_aud_exp_and_sub() -> None:
    """
    A behavioural test would need a real ES256 key, so this asserts the option
    that carries the guarantee.

    `verify_aud: True` alone was *not* enough — a token with no `aud` was
    accepted, measured on 15 Oct. `require` is what makes a missing claim an
    error rather than a skipped check.
    """
    source = (APP / "core" / "jwks.py").read_text(encoding="utf-8")
    assert '"require"' in source, "jwks.py no longer requires any claim"
    for claim in ("exp", "aud", "sub"):
        assert f'"{claim}"' in source, f"the {claim!r} claim is no longer required"


# ---------------------------------------------------------------------------
# The route itself
# ---------------------------------------------------------------------------


def test_there_is_no_auth_router() -> None:
    """
    The endpoint is the part a stranger can reach. Everything above is defence
    behind it.
    """
    auth_paths = [
        route.path
        for route in api_router.routes
        if getattr(route, "path", "").startswith("/auth")
    ]
    assert auth_paths == [], (
        f"an /auth router is registered again: {auth_paths}. ADR 0002 — "
        "registration, login and refresh are client-to-Supabase. The previous "
        "one returned a valid token to anyone who posted an email address."
    )


def test_the_deleted_endpoint_module_is_still_deleted() -> None:
    assert not (APP / "api" / "v1" / "endpoints" / "auth.py").exists(), (
        "endpoints/auth.py is back. It was not a stub: /auth/login and "
        "/auth/register minted accepted tokens with no credential check."
    )
    assert not (APP / "schemas" / "auth.py").exists(), (
        "schemas/auth.py is back. LoginRequest/RegisterRequest/TokenResponse "
        "describe a flow this backend does not implement, and they are the "
        "template for reintroducing it."
    )


def test_get_current_user_still_exists_and_is_the_only_gate() -> None:
    """
    The opposite failure: removing the bypass by removing authentication.
    """
    from app.core.security import decode_token, get_current_user

    assert callable(get_current_user)
    assert callable(decode_token)
