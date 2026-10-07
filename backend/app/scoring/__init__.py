"""
Scoring — the database-backed risk surface.

D01 ships one thing: `DbRiskSurface`, so the map can read flags through the
`RiskSurface` seam instead of around it.

D02 owns the rest and will grow this package considerably — exponential decay
computed on read, the per-kind half-life and radius table, time-of-day modulation,
the expiry sweep, and `SeededRiskSurface` beside the database one. None of that is
here yet because nothing calls it yet; `risk_flags.expires_at` is derived by a
database trigger, which is the only decay arithmetic D01 actually needs.
"""
