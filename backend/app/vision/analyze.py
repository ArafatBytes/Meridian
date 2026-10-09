"""
One report photo in, a description and a proposal out. D07, ADR 0006.

    result = await analyze_photo(image_bytes, report_text="...")

The whole flow:

    photo
      -> resize to <=1024px, re-encode as JPEG      strips EXIF, including GPS
      -> [gate] is there an image at all?           no: stop, nothing spent
      -> content hash                               the replay tier's key
      -> ONE model call, five cue questions         gemini -> replay -> ollama
      -> our mapping turns cues into a proposal     app/vision/mapping.py
      -> cross-check against the report text        agrees / disagrees / silent
      -> the reporter confirms or overrides         NOT here; this only proposes

Nothing in this module decides what gets filed. It returns what was seen and what
that might mean, and the endpoint hands both to the person who was standing there.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
from dataclasses import dataclass
from typing import Final

from PIL import Image

from app.llm.client import FEATURE_CRIME, LLMUnavailable, complete_with_engine
from app.llm.models import CrimeCues
from app.vision.mapping import Agreement, Confidence, Proposal, cross_check, propose

logger = logging.getLogger(__name__)

# Long edge, pixels. Chosen for upload size and privacy, NOT for speed: measured
# 2026-10-09, the local model's prompt stays ~1,150 tokens whether the image is
# 384px or 1024px, so shrinking it further buys no latency and only loses detail.
MAX_EDGE: Final = 1024
JPEG_QUALITY: Final = 85

SYSTEM: Final = (
    "You report only what is visibly present in the image. "
    "You never infer intent, consent, legality, or who is at fault. "
    "You never name a crime."
)

# Short on purpose. The field descriptions on `CrimeCues` carry the definitions
# and are sent with the schema, so repeating them here would be two sources of
# truth for the same words.
#
# The three answers are spelled out separately because an earlier wording -- "use
# 'unclear' whenever you are not sure, it is the right answer far more often than
# you would expect" -- had a cost that only showed up once real photos were
# tested. Gemini tolerated it and still committed when a cue was plain. The local
# 4B model obeyed it literally and answered `unclear` to all seven cues on three
# of four scenes it had in fact described correctly. Measured 2026-10-10: this
# wording takes the local tier from 2 of 4 to 3 of 4 with no change to cloud, and
# neither tier proposes anything on the benign photos under either version.
USER: Final = (
    "Answer each cue for this photo from what you can see.\n"
    "Answer 'yes' when the cue is clearly present.\n"
    "Answer 'no' when you can see that it is not happening.\n"
    "Answer 'unclear' only when the image genuinely does not show enough to tell.\n"
    "A wrong 'yes' starts a false accusation against a real person. A wrong "
    "'unclear' hides something that is plainly visible."
)


@dataclass(frozen=True, slots=True)
class PhotoAnalysis:
    """Everything the screen needs, and nothing it has to interpret."""

    cues: CrimeCues
    proposed_category: str | None
    confidence: Confidence
    reason: str
    cues_fired: tuple[str, ...]
    agreement: Agreement
    engine: str
    """Which tier answered: `gemini`, `replay` or `ollama`. Shown to the user."""
    image_sha256: str
    elapsed_seconds: float
    prepared_jpeg: bytes
    """Resized, EXIF-stripped bytes. The only copy without the phone's GPS tags,
    so this is what gets stored -- see `app/vision/storage.py`."""


def prepare(raw: bytes) -> tuple[bytes, str]:
    """
    Resize, strip metadata, and hash. Returns `(jpeg_bytes, sha256_hex)`.

    Re-encoding through Pillow is what removes EXIF — including the GPS tags a
    phone writes into a photo. The report's own coordinates are collected
    separately and deliberately, so the location a user agreed to share is the
    only one we keep.

    The hash is of the **prepared** bytes, not the upload, so the same photo
    always keys the same replay entry regardless of what the phone sent.
    """
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE))
        buffer = io.BytesIO()
        img.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True)
    prepared = buffer.getvalue()
    return prepared, hashlib.sha256(prepared).hexdigest()


async def analyze_photo(
    raw: bytes,
    *,
    report_text: str | None = None,
    request_timeout: float = 15.0,
) -> PhotoAnalysis:
    """
    Ask the chain what is visible, then propose from it.

    Raises `LLMUnavailable` when every tier is exhausted. The caller stores the
    photo anyway and shows an honest "could not analyse" — a photo with no
    analysis is still evidence, and D08 needs it either way.

    The 15s timeout applies to the *cloud* tier only; `PROVIDERS["ollama"]`
    carries its own 120s. They want opposite things. A Gemini call that has not
    answered in 15 seconds is no use to a three-second demo beat, and every
    second it keeps hanging is a second the offline tier is not being asked --
    with the network down that is exactly when the answer matters most.
    """
    if not raw:
        raise ValueError("empty image")

    started = time.perf_counter()
    prepared, digest = prepare(raw)
    data_url = "data:image/jpeg;base64," + base64.b64encode(prepared).decode("ascii")

    cues, engine = await complete_with_engine(
        SYSTEM,
        USER,
        CrimeCues,
        feature=FEATURE_CRIME,
        image_data_url=data_url,
        replay_key=digest,
        request_timeout=request_timeout,
        # The cue answers are short; the description is capped at 200 characters.
        max_tokens=300,
    )

    proposal: Proposal = propose(cues)
    elapsed = time.perf_counter() - started
    logger.info(
        "photo %s analysed by %s in %.2fs — %s",
        digest[:12],
        engine,
        elapsed,
        proposal.category or "no proposal",
    )
    return PhotoAnalysis(
        cues=cues,
        proposed_category=proposal.category,
        confidence=proposal.confidence,
        reason=proposal.reason,
        cues_fired=proposal.cues_fired,
        agreement=cross_check(proposal, report_text),
        engine=engine,
        image_sha256=digest,
        elapsed_seconds=round(elapsed, 2),
        prepared_jpeg=prepared,
    )


__all__ = ["PhotoAnalysis", "analyze_photo", "prepare", "LLMUnavailable"]
