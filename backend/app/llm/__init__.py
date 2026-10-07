"""
LLM — the one place this codebase talks to a language model.

    models.py   the validated output shapes. Every call returns one of these.
    client.py   the provider-agnostic caller, key rotation, and the chain.

**This file is deliberately empty of imports**, for the same reason
`app/scoring/__init__.py` is: `client.py` needs `app.core.config.settings`, and
re-exporting from here would make every import of the package require a
discoverable `.env`. That was a real bug in D02 — `scripts/seed_risk_flags.py
--sql` turns JSON into SQL text and has no business needing a database URL, but
a package-level import made it fail without one. Import from the module you want.

The invariant
-------------
`client.py` is the only module in the repository that may import an LLM SDK, and
`tests/invariants/test_only_llm_client_calls_models.py` asserts it. The plan
wrote that rule as "only `app/llm/client.py` may import `anthropic`"; there is no
Anthropic key on this project, so the SDK is `openai` — pointed at Gemini and
Groq, both of which serve the OpenAI Chat Completions wire format. The rule is
unchanged in substance: one module, one seam, everything validated on the way out.
"""
