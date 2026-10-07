"""
Agents — scheduled jobs that read the world and write the risk surface.

Each module here that exports `AGENT = SomeAgent()` is discovered by `registry.py`,
which schedules its `cron` with Celery beat and records every run in `agent_runs`.
Adding an agent is one new module and never an edit to a central list.

    live_risk.py      news → incidents → flags, every 15 minutes (D04)
    expiry_sweep.py   retire flags past expires_at (housekeeping, D02's sweep)

    python -m app.agents run live_risk [--dry-run]
    python -m app.agents export-replay
"""
