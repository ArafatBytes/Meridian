"""
Token verification. **This module cannot issue a token, only check one.**

ADR 0002: Supabase Auth is the only identity provider. Four functions used to
live here and are deliberately gone —

* `create_access_token`, `create_refresh_token` — they signed with
  `JWT_SECRET_KEY`, which contradicted the entire argument for verifying
  against a published public key. Their only caller was `endpoints/auth.py`,
  which handed a signed token to anyone who posted an email address and never
  checked a password. The endpoint and the helpers went together on 15 Oct;
  see ADR 0002's finding for the measurement.
* `verify_password`, `get_password_hash` — no password reaches this backend.
  There is no local credential to compare against: ADR 0003 removed the last
  user table, and `auth.users` is Supabase's.

Adding any of them back re-opens the bypass, which is why
`tests/invariants/test_the_backend_cannot_mint_a_token.py` scans for
`jwt.encode` across `app/` rather than trusting a comment.
"""
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.jwks import verify_supabase_token

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


async def decode_token(token: str) -> dict:
    """
    Verify a Supabase access token and return its claims.

    Was `jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"],
    options={"verify_aud": False})`. That failed on every authenticated request
    with "The specified alg value is not allowed", because Supabase signs with
    ES256 by default now and the tokens are ECDSA signatures, not HMACs. No
    secret value could have made it work.

    Verification moved to app/core/jwks.py, which fetches the project's
    published public key. **Asymmetric only since 15 Oct** — the HS256 branch
    was removed with the rest of ADR 0002's finding, because a shared secret
    that verifies is a shared secret that mints.

    Audience is now actually checked, and — the part that was still missing —
    the `aud` claim is *required to be present*. `verify_aud: True` alone
    accepted a token that carried no `aud` at all.
    """
    try:
        return await verify_supabase_token(token)
    except JWTError as exc:
        # Log the reason server-side; never echo token contents to the client.
        logger.warning("Rejected token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from token"""
    token = credentials.credentials
    payload = await decode_token(token)
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    return {"user_id": user_id, "email": payload.get("email")}
