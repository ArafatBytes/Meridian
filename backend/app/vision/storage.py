"""
Keeping the evidence photo. D07, defect 13.

This is the first storage write in the codebase, so the choices are stated here
rather than inferred:

**The backend uploads, not the app.** The phone holds the original, and a phone
photo carries EXIF GPS. `analyze.prepare()` has already re-encoded it, which is
what strips that metadata, so the EXIF-free bytes only exist on this side. If the
app uploaded directly it would be storing the original, with the coordinates we
deliberately did not ask for. The report's own location is collected separately
and with consent; that is the only one we keep.

**The bucket is private.** An evidence photo of a real incident involving real
people is not public data. Reads go through `signed_url`, which mints a
short-lived URL per request rather than handing out a permanent one.

**A failed upload is not a failed report.** Every function here returns `None`
instead of raising. The analysis is still worth showing and the report is still
worth filing; a missing photo renders as "photo unavailable", which is true.
"""

from __future__ import annotations

import logging
from typing import Final

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET: Final = "report-evidence"
SIGNED_URL_TTL_SECONDS: Final = 3600
_TIMEOUT: Final = 30.0


def _base_and_headers() -> tuple[str, dict[str, str]] | None:
    url = (settings.SUPABASE_URL or "").rstrip("/")
    key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
    if not url or not key:
        logger.warning("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — not storing photos")
        return None
    return f"{url}/storage/v1", {"Authorization": f"Bearer {key}", "apikey": key}


def object_path(user_id: str, digest: str) -> str:
    """
    `<user_id>/<sha256>.jpg`.

    Content-addressed on purpose: the same photo uploaded twice overwrites itself
    rather than accumulating copies, and the path is already in the analysis
    result, so nothing has to be threaded through to match them up.
    """
    return f"{user_id}/{digest}.jpg"


async def store_evidence(user_id: str, jpeg: bytes, digest: str) -> str | None:
    """Upload prepared JPEG bytes. Returns the object path, or None if it failed."""
    target = _base_and_headers()
    if target is None:
        return None
    base, headers = target
    path = object_path(user_id, digest)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{base}/object/{BUCKET}/{path}",
                content=jpeg,
                headers={
                    **headers,
                    "Content-Type": "image/jpeg",
                    # Same photo, same path: replace rather than 409.
                    "x-upsert": "true",
                },
            )
        if response.status_code >= 400:
            logger.warning("evidence upload failed %s: %s", response.status_code, response.text[:200])
            return None
    except httpx.HTTPError as problem:
        logger.warning("evidence upload failed: %s", problem)
        return None
    logger.info("stored evidence photo %s (%d bytes)", path, len(jpeg))
    return path


async def signed_url(path: str, ttl_seconds: int = SIGNED_URL_TTL_SECONDS) -> str | None:
    """A time-limited URL for one stored photo, or None if it could not be signed."""
    target = _base_and_headers()
    if target is None or not path:
        return None
    base, headers = target
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{base}/object/sign/{BUCKET}/{path}",
                json={"expiresIn": ttl_seconds},
                headers=headers,
            )
        if response.status_code >= 400:
            logger.warning("signing %s failed %s: %s", path, response.status_code, response.text[:200])
            return None
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
    except (httpx.HTTPError, ValueError) as problem:
        logger.warning("signing %s failed: %s", path, problem)
        return None
    if not signed:
        return None
    # Supabase returns a path-relative URL; the app needs an absolute one.
    return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}" if signed.startswith("/") else signed
