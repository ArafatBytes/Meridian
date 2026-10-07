# Contributing to Meridian

Two developers, non-overlapping hours, **one writer at a time**. This page is
the short version of the rules. The long version is
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) §2 and §3.

**If you are a Claude Code agent: read [PROGRESS.md](PROGRESS.md) first, in
full, before touching any file.** It is the only record of what the other
developer's session did.

---

## The four relay rules

1. **One writer at a time. The trunk is a baton.** You either hold it or you
   don't. If you don't, you don't touch the repo — not a typo fix, not a
   dependency bump.
2. **Every push is a working prototype.** Not "compiles" — *runs*, on a device,
   doing what the sprint promised. The Prototype Gate below is the checklist.
3. **The handoff log is part of the push.** No `PROGRESS.md` entry, no push. CI
   enforces this.
4. **Stub-first.** Every contract ships a working stub before the real
   implementation. That is how a sprint ends in something demoable while half
   the system does not exist yet.

The one exception to Rule 1 is **background activities** (§3.6): the corpus, the
gazetteer, the Journey Guardian trial. Those touch data files only, never code,
and the person *not* holding the baton can work on them.

---

## Taking the baton

```bash
git checkout main && git pull
cat PROGRESS.md                     # read it, don't skim it
./scripts/seed.sh                   # bring your DB up to the schema
./scripts/check.sh                  # confirm you received a GREEN trunk
git checkout -b sprint/S<nn>-<slug>
```

**If `check.sh` fails on a trunk you just received, stop and say so.** Do not
debug the previous sprint inside yours. You will lose your window and the log
will stop reflecting reality.

Then open [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) at the sprint named
in `CURRENT STATE → NEXT SPRINT`. That sprint's checklist is your scope. Not the
one after it.

## Passing the baton

```bash
./scripts/check.sh                  # green
./scripts/seed.sh --fresh           # schema builds from zero
./scripts/smoke.sh                  # every sprint's demo still passes
```

Then, in the same commit:

1. Write a new entry at the top of `PROGRESS.md`'s handoff log (template is at
   the bottom of that file).
2. **Overwrite** the `CURRENT STATE` block.
3. Tick your sprint's checkboxes in `IMPLEMENTATION_PLAN.md`.
4. Add a `demo_S<nn>` function to `scripts/smoke.sh`.
5. Push, open a PR, squash-merge to `main`, and tell your partner the baton is
   free.

---

## The Prototype Gate

All seven, every handoff.

| # | Gate |
|---|---|
| 1 | `./scripts/check.sh` green |
| 2 | `./scripts/seed.sh --fresh` works from an empty database |
| 3 | The app **builds and launches** on a real device or emulator |
| 4 | This sprint's demo is in `scripts/smoke.sh` and passes |
| 5 | `PROGRESS.md`: new entry + `CURRENT STATE` overwritten |
| 6 | New env vars in `.env.example` **and** plan §9 |
| 7 | Nothing half-migrated: contracts have consumers, migrations seed clean |

**A sprint that cannot clear the gate ends early rather than ending broken.**
Cut scope, push what works, write down what you dropped. A broken trunk costs
your partner their entire window.

---

## Branches

```
main                     protected, always green, always demoable
sprint/S<nn>-<slug>       one sprint, one branch, one PR, squash-merged
fix/<slug>                urgent production fix, any time
```

Rebase from `main`, never merge into your branch. Because only one person ever
has a branch open, conflicts are essentially impossible — if you hit one,
something has gone wrong with the baton.

---

## Contracts

`backend/app/contracts/` holds the shapes everything else communicates through.
Stable by default. To change one (plan §2.5):

1. Add a `CONTRACT CHANGE` block to your `PROGRESS.md` entry — what changed,
   what it breaks.
2. Update **every** consumer in the same sprint. You hold the baton; there is no
   excuse for leaving one broken.
3. Update the TypeScript mirror in `frontend/src/types/contracts/` in the same
   push.

---

## Invariants

Five ethical constraints from the concept document, plus two of ours, are
enforced by tests in `backend/tests/invariants/` that run on every PR
(plan §4):

- **Mobility framing, never judgment** — flag text is only ever written by
  `app/policy/framing.py`
- **Verification before publication** — one source can never produce a
  `confirmed` flag
- **Decay by default** — every flag has a half-life; the database enforces it
- **Graded escalation** — no escalation step is skipped, and each requires a
  recorded non-response
- **Data minimisation** — every location-bearing table declares a retention
  window
- **No unvalidated LLM output** — `app/llm/client.py` is the only module that
  may import `anthropic`
- **Unresolvable locations are discarded, never guessed**

If the `invariants` CI job is red, an ethical constraint has been violated.
Treat it differently from a type error.

---

## Code conventions

**Python** (`backend/`)
- `ruff` and `mypy` config live in `backend/pyproject.toml`
- New modules (`app/contracts`, `app/agents`, `app/llm`, …) are `mypy --strict`
- Legacy modules are silenced per-module, **each annotated with the sprint that
  un-silences it**. Do not add a row there without a sprint number — that is
  how a temporary exemption becomes permanent.
- No `print()` in application code; use the logger
- Every LLM call goes through `app/llm/client.py` and returns a validated
  Pydantic model (plan §6.4)

**TypeScript** (`frontend/`)
- One directory per feature under `src/features/`, self-contained
- `src/components/` is shared primitives only
- Contract types are mirrored, not redefined
- `tsc --noEmit` and `eslint --max-warnings=0` must both be clean

**Database**
- Forward-only migrations. A merged migration is immutable — correct it with a
  new one. CI enforces this.
- Until S02, `backend/migrations/supabase/SCHEMA.sql` is the schema and is
  hand-run in the Supabase SQL Editor. See its README.

**Secrets**
- Never commit a `.env`. The ignore rules allow `*.env.example` only.
- The app may hold the Supabase **anon** key, and only because Row Level
  Security is what actually guards the data.
- The **service-role** key and the database password are backend-only.

---

## Local setup

```bash
# Hooks (once per machine)
pip install pre-commit && pre-commit install

# Frontend
cd frontend
cp .env.example .env        # fill in your Supabase project
npm install                 # then COMMIT package-lock.json
npx expo start --clear      # --clear matters: EXPO_PUBLIC_* is inlined at build time

# Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL, JWT_SECRET_KEY, SMTP_*
python scripts/download_models.py                 # yolov9c.pt, ~82 MB
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Database setup is its own guide:
[`backend/migrations/supabase/README.md`](backend/migrations/supabase/README.md).
Read §2 and §4 of it — email confirmation and the JWT secret are the two things
that will otherwise cost you an afternoon.
