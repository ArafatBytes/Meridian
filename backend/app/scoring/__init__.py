"""
Scoring — the risk surface and the arithmetic behind it.

    kinds.py          per-kind half-life, radius and severity. The reviewed table.
    decay.py          severity on read: halving, plus the hour-of-day profile.
    chronic.py        the chronic baseline, from real police-unit statistics.
    fixture.py        data/fixtures/risk_flags.json, resolved into rows.
    surface_db.py     DbRiskSurface  — the risk_flags table.
    clusters.py       DbClusterSurface — the community_clusters table (B13).
    surface_seeded.py SeededRiskSurface — the fixture, with no database at all.
    factory.py        get_risk_surface() — the only place that chooses between them.

**This file is deliberately empty of imports.** `factory.py` needs
`app.core.config.settings`, whose required fields mean importing it fails without a
discoverable `.env`. Re-exporting the factory from here would put that cost on every
import of the package, including `scripts/seed_risk_flags.py --sql`, which only turns a
JSON file into SQL text and has no business needing a database URL. That is not
hypothetical — it is a bug this package had, briefly, in D02. Import from the module you
want.
"""
