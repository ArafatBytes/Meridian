"""
Capturing the rehearsed photos. D07, ADR 0006.

    python -m app.agents export-vision-replay

Run it **after the final rehearsal, not before.** It freezes whatever the models
say at that moment, so capturing early just preserves an answer nobody has
signed off on.

Why a cache is a tier at all, given two working models: **it is the only tier
that guarantees its output.** Google can change what sits behind
`gemini-3.5-flash-lite` between a rehearsal and the 24th, and temperature 0
constrains sampling, not the model version. The local model is reproducible but
unproven on detection. A capture is the only thing that returns exactly what was
checked.

What is stored is the **model's own fields only** -- the five cue answers, the
people count, the scene, the description. The proposed category is *not* stored;
`mapping.propose()` re-derives it at read time. That keeps our own layer out of
the fixture, so a change to the rules takes effect without a recapture, and the
fixture stays a record of what the model said rather than what we concluded. It
is the same split D04 keeps by re-deriving prose through `framing.py`.

A replayed answer is labelled `engine: replay` on the response and shown on
screen. Canned answers behind a live-analysis screen would be the one version of
this that is indefensible.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Final

from app.llm.client import FEATURE_CRIME, LLMUnavailable, chain, complete_with_engine
from app.llm.models import CrimeCues
from app.vision.analyze import SYSTEM, USER, prepare

logger = logging.getLogger(__name__)

_FIXTURE_DIR: Final = Path(__file__).resolve().parents[2] / "data" / "fixtures"
FIXTURE_PATH: Final = _FIXTURE_DIR / "crime_vision_replay.json"

DEFAULT_PHOTO_DIR: Final = Path(__file__).resolve().parents[2] / "data" / "demo" / "vision"
"""The staged demo photos. Not the eval set: that measures, this rehearses."""

_SUFFIXES: Final = {".jpg", ".jpeg", ".png", ".webp"}


def chain_without_replay() -> str:
    """
    The configured chain with the replay tier removed.

    Filtered from `LLM_CHAIN_CRIME` rather than written out again, so adding or
    reordering a model never leaves a second copy here to drift.

    Two callers, same reason. **Capture** must not replay itself: without the
    filter the first capture would be fine and every later one would re-freeze a
    stale answer forever. **The eval harness** must not let the cache answer its
    own exam -- if a captured photo were also an eval image, the measured score
    would be of the fixture, not the model.
    """
    return ",".join(
        f"{provider}:{model}"
        for provider, model in chain(FEATURE_CRIME)
        if provider != "replay"
    )


async def export_vision_replay(photo_dir: Path | None = None) -> int:
    """
    Analyse every photo in `photo_dir` for real and write the answers. Returns the count.

    Existing entries are replaced, and photos that fail are skipped with a warning
    rather than aborting the run: a partial capture is useful, and a half-written
    fixture is not.
    """
    source = photo_dir or DEFAULT_PHOTO_DIR
    if not source.is_dir():
        logger.error("no photo directory at %s — nothing to capture", source)
        return 0

    photos = sorted(p for p in source.iterdir() if p.suffix.casefold() in _SUFFIXES)
    if not photos:
        logger.error("no images in %s (looked for %s)", source, ", ".join(sorted(_SUFFIXES)))
        return 0

    captured: dict[str, dict] = {}
    if FIXTURE_PATH.is_file():
        try:
            captured = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("existing fixture unreadable — starting fresh")

    override = chain_without_replay()
    logger.info("capturing %d photo(s) through %s", len(photos), override)

    written = 0
    for photo in photos:
        try:
            prepared, digest = prepare(photo.read_bytes())
        except Exception as problem:  # noqa: BLE001 - any unreadable file, same outcome
            logger.warning("%s could not be read as an image (%s) — skipped", photo.name, problem)
            continue

        data_url = "data:image/jpeg;base64," + base64.b64encode(prepared).decode("ascii")
        try:
            cues, engine = await complete_with_engine(
                SYSTEM,
                USER,
                CrimeCues,
                feature=FEATURE_CRIME,
                image_data_url=data_url,
                request_timeout=90.0,
                max_tokens=300,
                chain_override=override,
            )
        except LLMUnavailable as exhausted:
            logger.warning("%s: no tier answered (%s) — skipped", photo.name, exhausted)
            continue

        captured[digest] = cues.model_dump()
        written += 1
        logger.info(
            "%-34s %s  %s  %s",
            photo.name,
            digest[:12],
            engine,
            cues.description[:60],
        )

    if not written:
        logger.error("captured nothing — fixture left unchanged")
        return 0

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(captured, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return written
