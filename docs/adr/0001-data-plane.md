# ADR 0001 — Two data planes, and the line between them

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-15 |
| **Decider** | Arafat (owner) |
| **Consulted** | Written retrospectively from the code. The split below was not designed in a meeting; it emerged, and this document ratifies it and names the one place it is contradicted. |
| **Supersedes** | Nothing. It writes down a rule `IMPLEMENTATION_PLAN.md` §S02 proposed and nobody recorded. |
| **Does not supersede** | ADR 0002 (auth), which depends on this one and must stay consistent with it. |

---

## Context

Meridian has **two** ways to reach its database, and both are in use today.

1. **Supabase-direct.** The React Native client holds a Supabase client and talks
   to PostgREST with the signed-in user's own JWT. Row-level security is what
   decides whether a statement is allowed.
2. **FastAPI.** The backend holds a service-role connection and talks to the same
   Postgres over SQLAlchemy/asyncpg.

This was never a decision. The inherited application routed everything through
FastAPI — which is why `endpoints/users.py`, `crimes.py`, `tracking.py` and
`auth.py` exist. Meanwhile the client, needing to ship screens, went straight to
Supabase for the things a user owns. Both halves grew. The plan proposed a rule
in S02 (*"Supabase for user-owned CRUD; FastAPI for anything agentic,
geospatial, or multi-user"*) and the sprint that would have written it down was
reordered away by ADR 0005.

The cost of not writing it down is not hypothetical. It is four endpoint files
that are registered on the public API and do nothing, and a reader who cannot
tell whether that is a gap to fill or dead code to delete.

## Decision

**User-owned rows are read and written Supabase-direct, under RLS. Everything
else goes through FastAPI.**

"Everything else" is three properties, any one of which is sufficient:

* **Agentic** — it calls an LLM, runs on a schedule, or scrapes.
* **Geospatial** — it needs PostGIS. `ST_DWithin`, geography columns, bounding
  boxes.
* **Multi-user** — the output is derived from more than one person's data, so no
  single user's RLS context is the right authority.

### Where each table lives

| Plane | Tables | Why |
|---|---|---|
| **Supabase-direct** | `profiles`, `emergency_contacts`, `sos_hot_words`, `crime_reports` | Each row has exactly one owner, and `auth.uid()` is the whole of the access rule |
| **FastAPI** | `risk_flags`, `community_clusters`, `raw_documents`, `extracted_incidents`, `news_crime_incidents`, `sos_incidents`, `gd_drafts`, `gd_profiles`, `push_devices`, `notification_preferences`, `alert_history`, `schema_migrations` | Agent output, cross-user derivation, PostGIS, or a service-role write the client must not be able to forge |

The first column is not aspirational: it is what
`frontend/src/services/auth.service.ts`, `EditProfileScreen`,
`EmergencyContactsScreen`, `SOSHotWordsScreen` and `MapScreen` already do.

`crime_reports` is the interesting one, and it belongs in the first column for a
reason worth stating: a report is **authored** by one person and is theirs to
withdraw, so CRUD is user-owned. What the *aggregate* of reports means is not —
`community_clusters` is a different table, written by an hourly agent, and
publishing needs two independent reporters within 200 m (B13). **Ownership of a
row and authority over what rows collectively claim are different questions, and
they land on different planes.**

### Why RLS is the enforcement point, not a FastAPI endpoint

A backend endpoint that checks ownership re-implements, in Python, a rule the
database can state once in SQL. Two implementations of one rule is two places to
get it wrong, and the one that is wrong will be the one nobody is looking at.
Worse, the backend holds a service-role key, so a missing check there is
unlimited rather than scoped — exactly the failure that the dropped
`public.users` mirror made possible (ADR 0003).

### Why the client cannot own the second column

Not for lack of ability — PostgREST would happily serve `risk_flags` — but
because the write side cannot be delegated. A flag's `mobility_statement` is
produced by `app/policy/framing.py` and guarded by a database CHECK; a severity
is decayed on read from `severity_0`; an incident is published only after
`app/policy/independence.py` has agreed the sources are independent. Those are
invariants with code behind them, and a client that could insert a `risk_flag`
could bypass all of them.

## Consequences

### `auth.py`, `crimes.py`, `users.py` and `tracking.py` are dead and must go

All four are registered in `app/api/v1/api.py` and every handler is a bare
`pass`. Under this ADR none of them should exist: every operation they name is
user-owned CRUD that the client already does Supabase-direct.

They are not harmless. A `pass` handler with a `response_model` returns `None`
against a non-optional schema, so the endpoint is a 500 rather than a 404 — a
public API that advertises `POST /api/v1/crimes/report` and fails in a way that
reads like a bug in the caller. `/auth/refresh` is the clearest case:
`api.service.ts` documents in a comment that it is a stub which *"would have
422'd even if it were implemented"*, and refreshes through
`supabase.auth.refreshSession()` instead. The client has already routed around
all four.

**✅ Deleted the same day, 15 Oct**, along with their `include_router` lines and
their orphaned schemas (`schemas/auth.py`, `user.py`, `crime.py`,
`tracking.py` — nothing else imported them, and a schema describing an endpoint
that does not exist is the template for recreating it).

`auth.py` went first and separately: it was not dead weight but **defect 56**, a
live authentication bypass. The other three were genuinely inert. Verified after
removal: `/users/me`, `/crimes/nearby` and `/tracking/check-danger-zone` return
**404** where they used to 500; `/sos/history` still returns **401**;
`/risk/flags` still **422**s on a missing bbox. **The client needed no change at
all**, which is the evidence that the rule above was already how this system
worked.

`tests/invariants/test_no_endpoint_is_a_stub.py` holds the line, and
deliberately does not name these four: it parses every handler under
`endpoints/` and fails on any body that is only a docstring and/or `pass`, and
it refuses any router mounted on `/auth`, `/users`, `/crimes` or `/tracking`. A
check that named the four already dealt with would never catch a fifth.

### `public.user_locations` is written by nothing

It is PostGIS-shaped and therefore in the FastAPI column, but S17 found it needs
no writer at all: OS-level geofencing hands back a region identifier, not a
position, and `push_devices.last_location` holds a single overwritten point. A
table on the FastAPI plane with no writer is not a violation of this ADR, but it
is a thing to either use or drop — see `app/privacy/retention.py`, which
classifies it.

### This does not migrate off Supabase

Both planes stay. `IMPLEMENTATION_PLAN.md` §B21 already records why: a migration
would cost two sprints and buy nothing the product needs. Auth, storage and RLS
are the parts of Supabase this project is actually leaning on, and ADR 0002
commits to the first of those explicitly.

### What a reviewer can now check

Any new table has to be placed in one of the two columns above, and the three
properties decide it. Any new FastAPI endpoint over a first-column table needs
to explain why RLS is not sufficient, and "it was easier from the client" is not
one of the three properties.
