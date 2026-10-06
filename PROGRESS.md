# Meridian — Relay Progress Log

> This file is the handoff between two developers whose working hours never overlap.
> It is the only memory your partner's Claude Code agent has of your session.

---

## ⚡ AGENT: READ THIS BEFORE WRITING ANY CODE

If you are a Claude Code agent starting a session on this repository, do these in order:

1. **Read the `CURRENT STATE` block below, in full.** It is the authoritative answer to "where is this project right now." Do not infer state from the code; the code does not tell you what was deliberately left unfinished.
2. **Read the most recent 1–2 entries in the Handoff Log.** They tell you what just changed, what was decided, and what traps are waiting.
3. **Read the `RESUME HERE` line.** That is your starting point. Do not pick your own.
4. **Open [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) at the sprint named in `NEXT SPRINT`.** That sprint's task list is your scope. Not the one after it.
5. **Verify you received a green trunk** before changing anything:
   ```bash
   ./scripts/seed.sh && ./scripts/check.sh
   ```
   If this fails, **stop and tell the user.** Do not debug the previous sprint's work inside this sprint — report it, and let them decide whether to fix or revert.

**Before the session's final push, you must write a new Handoff Log entry and overwrite `CURRENT STATE`.** Use the template at the bottom. The `handoff-log` CI job rejects any PR to `main` that does not modify this file.

**Rules for this file**
- `CURRENT STATE` is **overwritten** every handoff — it is a snapshot, not a history.
- The Handoff Log is **append-only, newest entry first**. Never edit or delete a past entry. If a past entry turns out to be wrong, say so in the *new* entry.
- Write `RESUME HERE` as if to a stranger, because your partner's agent is one.
- **Record what you deliberately did *not* do, and why.** An unexplained gap gets rediscovered, re-litigated, or silently "fixed" in a way that breaks your intent.

---

## 📍 CURRENT STATE

*Last updated: 2026-10-07 · by: Arafat (planning session) · after: S00*

| | |
|---|---|
| **Last sprint completed** | S00 — Planning (no code) |
| **NEXT SPRINT** | **S01 — Unblock the repository** → [plan](IMPLEMENTATION_PLAN.md) |
| **Baton holder** | Arafat |
| **Trunk** | `main` @ `975d431` · working branch `agent/Arafat` (delete after S01) |
| **Build status** | 🔴 **RED** — see below |
| **Phase** | 0 — Foundation & Contracts |

### 🔴 Why the trunk is red

This is the pre-existing state, not a regression. Both are S01's job.

- **Frontend does not build from a clean clone.** `frontend/src/lib/` is imported by 8 files, does not exist on disk, and was never committed — root `.gitignore:44` has a bare `lib/` that matches it. Verify with `git check-ignore -v frontend/src/lib/supabase.ts`.
- **Backend is not runnable in this tree.** No `.env`, no `venv/`, no `yolov9c.pt`.

### System state

| Subsystem | State |
|---|---|
| `scripts/{check,seed,smoke}.sh` | ❌ Do not exist — created in S01 |
| CI (`.github/workflows/`) | ❌ Does not exist — created in S01 |
| `app/contracts/` | ❌ Not authored — S03 |
| `RISK_SURFACE_IMPL` | ❌ n/a — no surface implementation exists yet (first one lands S04) |
| Agents live | **0 of 8** |
| LLM client | ❌ `anthropic` is not a dependency yet — S04 |
| Migrations | ⚠️ Four ad-hoc `.sql` files in `backend/migrations/`, no runner, no `schema_migrations` table — S02 |
| `tests/invariants/` | ❌ Does not exist — S03 |
| Known defects | **17 open** — see [plan §1](IMPLEMENTATION_PLAN.md). None fixed yet. |

### 🧵 Background activities (off-baton, §3.6)

None active yet. First one starts in S09 (corpus annotation).

| Activity | Owner | Started | Status |
|---|---|---|---|
| — | — | — | — |

### ▶️ RESUME HERE

**Start S01, task 1: fix `.gitignore:44`** — change the bare `lib/` to `/backend/lib/`, then confirm `git check-ignore -v frontend/src/lib/supabase.ts` returns nothing. Then author and commit `frontend/src/lib/supabase.ts` and `supabase-storage.ts` so a clean clone builds.

Work through S01's checklist in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) in order. Stop at the end of S01 — do not start S02.

---

## 🔖 Quick reference

```bash
# Take the baton
git checkout main && git pull
cat PROGRESS.md && ./scripts/seed.sh && ./scripts/check.sh
git checkout -b sprint/S<nn>-<slug>

# Pass the baton
./scripts/check.sh && ./scripts/seed.sh --fresh && ./scripts/smoke.sh
# → write the Handoff Log entry + overwrite CURRENT STATE
# → tick the sprint's checkboxes in IMPLEMENTATION_PLAN.md
git push   # then PR, squash-merge to main, tell your partner
```

**The Prototype Gate** — all seven, every handoff ([plan §3.4](IMPLEMENTATION_PLAN.md)):
`check.sh` green · `seed.sh --fresh` works · app launches on a device · `smoke.sh` passes · this file updated · env vars in `.env.example` + plan §9 · nothing half-migrated

**Where things live:** contracts → `backend/app/contracts/` · fixtures → `backend/data/fixtures/` · invariants → `backend/tests/invariants/` · ADRs → `docs/adr/`

---

# 📜 Handoff Log

*Newest first. Append-only.*

---

## S00 — Planning

**Owner:** Arafat · **Date:** 2026-10-07 · **Branch:** `agent/Arafat` · **Merge:** n/a (docs only)

### Shipped
Full audit of the existing codebase (86 source files, both READMEs, all 13 backend docs, migrations, data assets, the concept document) and a relay-model implementation plan built on it.

- `IMPLEMENTATION_PLAN.md` — 39 sprints across 8 phases, relay model, contracts, invariants, risk register
- `PROGRESS.md` — this file

### Decisions

1. **Relay over parallel tracks.** Our working hours do not overlap, so parallel branches would buy wall-clock compression we cannot collect, in exchange for merge complexity we would pay in full. Relay gives a single always-integrated trunk and a working prototype at every handoff. Reasoning recorded in [plan §2.1](IMPLEMENTATION_PLAN.md).
2. **Stub-first is retained**, with a new justification. It no longer exists to unblock a parallel developer; it exists so a sprint can end in a working prototype while half the system does not exist. `SeededRiskSurface` (S04) is what makes S12–S13 demoable before any agent is written.
3. **Contracts are retained, the pair-review ceremony is dropped.** The architecture needs stable shapes — the concept doc requires eight agents that fail independently. The two-approval process does not apply when there is one writer.
4. **Fixes come before features.** All 17 known defects are paid down in Phase 1 (S05–S08) before the first agent is built. Phase 0 comes before even that, because the repo does not currently build from a clean clone.
5. **Geocoding is sequenced first among the agents** (S10–S11). The concept document names it the primary technical risk; if it fails we want to know in Phase 2, not Phase 5.
6. **Concept doc §9 ethics became executable invariants** ([plan §4](IMPLEMENTATION_PLAN.md)), each with a test in `tests/invariants/` running on every PR. Mobility framing, multi-source verification, mandatory decay, graded escalation, data minimisation — enforced in code, not documented as intentions.
7. **Hackathon deadline dropped.** Target is a production public release.

### Deliberately NOT done
- **No code was written.** This was a planning session only. The trunk is in exactly the state it was found in.
- **Did not restore or modify `Meridian_Concept_Document.md`** — it briefly showed as deleted in the working tree during the session but is present and the tree is clean.
- **Did not fix the `.gitignore` blocker**, despite it being an hour's work, so that S01 starts from a known state with a scripted gate behind it.

### Known broken
All 17 defects in [plan §1](IMPLEMENTATION_PLAN.md). The two blockers (missing `frontend/src/lib/`, `pydub`/`AudioSegment` `NameError`) are the ones that prevent the project from running at all.

### Gotchas for the next agent
- **`frontend/src/lib/` is gitignored by accident.** The root `.gitignore` has `lib/` for Python build artifacts; it matches `frontend/src/lib/` too. Fixing the ignore pattern is not enough — the two files were never committed and must be authored.
- **`backend/app/api/v1/endpoints/crime_ai.py` is dead code.** 227 lines, never registered in `api.py`, a near-duplicate of `ai.py`. Do not "fix" it; it is deleted in S05.
- **The README is substantially out of date** — wrong RN/Expo versions, claims FCM (the app uses `expo-notifications`), claims a 5-minute SOS video (it is 10 seconds), claims SMS (there is none). Trust the code and this plan, not the README. It gets rewritten late, not early.
- **Three user tables exist** (`auth.users`, `public.profiles`, `public.users`) with incompatible definitions between `create_users_table.sql` and `models/user.py`. Do not add a fourth. ADR 0003 in S02 collapses them.
- **`backend/scripts/crime_risk_model.json` is real, useful data** — 16 geo-anchored risk zones derived from 1,105 rows of Bangladesh Police statistics. It becomes `LegacyRegionalSurface` in S12. Do not delete it.

### RESUME HERE
See the `CURRENT STATE` block at the top of this file.

### Prototype Gate
- [x] 1 · `check.sh` green — n/a, docs-only change
- [x] 2 · `seed.sh --fresh` — n/a
- [x] 3 · App launches — n/a (trunk is knowingly red; S01 fixes it)
- [x] 4 · `smoke.sh` — n/a
- [x] 5 · `PROGRESS.md` updated
- [x] 6 · Env vars — none added
- [x] 7 · Nothing half-migrated

---

# 📋 Entry template

Copy this block, fill it in, and paste it directly under `# 📜 Handoff Log` so the newest entry is always first.

```markdown
## S<nn> — <Sprint title>

**Owner:** <name> · **Dates:** <start> → <end> · **Branch:** `sprint/S<nn>-<slug>` · **Merge:** `<sha>`

### Shipped
<What now works that did not work before. One or two sentences, then bullets.
 Write it as a demo script: "you can now do X by doing Y".>

### Files
- **Added:** `path/one.py`, `path/two.tsx`
- **Changed:** `path/three.py` — <why>
- **Deleted:** `path/four.py` — <why>

### Decisions
<The most valuable section in this file. Choices you made that the code does not
 explain, and the reasoning. Numbered, so the next entry can reference them.>
1.
2.

### CONTRACT CHANGE
<Delete this section if contracts were untouched. Otherwise, per plan §2.5:>
- **Changed:** `app/contracts/<file>.py` — <what>
- **Breaks:** <which consumers>
- **Updated in this sprint:** <list — all consumers must be fixed before the push>
- **TS mirror updated:** yes / no (must be yes)

### Migrations
- `<utc>__<slug>.sql` — <what it does>
<or: none>

### Env vars added
- `VAR_NAME=default` — <purpose> (also added to `.env.example` and plan §9)
<or: none>

### Measurements
<Required when applicable — plan §10 items 8 and 9.>
- Latency: <endpoint> p50 / p95 = <n> / <n> ms
- Eval delta: <harness> — <metric> <before> → <after>
- LLM cost: <n> ৳ per run · cache hit rate <n>%
- Battery: <n>% per hour with background tracking

### Deliberately NOT done
<Scope you cut, and why. An unexplained gap gets rediscovered or silently
 "fixed" against your intent. Be specific about what you chose and why.>

### Known broken / rough edges
<Anything you are knowingly handing over imperfect. If it breaks the Prototype
 Gate, you should have cut scope instead — say so here if you did not.>

### Gotchas for the next agent
<Traps you hit. Non-obvious build steps, a library that behaves unexpectedly,
 a test that is slow, a fixture that must be regenerated. Save your partner
 the hour you just lost.>

### RESUME HERE
<The exact next action, as if to a stranger. Name the file, the function, the
 sprint task. Not "continue the agent work" — "implement
 `RumourGuard._promote()` per plan S15 task 2; the embedding model is already
 cached in `data/models/`".>

### Prototype Gate
- [ ] 1 · `./scripts/check.sh` green
- [ ] 2 · `./scripts/seed.sh --fresh` works from an empty DB
- [ ] 3 · App builds and launches on a real device or emulator
- [ ] 4 · This sprint's demo is in `scripts/smoke.sh` and passes
- [ ] 5 · `PROGRESS.md`: this entry written + `CURRENT STATE` overwritten
- [ ] 6 · New env vars in `.env.example` **and** plan §9
- [ ] 7 · Nothing half-migrated (contracts have consumers, migrations seed clean)
```

---

# 📐 `CURRENT STATE` template

Overwrite the block at the top of this file with this shape every handoff.

```markdown
## 📍 CURRENT STATE

*Last updated: <date> · by: <name> · after: S<nn>*

| | |
|---|---|
| **Last sprint completed** | S<nn> — <title> |
| **NEXT SPRINT** | **S<nn+1> — <title>** → [plan](IMPLEMENTATION_PLAN.md) |
| **Baton holder** | <name, or "free"> |
| **Trunk** | `main` @ `<sha>` |
| **Build status** | 🟢 GREEN / 🔴 RED (+ why) |
| **Phase** | <n> — <name> |

### System state

| Subsystem | State |
|---|---|
| `RISK_SURFACE_IMPL` | `seeded` / `legacy` / `db` |
| Agents live | <n> of 8 — <names> |
| Migrations applied | through `<latest filename>` |
| Contracts | <stable since S<nn> / changed in S<nn>> |
| Known defects | <n> open of 17 — <which> |
| Feature flags off | <POLICE_ROUTING_ENABLED, CASEWORK_ENABLED, ...> |

### 🧵 Background activities (off-baton)

| Activity | Owner | Started | Status |
|---|---|---|---|
| Corpus annotation | | | <n>/200 articles annotated |
| Gazetteer entry | | | <n> entries, <n> reviewed |
| Guardian self-trial | | | week <n>/2 · <n> false check-ins |

### ▶️ RESUME HERE

<The one action that starts the next sprint.>
```
