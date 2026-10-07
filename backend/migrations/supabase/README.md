# Fresh Supabase setup

Everything needed to stand up a new Supabase project that runs the **current**
Meridian implementation. Takes about ten minutes.

| File | Purpose |
|---|---|
| `SCHEMA.sql` | The whole schema. Idempotent — safe to re-run. |
| `VERIFY.sql` | Post-run checks. Every row should say `✅ OK`. |
| `RESET.sql` | **Destructive.** Drops everything so you can start over. |

> **These are hand-run files, not managed migrations.** The migration runner
> (`scripts/migrate.py` + a `schema_migrations` table) arrives in **S02** under
> ADR 0004. Until then, the Supabase SQL Editor is the deployment mechanism.

---

## 1. Create the project

Supabase dashboard → **New project**. Pick the region closest to Bangladesh
(`ap-southeast-1`, Singapore) — every query from a Dhaka phone pays this
round trip.

Collect four values from **Settings**; you will need all of them:

| Value | Where | Used by |
|---|---|---|
| Project URL | Settings → API | frontend |
| `anon` public key | Settings → API | frontend |
| Database password | Settings → Database | backend |
| JWT secret | Settings → API → JWT Settings | backend (see §4) |

---

## 2. Turn off email confirmation

**Authentication → Sign In / Providers → Email → disable "Confirm email".**

This is not optional for the current code. `auth.service.ts` does:

```ts
const { data: authData } = await supabase.auth.signUp({ ... });
if (!authData.user || !authData.session) throw new Error('Registration failed');
```

With confirmation enabled, `signUp` returns a user but **no session**, so every
registration fails with "Registration failed" and no indication why.

Proper email confirmation is a pre-launch item (Phase 6), and it needs the
register flow reworked to handle a session-less signup. Not now.

---

## 3. Run the SQL

Supabase dashboard → **SQL Editor** → new query, then in order:

1. `RESET.sql` — only if the project already has Meridian tables. Skip on a brand-new project.
2. `SCHEMA.sql` — paste the whole file, run once.
3. `VERIFY.sql` — every row should read `✅ OK`.

`VERIFY.sql` may report PostGIS as `⚠️ NOT INSTALLED`. That is fine for now:
nothing in the current code writes a `geography` column. If `SCHEMA.sql` failed
on the `create extension postgis` line, enable it under
**Database → Extensions → postgis**, then re-run `SCHEMA.sql`.

### What gets created

| Table | Written by | Read by |
|---|---|---|
| `profiles` | app | app |
| `crime_reports` | app | app (all users' reports) + backend `route_service` |
| `emergency_contacts` | app | **backend `sos_service`** — this is what makes SOS work |
| `sos_hot_words` | app | nothing yet (S18) |
| `users` | backend `sos.py` | backend — **transitional, deleted in S02** |
| `sos_incidents` | nothing yet (S05) | — |
| `user_locations` | nothing yet (S17) | — |

Plus: the `crime_category` enum, `updated_at` triggers, RLS on all seven
tables, and a public-read `avatars` storage bucket scoped so a user can only
write inside their own `<uid>/` folder.

---

## 4. Point the apps at it

### Frontend — `frontend/.env`

```bash
EXPO_PUBLIC_SUPABASE_URL=https://<your-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=<your anon key>
```

Then restart Metro with a cleared cache — `EXPO_PUBLIC_*` values are inlined at
bundle time, so a running dev server will keep serving the old ones:

```bash
npx expo start --clear
```

### Backend — `backend/.env`

```bash
# Settings → Database → Connection string → URI, with the driver swapped
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

SUPABASE_URL=https://<your-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key — server only, never in the app>
JWT_SECRET_KEY=<JWT secret from Settings → API → JWT Settings>
```

**Two connection traps, both of which produce confusing errors:**

1. **Use port `5432` (session pooler), not `6543`.** Port 6543 is PgBouncer in
   transaction mode, which breaks asyncpg's prepared-statement cache. The
   symptom is intermittent `prepared statement "__asyncpg_stmt_x__" does not
   exist`. If you must use 6543, pass `statement_cache_size=0` in the
   SQLAlchemy `connect_args`.
2. **`postgresql+asyncpg://`, not `postgresql://`.** Supabase gives you the
   latter; `backend/app/core/database.py` uses the async engine and will fail
   at startup without the `+asyncpg` driver suffix.

### ⚠️ The JWT secret will probably bite you

`backend/app/core/security.py` validates the app's Supabase token with a
**shared HS256 secret**:

```python
jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"], ...)
```

New Supabase projects default to **asymmetric (ECC/RSA) signing keys**. If
yours does, HS256 validation cannot work and every authenticated backend call —
which today means SOS — returns `401 Could not validate credentials`.

Two ways forward:

- **Now:** use the legacy HS256 secret from Settings → API → JWT Settings, if
  your project still exposes one.
- **Properly:** **ADR 0002 in S02** replaces this with JWKS verification against
  Supabase's published public keys, which works with asymmetric keys and
  removes the shared secret entirely. If the legacy secret is unavailable on
  your project, pull that ADR forward rather than working around it.

---

## 5. Confirm it works

In this order, because each step depends on the one before it:

1. **Register** a new account in the app → a row appears in `profiles`.
2. **Submit a crime report** with a photo → a row appears in `crime_reports`,
   and it shows on the map.
3. **Add an emergency contact** with a real email → a row appears in
   `emergency_contacts`.
4. **Trigger SOS** → the backend reads that contact and sends the alert email.
   This is the step that exercises `DATABASE_URL` *and* `JWT_SECRET_KEY`, so
   it is where a misconfiguration surfaces.

---

## 6. Known issues this schema deliberately preserves

Each of these is scheduled. Do not fix them here — the fix needs a client
change in the same commit, or it breaks something.

| Issue | Why it stays | Fixed in |
|---|---|---|
| `crime_reports.latitude/longitude` are `varchar` | The app sends strings and the ORM declares `String`. Changing the column alone breaks reads. | S05 |
| `incident_date_time` is `timestamp` without a zone | The app encodes Dhaka local time *as if it were UTC*. The column matches the client's bug on purpose; changing one without the other shifts every timestamp by six hours. | S07 |
| `public.users` duplicates `profiles` | `sos.py` auto-provisions into it. Removing it now breaks SOS. | S02 (ADR 0003) |
| `password_hash` is always `"supabase_managed"` | Vestigial — Supabase owns authentication. Column dies with the table. | S02 |
| `sos_hot_words` is written and never read | The screen works; nothing consumes the words. | S18 |

---

## 7. Retire the old project

The previous Supabase URL and anon key were committed in `frontend/app.json`
and are in git history. S01 moves them to `.env`, but **git history is not
rewritten** — so treat the old project as compromised:

- Pause or delete it in the dashboard.
- A Supabase `anon` key is designed to be public and is only as strong as your
  RLS, so this is not an emergency. But the old project had no RLS review, so
  do not leave it running with real data in it.
