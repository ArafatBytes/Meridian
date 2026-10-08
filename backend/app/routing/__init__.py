"""
Route generation, scoring and explanation. D06 — sources S12, S13, S05, S07.

    osrm.py     the routing engine client. Honours OSRM_BASE_URL, uses OSRM's own
                durations, driving and foot profiles, loud fallback.
    scorer.py   path scoring over the RiskSurface protocol. One scale: safety_score,
                0-100, higher is safer.
    explain.py  the plain-English sentence, assembled from framed flag statements.

**Nothing in this package imports a model or touches a table.** Risk arrives through
`app.contracts.surface.RiskSurface`, which is what lets every module here work unchanged
on `RISK_SURFACE_IMPL=seeded` — S12's own check, and the offline demo path.

See `CLAUDE.md` in this directory for the conventions.
"""
