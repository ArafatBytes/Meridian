"""
Alerting — deciding to interrupt someone, and then doing it. B6a / S16.

    policy.py    whether to send. Pure: no clock, no session, no network.
    compose.py   what it says. Forwards framed flag text; composes no prose.
    expo.py      how it leaves the building. One `PushTransport` seam.
    service.py   the database half: devices, preferences, the ledger, the sweep.

The split is along the line that matters for testing. `policy.py` and
`compose.py` together are the two things a judge will ask about — the alert-fatigue
cap and the framing commitment — and both are decidable from plain data, so both
have tests that run in milliseconds with no fixtures.

**This file imports nothing**, for the same reason `app/scoring/__init__.py` does
not: `expo.py` and `service.py` need `app.core.config.settings`, which raises
without a discoverable `.env`. Re-exporting from here would make
`from app.alerts.policy import decide` — the import a pure test wants — require a
database URL. Import from the module you want.
"""
