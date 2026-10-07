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

## 🚨 SECURITY INCIDENT — read before touching this repo

**2026-10-07: malware was found in `frontend/babel.config.js`** and has been
removed. It was present since the initial commit (`db6c42f`) and executed on
every Metro bundle and every Jest run.

Full write-up, indicators of compromise and the remediation checklist:
**[docs/SECURITY-INCIDENT-2026-10-07.md](docs/SECURITY-INCIDENT-2026-10-07.md)**

**Your step-by-step manual checklist:**
**[docs/INCIDENT-RESPONSE-CHECKLIST.md](docs/INCIDENT-RESPONSE-CHECKLIST.md)**

### Done

- ✅ Payload removed; `babel.config.js` is back to its 5 legitimate lines.
- ✅ `node_modules` deleted and reinstalled from the lockfile; all 1,175
  packages verified against registry signatures.
- ✅ **Arafat's host triaged clean** — offline Defender scan, scheduled tasks,
  `Run`/`RunOnce`, startup folder, and a post-reboot process sweep after 10
  minutes all came back empty.
- ✅ Guards in place: `scripts/scan-injection.sh`, a `supply-chain` CI job, a
  pre-commit hook, and `demo_S01c` in `scripts/smoke.sh`. **The scanner was
  validated against the preserved sample**, not merely assumed to work.

### ⏳ Still outstanding — these are not optional

1. **Rotate every credential** the compromised host touched: Supabase
   (service-role, anon, DB password, JWT secret), Anthropic, SMTP, GitHub
   tokens/SSH, browser and password-manager entries, and **any crypto wallet
   keys or seed phrases first** — the dead-drop design is characteristic of
   crypto-targeting campaigns. Do this **from a different device.**
2. **Nakib: pull before you run anything.** Your clone still has the infected
   file. `npm install`, `expo start` and `npx jest` all detonate it.
3. **Do not make this repository public**, and do not transfer it, until git
   history is rewritten — commit `db6c42f` still carries the payload.

---

## 📍 CURRENT STATE

*Last updated: 2026-10-07 · by: Arafat · after: S01 (+ S01b, S01c, S01d)*

| | |
|---|---|
| **Last sprint completed** | **S01 — ✅ closed.** Grew three unplanned addenda: S01b dockerisation, S01c malware removal, S01d SDK 57 + real auth |
| **NEXT SPRINT** | **S02 — DB foundation & ADRs** → [plan](IMPLEMENTATION_PLAN.md) |
| **Baton holder** | **free — passing to Nakib** |
| **Trunk** | `develop` @ `d78416b` · **60 uncommitted paths in the working tree** (see RESUME HERE) |
| **Build status** | 🟢 **GREEN** — backend `test.sh --ai` 14/14, and the app has now run end to end on a real device |
| **Phase** | 0 — Foundation & Contracts |

### ✅ The app works. This is the first handoff where that is true.

Walked on a device against live Supabase (`docs/RUNNING.md` §4):

| Step | Result |
|---|---|
| Register an account | ✅ row in `profiles` |
| Upload a profile picture | ✅ `avatar_url` populated |
| Submit a crime report with a photo | ✅ row in `crime_reports`; AI pipeline ran and returned *no crime* |
| Add an emergency contact | ✅ row in `emergency_contacts` |
| **Trigger SOS** | ✅ **email with video attachment delivered to the contact** — owner-confirmed |

That last row is what closes S01. Everything before it was configuration.

### 🚀 How to run it

```powershell
.\scripts\run.ps1       # everything: containers, health wait, npm, Expo
./scripts/test.sh       # verify the running stack (5 phases)
./scripts/test.sh --ai  # + the vision pipeline (slow; downloads ~700 MB once)
```

Full guide including the failure-symptom table: [`docs/RUNNING.md`](docs/RUNNING.md).

**Expo Go must be current.** The project is on **SDK 57**; Expo Go ships only the
newest SDK, which is why the SDK 54 pin had to go (defect 36).

### ⚠️ Standing consequence of the `.env` decision

`.env` files are committed by design (private repo, S01b decision 1). Three
values are therefore permanently in git history: the **Supabase service-role
key** (bypasses all RLS), the **Anthropic API key** (direct cost), and the
**SMTP app password**. If this repo ever goes public or changes hands they must
be **rotated** — deleting the files does not remove them from history. This is
independent of, and additional to, the incident rotation above.

### System state

| Subsystem | State |
|---|---|
| Auth | ✅ **Real.** Supabase ES256 verified via JWKS (`app/core/jwks.py`), `aud=authenticated`, HS256 still accepted for legacy tokens |
| Supabase | ✅ 7 tables, RLS on all, `avatars` bucket. `public.users` is TRANSITIONAL — ADR 0003 deletes it |
| Frontend | ✅ Expo **SDK 57**, RN 0.86.3, React 19.2.3. `tsc --noEmit` clean. ESLint runs (3 React Compiler rules at `warn` until S08) |
| Docker | ✅ `docker compose up` → `api` + `redis`; one command via `scripts/run.ps1` |
| AI vision | ⚠️ **Runs, but measurably limited** — see the two new blockers below |
| SOS | ⚠️ Email delivery works; **nothing is persisted** (defect 35) |
| `app/contracts/` | ❌ Not authored — S03 |
| `RISK_SURFACE_IMPL` | ❌ n/a — first implementation lands S04 |
| Agents live | **0 of 8** |
| LLM client | ❌ `anthropic` not installed — S04. Env vars declared, unused. |
| Migrations | ⚠️ Hand-run SQL in the Supabase editor. No runner, no `schema_migrations` — S02 (ADR 0004) |
| `tests/invariants/` | ❌ Does not exist — S03 |
| Known defects | **17 open of 41.** 24 closed across S01/S01b/S01c/S01d. **Defects 29–41 are new since the last handoff** — see [plan §1](IMPLEMENTATION_PLAN.md) |
| Feature flags off | `POLICE_ROUTING_ENABLED=false` — and it is now actually *checked* (defect 31) |

### 🔴 Two new blockers Nakib should know about before S06

Both were found by building a measurement harness rather than by reading code,
and both mean the AI pipeline is weaker than it looks:

1. **Pose analysis has never run.** `mediapipe==1.1.0` removed the
   `mp.solutions` namespace that `pose_service.py` is built on, so the import
   fails and `pose_service` is left `None`. Every response carries
   `pose_analysis: null`. **This supersedes the S01b entry's claim that defect 5
   was reproduced live** — defect 5 was never the binding constraint, because
   pose never ran at all. Logged as **defect 29**.
2. **Three of the six crime classes are structurally unreachable.** The decision
   engine scores against 21 object signals; YOLOv9c emits COCO's 80 classes, and
   11 of those signals are not among them (`gun`, `blood`, `broken window`,
   `damaged property`, `graffiti`, `crowbar`, `spray paint`, `money`, `door`,
   `window`, `building`). With pose dead, no input can produce `harassment`,
   `theft` or `vandalism`. Logged as **defect 30**.

```bash
docker compose exec api python scripts/eval_crime_vision.py   # prints the reachability table
```

**Do not tune the pipeline before the eval set has images in it.** The harness
and a committed baseline exist; the set itself has 2 seed negatives. "Detection
is poor" was an accurate impression but an unmeasurable one, and the chosen
order was *measure first, then decide* — so the reasoning-layer decision
(local-only / local + Claude vision / Claude-only) is **open and deliberately
deferred** until Arafat and Nakib have discussed it.

### 🧵 Background activities (off-baton, §3.6)

| Activity | Owner | Started | Status |
|---|---|---|---|
| Credential rotation (incident) | Arafat | 2026-10-07 | ⏳ in progress, from a separate device |
| Crime-vision eval set | Arafat | 2026-10-07 | 2 of ~60 target images; **S06 is blocked on this** |

### ▶️ RESUME HERE

**Arafat, before passing the baton — two things, in this order:**

1. **Commit and push the working tree (60+ paths).** All of S01's work lives
   only here. `smoke.sh` deliberately fails two assertions until it lands, and
   both are correct to fail:
   - *"supabase.ts is tracked by git"* — the original defect 1 was that this
     file had never been committed.
   - *"package-lock.json committed (tracked, not merely present)"* — defect 19.

   **`git add -A` now actually picks the lockfile up.** It could not before:
   `.gitignore` listed `package-lock.json` and `yarn.lock` outright, so the file
   `npm install` generated was unaddable. That is the real reason defect 19
   survived a whole sprint of being called a "manual step". Rules removed
   (defect 19). Check it worked:

   ```bash
   git check-ignore -v frontend/package-lock.json   # must print nothing
   ```
2. **Tell Nakib about the incident** before he runs anything (banner item 2).

**Nakib, when you take the baton:**

```bash
git checkout develop && git pull      # do this BEFORE npm install — see the banner
./scripts/run.ps1 && ./scripts/test.sh
git checkout -b sprint/S02-db-foundation
```

Then start **S02** in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Its first
task is **ADR 0001**, the Supabase-vs-FastAPI data-plane rule.

Two notes on S02's scope that changed underneath you:

- **ADR 0002 (auth) is already implemented.** `app/core/jwks.py` landed early
  because SOS was returning 401 and nothing else would work until it did. The
  *document* is still owed. Write it to describe what is in place, not what you
  would have chosen from scratch.
- **ADR 0003 (collapse the three user tables) is worth more than it looks.**
  `endpoints/sos.py` auto-provisions into `public.users` on every SOS, and that
  is where the single row now sitting in that table came from. It exists because
  a code path ran, not because anyone designed it.

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

## S01d — SDK 57, real auth, and the first live walkthrough

**Owner:** Arafat · **Dates:** 2026-10-07 · **Branch:** working tree · **Merge:** _pending_

### Shipped

**The app runs.** Register → profile picture → crime report with AI analysis →
emergency contact → **SOS email with video attachment, delivered.** That last
step was confirmed by the owner against a real inbox, and it is what closes S01.

Getting there took an SDK upgrade, a rewrite of token verification, and five
defects that only surface when a human actually uses the screens.

- **Expo SDK 54 → 57.** Not optional: Expo Go ships only the newest SDK, so the
  project could not be opened on a phone at all — *"Project is incompatible with
  this version of Expo Go."* 35 packages, React Native 0.86.3, React 19.2.3,
  every version taken from `bundledNativeModules.json`.
- **Authentication actually verifies tokens now.** `app/core/jwks.py` fetches the
  Supabase project's JWKS, caches keys by `kid`, and verifies ES256. Before this,
  every authenticated request returned 401.
- **A measurement harness for the AI pipeline**, built instead of tuning it —
  `scripts/eval_crime_vision.py` plus a labelled set and a committed baseline.
  It immediately found two structural defects that reading the code had missed.

### Files

- **Added:**
  - `backend/app/core/jwks.py`
  - `backend/scripts/eval_crime_vision.py`
  - `backend/data/eval/crime_vision/{README.md,manifest.csv,baseline.json,images/}`
  - `frontend/src/hooks/useVoiceRecorder.ts`
- **Changed:**
  - `backend/app/core/security.py` — `decode_token` is now `async`, delegates to
    `verify_supabase_token`, and no longer prints tokens or secrets to logs
  - `backend/app/core/config.py` — nine previously-undeclared env vars
  - `backend/app/services/sos_service.py` — `POLICE_ROUTING_ENABLED` gate +
    placeholder-data warning
  - `frontend/package.json` — SDK 57; React family exact-pinned; `expo-av` out,
    `expo-audio` in; `@react-navigation/drawer` removed
  - `frontend/src/services/speech.service.ts` — transcription only
  - `frontend/src/screens/Home/HomeScreen.tsx` — voice-monitoring block deleted
  - `frontend/src/screens/Profile/EditProfileScreen.tsx` — uses `uploadAvatar()`
  - `frontend/src/screens/Profile/EmergencyContactsScreen.tsx` — `expo-contacts/legacy`
  - `frontend/src/screens/Map/MapScreen.tsx` — permission rejection handled
  - `frontend/.eslintrc.js` — `extends: 'expo'`
  - `frontend/jest.config.js` — `jest-expo` preset, spread not replaced
  - `docker-compose.yml` — `./backend/data:/app/data`
  - `backend/.env` / `.env.example` — SMTP values

### Decisions

1. **Pulled ADR 0002 forward from S02 rather than working around the 401.** The
   previous entry predicted this exact failure and said to pull the ADR forward
   instead of hacking it, so that is what happened. **Supabase signs access
   tokens with ES256 by default** — there is no shared secret to verify against,
   and the project had no legacy HS256 secret to fall back on. `jwks.py` fetches
   `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, caches by `kid` with a 10-min
   TTL and a 30-s refetch floor so a rotated key cannot be used to hammer the
   endpoint, verifies `aud=authenticated` with 10 s of leeway, and **still
   accepts HS256** so a project with a legacy secret keeps working. Verified
   live: `kid=6167b251…`, `alg=ES256`, `kty=EC`, `crv=P-256`.
   **The ADR document itself is still owed — S02.**
2. **Upgraded to SDK 57 rather than installing an older Expo Go.** Pinning the
   tooling to a dead SDK to avoid an upgrade is a debt that compounds every
   month, and this is a production target, not a hackathon build. Done against
   `bundledNativeModules.json`, which is the authoritative manifest — guessing
   versions is how the four-way React mismatch in defect 25 happened.
3. **`expo-av` deletion closed defect 4 for free.** SDK 57 removed `expo-av`, and
   it was imported in exactly two places: `speech.service.ts` and the
   `HomeScreen` voice block that S07 was already scheduled to delete for
   recording continuously and detecting nothing. Deleting it was cheaper than
   porting it. Recording now lives in `useVoiceRecorder`, which owns the 30-s cap
   and unmount cleanup; `speech.service.ts` is transcription only, and the dead
   `recordAndTranscribe()` went with it. **Real hot-word detection is still S18.**
4. **Downgraded three React Compiler lint rules to `warn`, with an expiry note.**
   `eslint-plugin-react-hooks` v6 enables `refs`, `immutability` and
   `set-state-in-effect`; the existing screens violate all three structurally,
   and S08 is the sprint that decomposes them. Each is annotated *"delete when
   S08 lands"*. A rule silenced without a named sprint is a rule silenced
   forever.
5. **Built the eval harness before touching the pipeline.** The owner's
   instruction was "detection is poor, make it better", and the honest answer was
   that nothing in the repo could tell an improvement from a regression. Offered
   the choice explicitly and the owner chose *build an eval set first*. The
   harness reports per-class precision/recall/F1, a confusion matrix, and — the
   part that matters — a **stage-attributed failure breakdown**, because "47%
   recall" is not actionable and "31 of 44 misses never got past YOLO" is.
6. **The capability report is derived from the live model, not hardcoded.** It
   asks the loaded YOLO for its class list and the service for whether
   `pose_service` and `scene_service` are actually non-`None`, then computes
   which crime verdicts are reachable. Hardcoding the answer would have gone
   stale the moment someone swapped the model — and it is what surfaced defects
   29 and 30.
7. **`expo-contacts/legacy` is the correct import, not a workaround.** Checked
   before writing it: SDK 57's new class-based API exports `Contact`, `Container`,
   `Group` and permissions, and **no picker at all**. `ContactAccessButton` is
   iOS 18+ and a different interaction model. The legacy entry point exports
   exactly `presentContactPickerAsync`, `getContactByIdAsync` and
   `requestPermissionsAsync`. Revisit when Expo ships a cross-platform picker.
8. **Declared `POLICE_ROUTING_ENABLED` and made it default off.** It had been
   documented in `.env.example` and `docs/` since S01b, **declared nowhere and
   checked nowhere**, so police routing was unconditionally on — and all 606 rows
   of `police_stations.csv` carry the same placeholder address. Every SOS test
   was emailing an uninvolved third party. `_load_police_stations` now warns
   loudly when hundreds of stations share one address.

### CONTRACT CHANGE

None. `app/contracts/` does not exist until S03.

**One signature did change:** `security.decode_token` is now `async`. Its only
caller, `get_current_user`, was updated in the same change. Anything new that
decodes a token must `await` it.

### Migrations

None.

### Env vars added

No new names — but **nine existing ones were being silently discarded** and now
work (defect 32). `Settings` is configured with `extra = "ignore"`, so a var
present in `.env` but undeclared on the model is dropped without a warning.
`SUPABASE_URL` was the one that bit, as `AttributeError: 'Settings' object has
no attribute 'SUPABASE_URL'` at the first JWKS fetch. Audited the rest rather
than fixing only the one that failed.

Declared: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `POLICE_ROUTING_ENABLED`,
`ANTHROPIC_API_KEY`, `LLM_MODEL_JUDGMENT`, `LLM_MODEL_BULK`, and the SMTP group.
All are now in [plan §9](IMPLEMENTATION_PLAN.md) under *live now*.

### Measurements

First baseline committed to `backend/data/eval/crime_vision/baseline.json`.
**The accuracy number in it is meaningless and the README says so** — n=2.

What is meaningful is the capability report:

```
YOLO classes available : 80
object signals wanted  : 21   reachable: 10   IMPOSSIBLE: 11
pose analysis running  : False
scene analysis running : True

can each crime type EVER be returned?
  assault    yes    - pose dead -> requires a visible baseball bat/knife
  burglary   yes    - entry signs unreachable -> only detectable at night
  harassment NEVER  - needs pose interaction, pose analysis is not running
  robbery    yes    - pose dead -> requires a visible knife
  theft      NEVER  - needs a pose action, pose analysis is not running
  vandalism  NEVER  - needs damage evidence - none emittable
```

Three of six crime classes cannot be produced by any input. That is the real
answer to "detection is poor", and it is not a tuning problem.

### Deliberately NOT done

- **Nothing committed.** Working tree only, same as S01 and S01b. 60 paths.
- **Did not change the AI pipeline's reasoning.** Deliberate: the owner is
  discussing the local / hybrid / Claude-only question with Nakib, and the eval
  set has 2 images. Changing behaviour now would be unmeasurable, and it would
  burn the decision before it is made. **S06 owns it.**
- **Did not populate the eval set.** It needs real Bangladesh scenes and
  judgement about what counts as a hard negative. The README says what to
  collect and in what proportions; the images are the owner's to take.
- **Did not write `docs/adr/0002-auth.md`** even though the code it describes
  landed. S02 owns the ADRs as a set, and writing one in isolation would
  pre-empt ADR 0001's data-plane rule, which 0002 has to be consistent with.
- **Did not fix defect 29 or 30.** Found and documented in the same session they
  were discovered, and handed to S06 where the pose work already lived. Porting
  `pose_service` to `PoseLandmarker` is a real piece of work, not a line change.
- **Did not persist `SOSIncident`** (defect 35). Found while verifying the email
  test; it needs a status model and a Storage upload, which is S05's scope.
- **Did not add a `demo_S01d` to `smoke.sh`.** The things worth asserting here —
  SDK 57 resolving, JWKS reachable, an ES256 token verifying — all need network
  and a live Supabase project, and `smoke.sh` is the offline structural check.
  `scripts/test.sh` is where live assertions belong, and Phase 4 already covers
  auth rejection. **Flagging it rather than half-doing it.**

### Late addendum — two findings from writing this entry up

Both found while verifying the claims in this file rather than by writing code,
which is an argument for writing the handoff before believing the sprint is done.

1. **`.gitignore` made defect 19 impossible to fix** (defect 19, amended). It
   listed `package-lock.json` and `yarn.lock` outright. Three handoffs in a row
   recorded "commit the lockfile" as a pending manual step, and it could not
   have been done — `git add` silently skipped it. Correct for a published
   library, wrong for an application, and **the same mistake as defect 1's bare
   `lib/`**: a pattern copied from a generic template that matches more than it
   meant to. If a third instance of this shows up, the `.gitignore` deserves a
   line-by-line audit rather than another spot fix.
2. **`smoke.sh` was giving a false green on that very defect** (defect 41). The
   assertion was named *"package-lock.json committed"* and its command was
   `test -f frontend/package-lock.json` — which passes for an untracked,
   gitignored file. Now `git ls-files --error-unmatch`. **An assertion whose
   name claims more than its command checks is worse than no assertion,
   because it gets trusted.** Worth a scan of the other 60-odd assertions in
   that file at some point; I only fixed the one that was actively lying.

`smoke.sh` now reports **2** expected failures instead of 1, and both clear the
moment the tree is committed.

### Known broken / rough edges

- **The AI pipeline is honest but weak.** It correctly returns "no crime" on
  ordinary photos. It cannot return three of its six classes at all.
- **`pose_analysis` is `null` on every response** and will stay that way until
  S06. Do not read it as "no interaction detected" — nothing ran.
- **Eval set is 2 images.** Any accuracy figure from it is noise.
- Host has **Node 24** against SDK 57's Node 20/22 target; `run.ps1` warns.
- Three ESLint rules are `warn` and will become errors in S08.

### Gotchas for the next agent

- **`extra = "ignore"` on `Settings` will eat your new env var silently.** If a
  value in `.env` seems to have no effect, check it is declared in
  `config.py` *first*. This cost a debugging session.
- **Supabase tokens are ES256, not HS256.** `JWT_SECRET_KEY` is now a legacy
  fallback only. Do not "simplify" `jwks.py` back to a shared secret.
- **`decode_token` is `async` now.** Await it.
- **`AudioRecorder` from `expo-audio` is a type-only export.** `new AudioRecorder()`
  fails at runtime — the constructor lives on an internal native module. Use the
  `useAudioRecorder` hook, which is what `useVoiceRecorder` wraps.
- **Never replace a Jest preset's `transformIgnorePatterns` or `setupFiles` —
  spread them.** Replacing `jest-expo`'s broke `expo-modules-core` with an error
  that points nowhere near the config.
- **`image/jpg` is not a MIME type.** It is `image/jpeg`. Supabase Storage
  rejects the former, and `` `image/${fileExt}` `` produces it for any `.jpg`
  file. Use `uploadAvatar()` in `lib/supabase-storage.ts`, which maps extensions
  properly.
- **`mediapipe` 1.x has no `mp.solutions`.** If you see `pose_analysis: null`,
  the import failed and `pose_service` is `None` — it is not a detection miss.
  Check the startup logs before debugging the fusion engine.
- **`backend/data/` must stay mounted in compose.** Without it the eval harness
  cannot see its own manifest, and the baseline it writes vanishes on recreate.
- **Expo Go only supports the newest SDK.** When Expo ships 58, this project
  stops opening on a phone until it is upgraded. That is the cost of Expo Go;
  a development build is the escape hatch, and it is S37's problem.

### RESUME HERE

See the `CURRENT STATE` block at the top of this file.

### Prototype Gate

- [x] 1 · `check.sh` green
- [x] 2 · Schema applied and verified against live Supabase
- [x] 3 · **App builds and launches on a real device** — closed at last, see the
      walkthrough table in `CURRENT STATE`
- [x] 4 · `smoke.sh` passes except the one assertion that needs the commit
- [x] 5 · `PROGRESS.md` entry + `CURRENT STATE` overwritten
- [x] 6 · Env vars in `.env.example` and plan §9 (new *live now* block)
- [x] 7 · Nothing half-migrated

**Gate 4 has a known exception:** *"supabase.ts is tracked by git"* fails until
the working tree is committed, which is manual step 1 in `RESUME HERE`. It is
correct to fail — the original defect was that the file had never been committed.

---

## S01c — Malware in `babel.config.js`

**Owner:** Arafat · **Dates:** 2026-10-07 · **Branch:** working tree · **Merge:** _pending_

### Shipped

**This sprint was not planned and should not have been needed.** Running ESLint
for the first time (defect 28) surfaced ~26 KB of obfuscated code sitting after
the closing brace of `frontend/babel.config.js`, hidden behind roughly 400
spaces of indentation. **It was present in the initial commit `db6c42f`** and
executed on every Metro bundle and every Jest run — including the ones run
during S01 and S01b.

- Payload removed; `babel.config.js` is back to its five legitimate lines.
- Mechanism, IoCs and blast radius written up in
  [docs/SECURITY-INCIDENT-2026-10-07.md](docs/SECURITY-INCIDENT-2026-10-07.md).
- `scripts/scan-injection.sh` — detects config trailers, absurd line lengths,
  `eval`, hidden `spawn`, and wallet-address literals. **Validated against the
  preserved sample.**
- Wired into CI (`supply-chain`), `.pre-commit-config.yaml`, and `demo_S01c`.
- `node_modules` deleted and reinstalled from the lockfile; 1,175 packages
  verified against registry signatures.
- Owner-side host triage completed: offline Defender scan, scheduled tasks,
  `Run`/`RunOnce`, startup folder, post-reboot process sweep — **all clean**.

### Files

- **Added:** `scripts/scan-injection.sh`,
  `docs/SECURITY-INCIDENT-2026-10-07.md`,
  `docs/INCIDENT-RESPONSE-CHECKLIST.md`
- **Changed:** `frontend/babel.config.js` (payload stripped),
  `.github/workflows/ci.yml` (`supply-chain` job),
  `.pre-commit-config.yaml`, `scripts/smoke.sh` (`demo_S01c`)

### Decisions

1. **Cleaned the file rather than reverting it.** The legitimate five lines are
   needed and the infected commit is the initial one — there is no clean version
   to revert to.
2. **Kept a copy of the payload out-of-tree** before deleting it. Deleting the
   only sample would have made the scanner unverifiable, and an unverified
   scanner is worse than none because it is trusted.
3. **The scanner was tested against the real sample, not a synthetic one.**
   It initially false-positived on the incident write-up itself, which quotes the
   IoCs; pathspec exclusions fixed that. A scanner that cries wolf on its own
   documentation gets disabled within a week.
4. **Guards in three places, deliberately.** CI catches it on a PR, pre-commit
   catches it before the push, `smoke.sh` catches it during a handoff check. The
   payload survived four commits and two of our own sprints precisely because
   nothing looked.
5. **The banner lives at the top of this file**, above `CURRENT STATE`, because
   the dangerous action — Nakib running `npm install` on an unpulled clone — can
   be taken before reading anything else.

### CONTRACT CHANGE

None.

### Migrations

None.

### Env vars added

None.

### Measurements

- Payload: ~26 KB, after ~400 spaces, one line.
- Dormant in-repo across **all 4 commits** of this repository's history, from
  `db6c42f` (initial) through `d78416b` (current `HEAD`).
- Executions during our own work: every `expo start`, every `npx jest`.
- Reinstall: 1,175 packages, all signature-verified, no other findings.

### Deliberately NOT done

- **Git history not rewritten.** `db6c42f` still carries the payload. Rewriting
  needs both of us present and coordinated re-clones; it is recorded as a hard
  precondition on ever making this repo public.
- **No credential rotation performed by me.** It must be done from an uncompromised
  device and it touches accounts I have no business touching. It is the owner's,
  tracked in `CURRENT STATE`.
- **No attempt to attribute or to contact the wallet's chain.** Out of scope and
  not useful to this project.

### Known broken / rough edges

- Credential rotation is **in progress, not done.** Until it is, treat every
  secret this host has seen as known to a third party.
- Nakib's clone is still infected until he pulls.

### Gotchas for the next agent

- **Run ESLint. It is how this was found.** A linter that has never run is not a
  passing linter.
- **`scan-injection.sh` excludes the incident docs by pathspec**, because they
  quote the IoCs. If you add more security documentation, add it to the exclusion
  list or the scanner will flag your write-up.
- **Capture evidence before killing a suspect process.** During triage the
  process was killed before its parent PID was recorded, which destroyed the
  attribution link that was then needed. Order matters: dump first, kill second.
- **A trailing payload survives code review because diffs fold long lines.**
  The long-line check in the scanner exists for that reason specifically.

### RESUME HERE

See the `CURRENT STATE` block at the top of this file — the banner's three
outstanding items come before any sprint work.

### Prototype Gate

- [x] 1 · `check.sh` green
- [x] 2 · n/a — no schema change
- [x] 3 · App launches (closed in S01d)
- [x] 4 · `demo_S01c` added and passing; scanner reports the repo clean
- [x] 5 · `PROGRESS.md` entry + banner
- [x] 6 · No new env vars
- [x] 7 · Nothing half-migrated

---

## S01b — Dockerised stack & one-command run

**Owner:** Arafat · **Dates:** 2026-10-07 · **Branch:** working tree · **Merge:** _pending_

Unplanned addendum to S01, requested once the Supabase schema was live: one
command to start both halves instead of managing the Python/ML toolchain and
Metro separately.

### Shipped

```
.\scripts\run.ps1     # → preflight, LAN IP, containers, health wait, npm, Expo
./scripts/test.sh     # → 5-phase live verification of the running stack
```

- **Root `docker-compose.yml`** — `api` + `redis`, with `osrm` and `mobile` as
  opt-in profiles.
- **`backend/Dockerfile` rewritten.** The previous one could not have worked: it
  omitted `libgl1`/`libglib2.0-0`, so `import cv2` and `import mediapipe` fail
  at startup; it pulled the CUDA torch wheel (~2.5 GB of unusable GPU runtime);
  and its healthcheck imported `requests`, which is not a dependency, so the
  container was permanently `unhealthy`.
- **`scripts/test.sh`** — 5 phases: backend up, Supabase schema (per-table,
  distinguishing "missing" from "RLS is working"), backend↔database via
  `/routes/calculate`, auth rejection, AI stack.
- **`docs/RUNNING.md`** — run + test guide with a failure-symptom table.

### Files

- **Added:** `docker-compose.yml`, `backend/.dockerignore`,
  `frontend/.dockerignore`, `frontend/Dockerfile.dev`, `scripts/run.ps1`,
  `scripts/run.sh`, `scripts/test.sh`, `docs/RUNNING.md`
- **Changed:** `backend/Dockerfile` (rewritten), `backend/app/core/config.py`,
  `frontend/src/constants/app.constants.ts`, `.gitignore`, `scripts/smoke.sh`
  (added `demo_S01b`; rewrote the `.env` assertions)
- **Deleted:** `backend/docker-compose.yml`

### Decisions

1. **`.env` files are committed now.** Owner's call: private repo, and manual
   env sync across two machines was costing more than it saved. Every piece of
   tooling that asserted the opposite was updated in the same change —
   `.gitignore`, `smoke.sh`, and both `.dockerignore` files. **Tooling that
   contradicts a decision is broken tooling, not a safety net.** What this means
   in practice: the Supabase service-role key, the Anthropic key and the SMTP
   app password are now in git history permanently, so if the repo ever changes
   hands or goes public, all three must be rotated, not deleted.
   `.dockerignore` still excludes `.env` — a committed secret should not also
   be baked into an image layer.
2. **No Postgres container.** The database is Supabase. A local Postgres would
   be a second, divergent source of truth, and `SCHEMA.sql` targets Supabase's
   `auth.users` and `storage` schemas that a bare `postgres` image lacks.
3. **No Celery worker or beat.** `celery_app.py` schedules two tasks whose
   modules do not exist and there are no `@task` definitions, so beat crashes on
   boot. Leaving it out of compose is more honest than shipping a container that
   restart-loops. S04.
4. **Expo runs on the host, not in a container** — despite "dockerize the app"
   being the request. Three concrete costs to containerising it: inotify does
   not propagate reliably across Docker Desktop bind mounts so hot reload
   degrades *silently*; the phone must reach Metro directly, so the container
   must advertise the host's IP; and native builds need the host SDKs anyway.
   The `mobile` profile exists for anyone who wants it, with the caveats written
   on the service. **The ask was one command, not one container** — `run.ps1`
   delivers that without the regression.
5. **CPU-only torch, from PyTorch's CPU index, installed before
   `requirements.txt`.** Saves ~2 GB; the later install sees torch satisfied and
   skips it. Measured: 48s instead of several minutes.
6. **`SECRET_KEY` and `POSTGRES_*` were given defaults.** All four were
   *required* by pydantic and *read by nothing* — `database.py` uses
   `DATABASE_URL` directly. A minimal `.env` therefore crashed at import with a
   ValidationError naming four fields that do not matter. Making them optional
   beat asking for four dead values in every `.env`.
7. **`API_BASE_URL` now reads `EXPO_PUBLIC_API_BASE_URL`** — pulled forward from
   S07 because it blocks this work. It was hardcoded to `192.168.0.103`, correct
   on one machine; on any other the app reached Supabase fine and the backend
   not at all, which looks like a backend bug and is not one. `run.ps1` detects
   the LAN IP and exports it.
8. **`--clear` on every Expo start.** `EXPO_PUBLIC_*` is inlined at bundle time,
   so a warm Metro cache serves stale config. Cheap to always do, confusing to
   debug when forgotten.

### CONTRACT CHANGE

None.

### Migrations

None.

### Env vars added

None new. `REDIS_URL`, `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are now
**overridden in compose** to point at the `redis` service rather than
`localhost`, which is what they resolve to inside the container network.

### Measurements

Image build, cold (no cache):

| Layer | Time |
|---|---|
| apt system packages | 71.7 s |
| torch + torchvision (CPU index) | 48.5 s |
| `requirements.txt` + Pillow/pandas | see the final entry below |

Rebuild after a code-only change: **instant** — `backend/app` is bind-mounted,
so nothing is copied and uvicorn reloads in place.

### Deliberately NOT done

- **Nothing committed.** Working tree only, as with S01.
- **No local OSRM data.** The `osrm` profile is wired but the ~1 GB extract and
  its 10–30 minutes of preprocessing are opt-in; `docs/RUNNING.md` §6 has the
  commands. `route_service` also still hardcodes the demo URL and ignores
  `OSRM_BASE_URL` — that is S05, not here.
- **No non-root container user, no multi-stage slimming, no pinned digests.**
  This is a dev image. Hardening is S31/S37.
- **Did not remove the phantom Celery beat entries.** S04 owns that; leaving
  Celery out of compose neutralises them for now.
- **Did not split `requirements.txt`** into `requirements/{base,ai,agents,dev}.txt`.
  That is still S04. Only the five lines below were corrected, because two of
  them were hard blockers.

### 🔴 `requirements.txt` had drifted from the code — defects 20–22

Running the image is what exposed this. **The backend has never started from a
clean dependency install**; existing `venv`s had acquired the missing packages
some other way.

| Fix | Why |
|---|---|
| `sqlalchemy` → `sqlalchemy[asyncio]` | **Blocker.** SQLAlchemy's asyncio support needs `greenlet`, which the bare package does not pull in. `app.main` could not be imported: *"The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed."* |
| `# email-validator` → `email-validator` | **Blocker.** `schemas/auth.py` and `schemas/user.py` use pydantic `EmailStr`, which raises `ImportError` at import without it. |
| `ultralytics==8.1.34` → `>=8.3.0` | **Blocker.** 8.1.x cannot load the YOLOv9c checkpoint under torch ≥2.6, which changed `torch.load` to default `weights_only=True`: *"Weights only load failed."* The vision stack never loaded. Resolved to 8.4.174, verified loading 80 classes. |
| `shapely==2.0.2` → `shapely>=2.1` | 2.0.x was built against numpy 1.x; `numpy` is unpinned and resolves to 2.4.x, so importing shapely emits `AttributeError: _ARRAY_API not found` and its numpy interop is broken. Non-fatal only because nothing calls shapely directly — `geoalchemy2` imports it. |
| `# pillow` → `Pillow` | Imported as `PIL` by all three services in `app/services/ai/`. |
| `# pandas` → `pandas` | `scripts/train_crime_model.py`. |

Also **defect 24**: `YOLO('yolov9c.pt')` resolves a bare filename against the
working directory, which in the container is an image layer, not a mounted
volume — so the 82 MB download repeated on every `--force-recreate` and stalled
the first AI request by ~3 minutes each time. The Dockerfile now fetches it at
build time (cached layer, offline-capable, +0.37 GB).

### ✅ Verified live against the owner's Supabase

`scripts/test.sh --ai` → **14 passed, 0 failed, 1 skipped**

| Phase | Result |
|---|---|
| 1 Backend up | `/health`, `/`, OpenAPI schema builds, **21 v1 routes** |
| 2 Supabase schema | all four app tables present |
| 3 Backend ↔ database | `POST /routes/calculate` → 1 route, `safety_score` 70.0 |
| 4 Auth wiring | no token → 401; bogus token → 401 |
| 5 AI vision | YOLOv9c loaded; full pipeline ran on a real photo |

Two results worth keeping:

- **`init_db()` found all 7 tables already present and created nothing.** The
  ORM and `SCHEMA.sql` agree exactly — including the `crime_category` enum,
  which it looked up by the name the model now specifies.
- **The fusion engine returned the right answer on a real photo.** Given
  Ultralytics' bus-and-pedestrians test image, CLIP classified
  `scene_type="public transport"` (0.944), `lighting="bright daylight"` (0.963),
  `crowd="few people"`, and the decision engine returned `validation_failed` —
  i.e. *not a crime*. The frontend maps that to "No Crime Detected ✅".

**Defect 5 reproduced live.** `pose_analysis` came back `null` on that photo:
`detect_poses` runs MediaPipe on the whole frame rather than on YOLO's person
crops, so distant or partial figures yield no pose at all. Exactly the gap S06
closes.

The skipped check is the `avatars` bucket, which needs the service-role key to
inspect over HTTP — worth adding to `test.sh` when there is a reason to read
`backend/.env` from it.

**Method worth reusing:** rather than rebuild once per `ImportError` (≈4 min
each), install candidates ad-hoc in a throwaway container —
`docker compose run --rm --no-deps api bash -c "pip install -q X && python -c 'import app.main'"`
— and iterate until the import succeeds. Two rebuilds instead of five.

Fixed in `requirements.txt` rather than in the Dockerfile, so a native `pip
install -r requirements.txt` into a fresh venv now works too.

### Known broken / rough edges

- Host has **Node 24**; Expo SDK 54 targets Node 20/22. `run.ps1` warns. If
  Metro misbehaves, install Node 22 LTS before suspecting the code.
- Host has **Python 3.14**; the project targets 3.11. Irrelevant for Docker
  (the image is 3.11), relevant if anyone runs the backend natively.
- Still no `package-lock.json`. `run.ps1` runs `npm install` and tells you to
  commit the lockfile it generates.
- `smoke.sh` still reports one failure until the commit lands (by design).

### Gotchas for the next agent

- **`docker compose up` must run from the repo root**, not from `backend/`. The
  root compose file is authoritative; `backend/docker-compose.yml` was deleted
  because it provisioned a competing Postgres and a crash-looping Celery.
- **`python:3.11-slim` is Debian trixie now**, not bookworm. `libgl1` is the
  correct package name there; the older `libgl1-mesa-glx` does not exist.
- **The first AI request downloads ~700 MB** (YOLOv9c 82 MB + CLIP ~600 MB) and
  can take several minutes. It lands in the `model_cache` volume. If you ever
  `docker compose down -v`, you pay it again.
- **Cold start is 15–40 s** just importing torch/mediapipe/cv2/transformers.
  The healthcheck `start-period` is 90 s for that reason — shortening it kills
  the container mid-import.
- **`environment:` beats `env_file:` in compose.** That is how `REDIS_URL` is
  redirected to the `redis` service without editing `backend/.env`.
- **`scripts/test.sh` Phase 2 printing "RLS blocks anonymous reads" is a
  pass**, not a warning. It means the table exists *and* is protected.
- **Phase 3 (`/routes/calculate`) is the highest-value single check** in the
  repo. It only passes if `DATABASE_URL`, the asyncpg driver and the uuid
  column types are all simultaneously correct, and it recognises each of those
  three failures by name.

### RESUME HERE

See `CURRENT STATE` at the top of this file.

### Prototype Gate

- [x] 1 · `check.sh` green (skips for uninstalled local tools)
- [x] 2 · Schema applied and verified — **owner ran it against live Supabase**
- [ ] 3 · App builds and launches — pending `npm install` + a device
- [x] 4 · `smoke.sh`: `demo_S01b` added, 18/18 pass
- [x] 5 · `PROGRESS.md` entry + `CURRENT STATE`
- [x] 6 · No new env vars
- [x] 7 · Nothing half-migrated

---

## S01 — Unblock the repository

**Owner:** Arafat · **Dates:** 2026-10-07 · **Branch:** working tree · **Merge:** _pending_

### Shipped

The repository can be built from a clean clone, and there is a fresh Supabase
schema that the current implementation actually runs on.

- **Both blockers gone.** `frontend/src/lib/{supabase,supabase-storage}.ts` are
  authored, and the `.gitignore` rule that silently excluded them is anchored.
- **A fresh-start Supabase schema** — 7 tables, RLS on every one, the `avatars`
  bucket with per-user folder policies, and a verification script.
- **Secrets are out of git.** `EXPO_PUBLIC_*` from `.env`, and `.env` itself is
  now ignored — it was not.
- **The relay machinery is real**, not placeholder: `check.sh` runs what is
  installed and skips what is not, `smoke.sh` holds 31 assertions, CI runs all
  five jobs including the two that enforce the protocol.

### Files

- **Added:**
  - `backend/migrations/supabase/{SCHEMA,VERIFY,RESET}.sql`, `README.md`
  - `frontend/src/lib/supabase.ts`, `frontend/src/lib/supabase-storage.ts`
  - `frontend/.env.example`
  - `backend/app/models/columns.py`
  - `backend/pyproject.toml`
  - `scripts/check.sh`, `scripts/seed.sh`, `scripts/smoke.sh`
  - `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `.gitattributes`
  - `CONTRIBUTING.md`
- **Changed:**
  - `.gitignore` — anchored `lib/`; added real `.env` coverage
  - `frontend/app.json` — removed the hardcoded Supabase URL + anon key
  - `frontend/package.json` — added `react-native-url-polyfill`
  - `backend/.env.example` — added Supabase, SMTP, Anthropic; corrected
    `SOS_VIDEO_MAX_SIZE_MB` 100 → 25 to match `config.py`
  - `backend/app/models/{user,crime,emergency_contact,sos,location}.py` — ids to
    `uuid`; `crime_category` enum named explicitly
- **Moved:** the four old `backend/migrations/*.sql` → `_superseded/` with a
  README saying not to run them

### Decisions

1. **The ORM's id columns became `uuid`.** This was not in S01's scope, but the
   schema cannot work without it. The models declared `Column(String)` while a
   schema with real `ON DELETE CASCADE` FKs to `auth.users` needs `uuid`, and
   the two do not meet: a lookup renders as `uuid = varchar` (no such operator)
   and an insert fails asyncpg's type check. Both failures land on the SOS path,
   which is the only feature using the backend database. `UUID(as_uuid=False)`
   keeps every attribute a `str` in Python, so no calling code changed.
   Reasoning is in `app/models/columns.py`.
2. **`public.users` was created even though ADR 0003 deletes it in S02.**
   `endpoints/sos.py` auto-provisions into it; without the table, SOS breaks
   today. It is commented as TRANSITIONAL in the schema. Do not build on it.
3. **Secrets moved to `EXPO_PUBLIC_*` rather than `app.config.ts`.** Expo
   inlines those at build time, so it needs no config-file rewrite and no
   `expo-constants` read. Cost: changing one requires `expo start --clear`,
   which is noted in three places because it will be forgotten.
4. **`crime_reports.latitude/longitude` stay `varchar`, and
   `incident_date_time` stays `timestamp` without a zone.** Both are wrong, and
   both match what the client sends. Fixing the column without the client in the
   same commit shifts every timestamp by six hours. Scheduled for S05/S07.
5. **`check.sh` distinguishes "tool missing" from "code broken."** A check that
   fails because ruff is not installed trains you to ignore it. Missing tools
   skip by default and fail only under `--strict`.
6. **Old migrations archived rather than deleted.** `create_users_table.sql`
   defines a `public.users` incompatible with both the ORM and the new schema;
   leaving it beside `SCHEMA.sql` was an invitation to run the wrong one.
7. **A `UNIQUE (user_id, hot_word)` constraint was added to `sos_hot_words`**,
   which the existing screen does not handle gracefully — a duplicate shows
   "Failed to add SOS hot word". Silent duplicates seemed worse. Revisit in S18
   when hot words become functional.

### CONTRACT CHANGE

None. `app/contracts/` does not exist until S03.

### Migrations

Hand-run, not yet under a runner (ADR 0004, S02):

- `backend/migrations/supabase/SCHEMA.sql` — the whole fresh schema, idempotent
- `backend/migrations/supabase/RESET.sql` — destructive teardown
- `backend/migrations/supabase/VERIFY.sql` — 8 verification queries

### Env vars added

Frontend (`frontend/.env.example`):
- `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` — **live now**
- `EXPO_PUBLIC_API_BASE_URL` — declared but **not yet read**; the app still uses
  the hardcoded constant in `src/constants/app.constants.ts`. Wired up in S07.

Backend (`backend/.env.example`):
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` —
  **these were missing entirely**, even though `email_service.py` cannot send
  without them. SOS is email-only, so an unconfigured install reports success
  to the user and delivers nothing.
- `POLICE_ROUTING_ENABLED=false`
- `ANTHROPIC_API_KEY`, `LLM_MODEL_JUDGMENT`, `LLM_MODEL_BULK` — unused until S04

### Measurements

None — no request-path code or LLM calls in this sprint.

### Deliberately NOT done

- **Nothing was committed.** The working tree holds every change; the commit and
  PR are yours. This is why `smoke.sh` reports one failure.
- **`npm install` was not run**, so `package-lock.json` does not exist yet. It
  needs several minutes and network, and it changes `node_modules` on your
  machine. It is manual step 1.
- **No Supabase project was created**, so none of the SQL has been executed
  against a real database. **The SQL is unverified.** It is written carefully
  and `VERIFY.sql` will tell you if anything is wrong, but treat the first run
  as the real test.
- **Did not fix the other 16 known defects.** They are Phase 1 (S05–S08) and
  several need a client and server change in the same commit.
- **Did not touch `app.constants.ts`'s hardcoded `API_BASE_URL`.** Moving it
  changes behaviour for anyone whose `.env` lacks the new variable; it belongs
  with the other frontend work in S07.
- **Did not delete the `agent/Arafat` branch** — it holds the only copy of this
  work until it is committed.

### Known broken / rough edges

- `smoke.sh` fails one assertion until the commit lands (by design).
- The system Python here is **3.14**; the project targets **3.11**. `check.sh`
  warns about this. Use `backend/venv`.
- `ruff` and `mypy` have never been run against this codebase. The first run
  will surface findings. The config is deliberately a starter set with legacy
  modules silenced per-module — **each silenced module names the sprint that
  un-silences it**, and that annotation is the only thing keeping it temporary.
- `SOS_VIDEO_MAX_DURATION` is still 300 s in the template while
  `SOSCameraModal` records 10 s. Harmless, but the template is aspirational.

### Gotchas for the next agent

- **`.env` was never gitignored.** Only `.env.*.local` was. A single
  `git add -A` would have published the service-role key, the database password
  and the Anthropic key. Fixed, and history is clean — no `.env` was ever
  committed. Do not loosen those rules.
- **There is no lockfile.** Until `package-lock.json` is committed, the two of
  us are running different dependency trees and CI falls back to `npm install`
  with a warning.
- **Never name a module `types.py` inside `app/`.** One was created in this
  sprint and it shadowed the standard library's `types`, so `import enum`
  exploded with a traceback pointing at SQLAlchemy. Renamed to `columns.py`.
  `smoke.sh` now asserts `types.py` does not come back.
- **Email confirmation must be OFF in Supabase.** `auth.service.ts` requires
  `authData.session` immediately after `signUp`; with confirmation on, the
  session is null and every registration fails with a bare "Registration
  failed". Schema README §2.
- **The JWT secret is the likeliest setup failure.** `security.py` validates
  Supabase tokens with a shared HS256 secret, and new Supabase projects default
  to asymmetric keys. Symptom: SOS returns 401 while everything else works.
  Schema README §4. If your project has no legacy HS256 secret, pull ADR 0002
  forward from S02 rather than working around it.
- **Use Supabase port 5432, not 6543.** 6543 is PgBouncer in transaction mode
  and breaks asyncpg's prepared-statement cache intermittently — the worst kind
  of failure to debug.
- **`EXPO_PUBLIC_*` is inlined at bundle time.** A running Metro server keeps
  serving stale values. `npx expo start --clear`.
- **`crime_category` is lowercase in the database** and capitalised in
  `types/index.ts` + `MapScreen`'s `CRIME_COLORS`. The database is right; the
  client is Defect 3. Do not "fix" it by changing the enum.
- **`scripts/smoke.sh` is cumulative.** Add a `demo_S<nn>` function; do not
  replace the existing ones. A sprint that breaks an earlier demo is caught here
  rather than by your partner.

### RESUME HERE

See the `CURRENT STATE` block at the top of this file — the five numbered manual
steps, in order.

### Prototype Gate

- [x] 1 · `./scripts/check.sh` green (5 skips: tools not installed locally)
- [ ] 2 · `./scripts/seed.sh --fresh` — **not run; no database exists yet**
- [ ] 3 · App builds and launches — **blocked on `npm install` + `.env`**
- [ ] 4 · `smoke.sh`: 30/31 pass; the last needs the commit
- [x] 5 · `PROGRESS.md` entry written + `CURRENT STATE` overwritten
- [x] 6 · New env vars in both `.env.example` files and plan §9
- [x] 7 · Nothing half-migrated — ORM and schema agree on `uuid`

**Gate 2, 3 and 4 are open.** S01 is code-complete, not closed. Per plan §3.4 a
sprint ends early rather than ending broken: the remaining work needs a
toolchain and a Supabase account, and it is written down rather than guessed at.

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
| Known defects | <n> open of <total> — <which> |
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
