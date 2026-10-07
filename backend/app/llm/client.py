"""
The only module in this repository that imports an LLM SDK.

    from app.llm.client import FEATURE_GEO, complete, LLMUnavailable
    from app.llm.models import GeoGuess

    guess = await complete(SYSTEM, "Mirpur 10 golchattar", GeoGuess, feature=FEATURE_GEO)

One SDK, several providers
--------------------------
Gemini and Groq both serve the OpenAI Chat Completions wire format, so a single
`openai` client reaches either one by changing three values: base URL, API key,
model name. Confirmed against both providers' own documentation on 2026-10-07:

    Gemini  https://generativelanguage.googleapis.com/v1beta/openai/
            ai.google.dev/gemini-api/docs/openai
    Groq    https://api.groq.com/openai/v1
            console.groq.com/docs/structured-outputs

That is why there is no adapter class hierarchy here. A provider is a base URL
and the name of an environment variable; adding one is a row in `PROVIDERS`.

Everything is per **feature**, not global
----------------------------------------
A feature is one job that needs a model: `GEO` (place resolution, D03), and later
`EXTRACT` (D04), `VISION` (D07), `CASEWORK` (D08). Each one names its own chain
and its own keys:

    LLM_CHAIN_GEO=gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b
    GEMINI_KEY_GEO_ONE=...
    GROQ_KEY_GEO_ONE=...

Two reasons this is split rather than one global `LLM_CHAIN`:

**Different jobs want different models.** `openai/gpt-oss-120b` is a sound
fallback for place names and is **not multimodal at all**, so the same chain would
simply fail for D07's images. One global setting would hide that behind a name
that gave no hint of it.

**Different keys mean isolated quota.** Per `Free_AI_API_List.md`, multiple keys
on this project belong to *different accounts*, so their limits are genuinely
independent — Gemini's apply per project and Groq's per organization. Giving D04's
ingestion loop its own keys means it cannot exhaust the daily budget that D03's
search box depends on. Sharing one pool would make that failure invisible until a
rehearsal.

Within a feature, every variable named `GEMINI_KEY_<FEATURE>_*` is a Gemini key
for it; likewise `GROQ_KEY_<FEATURE>_*`. Add `GEMINI_KEY_GEO_TWO` and it joins the
rotation with no code change.

Which model runs
----------------
The chain is tried left to right; change the order to change the primary. The
`GEO` default was chosen from a six-case probe of real Dhaka place names on
2026-10-07 and a 53-case eval (both in `docs/walkthroughs/D03.md`):
`gemini-3.5-flash-lite` 6/6, `openai/gpt-oss-120b` 4/6, `gemini-3.1-flash-lite`
5/6 but it fabricated coordinates for a nonexistent place, twice, at 0.95
confidence — so it is deliberately absent. `qwen/qwen3.8-27b` scored 1/6.

The fallback is on a different provider on purpose: same-provider fallbacks share
a rate limit, so they fail together, which is the one moment a fallback is for.

A 429 advances to the next key, then to the next model in the chain. Nothing
retries the same key twice and nothing sleeps — a request that cannot be served
now should fail now and let the gazetteer answer stand, because the caller is a
map screen with a person waiting at it.
"""

from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

Output = TypeVar("Output", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """
    No model in the chain produced a validated answer.

    Callers must treat this as "no answer", never as "no such place". The
    Geolocation Agent returns `method="unresolved"` on it, which is also what it
    returns when a model honestly refuses — the difference does not matter to a
    user and collapsing it keeps the discard invariant simple.
    """


@dataclass(frozen=True, slots=True)
class Provider:
    base_url: str
    key_prefix: str


PROVIDERS: Final[dict[str, Provider]] = {
    "gemini": Provider(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_prefix="GEMINI_KEY_",
    ),
    "groq": Provider(
        base_url="https://api.groq.com/openai/v1",
        key_prefix="GROQ_KEY_",
    ),
}

# Errors worth moving to the next key or model. Anything else is a bug in our
# request and is raised, because silently falling through a schema error would
# hide it behind a plausible-looking "unresolved".
_TRY_NEXT: Final = (
    openai.RateLimitError,
    openai.AuthenticationError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)

# A 400 is normally our fault and must surface. These two codes are not: they mean
# the *model* failed to produce output matching the schema we asked for, which is a
# model failure like any other and should fall through to the next one.
#
# Found the hard way. Benchmarking `openai/gpt-oss-120b` over 53 place names, it
# returned `json_validate_failed` with an empty `failed_generation` and the whole
# run died. In production that is worse than a bad answer: with Gemini rate-limited
# and the request falling through to Groq, a map search would return HTTP 500
# instead of an honest "could not find that place".
_MODEL_SIDE_400_CODES: Final = frozenset({"json_validate_failed", "tool_use_failed"})


def _is_model_side_400(problem: openai.BadRequestError) -> bool:
    """Did the model fail to produce valid output, or did we send a bad request?"""
    code = getattr(problem, "code", None)
    if isinstance(code, str) and code in _MODEL_SIDE_400_CODES:
        return True
    body = getattr(problem, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict) and inner.get("code") in _MODEL_SIDE_400_CODES:
            return True
    return False

_ENV_FILE: Final = Path(__file__).resolve().parents[2] / ".env"
_KEY_CACHE: dict[tuple[str, str], tuple[str, ...]] = {}
_ROTATION: dict[tuple[str, str], itertools.count[int]] = {}

# The features that may ask for a model. Each needs `LLM_CHAIN_<name>` declared in
# `app/core/config.py`, and keys named `<PROVIDER>_KEY_<name>_*`. Listed so a
# typo'd feature fails loudly at the call rather than quietly finding no keys.
FEATURE_GEO: Final = "GEO"
FEATURE_EXTRACT: Final = "EXTRACT"
KNOWN_FEATURES: Final = frozenset({FEATURE_GEO, FEATURE_EXTRACT})


def _env_pairs() -> dict[str, str]:
    """
    Every available environment variable, however it arrived.

    In Docker, compose's `env_file` puts them in the real environment. Run
    locally — pytest, a script — they are only in the `.env` file, because
    `Settings` declares named fields and `extra = "ignore"` drops the rest
    rather than exporting them. Both paths are needed; neither is enough alone.
    """
    pairs = dict(os.environ)
    if _ENV_FILE.is_file():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            # The real environment wins: Docker's value is the live one.
            pairs.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    return pairs


def keys_for(provider: str, feature: str) -> tuple[str, ...]:
    """
    Keys for one provider **and one feature**, in name order so rotation is stable.

    Matches `<PROVIDER>_KEY_<FEATURE>_*` — for example `GEMINI_KEY_GEO_ONE`. Name
    matching is case-insensitive because `.env` mixes cases, and requiring one
    spelling would mean a key that is present, correct, and silently unused.

    A feature with no keys of its own gets none. It does **not** fall back to
    another feature's: silently spending D04's ingestion budget on D03's search box
    is the exact coupling this split exists to prevent, and a missing key should be
    a loud "no keys configured" rather than a quota mystery three days later.
    """
    cache_key = (provider, feature)
    if cache_key in _KEY_CACHE:
        return _KEY_CACHE[cache_key]
    prefix = f"{PROVIDERS[provider].key_prefix}{feature}_".casefold()
    found = {
        name: value
        for name, value in _env_pairs().items()
        if name.casefold().startswith(prefix) and value.strip()
    }
    keys = tuple(found[name] for name in sorted(found, key=str.casefold))
    _KEY_CACHE[cache_key] = keys
    return keys


def chain_setting(feature: str) -> str:
    """The raw `LLM_CHAIN_<FEATURE>` string, or "" if the feature declares none."""
    if feature not in KNOWN_FEATURES:
        raise ValueError(
            f"unknown LLM feature {feature!r} — add it to KNOWN_FEATURES and declare "
            f"LLM_CHAIN_{feature} in app/core/config.py"
        )
    return str(getattr(settings, f"LLM_CHAIN_{feature}", ""))


def chain(feature: str, override: str | None = None) -> tuple[tuple[str, str], ...]:
    """
    `LLM_CHAIN_<FEATURE>` parsed into (provider, model) pairs.

    Unknown providers and malformed entries are dropped with a warning rather than
    raising: a typo in one entry should cost that entry, not the whole request.
    `override` lets a benchmark pin one model without touching `.env`.
    """
    raw = override if override is not None else chain_setting(feature)
    label = f"LLM_CHAIN_{feature}"
    out: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            logger.warning("%s entry %r is not provider:model — ignored", label, item)
            continue
        # Split once: a model name may itself contain a colon, and Groq's
        # contain a slash ("openai/gpt-oss-120b").
        provider, model = (part.strip() for part in item.split(":", 1))
        if provider not in PROVIDERS:
            logger.warning("%s names unknown provider %r — ignored", label, provider)
            continue
        if not model:
            continue
        out.append((provider, model))
    return tuple(out)


def _redact(key: str) -> str:
    """A key's identity for a log line, without the key."""
    return f"{key[:4]}…{len(key)}"


async def complete(
    system: str,
    user: str,
    schema: type[Output],
    *,
    feature: str,
    chain_override: str | None = None,
    request_timeout: float = 20.0,
    max_tokens: int = 512,
) -> Output:
    """
    Ask one feature's chain for a validated `schema` instance.

    `feature` is required and has no default on purpose: it selects both the model
    chain and the key pool, and a wrong default would silently spend another
    feature's quota. Use the `FEATURE_*` constants.

    Walks `LLM_CHAIN_<FEATURE>` in order and, within each entry, every key that
    provider has for this feature. Returns the first validated result. Raises
    `LLMUnavailable` if the chain is exhausted — including when it is empty, which
    is what a feature with no keys configured looks like.

    `chain_override` pins a chain for one call, ignoring `.env`. It exists for
    benchmarks (`scripts/eval_geocoding.py --chain`) so a single model can be
    measured without editing configuration that other work depends on.
    """
    attempts = 0
    for provider, model in chain(feature, chain_override):
        keys = keys_for(provider, feature)
        if not keys:
            logger.warning(
                "LLM_CHAIN_%s asks for %s:%s but no %s%s_* key is set — skipping",
                feature, provider, model, PROVIDERS[provider].key_prefix, feature,
            )
            continue
        # Start each call at a different key so load spreads across accounts
        # instead of always burning the first one's daily quota first.
        offset = next(_ROTATION.setdefault((provider, feature), itertools.count()))
        for step in range(len(keys)):
            key = keys[(offset + step) % len(keys)]
            attempts += 1
            client = AsyncOpenAI(api_key=key, base_url=PROVIDERS[provider].base_url, timeout=request_timeout)
            try:
                response = await client.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format=schema,
                    max_tokens=max_tokens,
                )
            except openai.BadRequestError as problem:
                # Our bad request, or the model's bad output? Only the second is
                # recoverable; re-raising the first is what keeps a broken schema
                # from masquerading as "no answer".
                if not _is_model_side_400(problem):
                    raise
                logger.warning(
                    "%s:%s produced output that failed the %s schema; trying the next option",
                    provider, model, schema.__name__,
                )
                continue
            except _TRY_NEXT as problem:
                logger.warning(
                    "%s:%s key %s — %s; trying the next option",
                    provider, model, _redact(key), type(problem).__name__,
                )
                continue
            finally:
                await client.close()

            parsed = response.choices[0].message.parsed
            if parsed is None:
                # A refusal, or output the schema rejected. Either way this model
                # gave us nothing usable; another may do better.
                logger.warning("%s:%s returned no parsable content", provider, model)
                continue
            return parsed

    raise LLMUnavailable(
        f"no model in LLM_CHAIN_{feature} produced a validated {schema.__name__} "
        f"after {attempts} attempt(s)"
    )


def reset_key_cache() -> None:
    """Forget discovered keys. For tests, and after editing `.env` in a dev run."""
    _KEY_CACHE.clear()
    _ROTATION.clear()
