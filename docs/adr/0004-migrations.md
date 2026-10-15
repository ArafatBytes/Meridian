# ADR 0004 — Forward-only hand-written SQL, and why not Alembic

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-15 |
| **Decider** | Arafat (owner) |
| **Consulted** | Written retrospectively. `backend/scripts/migrate.py` has carried the argument in its module docstring since S01; this promotes it to a decision and adds what operating it has since taught. |
| **Supersedes** | `alembic` in `requirements.txt`, which was listed and never used. There is no `alembic.ini` and nothing imports it. |

---

## Context

Meridian's database is Postgres with PostGIS, hosted on Supabase, and **shared
between two developers' machines**. Schema changes have to be reviewable,
repeatable, and applicable through whatever connection the host actually allows.

## Decision

**Migrations are hand-written SQL files, applied forward-only, in filename
order, by `backend/scripts/migrate.py`.**

```
migrations/versions/<utc-timestamp>__<slug>.sql
```

### Why not Alembic

Alembic's value is `autogenerate`: it diffs SQLAlchemy models against the
database. **This project's database is not described by its models.** What the
schema actually contains:

* PostGIS `geography` columns and GiST indexes;
* partial indexes;
* `CHECK` constraints carrying ethical invariants — the one that forbids a live
  news flag from being `confirmed`, the one that requires an attributed crime
  statement to name its publisher;
* row-level security policies, which ADR 0001 relies on as *the* enforcement
  point for user-owned rows;
* triggers.

Alembic either cannot see those or renders them badly, so autogenerate would
produce migrations that silently drop the most important objects in the schema.
And ADR 0001 means the models are deliberately an incomplete picture: tables the
client owns are reached through PostgREST and have no SQLAlchemy model at all.
A diff against the models would propose dropping them.

So the generator is worth nothing here, and once it is gone Alembic is a
dependency, a config file and a revision graph wrapped around SQL somebody wrote
by hand anyway. **Hand-written SQL is honest about what is being run: the thing
a reviewer reads is the thing the database executes.**

### Why forward-only

There are no `down` migrations. Rolling back a schema change on a live database
is a fiction most of the time — a dropped column's data is gone, and the
`down` that "restores" it restores an empty column. What actually happens is a
new migration that corrects the last one, so that is the only mechanism offered.
`RESET.sql` exists for the development case where starting over is genuinely
what you want.

### Immutability, and how it is enforced

The runner records a **sha256 of each file**. Editing an applied migration is
therefore an error rather than a silent divergence between two developers'
databases. CI's `migrations-guard` job refuses a diff that modifies a merged
migration, and `tests/test_migrate_checksum.py` covers the runner's side.

### Applying by paste

`migrate.py sql` prints pending SQL and **needs no database connection**. That
is not a convenience: a managed Postgres that only accepts pooled connections,
or a network that filters 5432, makes `up` impossible, and this project has hit
both. The printed output includes the `schema_migrations` insert, so the applied
state is still recorded.

**The raw file in `migrations/versions/` deliberately does not carry that
insert.** A migration applied by pasting the file — rather than the `sql`
output — therefore leaves the ledger untouched, and `migrate.py mark VERSION`
is how that is corrected. This is not hypothetical: it happened with ADR 0003's
drop migration on 15 Oct, where `migrate.py status` read `pending` on a
migration that had already run.

## Operating it has taught three things

These are in this ADR rather than in the script because each one cost real time.

### 1. A duplicate version number is applied-once and then skipped for ever

`up` decides what to run by **version**, not by checksum. So a file whose
timestamp already exists in `schema_migrations` is treated as applied and is
never run — silently, and for ever.

This nearly shipped on 15 Oct. ADR 0003's drop migration was numbered
`20261015120000`, which was **already in the ledger** as `journey_deadline`
(`by=nakib`). Only a checksum mismatch surfaced it; the migration was renumbered
to `20261015160000`. Defect 55 was the same failure mode found the hard way.

**The ledger is shared, so a timestamp is a shared namespace.** Check `status`
before naming a file, and prefer a timestamp that is actually now.

### 2. The ledger can name migrations whose files are not in this repository

`schema_migrations` currently holds `20261014150000` (`journeys`),
`20261015120000` (`journey_deadline`, `by=nakib`) and `20261015140000`
(`journey_leash`, `by=nakib`) with **no corresponding files committed**. They
are a teammate's uncommitted work against the shared database.

So `status` showing a version you cannot find is **not** evidence of corruption,
and the correct response is to ask, not to reconcile. It also means
`journeys` must not be dropped or built on: see `PROGRESS.md`'s CURRENT STATE.

### 3. A drop is not final while another checkout declares the model

`init_db()` runs `Base.metadata.create_all` on every API boot. A table dropped
by migration comes back the moment any machine with the model boots — which is
exactly what happened to `public.users` hours after ADR 0003's migration ran.
A destructive migration therefore needs the *code* change merged and pulled
everywhere, and the migration alone is not the deliverable.

## Consequences

**Every schema change is a code review of SQL**, which is slower per change and
is the point: the `CHECK` constraints in this schema are policy, and policy
should be read before it ships.

**`migrate.py status` is the source of truth for what a database has**, and it
can disagree with `git` in both directions — a file with no ledger row (needs
`up` or `mark`), or a ledger row with no file (a teammate's, see above).

**New tables must be classified in `app/privacy/retention.py`** or
`test_retention_is_declared.py` fails. That tripwire is how `journeys` was
discovered holding movement history with no rule, and how `public.users` was
caught coming back.

**No rollback plan means forward fixes must be cheap**, which argues for small
migrations. The largest in this repo is ADR 0003's drop, and it is large because
it refuses to proceed rather than because it does many things: it raises if a
dependent FK exists, and announces what it is about to destroy first.
