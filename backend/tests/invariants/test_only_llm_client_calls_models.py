"""
Invariant: **no LLM output reaches a user unvalidated.**

IMPLEMENTATION_PLAN.md §4. Every call to a language model goes through
`app/llm/client.py` and comes back as a validated Pydantic model, or raises.

The plan phrases the rule as "`app/llm/client.py` is the only module that may
import `anthropic`". There is no Anthropic key on this project, so the SDK is
`openai`, pointed at Gemini and Groq — both serve the OpenAI Chat Completions
wire format. The rule is unchanged in substance and this test enforces it against
whichever SDKs are actually in use: **one module, one seam.**

Two checks:

1. no module outside `app/llm/client.py` imports an LLM SDK;
2. `complete()` is typed to return a `BaseModel` subclass, so there is no code
   path that hands raw model text to a caller.

Check 1 reads the source, which is crude, and is the only check that catches the
failure that actually happens: somebody importing the SDK directly inside an
agent at 1 a.m. because it is two lines shorter.
"""

import ast
from pathlib import Path

import pytest

from app.llm import client as llm_client
from app.llm.models import GeoGuess

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
APP = BACKEND / "app"

# Any SDK that talks to a *language model* provider. `openai` is the one in use;
# the others are listed so that adding a provider the easy-but-wrong way trips
# this test rather than passing silently.
#
# These are matched as full dotted prefixes, not top-level packages, and that
# precision is load-bearing: `app/services/ai/speech_service.py` legitimately
# imports `google.cloud.speech`, which is speech-to-text and has nothing to do
# with this invariant. An earlier version of this test matched the bare top-level
# name and failed on it — the test was wrong, not the code.
LLM_SDK_PREFIXES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "groq",
    "cohere",
    "mistralai",
)

# The one module allowed to import them, relative to `app/`.
SOLE_IMPORTER = Path("llm") / "client.py"


def _imported_modules(source: str) -> set[str]:
    """Full dotted module names imported by this source, however they are written."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # `level > 0` is a relative import and cannot reach a third-party SDK.
            if node.level == 0 and node.module:
                found.add(node.module)
    return found


def _llm_sdks_in(source: str) -> set[str]:
    hits: set[str] = set()
    for module in _imported_modules(source):
        for prefix in LLM_SDK_PREFIXES:
            if module == prefix or module.startswith(prefix + "."):
                hits.add(prefix)
    return hits


def test_only_the_llm_client_imports_an_llm_sdk() -> None:
    offenders: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(APP)
        if relative == SOLE_IMPORTER:
            continue
        for sdk in sorted(_llm_sdks_in(path.read_text(encoding="utf-8"))):
            offenders.append(f"app/{relative.as_posix()} imports {sdk}")

    assert not offenders, (
        "Only app/llm/client.py may import a model SDK. Route the call through "
        "app.llm.client.complete(), which validates the response against a "
        "Pydantic model.\n  " + "\n  ".join(offenders)
    )


def test_the_sole_importer_really_does_import_one() -> None:
    """
    Guards the guard.

    If `client.py` stopped importing an SDK — renamed, moved, rewritten — the
    test above would pass trivially while the invariant went unchecked.
    """
    source = (APP / SOLE_IMPORTER).read_text(encoding="utf-8")
    assert _llm_sdks_in(source), (
        f"app/{SOLE_IMPORTER.as_posix()} imports no LLM SDK, so "
        "test_only_the_llm_client_imports_an_llm_sdk proves nothing. If the seam "
        "moved, move SOLE_IMPORTER with it."
    )


def test_every_call_is_shaped_by_a_pydantic_model() -> None:
    """
    `complete()` takes the output type as a parameter and returns an instance of
    it. There is no overload that returns `str`, which is the whole point.
    """
    from pydantic import BaseModel

    annotations = llm_client.complete.__annotations__
    assert annotations["schema"] is not str
    assert issubclass(GeoGuess, BaseModel)
    # The declared return is the TypeVar bound to BaseModel, not a plain string.
    assert annotations["return"] is not str


def test_the_chain_is_parsed_and_unknown_providers_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "LLM_CHAIN_GEO", "gemini:gemini-3.5-flash-lite,nosuchprovider:x,groq:openai/gpt-oss-120b"
    )
    parsed = llm_client.chain(llm_client.FEATURE_GEO)
    assert parsed == (
        ("gemini", "gemini-3.5-flash-lite"),
        ("groq", "openai/gpt-oss-120b"),
    ), "unknown providers must be dropped, and a model name containing '/' must survive"


def test_the_default_chain_does_not_include_the_model_that_fabricated() -> None:
    """
    `gemini-3.1-flash-lite` invented coordinates for a nonexistent Mirpur sector,
    reproducibly, at 0.95 confidence (measured 2026-10-07). It scored 5/6 on the
    probe, so it is the obvious thing to add when someone wants more fallback
    capacity. This test is here to make that a deliberate decision rather than an
    accident.
    """
    from app.core.config import settings

    assert "gemini-3.1-flash-lite" not in settings.LLM_CHAIN_GEO, (
        "gemini-3.1-flash-lite fabricates coordinates for places that do not "
        "exist, which is the one failure the discard invariant forbids. If you "
        "are adding it back, say why here."
    )


def test_every_known_feature_declares_a_chain() -> None:
    """
    A feature in KNOWN_FEATURES with no `LLM_CHAIN_<NAME>` in config would find no
    models and fail only at the call, in production, as "LLM unavailable".
    """
    from app.core.config import settings

    missing = [
        f for f in sorted(llm_client.KNOWN_FEATURES)
        if not getattr(settings, f"LLM_CHAIN_{f}", "")
    ]
    assert not missing, f"features with no LLM_CHAIN_* declared: {missing}"


def test_an_unknown_feature_raises_rather_than_silently_finding_no_keys() -> None:
    with pytest.raises(ValueError, match="unknown LLM feature"):
        llm_client.chain("NOT_A_FEATURE")


def test_keys_are_scoped_per_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    `GEMINI_KEY_GEO_ONE` belongs to GEO and to nothing else.

    The whole point of the per-feature split is that D04's ingestion loop cannot
    spend the quota D03's search box depends on, so a feature must never fall back
    to another's keys.
    """
    llm_client.reset_key_cache()
    monkeypatch.setattr(
        llm_client, "_env_pairs",
        lambda: {"GEMINI_KEY_GEO_ONE": "a-geo-key", "GEMINI_KEY_VISION_ONE": "a-vision-key"},
    )
    try:
        assert llm_client.keys_for("gemini", "GEO") == ("a-geo-key",)
        assert llm_client.keys_for("gemini", "VISION") == ("a-vision-key",)
        assert llm_client.keys_for("gemini", "EXTRACT") == ()
    finally:
        llm_client.reset_key_cache()


def test_complete_requires_an_explicit_feature() -> None:
    """
    No default: a wrong one would quietly spend another feature's daily quota.
    """
    import inspect

    parameter = inspect.signature(llm_client.complete).parameters["feature"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_a_model_that_emits_invalid_json_falls_through_instead_of_raising() -> None:
    """
    `json_validate_failed` is a model failure, not a bad request from us.

    Found while benchmarking `openai/gpt-oss-120b`: it returned that code with an
    empty generation and the whole eval run died. In production the same thing with
    Gemini rate-limited would turn a map search into an HTTP 500 rather than an
    honest "could not find that place".
    """
    import httpx
    import openai

    response = httpx.Response(
        400,
        json={"error": {"message": "Failed to validate JSON.", "code": "json_validate_failed"}},
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )
    problem = openai.BadRequestError("boom", response=response, body=response.json())
    assert llm_client._is_model_side_400(problem) is True


def test_a_genuinely_bad_request_from_us_is_not_swallowed() -> None:
    """
    The other half: a 400 we caused must surface, or a broken schema would read as
    "the model had no answer" forever.
    """
    import httpx
    import openai

    response = httpx.Response(
        400,
        json={"error": {"message": "Unknown parameter: 'nonsense'.", "code": "unknown_parameter"}},
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )
    problem = openai.BadRequestError("boom", response=response, body=response.json())
    assert llm_client._is_model_side_400(problem) is False
