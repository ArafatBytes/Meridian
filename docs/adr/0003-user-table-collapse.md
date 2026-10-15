# ADR 0003 — One identity: `auth.users`, with `profiles` for display

| | |
|---|---|
| **Status** | Accepted — **and executed**, 2026-10-15 |
| **Date** | 2026-10-15 (written after execution; see *Why this is written late*) |
| **Decider** | Arafat (owner) |
| **Depends on** | ADR 0002. "Supabase is the IdP" is only true if there is no second user table to authenticate against. |
| **Supersedes** | `public.users` as declared in `migrations/supabase/SCHEMA.sql` §5.1 |

---

## Context

This project had **three** tables that each claimed to describe a user:

| table | owner | what it held |
|---|---|---|
| `auth.users` | Supabase | the real identity: id, email, confirmation state |
| `public.users` | us | a mirror: `id`, `email`, `full_name`, `phone`, `hot_words`, **`password_hash`**, `is_active`, `is_verified` |
| `public.profiles` | us | display: `id`, `email`, `name`, `phone`, `avatar_url` |

`public.users` was inherited. It existed because the inherited application
intended to authenticate locally — hence `password_hash` — and that intention
was abandoned when Supabase Auth was adopted, without the table going with it.

It was not inert. `endpoints/sos.py` auto-provisioned a row into it on **every
SOS trigger**, and read `full_name` back to address the alert. Nothing kept that
copy in step with `profiles`, so the alert's name came from whichever table had
been written most recently by which code path.

## Decision

**`auth.users(id)` is the identity. `public.profiles` is the only place
user-facing attributes live. `public.users` is dropped.**

Concretely:

* every `user_id` column references `auth.users(id)`;
* a backend that needs a human-readable name reads `profiles.name`;
* no table in `public` stores a password, a hash, or a verification flag — those
  are Supabase's, and ADR 0002 is why.

## Why this is written late

**This ADR documents a decision that had already been executed, and that is the
point of writing it.**

By the time anyone audited it, the migration half had happened piecemeal across
several sprints: `migrations/.../20261010160000__gd_profiles_on_auth_users.sql`
repointed the last holdout (`gd_drafts.user_id`), and every other `user_id` had
pointed at `auth.users(id)` since commit `2d924a2`. The table was a mirror that
nothing referenced.

Nobody knew that. **Three documents — DEMO_PLAN D09, the B1 backlog row, and a
PROGRESS note on ADR 0005 — all stated that dropping `public.users` "would have
broken SOS".** That claim had one root cause: somebody read a SQLAlchemy
`ForeignKey` in `app/models/` as a description of the deployed schema. The ORM
models declared relationships to `public.users`; `SCHEMA.sql` did not. The
models were a *client* of the schema and had drifted from it, and reading them as
the schema produced a confident, wrong, and repeatedly-copied conclusion that
blocked this work for weeks.

The lesson is the reason this file exists even though it changes nothing:
**an unwritten decision gets re-derived, and re-derivation goes wrong silently.**
`git log -L 203,207` on `SCHEMA.sql` answered the question in one command. No
one ran it, because the belief was already written down three times.

## What was executed (defect 9, 2026-10-15)

1. **`endpoints/sos.py`** — the auto-provisioning block deleted; a new
   `_display_name()` reads `public.profiles.name` and falls back to the email
   address with a logged warning. The old code derived the name from the email's
   **local part**, so alerts read *"EMERGENCY: mdarafat1661 needs help"*. They
   now read *"EMERGENCY: Arafat Ullah needs help"* — verified against the three
   live accounts. That string appears in the subject and five more times in the
   body, including *"Try calling {user_name}."*
2. **`app/models/user.py` deleted**, and its import removed from
   `models/__init__.py`. This was a *prerequisite*, not tidying: `init_db()`
   runs `Base.metadata.create_all` on every API boot inside a try/except that
   logs "Database not available" and continues. With the model present, the
   restart after the drop would have recreated the table and swallowed the
   reason.
3. **Four `relationship()` declarations and their `ForeignKey`s removed** from
   `crime.py`, `emergency_contact.py`, `location.py`, `sos.py`. `crime.py`
   carries the canonical note on why `user_id` has no `ForeignKey`: `auth.users`
   lives in Supabase's own schema, and an ORM FK cannot be declared across it.
4. **`20261015160000__drop_public_users_mirror.sql`** — five sections: announce
   the rows about to be destroyed; carry any orphaned `full_name` into
   `profiles`; **raise** if any dependent FK exists; drop the trigger and the
   table; prove it is gone. Applied via the Supabase SQL Editor and recorded with
   `migrate.py mark` (ADR 0004 explains why a pasted migration needs that).
5. `SCHEMA.sql` §5.1 and `VERIFY.sql` updated, the latter gaining a check that
   **asserts the table is absent**.

## Consequences

**`profiles` is now load-bearing for the SOS alert.** If a profile row is
missing, the alert names the person by email address and the server logs a
warning. That is a deliberate degradation — an alert that goes out with a poor
name beats one that does not go out — but it means registration must create the
profile row, which `auth.service.ts` does.

**Account deletion is still not built**, and this ADR makes it a single
question: deleting the `auth.users` row is the act, and `profiles`,
`gd_profiles` and every `user_id`-bearing table must follow it. There is no
longer a fourth copy to forget.

**The drop does not stay dropped by itself.** On 15 Oct, hours after the
migration ran, `public.users` **reappeared** — 0 rows, no trigger, no
dependents, and absent from our `Base.metadata`. That shape is what
`create_all` produces from a checkout that still has `app/models/user.py`, so a
teammate's machine on the shared Supabase database recreated it. Step 2 above is
necessary but only sufficient *per checkout*. `test_retention_is_declared.py` is
what noticed, and the owner chose to leave that test red as a standing signal
rather than drop the table again or classify it away.
