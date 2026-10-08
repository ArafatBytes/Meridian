# Meridian — Implementation Plan (Relay Model)

**From the current codebase to the agentic safety navigation platform described in [Meridian_Concept_Document.md](Meridian_Concept_Document.md).**

Audience: Arafat and Nakib. Two developers working in **relay** — one writer at a time, one trunk, a working prototype at every handoff.
Target: production-grade public release. No hackathon deadline governs this plan.

**Companion file: [PROGRESS.md](PROGRESS.md).** It is the handoff log. Your Claude Code agent reads it *before* reading this plan, and writes to it *before* every push. This plan says what to build; `PROGRESS.md` says where the work currently stands.

---

## 0. How to use this document

**If you are a Claude Code agent starting a session: read [PROGRESS.md](PROGRESS.md) first.** It tells you the current state of the trunk and which sprint is next. Come back here for that sprint's specification.

1. **Read §2 (Relay Model) and §3 (Branch & Handoff Protocol) before writing any code.** Everything else depends on them.
2. Work is a single ordered sequence of **sprints** (`S01`, `S02`, …). One person holds the baton for one sprint, pushes, and hands over. There is no parallel track.
3. **One sprint = one relay turn** = one person's stretch of work ending in a push. Typically 3–6 Claude Code sessions, roughly a week of part-time work. The owner column in §11 is a suggestion; `PROGRESS.md` records who actually took it.
4. Every sprint ends at the **Prototype Gate** (§3.4). A push that does not clear the gate is not a handoff — it is a broken trunk, and that is the only P0 on this project.
5. Task checkboxes are ticked in this file, in the commit that does the work.
6. Phase exit criteria are the real milestones. Sprints are how you get there; phases are what you demo.

---

## 1. Where we are starting from

A full audit of the existing codebase produced this summary. It is the baseline Phase 1 pays down.

**What works end to end today**
- Supabase email/password auth, profile creation, token caching, Zustand store
- Crime image analysis: YOLOv9c + MediaPipe + CLIP behind a weighted fusion decision engine (~2,250 lines, genuinely good work, graceful degradation at every stage)
- Community crime reporting: Nominatim search, map pin, Supabase persist, list/detail/delete
- Safety-weighted routing: OSRM alternatives scored against a regional risk model derived from 1,105 rows of real Bangladesh Police unit statistics
- SOS: 10-second video capture → upload → nearest police stations within 5 km + emergency contacts → HTML email with video attached

**What is scaffolding**
- 26 of ~35 backend endpoints are `pass` with a `# TODO`: all of `auth.py`, `crimes.py`, `users.py`, `tracking.py`
- `crime_ai.py` (227 lines) is never registered in `api.py` — dead duplicate of `ai.py`
- Celery beat references two modules that do not exist; there are no `@task` definitions anywhere
- Redis is configured and unused
- Hot words are written to Supabase and read by nothing; `/voice/analyze` returns an empty transcript unconditionally
- No background location tracking (`expo-task-manager` is not installed)

**Known defects carried into Phase 1**
| # | Severity | Issue | Fixed in |
|---|---|---|---|
| 1 | Blocker | `frontend/src/lib/` is imported by 8 files, does not exist, and was never committed — root `.gitignore:44` has a bare `lib/` that matches it. Fresh clone cannot build. | **S01 ✅** |
| 2 | Blocker | `speech_service.py` calls `AudioSegment` with the `pydub` import commented out → `NameError` on every speech-to-text request | S05 |
| 3 | High | `MapScreen` `CRIME_COLORS` keys are capitalised; DB values are lowercase → every marker colour resolves `undefined` | S07 |
| 4 | High | `HomeScreen` voice SOS records 1 s of audio every 2 s forever, reads `status.isRecording` *after* unload (always false), and the trigger in the reachable branch is commented out. Continuous recording, zero detection. | **S01 ✅** — the whole block was deleted with the `expo-av` removal (defect 37); real hot-word detection is still S07 |
| 5 | High | MediaPipe `Pose` is single-person, so `analyze_interaction` always short-circuits — all multi-person interaction logic and the harassment profile are unreachable. **Re-scoped:** pose analysis never ran at all (defect 29), so this was never the binding constraint; the `PoseLandmarker` port fixes both at once via its `num_poses` option. | S06 |
| 6 | Medium | `avoid_high_crime_zones` / `max_crime_score` accepted by `RouteRequest` and never read. Both honoured now, with one decision attached: **a filter that would reject every route is relaxed, not applied** — everything comes back best-first with `filter_relaxed: true`, because answering "no acceptable route" to someone asking how to get home is the worst available answer. | **D06 ✅** |
| 7 | Medium | `route_service` hardcodes the public OSRM demo server, ignores `OSRM_BASE_URL`, uses the `driving` profile, and discards OSRM's own durations for a flat 30 km/h. All four fixed in `app/routing/osrm.py`, and the fallback to the demo server is now **loud** — `RouteResponse.engine` carries it. ⚠️ **Two honest limits remain:** walking answers from a `car.lua` graph (durations recomputed, caveat on screen; a `foot.lua` graph is the fix), and OSRM's own duration turned out to be **free-flow** — 54.8 km/h across central Dhaka — because an OSM extract holds no traffic data, so it is scaled by `ROUTE_CONGESTION_FACTOR`. The real fix is `osrm-customize --segment-speed-file`, which needs a traffic source → **Track B**. | **D06 ✅** |
| 8 | Medium | `_calculate_path_risk` loads all crimes then loops path-points × crimes in Python — `select(CrimeReport)` with **no spatial predicate at all**. Now one `ST_DWithin` against an `ST_MakeLine` of the route, through a new `RiskSurface.flags_near_path` so both surfaces answer it and `routing/` works unchanged on the offline fixture (S12's own check). | **D06 ✅** |
| 9 | Medium | Three user tables: `auth.users`, `public.profiles` (app), `public.users` (backend). `create_users_table.sql` and `models/user.py` define incompatible shapes. | S02 / S05 |
| 10 | Medium | Nominatim called from the device with no `User-Agent`, against their usage policy — and from **five** call sites with no caching, so the per-IP limit was spent separately by every phone. Now `app/geo/nominatim.py` behind `GET /geo/search` and `GET /geo/reverse`: one identifying agent, one shared Redis cache (**471 ms cold → 52 ms warm**, 24 h TTL). Kept separate from `/geo/resolve`, which is allowed to refuse. | **D06 ✅** |
| 11 | Medium | Three crime-score scales coexist: 0–100, 0–10, and percent. One scale now — **`safety_score`, 0–100, higher is safer.** `RouteSegment.crime_score` deleted, the card renders `71/100` rather than `70.6% Safe`, and a test asserts the response carries exactly one risk scale so a second cannot return quietly. | **D06 ✅** |
| 12 | Low | `EmergencyContact` declared twice in `types/index.ts` with different shapes | **S01b ✅** — re-point at the contract type in S03 |
| 13 | Low | Report photos are analysed then discarded — evidence is never persisted | S06 |
| 14 | Low | `MapScreen` SOS button is still a `// TODO` alert while `HomeScreen`'s is real | S07 |
| 15 | Low | `Pillow`, `pandas`, `pytest` commented out in `requirements.txt` but used by code, scripts, tests | S04 |
| 16 | Low | `theme/colors.ts` + `theme/darkTheme.ts` are dead; `routeService` not exported from the services barrel | S04 / S07 |
| 17 | Low | All 606 rows of `police_stations.csv` share one placeholder email and phone | S05 |
| 18 | **Blocker** | `.env` was **not** gitignored — the root rule covered only `.env.*.local`, so a `backend/.env` holding the Supabase service-role key, the database password and the Anthropic key was fully trackable. Found during S01; no `.env` ever reached history. | **S01 ✅** |
| 19 | High | No `package-lock.json` is committed, so the two of us resolve different dependency trees and CI cannot use `npm ci`. Found during S01. **Root cause found later:** `.gitignore` listed `package-lock.json` and `yarn.lock` outright, so the file `npm install` generated could not be added — correct for a published library, wrong for an application, and the same shape as defect 1's bare `lib/`. The rules are removed; the file still needs committing. | **S01 ✅ unblocked**, commit outstanding |
| 20 | **Blocker** | `requirements.txt` declared plain `sqlalchemy`, but SQLAlchemy's asyncio support requires `greenlet`. `app.main` could not be imported at all: *"The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed."* The backend has therefore never started from a clean dependency install. Found when the Docker image first ran. | **S01b ✅** |
| 21 | **Blocker** | `email-validator` was commented out in `requirements.txt` while `schemas/auth.py` and `schemas/user.py` use pydantic `EmailStr`, which raises `ImportError` at import time. Same root cause as 20: the dependency file had drifted from the code. | **S01b ✅** |
| 22 | Medium | `shapely==2.0.2` was built against numpy 1.x, but `numpy` is unpinned and resolves to 2.4.x, so importing shapely emits `AttributeError: _ARRAY_API not found` and its numpy interop is silently broken. Non-fatal today because nothing calls shapely directly; `geoalchemy2` imports it. | **S01b ✅** |
| 23 | **Blocker** | `ultralytics==8.1.34` cannot load the YOLOv9c checkpoint under torch ≥2.6, which changed `torch.load` to default `weights_only=True`: *"Weights only load failed."* The vision stack therefore never loaded. Verified fixed on `ultralytics>=8.3.0` (resolved 8.4.174). | **S01b ✅** |
| 24 | Medium | `YOLO('yolov9c.pt')` resolves a bare filename against the working directory, which in the container is an image layer rather than a mounted volume — so the 82 MB download repeated on every `--force-recreate` and stalled the first AI request ~3 min each time. Now fetched at build time. | **S01b ✅** |
| 25 | **Blocker** | `package.json` had four incompatible React-family versions: `react-native: ^0.81.5` drifted to 0.81.6 (peer `react ^19.1.4`) against a pinned `react 19.1.0`; `react-dom ^19.2.3` needs React 19.2; `react-test-renderer 18.3.1` is a **React 18** build. `npm install` was impossible. Root cause is defect 19 — no lockfile, so the registry moved under them. | **S01b ✅** |
| 26 | High | `@react-navigation/drawer` was declared but never used, and its `peer react-native-reanimated` pulled in reanimated 4.7.1, which demands `react-native 0.86-0.88`. An unused package blocked the entire install. 14 further unused dependencies remain, each a latent conflict. | **S01b ✅** |
| 27 | **CRITICAL** | **Malware in `frontend/babel.config.js`** — ~26 KB of obfuscated code after the closing brace, hidden behind ~400 spaces, present since commit `db6c42f`. Blockchain dead-drop C2 → XOR'd payload → `eval` plus a detached `spawn('node','-e',...)` with `windowsHide`. Executed on every bundle and every Jest run. See [docs/SECURITY-INCIDENT-2026-10-07.md](docs/SECURITY-INCIDENT-2026-10-07.md). | **S01b ✅ removed; rotation outstanding** |
| 28 | High | ESLint had **never run**: `.eslintrc.js` extended `@react-native`, a package that was never installed, so every lint invocation died on a missing config. Its first successful run is what surfaced defect 27. Jest was equally broken — `preset: 'react-native'` on an Expo app. | **S01b ✅** |
| 29 | **Blocker** | `mediapipe==1.1.0` removed the `mp.solutions` namespace that `pose_service.py` is built on, so the import raises and `CrimeDetectionService.pose_service` is left `None`. **Pose analysis has not run at all** — `pose_analysis: null` on every response. This is the real cause of the null field earlier attributed to defect 5. The fix is a port to `mediapipe.tasks.python.vision.PoseLandmarker`, whose `num_poses` option also resolves defect 5. | S06 |
| 30 | High | **The vision vocabulary does not match the decision engine.** `crime_detection_service` scores against 21 object signals; YOLOv9c emits COCO's 80 classes, of which 11 of those signals are not members (`gun`, `blood`, `broken window`, `damaged property`, `graffiti`, `crowbar`, `spray paint`, `money`, `door`, `window`, `building`). Combined with defect 29, three of the six crime classes — `harassment`, `theft`, `vandalism` — are **structurally unreachable**: no input can produce them. Measured by `scripts/eval_crime_vision.py --json`. | S06 |
| 31 | High | `POLICE_ROUTING_ENABLED` was documented in `.env.example` and `docs/` from S01b but **never declared in `Settings` and never read by `sos_service`**, so police routing was unconditionally on. With defect 17 (all 606 stations share `noorlabib@iut-dhaka.edu`) every SOS test emailed an uninvolved third party. Now declared, defaulted off, checked, and loud when the CSV is still placeholder data. | **S01 ✅** |
| 32 | High | Nine env vars shipped in `.env.example` were never declared on `Settings`, and `extra = "ignore"` meant pydantic **silently discarded** them rather than failing. `SUPABASE_URL` was the one that bit: `AttributeError: 'Settings' object has no attribute 'SUPABASE_URL'` at the first JWKS fetch. All nine are now declared. | **S01 ✅** |
| 33 | **Blocker** | Supabase signs access tokens with **ES256** (asymmetric) by default, but `security.decode_token` passed `JWT_SECRET_KEY` with `algorithms=["HS256"]`, so **every authenticated request returned 401** — the symptom was SOS failing after the UI reported success. Fixed by pulling ADR 0002 forward: `app/core/jwks.py` fetches the project JWKS, caches by `kid`, verifies `aud=authenticated`, and still accepts HS256 for legacy tokens. `decode_token` is now `async`. | **S01 ✅** |
| 34 | Medium | `EditProfileScreen` built its upload content type as `` `image/${fileExt}` ``, producing `image/jpg` — not a registered IANA type — and Supabase Storage rejected it. The screen was also duplicating upload logic instead of using `uploadAvatar()`, which maps extensions to real types. | **S01 ✅** |
| 35 | High | **An SOS leaves no audit trail.** `sos_incidents`, the `SOSIncident` model and the `User.sos_incidents` relationship all exist, but `trigger_sos` never inserts a row, and `_save_video` writes the clip to a temp file, attaches it, then deletes it. After a verified-delivered alert the table still held 0 rows: the only copy of the evidence is in the recipient's inbox, and the app can show no history, no resolution state and no false-alarm record. | S05 |
| 36 | **Blocker** | The app pinned Expo SDK 54 while Expo Go ships only the newest SDK, so it could not be launched on a device at all: *"Project is incompatible with this version of Expo Go."* Upgraded to **SDK 57** (35 packages, React Native 0.86.3, React 19.2.3) against `bundledNativeModules.json` rather than by guesswork. | **S01 ✅** |
| 37 | **Blocker** | `expo-av` was **removed** in SDK 57. It was imported by `speech.service.ts` and `HomeScreen`. Replaced with `expo-audio`, which is hook-based — note `AudioRecorder` is a type-only export, so a class cannot be constructed. `speech.service.ts` is now transcription-only and recording lives in the new `useVoiceRecorder` hook, which also removes the dead `recordAndTranscribe()` and the defect 4 polling loop. | **S01 ✅** (defect 4 closed with it) |
| 38 | Medium | Four APIs deprecated or removed under SDK 57 / RN 0.86 were still in use: `StyleSheet.absoluteFillObject` (→ `absoluteFill`), `ImagePicker.MediaTypeOptions` at 3 call sites (→ `['images']`), `DateTimePicker`'s `onChange` across 4 pickers (→ `onValueChange` / `onDismiss`), and `expo-contacts`' top-level `presentContactPickerAsync`. The last is now imported from `expo-contacts/legacy`, which is the correct target: SDK 57's class-based API exports no picker, and `ContactAccessButton` is iOS 18+ and a different interaction. | **S01 ✅** |
| 39 | Medium | `MapScreen` called the location-permission request without a rejection handler, so a denial surfaced as an unhandled promise rejection and a red box instead of the intended fallback. | **S01 ✅** |
| 40 | Low | `backend/data/` was not mounted into the `api` container, so the eval harness could not read its own `manifest.csv` and anything it wrote landed in the container layer and vanished on recreate. | **S01 ✅** |
| 41 | Medium | `smoke.sh` asserted *"package-lock.json committed"* with `test -f`, which passed for a file that was gitignored and untracked — **a false green on the exact defect it was named after** (19). Now `git ls-files --error-unmatch`. Worth generalising: an assertion whose name claims more than its command checks is worse than no assertion, because it is trusted. | **S01 ✅** |
| 42 | **Blocker** | **Live news ingestion had never published a flag.** `place_candidates()` in `app/agents/live_risk.py` stripped only `PLACE_FILLER` words, so a location the extraction model answered correctly — `মহাখালী বাস টার্মিনালে` for a real bus fire, 0.95 confidence — resolved to nothing while `মহাখালী` alone resolves at 1.00. **The most specific answer was the least resolvable one**, and the prompt explicitly asks for the most specific. Every such incident was discarded as `unresolved_location`, so D04 shipped a working pipeline that produced zero output. Fixed with `PLACE_GENERIC_TAIL`: generic place-*type* nouns stripped from the end only, longest match first, tried after the as-written and filler-stripped candidates so a fully-known place resolves to itself. D03's number-identity rule is what keeps the discard invariant intact — a fabricated `গুলশান ফ৭ গোলচত্বর` reduces to `গুলশান ফ৭` and is still refused. | **D04 ✅** |
| 43 | **Blocker** | **Every authenticated backend call 401'd about an hour after sign-in, SOS included.** `api.service.ts` and `auth.service.getAuthToken()` read the access token from a `SecureStore` copy written once at sign-in and never checked its expiry; Supabase access tokens last one hour. The 401 recovery path POSTed to the backend's `/auth/refresh`, which is a `# TODO: Implement token refresh logic` stub taking `refresh_token` as a query parameter while the app sent a JSON body — so it could never have worked, and it ended at `Error: No refresh token`, signing the user out. The Supabase client held a valid token in AsyncStorage throughout (`autoRefreshToken: true`). **`HomeScreen` SOS was broken identically** via `useAuthStore().token`, captured once by `initialize()`: the video uploaded and *then* 401'd. Undetected since D01 because `D01.md` is always run minutes after signing in. Fixed by making `supabase.auth.getSession()` the only token source in all three read paths. | **D04 ✅** |
| 44 | Medium | `smoke.sh`-adjacent lesson, recorded because it will recur: **a walkthrough re-run reproduces the steps, not the state.** Defect 43 needed a session older than an hour, and no amount of re-running `D01.md` would have surfaced it, because the first step of every walkthrough is signing in. Any auth-sensitive walkthrough step needs a *stale* session to be a real test — sign in the day before, or at least an hour ahead. | documented, D04 |

**The gap to the concept document:** none of the eight agents exist. There is no LLM client in the stack, no ingestion layer, no Bangla gazetteer, no deduplication, no decay, and no trip model.

---

## 2. The Relay Model

### 2.1 Why relay, for us specifically

Our working hours do not overlap. That single fact decides it.

Parallel branches buy exactly one thing: wall-clock compression from two people working *simultaneously*. We never work simultaneously, so there is nothing to compress — and we would be paying parallel's full cost (divergent branches, merge resolution, contract ceremony, two half-integrated states) for a benefit we cannot collect.

Relay instead buys us two things we actually want:

- **A single always-integrated trunk.** There is never a moment when two versions of the truth exist.
- **A working prototype at every handoff.** This is the goal we chose, and relay is the only model that makes it structural rather than aspirational.

It also eliminates the bus factor for free. In relay both of us touch every part of the system, so neither becomes the only person who understands half of it. The parallel plan had to schedule a deliberate track swap to buy that back.

**The cost we accept:** throughput is one person's, not two. There is no way around that and no plan can hide it. §11 sizes the project honestly on that basis.

### 2.2 The four relay rules

**Rule 1 — One writer at a time. The trunk is a baton.**
You either hold it or you don't. If you hold it, you are the only person committing. If you don't, you do not touch the repo — not a typo fix, not a dependency bump. There is never a situation where two people have uncommitted work.

**Rule 2 — Every push is a working prototype.**
The trunk must build, run, and demonstrate something at every single handoff. Not "compiles" — *runs*, on a device, doing what the sprint said it would. The Prototype Gate (§3.4) is the checklist. This is the rule that makes relay better than parallel for us, and the rule that is easiest to quietly break at 2 a.m.

**Rule 3 — The handoff log is part of the push.**
A push without a `PROGRESS.md` entry and an updated `CURRENT STATE` block is an incomplete push. Your partner's Claude Code agent has no memory of your session; that file *is* its memory. CI enforces this (§3.5).

**Rule 4 — Stub-first, still.**
Every contract ships with a working stub implementation *before* the real one. In the parallel plan this existed to unblock the other developer. In relay it exists for a better reason: **it is how a sprint ends in a working prototype when half the system does not exist yet.**

S04 ships `SeededRiskSurface` over ~200 hand-built risk flags. That means by S13 you can demo risk-aware routing, a live map overlay, and route explanations — a genuinely impressive prototype — while the agents that will eventually produce those flags are still two sprints away. Every sprint between now and then has something to show.

### 2.3 What relay lets us drop from the parallel plan

| Dropped | Why |
|---|---|
| Track A / Track B split | There is one writer; tracks are meaningless |
| `contracts-guard` pair-review ceremony | One writer cannot conflict with themselves. Contract changes now just need a loud `PROGRESS.md` entry |
| Track-stamped migration filenames | A timestamp alone is sufficient; no concurrent authoring |
| The deliberate Phase 4 track swap | Relay gives both of us whole-system knowledge continuously |
| Rebase discipline on long-lived feature branches | Short-lived sprint branches off an always-current trunk |

### 2.4 What relay makes *more* important

| Amplified | Why |
|---|---|
| **Sequencing** | In parallel, ordering within a phase barely mattered. In relay, each sprint must leave the trunk working, so the order in §11 is load-bearing — do not reorder sprints without checking what the next one assumes |
| **The handoff log** | It is the only channel between two sessions that never overlap. §3.3 and `PROGRESS.md` |
| **Per-area `CLAUDE.md`** | Still the cheapest way to give an agent correct context. Now scoped by *subsystem*, not by owner |
| **Stubs and fixtures** | Promoted from "unblocking device" to "the mechanism that makes every sprint demoable" |
| **Modular architecture** | §5's structure is no longer about conflict avoidance. It is about letting one person hold one subsystem in their head per sprint — and letting an agent load only that subtree |

### 2.5 Keeping contracts, dropping the ceremony

`app/contracts/` survives the move to relay, and §6 is unchanged. The reason is architectural, not organisational: the concept document (§5) requires eight agents that "can fail without breaking the others," and that is only true if they communicate through stable shapes rather than reaching into each other.

What changes is the process. A contract change no longer needs two approvals and a dedicated PR. It needs:

1. A `CONTRACT CHANGE` block in the `PROGRESS.md` entry, stating what changed and what it breaks
2. All existing consumers updated **in the same sprint** — you hold the baton, so there is no excuse for leaving a consumer broken
3. The TypeScript mirror in `frontend/src/types/contracts/` updated in the same push

---

## 3. Branch & Handoff Protocol

### 3.1 Branches

```
main                     protected, always green, always demoable — the baton
sprint/S<nn>-<slug>      e.g. sprint/S09-ingestion-framework
fix/<slug>               urgent production fix, any time
```

Delete `agent/Arafat` once S01 merges — it predates this structure.

One sprint, one branch, one PR, squash-merged. The branch lives as long as the sprint and no longer. Because only one person ever has a branch open, rebasing is trivial and conflicts are essentially impossible.

> You may also work directly on `main` if you prefer. The branch exists to give you a PR to review your own diff in before it becomes the trunk — which, with an AI agent writing most of the code, is worth more than it sounds.

### 3.2 Taking and passing the baton

**Taking it** (start of your sprint):

```bash
git checkout main && git pull
cat PROGRESS.md            # agent: read this FIRST, in full, before any code
./scripts/seed.sh          # rebuild dev DB from migrations + fixtures
./scripts/check.sh         # confirm you received a green trunk
git checkout -b sprint/S<nn>-<slug>
```

If `check.sh` fails on a trunk you just received, **stop and tell your partner.** Do not start your sprint on a broken baton; you will spend your window debugging their work and the log will no longer reflect reality.

**Passing it** (end of your sprint):

```bash
./scripts/check.sh         # green
./scripts/seed.sh --fresh  # works from zero
./scripts/smoke.sh         # the sprint's demo script passes
# update PROGRESS.md: new entry at top + overwrite CURRENT STATE
# tick this file's checkboxes for the sprint
git push && open a PR, squash-merge to main
# tell your partner the baton is free
```

### 3.3 The handoff log

[PROGRESS.md](PROGRESS.md) has two parts and they serve different purposes:

- **`CURRENT STATE`** — a pinned block at the top, **overwritten** every handoff. The single authoritative answer to "where are we right now." An agent reads this and knows the trunk's state without reading history.
- **Handoff log** — **append-only**, newest entry first. One entry per sprint: what was done, what was decided, what is deliberately unfinished, and exactly where to resume.

The template and the rules for filling it are in that file. Two things matter more than the rest:

1. **Write the "RESUME HERE" line as if to a stranger.** Your partner's agent *is* a stranger. It has never seen your session.
2. **Record what you deliberately did *not* do, and why.** An unexplained gap gets rediscovered, re-litigated, or silently "fixed" in a way that breaks your intent.

### 3.4 The Prototype Gate

Every handoff must clear all seven. This is Rule 2, made checkable.

| # | Gate |
|---|---|
| 1 | `./scripts/check.sh` green — lint, types, unit, integration, invariants |
| 2 | `./scripts/seed.sh --fresh` works from an empty database |
| 3 | The app **builds and launches** on a real device or emulator |
| 4 | The sprint's demo is scripted in `scripts/smoke.sh` and passes |
| 5 | `PROGRESS.md`: new log entry + `CURRENT STATE` overwritten |
| 6 | New env vars in `.env.example` **and** §9 of this file |
| 7 | Nothing left half-migrated: no contract without consumers updated, no migration without a working `seed.sh` |

**A sprint that cannot clear the gate ends early rather than ending broken.** Cut scope, push what works, write down what you dropped. Handing over a broken trunk costs your partner their whole window.

### 3.5 CI (set up in S01, `.github/workflows/`)

| Job | Runs | Fails on |
|---|---|---|
| `backend` | `ruff`, `mypy --strict app/contracts app/agents`, `pytest --cov` | any error; coverage < 70% on `app/` |
| `frontend` | `tsc --noEmit`, `eslint`, `jest` | any error |
| `invariants` | every PR | any test in `tests/invariants/` fails (§4) |
| `migrations-guard` | every PR | a migration file already on `main` was modified |
| `handoff-log` | every PR to `main` | `PROGRESS.md` was not modified (Rule 3, enforced) |

### 3.6 Background activities

Some work cannot fit in one relay turn: the Journey Guardian self-trial needs two weeks of real commuting, the corpus needs 200 hand-annotated articles, the gazetteer needs sustained manual entry.

These are **background activities**, not sprints. They are:
- listed in the `BACKGROUND` section of `CURRENT STATE`, with owner and status
- worked on by whoever has spare capacity, **including the person not holding the baton**
- the only exception to Rule 1 — but they touch **only data files** (`data/gazetteer/`, `data/corpus/`, trial logs), never code

Three are known in advance: corpus annotation (from S09), gazetteer entry (from S10), Guardian self-trial (from S23).

---

## 4. Non-negotiable invariants

Concept document §9 states five ethical constraints. In a production system those have to be *enforced by code and proven by tests*, not kept as intentions. Each one gets a home in `backend/tests/invariants/` and runs on every PR.

| Invariant | Enforced by | Test | Lands |
|---|---|---|---|
| **Mobility framing, never judgment.** Gatherings and processions surface as "road blocked", "heavy crowd", "expect delay" — never as safety or political characterisations. | `app/policy/framing.py` — `to_mobility_statement()` is the *only* writer of user-facing flag text; `assert_mobility_safe()` rejects a banned-term list and anything naming a group, party, religion, or ethnicity | `test_no_flag_text_bypasses_framing.py` — asserts every `RiskFlag.mobility_statement` in fixtures and in a live DB sample passes the guard; asserts no other module writes that field | S03 |
| **Verification before publication.** No single unverified source produces a confirmed flag. | Rumour Guard: `status` can only reach `confirmed` with ≥2 independent `source_id`s after semantic dedup | `test_single_source_never_confirmed.py` | S15 |
| **Decay by default.** No permanent area labels. | `RiskFlag` requires a non-null `half_life_hours`; the DB has a `CHECK (half_life_hours > 0)`; `expires_at` is generated, not supplied | `test_every_flag_decays.py`, `test_no_flag_outlives_expiry.py` | S02 (schema), S20 (engine) |
| **Graded escalation.** Journey Guardian assumes benign first and escalates only on non-response, in steps. | `app/trips/escalation.py` state machine; transitions to `notify_contacts` and `full_sos` require a recorded non-response with a timestamp | `test_escalation_requires_nonresponse.py`, `test_no_escalation_skips_a_step.py` | S23 |
| **Data minimisation.** Location history retained only as long as operationally necessary. | `app/privacy/retention.py` + a nightly job; every table holding user location declares a retention window in one registry | `test_every_location_table_has_retention.py` | S03 (registry), S31 (job) |

Two additions of our own, same status:

| Invariant | Enforced by | Lands |
|---|---|---|
| **No LLM output reaches a user unvalidated.** Every LLM call goes through `app/llm/client.py` and returns a validated Pydantic model, or raises. | `LLMClient` is the only module importing `anthropic`; a test asserts that | S04 |
| **Unresolvable locations are discarded, never guessed.** Concept doc §12. | `GeoResolution.method == "unresolved"` ⇒ the incident is dropped before flag creation, and logged | S11 |

---

## 5. Target architecture

Modular because one person needs to hold one subsystem in their head per sprint — and because an agent should be able to load one subtree instead of the whole repo.

```
backend/
├── app/
│   ├── contracts/              §6. Stable shapes. Changes are logged loudly (§2.5).
│   │   ├── risk.py             RawDocument, ExtractedIncident, GeoResolution, RiskFlag
│   │   ├── agents.py           BaseAgent, AgentContext, AgentResult
│   │   ├── surface.py          RiskSurface protocol — the seam stubs plug into
│   │   ├── trips.py            Trip, Checkpoint, EscalationState
│   │   └── casework.py         GDDraft
│   ├── agents/
│   │   ├── registry.py         auto-discovery + cron registration
│   │   ├── chronic_risk/       S25
│   │   ├── live_risk/          S14
│   │   ├── scheduled_risk/     S27
│   │   ├── geolocation/        S11
│   │   ├── rumour_guard/       S15
│   │   └── journey_guardian/   S22–S23
│   ├── ingestion/              S09
│   │   ├── sources/            one module per publisher, base.py defines the interface
│   │   ├── fetcher.py          politeness, robots, caching, backoff
│   │   └── store.py            RawDocument persistence
│   ├── llm/                    S04
│   │   ├── client.py           the ONLY importer of `anthropic`
│   │   ├── models.py           model selection constants
│   │   └── prompts/            versioned prompt templates
│   ├── scoring/                S19–S20
│   │   ├── decay.py            severity(t) = f(severity_0, half_life, time_profile)
│   │   ├── engine.py           RiskScoringEngine
│   │   └── surface_db.py       DbRiskSurface — implements contracts/surface.py
│   ├── routing/                S12–S13
│   │   ├── osrm.py             client, local-first with demo fallback
│   │   ├── scorer.py           path risk over a RiskSurface
│   │   └── explain.py          plain-language route explanations
│   ├── trips/                  S18, S22–S23
│   │   ├── service.py
│   │   └── escalation.py       the graded state machine
│   ├── casework/               S28
│   │   └── gd_service.py       General Diary drafting (uses app/llm)
│   ├── policy/
│   │   └── framing.py          mobility framing guard — S03
│   ├── privacy/
│   │   └── retention.py        retention registry + nightly purge — S03, S31
│   ├── config/                 one settings class per domain — S04
│   ├── api/v1/endpoints/       auto-mounted; one file per domain
│   ├── models/                 SQLAlchemy, auto-imported
│   └── services/               existing: ai/, route_service, sos_service, email_service
├── data/
│   ├── gazetteer/              Bangla landmark gazetteer (versioned, reviewed) — S10
│   ├── corpus/                 annotated articles — S09, background activity
│   └── fixtures/               seeded risk flags, documents, trips — S04
├── migrations/versions/        <utc>__<slug>.sql, forward-only
└── tests/
    ├── invariants/             §4 — runs on every PR
    ├── unit/
    └── integration/

frontend/src/
├── types/contracts/            mirrors backend/app/contracts
├── features/                   one directory per feature, self-contained
│   ├── risk-map/               S13
│   ├── routing/                S13
│   ├── journey/                S18, S23
│   ├── reporting/              S08
│   ├── casework/               S29
│   └── sos/                    S07
├── services/                   one file per domain
├── components/                 shared primitives only
└── theme/                      consolidated in S04
```

Add a `CLAUDE.md` to `backend/app/agents/`, `backend/app/routing/`, and `frontend/` as each becomes active. Each states that subsystem's contracts, conventions, and what not to touch. This is the cheapest context you will ever buy.

---

## 6. Shared contracts (authored in S03)

These are the actual signatures. Get them right in S03 and every sprint after it slots in cleanly.

### 6.1 `app/contracts/risk.py`

```python
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class IncidentKind(StrEnum):
    ROAD_ACCIDENT  = "road_accident"
    FIRE           = "fire"
    CLASH          = "clash"
    BLOCKADE       = "blockade"
    PROCESSION     = "procession"
    WATERLOGGING   = "waterlogging"
    CONSTRUCTION   = "construction"
    UTILITY_OUTAGE = "utility_outage"
    CHRONIC        = "chronic"          # from archive mining, long half-life
    OTHER          = "other"


class MobilityImpact(StrEnum):
    """The only vocabulary allowed to describe effect. Concept doc §9."""
    ROAD_BLOCKED = "road_blocked"
    HEAVY_CROWD  = "heavy_crowd"
    DELAY_LIKELY = "delay_likely"
    LANE_CLOSED  = "lane_closed"
    IMPASSABLE   = "impassable"
    NONE         = "none"


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str                      # stable publisher id, e.g. "prothom_alo"
    url: str
    published_at: datetime | None
    title: str | None = None
    snippet: str | None = None


class RawDocument(BaseModel):
    doc_id: str                         # sha256 of canonical URL
    source_id: str
    url: str
    fetched_at: datetime
    published_at: datetime | None
    language: Literal["bn", "en", "mixed"]
    title: str
    body: str
    raw_ref: str | None = None          # object-store key; never inline HTML


class ExtractedIncident(BaseModel):
    """Output of an LLM extraction pass over one RawDocument."""
    kind: IncidentKind
    summary_en: str
    summary_bn: str | None = None
    location_text: str                  # colloquial, exactly as written
    occurred_at: datetime | None
    severity_hint: Literal["low", "medium", "high"] | None = None
    mobility_impact: MobilityImpact
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    source: SourceRef


class GeoResolution(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0, le=20_000)
    resolved_name: str
    method: Literal["gazetteer", "llm_gazetteer", "nominatim", "unresolved"]
    confidence: float = Field(ge=0.0, le=1.0)
    admin_area: str | None = None


class TimeProfile(BaseModel):
    """Hour-of-day multipliers, 24 entries, 1.0 = neutral. Concept doc §5.6."""
    multipliers: list[float] = Field(min_length=24, max_length=24)


class RiskFlag(BaseModel):
    flag_id: UUID
    event_key: str                      # dedup identity, assigned by Rumour Guard
    kind: IncidentKind
    status: Literal["unconfirmed", "confirmed", "expired", "rejected"]
    lat: float
    lon: float
    radius_m: int = Field(gt=0)
    severity_0: float = Field(ge=0.0, le=100.0)   # severity at observed_at
    half_life_hours: float = Field(gt=0)          # §4: decay is mandatory
    observed_at: datetime
    expires_at: datetime                          # derived, never hand-set
    source_count: int = Field(ge=1)
    sources: list[SourceRef]
    mobility_statement: str                       # ONLY written by policy.framing
    time_profile: TimeProfile | None = None
```

**Default half-lives** (concept doc §5.6; owned by the Risk Scoring Engine, S19):

| Kind | Half-life | Default radius |
|---|---|---|
| `ROAD_ACCIDENT` | 1 h | 150 m |
| `FIRE` | 3.5 h | 400 m |
| `CLASH` | 9 h | 500 m |
| `BLOCKADE` / `PROCESSION` | event duration | 600 m |
| `WATERLOGGING` | 6 h | 800 m |
| `CONSTRUCTION` | 30 d | 200 m |
| `CHRONIC` | 90 d | 250 m |

### 6.2 `app/contracts/surface.py` — the stub seam

**The most important interface in the plan.** It is what lets S12–S13 build and demo risk-aware routing against fixtures, before the agents that produce real flags exist.

```python
from datetime import datetime
from typing import Protocol, Sequence
from app.contracts.risk import RiskFlag


class PointRisk(BaseModel):
    score: float = Field(ge=0.0, le=100.0)    # decayed, time-of-day adjusted
    contributing_flags: list[RiskFlag]


class PathRisk(BaseModel):
    safety_score: float = Field(ge=0.0, le=100.0)   # 100 = safest
    worst_point_score: float
    flags_on_path: list[RiskFlag]
    explanation_inputs: list[str]      # feeds routing/explain.py


class RiskSurface(Protocol):
    async def score_point(
        self, lat: float, lon: float, at: datetime
    ) -> PointRisk: ...

    async def score_path(
        self, path: Sequence[tuple[float, float]], at: datetime
    ) -> PathRisk: ...

    async def flags_near(
        self, lat: float, lon: float, radius_m: int, at: datetime
    ) -> list[RiskFlag]: ...
```

Three implementations exist by S20:

| Implementation | Source | Used by | Lands |
|---|---|---|---|
| `SeededRiskSurface` | `data/fixtures/risk_flags.json` | Dev + every test, S04 onward | **S04** |
| `LegacyRegionalSurface` | existing `crime_risk_model.json` | Fallback / cold start | S12 |
| `DbRiskSurface` | `risk_flags` table, decay applied at query time | Production | S20 |

Selection is a single settings value: `RISK_SURFACE_IMPL={seeded|legacy|db}`. Changing implementation must never require a change in `routing/` — if it does, the contract is wrong.

### 6.3 `app/contracts/agents.py`

```python
from abc import ABC, abstractmethod
from typing import ClassVar


class AgentResult(BaseModel):
    agent: str
    run_id: UUID
    started_at: datetime
    finished_at: datetime
    status: Literal["ok", "partial", "failed"]
    items_in: int
    items_out: int
    errors: list[str] = []
    metrics: dict[str, float] = {}


class AgentContext(BaseModel):
    """Everything an agent may touch. Injected — agents never build their own."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_id: UUID
    now: datetime
    dry_run: bool = False


class BaseAgent(ABC):
    name: ClassVar[str]
    cron: ClassVar[str | None] = None      # registry reads this
    enabled_by_default: ClassVar[bool] = True

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult: ...
```

Every agent module exports `AGENT = MyAgent()`. `agents/registry.py` discovers them and registers their cron with Celery beat — so adding an agent is one new directory, never an edit to a central list.

### 6.4 `app/llm/client.py` — the only `anthropic` importer

```python
# app/llm/models.py
MODEL_JUDGMENT = "claude-opus-5-5"   # geocoding disambiguation, GD drafting, adjudication
MODEL_BULK     = "claude-sonnet-5-5" # high-volume incident extraction
```

```python
# app/llm/client.py
import anthropic
from typing import TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)   # PEP 695 `def extract[T: BaseModel]` needs 3.12; we target 3.11


class LLMClient:
    def __init__(self) -> None:
        # Resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login` profile.
        self._client = anthropic.AsyncAnthropic()

    async def extract(
        self,
        *,
        schema: type[T],
        system: str,
        user: str,
        model: str = MODEL_BULK,
        effort: str = "medium",
        cache_system: bool = True,
    ) -> T:
        """Structured extraction. Returns a validated model or raises."""
        response = await self._client.messages.parse(
            model=model,
            max_tokens=16_000,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            system=(
                [{"type": "text", "text": system,
                  "cache_control": {"type": "ephemeral"}}]
                if cache_system else system
            ),
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise LLMRefusal(response.stop_details)
        return response.parsed_output
```

**Conventions that apply to every LLM call in this project:**

- **`claude-opus-5-5` is the default model.** Use `claude-sonnet-5-5` only for the high-volume bulk extractors (Live Risk, Chronic Risk), where volume justifies it and a wrong extraction is caught downstream by Rumour Guard.
- **Adaptive thinking** (`thinking={"type": "adaptive"}`) on everything. Control depth with `output_config.effort`, not a token budget — `budget_tokens` is rejected on these models.
- **Set `effort` explicitly.** Opus 5.5 defaults to `medium`. Use `high` for geocoding disambiguation and GD drafting; `medium` for bulk extraction; `low` for classification.
- **Structured outputs everywhere.** `messages.parse(output_format=PydanticModel)` → `.parsed_output`. Never parse free text, never use forced `tool_choice` (`any`/`tool` return a 400 on these models).
- **Cache the system prompt.** The gazetteer excerpt and extraction instructions are large and stable — put them in `system` with `cache_control`, put the volatile article text in `messages`. Verify with `usage.cache_read_input_tokens`; if it's zero across runs, something volatile leaked into the prefix.
- **Always check `stop_reason` before reading content.** A `refusal` is an HTTP 200.
- **Use the Batch API for the nightly archive job** (S25) — 50% cost on work that is not latency-sensitive.
- **Catch a chain, not one class:** `NotFoundError` → `RateLimitError` → `APIStatusError` → `APIConnectionError`.
- **Prompts are versioned files** under `app/llm/prompts/`, named `<agent>_v<n>.md`, referenced by constant. Changing a prompt is a code change with a diff — and an eval delta (§10).

> Verify `messages.parse` on the async client in the SDK version you pin. If the async surface differs, fall back to `messages.create` with `output_config={"format": {...}}` and validate with `schema.model_validate_json()` — the contract of `LLMClient.extract` does not change either way.

---

# PHASE 0 — Foundation & Contracts

**S01 – S04.** Goal: a repository that builds from a clean clone, a schema that holds risk flags, contracts for everything, and stubs that make the next twenty sprints demoable.

Nothing user-visible ships in this phase, and that is correct. S04 ends with a seeded risk surface you can query — that is the prototype.

---

## S01 — Unblock the repository

**Suggested owner:** Arafat (the current working-tree state is his). **Prototype:** clean clone → `npm ci` → the app launches.

- [x] Fix `.gitignore:44`: `lib/` → `/backend/lib/`. Verify with `git check-ignore -v frontend/src/lib/supabase.ts` (must return nothing) — **Defect 1**
- [x] Author and commit `frontend/src/lib/supabase.ts` and `supabase-storage.ts`
- [x] Confirm a clean clone builds: `package-lock.json` is committed (defect 19) and `npx tsc --noEmit` is clean
      ⏳ *the clean-clone-to-temp-dir rehearsal is still owed — Nakib's first `git pull` is the real test*
- [x] Move the Supabase URL / anon key out of `app.json` into `.env` + `expo-constants`; add `.env.example` for both sides
- [x] Commit `Meridian_Concept_Document.md` back if it is still deleted in a working tree
      *(present and tracked; nothing to do)*
- [x] `.github/workflows/` — the five jobs in §3.5, including `handoff-log`
- [x] `scripts/{check,seed,smoke}.sh` — stubs that exit 0 for now, wired into CI
- [x] `ruff` + `mypy` config; `pre-commit`
- [x] `CONTRIBUTING.md` — §2 and §3 condensed, so the relay rules live next to the code
- [x] Write the S01 entry in `PROGRESS.md`
- [ ] Delete the `agent/Arafat` branch — ⏳ *after S01 is committed and merged*

**Gate:** both of us clone fresh and launch the app. **Arafat's half met** — see S01d.

### S01b — Dockerised stack *(added mid-sprint, not in the original plan)*

Requested after the schema was live: one command to start both halves instead of
managing the Python/ML toolchain and Metro separately. Folded into S01 rather
than given its own sprint number because it is setup, not product.

- [x] Root `docker-compose.yml` — `api` + `redis`; `osrm` and `mobile` as opt-in
      profiles. **No Postgres** (the database is Supabase) and **no Celery**
      (beat still points at two phantom modules — S04)
- [x] `backend/Dockerfile` rewritten: `libgl1`/`libglib2.0-0` added so `cv2` and
      `mediapipe` can import, CPU-only torch from the PyTorch index (~2 GB
      saved), a healthcheck that uses stdlib `urllib` instead of the
      never-installed `requests`, and model weights in a cache volume
- [x] `backend/.dockerignore`, `frontend/.dockerignore` — the context previously
      included `venv/` (~4 GB) and `yolov9c.pt`
- [x] `scripts/run.ps1` + `scripts/run.sh` — preflight, LAN-IP detection,
      compose up, health wait, `npm install`, Expo. One command.
- [x] `scripts/test.sh` — live 5-phase verification: backend, Supabase schema,
      backend↔database, auth rejection, AI stack
- [x] `docs/RUNNING.md` — step-by-step run + test guide
- [x] `config.py`: `SECRET_KEY` and `POSTGRES_*` were **required and read by
      nothing**, so a minimal `.env` crashed at import. Given defaults;
      `REDIS_URL`/`CELERY_*` too. S04 still owns the split into `app/config/`.
- [x] `app.constants.ts`: `API_BASE_URL` now reads `EXPO_PUBLIC_API_BASE_URL`
      (pulled forward from S07 — the hardcoded `192.168.0.103` was correct on
      exactly one machine, so nothing else could reach the backend)
- [x] Deleted `backend/docker-compose.yml` — provisioned a competing Postgres
      and a Celery beat that crashes on boot
- [x] `frontend/Dockerfile.dev` — Metro in a container, for the `mobile` profile

**Decision recorded:** `.env` files are now **committed** (private repo; manual
env sync across two machines was costing more than it saved). `.gitignore`,
`smoke.sh` and both `.dockerignore` files were updated to match — tooling that
contradicts the decision is broken tooling. The three values that would matter
if the repo ever changed hands are the Supabase service-role key, the Anthropic
key and the SMTP app password.

---

### S01c — Malware removal & supply-chain guards *(unplanned, forced)*

Found while running ESLint for the first time (defect 28). ~26 KB of obfuscated
code sat after the closing brace of `frontend/babel.config.js`, behind ~400
spaces, **present since the initial commit `db6c42f`** and executed on every
Metro bundle and every Jest run — including the ones this project ran.

- [x] Remove the payload; `babel.config.js` is back to its 5 legitimate lines
- [x] Preserve the sample out-of-tree and write up the mechanism, IoCs and blast
      radius — [docs/SECURITY-INCIDENT-2026-10-07.md](docs/SECURITY-INCIDENT-2026-10-07.md)
- [x] `scripts/scan-injection.sh` — config-trailer, long-line, `eval`, hidden-
      `spawn` and wallet-literal detection. **Validated against the real sample**
      rather than assumed to work
- [x] Wire the scanner into CI (`supply-chain` job), `.pre-commit-config.yaml`
      and `demo_S01c` in `scripts/smoke.sh`
- [x] Delete `node_modules`, reinstall from the lockfile, verify all 1,175
      packages against registry signatures
- [x] Owner-side host triage: offline Defender scan, scheduled tasks,
      `Run`/`RunOnce`, startup folder, post-reboot process sweep — **clean**
- [x] [docs/INCIDENT-RESPONSE-CHECKLIST.md](docs/INCIDENT-RESPONSE-CHECKLIST.md)
      — the owner-owned steps, tracked to completion
- [ ] **Rotate every credential** the compromised host touched ⏳ *owner, from a
      different device; crypto keys first*
- [ ] **Rewrite git history** to drop the payload from `db6c42f` ⏳ *must happen
      before this repo is ever made public, and needs both of us present*
- [ ] **Nakib must pull before running anything** ⏳ *his clone still has the
      infected file; `npm install` / `expo start` / `npx jest` all detonate it*

**Process note, recorded because it cost real evidence:** during triage the
suspect process was killed *before* its parent PID was captured, which destroyed
the attribution link that was then asked for. Capture first, kill second.

---

### S01d — SDK 57 upgrade, real auth, and the first live walkthrough

The sprint that actually closed Prototype Gate 3. The app could not be launched
at all before it: Expo Go ships only the newest SDK, and the project was pinned
to 54.

**Upgrade and removals**

- [x] Expo **SDK 54 → 57** — 35 packages, React Native 0.86.3, React 19.2.3, all
      resolved against `bundledNativeModules.json` rather than guessed — **defect 36**
- [x] Exact-pin the React family; drop the unused `@react-navigation/drawer` that
      was dragging in an incompatible reanimated — **defects 25, 26**
- [x] `expo-av` is **gone** in SDK 57 — replaced with `expo-audio` — **defect 37**
- [x] New `frontend/src/hooks/useVoiceRecorder.ts` owns recording, the 30 s cap
      and unmount cleanup; `speech.service.ts` is now transcription-only with the
      dead `recordAndTranscribe()` removed
- [x] Delete the `HomeScreen` continuous-recording block — **defect 4**
- [x] `StyleSheet.absoluteFillObject`, `ImagePicker.MediaTypeOptions` ×3,
      `DateTimePicker.onChange` ×4, `expo-contacts` → `/legacy` — **defect 38**
- [x] `MapScreen` location-permission rejection handled — **defect 39**
- [x] ESLint runs for the first time; the three React Compiler rules are `warn`
      with a "delete when S08 lands" note rather than silently off — **defect 28**
- [x] Jest on `jest-expo`, spreading the preset's `transformIgnorePatterns`
      instead of replacing them

**Authentication — ADR 0002 pulled forward from S02**

- [x] `backend/app/core/jwks.py` — fetch the project JWKS, cache by `kid` with a
      TTL and a refetch floor, verify `aud=authenticated` with leeway, still
      accept HS256 for legacy tokens — **defect 33**
- [x] `decode_token` is now `async`; it no longer logs tokens or secrets
- [x] Declare all nine silently-dropped env vars on `Settings` — **defect 32**
- [x] Declare, default-off and actually *check* `POLICE_ROUTING_ENABLED`, and
      warn when `police_stations.csv` is still placeholder data — **defect 31**
- [x] SMTP vars wired into `backend/.env` so SOS can actually send
- [ ] Write `docs/adr/0002-auth.md` itself ⏳ *the code landed ahead of the ADR;
      S02 still owes the document, and it should describe what is now in place*

**Measurement before tuning**

- [x] `backend/scripts/eval_crime_vision.py` — per-class precision/recall/F1, a
      confusion matrix, a **stage-attributed failure breakdown**, and a
      capability report derived from the live model
- [x] `backend/data/eval/crime_vision/` — labelling guide, manifest, 2 seed
      negatives, committed baseline
- [x] Mount `backend/data/` into the container — **defect 40**
- [x] Record what the capability report found: **defects 29 and 30**
- [ ] Populate the set to the README's targets ⏳ *owner; this is the input S06 needs*

**Fixes found by walking the app**

- [x] `uploadAvatar()` adopted in `EditProfileScreen`; no more `image/jpg` — **defect 34**
- [x] `expo-contacts/legacy` for the contact picker — SDK 57's class-based API
      exports no picker at all

**Verified live, on a device, against the owner's Supabase** — `docs/RUNNING.md` §4:

| Step | Result |
|---|---|
| Register | ✅ row in `profiles` |
| Avatar upload | ✅ `avatar_url` populated |
| Crime report + AI | ✅ row in `crime_reports`; pipeline returned *no crime* |
| Add emergency contact | ✅ row in `emergency_contacts` |
| **SOS → email with video attachment** | ✅ **delivered** — owner-confirmed |

**Gate:** met. This is the first handoff where the app has actually run.

---

## S02 — Database foundation & architecture decisions

**Suggested owner:** Nakib. **Prototype:** `./scripts/seed.sh --fresh` builds the whole schema from zero.

- [ ] `docs/adr/0001-data-plane.md` — the Supabase-direct vs FastAPI rule. Proposal: **Supabase for user-owned CRUD; FastAPI for anything agentic, geospatial, or multi-user.** Write down which tables each may write.
- [ ] `docs/adr/0002-auth.md` — Supabase remains the IdP. Document the JWT path and **migrate off the shared HS256 secret** to Supabase JWKS verification (new projects default to asymmetric keys; the current `HS256` + `verify_aud=False` setup is fragile)
- [ ] `docs/adr/0003-user-identity.md` — collapse three user tables to one. Proposal: `auth.users` is identity, `public.profiles` is the only profile table, delete `public.users`, point `emergency_contacts.user_id` and `crime_reports.user_id` at `auth.users(id)` — **Defect 9**
- [ ] `docs/adr/0004-migrations.md` — forward-only timestamped SQL + runner, and why not Alembic
- [ ] `scripts/migrate.py` + `schema_migrations` table
- [ ] Migration: `risk_flags` with PostGIS `GEOGRAPHY(POINT, 4326)`, GiST index on location, index on `(status, expires_at)`, and **`CHECK (half_life_hours > 0)`** (§4 decay invariant, at the schema level)
- [ ] Migration: `raw_documents`, `extracted_incidents`, `agent_runs`
- [ ] Migration: execute ADR 0003
- [ ] `scripts/seed.sh` — rebuild a dev DB from migrations + fixtures in one command, for real this time

**Gate:** drop the dev DB, run `seed.sh --fresh`, get a complete schema.

---

## S03 — Contracts, policy & invariants

**Suggested owner:** Arafat. **Prototype:** `mypy --strict app/contracts` clean; invariant tests running in CI.

- [ ] `app/contracts/{risk,agents,surface,trips,casework}.py` — §6
- [ ] `frontend/src/types/contracts/` — hand-mirrored TypeScript, plus a CI check that flags drift
- [ ] `app/policy/framing.py` — `to_mobility_statement()`, `assert_mobility_safe()`, banned-term list
- [ ] `app/privacy/retention.py` — the retention registry, with every existing location-bearing table declared
- [ ] `backend/tests/invariants/` with the S03 tests from §4 wired into CI
- [ ] `mypy --strict` passes on `app/contracts/`

**Gate:** a deliberately bad flag statement is rejected by `assert_mobility_safe` in a test.

---

## S04 — Stubs, fixtures & modularization

**Suggested owner:** Nakib. **Prototype:** query the `RiskSurface` and get 200 real-looking Dhaka flags back.

**The fixture is the most valuable artifact in this sprint.** Twenty sprints of demos run on it.

- [ ] **`SeededRiskSurface` + `data/fixtures/risk_flags.json` — ~200 hand-built flags across Dhaka.** A mix of kinds, severities, half-lives, confirmed and unconfirmed, some already expired, several deliberately placed on common commuting corridors. Spend real time here.
- [ ] `StubGeolocationAgent` — fixed coordinate, `method="unresolved"`
- [ ] `NullLLMClient` — schema-valid canned responses, so tests never call the API
- [ ] `StubRumourGuard` — passes everything through as `unconfirmed`
- [ ] `app/llm/client.py` + `models.py` — real implementation, with the invariant test asserting it is the only `anthropic` importer
- [ ] Each stub has a test asserting it satisfies its protocol
- [ ] Endpoint auto-discovery replaces `api.py`'s manual includes; `models/__init__.py` auto-import
- [ ] `app/core/config.py` → `app/config/` package, one class per domain
- [ ] `requirements.txt` → `requirements/{base,ai,agents,dev}.txt`, **every dependency the whole plan needs added now**: `anthropic`, `sentence-transformers`, `beautifulsoup4`, `playwright`, `pandas`, `Pillow`, `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `shapely`, `httpx` — **Defect 15**
- [ ] Frontend: `expo-task-manager`, `expo-background-fetch`; `types/index.ts` → `types/`; services de-barrelled; all route names + placeholder screens pre-created in `navigation/`
- [ ] Delete `theme/colors.ts` and `theme/darkTheme.ts`; one theme source — **Defect 16 (partial)**
- [ ] Celery schedule registry; delete the two phantom beat entries
- [ ] `docker-compose.yml`: make the local OSRM service usable (document the Bangladesh OSM extract + `osrm-extract` / `osrm-partition` / `osrm-customize` steps)

### Phase 0 exit criteria

- [ ] Fresh clone → `seed.sh` → `check.sh` passes on both machines
- [ ] `RISK_SURFACE_IMPL=seeded` serves 200 fixture flags through the `RiskSurface` protocol
- [ ] Every stub satisfies its protocol, proven by a test
- [ ] CI green, all five jobs, `handoff-log` verified by a deliberately log-less test PR
- [ ] Both of us can state the §2 relay rules without rereading them

---

# PHASE 1 — Stabilization & Debt Paydown

**S05 – S08.** Goal: zero known defects from §1 carried forward. Every sprint after this builds on code that does what it says.

---

## S05 — Backend defects

**Suggested owner:** Arafat. **Prototype:** routing works against the local OSRM container, with a measured latency number.

- [ ] **Defect 2:** Fix `speech_service`. Either restore `pydub` + document the ffmpeg dependency, or (preferred) drop format conversion and send the device's m4a/webm straight through with the correct `RecognitionConfig` encoding. Add a test that would have caught the `NameError`.
- [ ] **Defect 6:** Honour `avoid_high_crime_zones` and `max_crime_score`, or delete them from the schema. Do not keep accepted-and-ignored parameters.
- [ ] **Defect 7:** `OSRMClient` — read `OSRM_BASE_URL`, prefer the local container, fall back to the demo server with a loud warning, add the `foot` profile alongside `driving`, use OSRM's own `duration` instead of a flat 30 km/h.
- [ ] **Defect 8:** Replace the Python double loop with a PostGIS query (`ST_DWithin` against the path as a `LINESTRING`). **Benchmark before and after on a full-overview Dhaka route; record both numbers in `PROGRESS.md`.**
- [ ] **Defect 9 (code half):** delete `models/user.py`'s table and the `sos.py` auto-provisioning block
- [ ] **Defect 10 (backend half):** `/geo/search` + `/geo/reverse` proxy with a compliant `User-Agent`, Redis cache, and rate limit. **First real use of Redis.**
- [ ] **Defect 17:** Replace `police_stations.csv` placeholder contacts with real data. The `POLICE_ROUTING_ENABLED` gate now exists and defaults off (defect 31), so this is no longer urgent — but the flag stays off until the CSV is real, which means **police routing is currently not a feature**, and the README should not claim it.
- [ ] **Defect 35:** Persist `SOSIncident` on trigger, and keep the evidence. Measured after a verified-delivered SOS: `sos_incidents` held **0 rows**, and `_save_video` writes the clip to a temp file, attaches it, then `os.remove`s it. So the README's "incident logged in database" is false and the only copy of the video is in the recipient's inbox. Needs: a row written before the send (so a failed send is still recorded), the clip uploaded to Storage with a `media_ref`, and a status field that can distinguish delivered / failed / cancelled / false alarm.
- [ ] **Cleanup:** delete `crime_ai.py` (dead duplicate). Delete or implement the `auth.py` / `crimes.py` / `users.py` / `tracking.py` stubs per ADR 0001 — a `pass` endpoint in a public API is worse than no endpoint.

---

## S06 — AI vision: multi-person pose & evidence

**Suggested owner:** Nakib. **Prototype:** a two-person photo produces a real interaction analysis for the first time.

- [ ] **Defects 29 + 5:** Port `pose_service.py` from the removed `mp.solutions.pose` namespace to `mediapipe.tasks.python.vision.PoseLandmarker`. Pose analysis is **not running at all** today — the import fails and `pose_service` is left `None`, which is why `pose_analysis` is `null` on every response. `PoseLandmarker` takes a `num_poses` option, so the multi-person fix (defect 5) comes with the port rather than needing a YOLO-crop loop. **This makes the interaction logic and the harassment profile reachable for the first time since they were written.**
- [ ] **Defect 30:** Close the vocabulary gap. 11 of the 21 object signals the decision engine scores against are not COCO classes, so `harassment`, `theft` and `vandalism` cannot currently be returned by any input. Pick one per signal: find a model that emits it, re-express the gate in terms of something reachable, or delete the signal. **A gate that cannot fire is worse than no gate — it reads as coverage.** `scripts/eval_crime_vision.py` prints the reachability table; it must show zero `NEVER` rows at the end of this sprint.
- [ ] Grow `backend/data/eval/crime_vision/` to the README's target (≥10 per class, ~50/50 negatives, real Bangladesh scenes) **before** changing pipeline behaviour, then `--save-baseline` and treat every later change as `--compare`
- [ ] Fixtures: two-person, three-person, single-person, no-person
- [ ] **Defect 13:** Persist report evidence. Supabase Storage bucket + `crime_reports.media_refs`; the analysed photo is kept, not discarded.
- [ ] Verify the fusion engine's confidence calibration still behaves with real multi-person input — the weights were tuned when interaction was always `none`, and the thresholds have never once been exercised against a live pose
- [ ] **Open decision (deferred to the baton holder):** whether the reasoning layer stays local-only, becomes local + Claude vision, or Claude-only. Not answerable until the eval set exists — that is the whole point of building it first.

---

## S07 — Frontend defects

**Suggested owner:** Arafat. **Prototype:** map markers correctly coloured; one SOS path from both screens; no background audio recording.

- [ ] **Defect 3:** `CRIME_COLORS` → lowercase keys matching the DB enum. Derive the map from the contract type so it cannot drift again.
- [x] **Defect 4:** ~~Delete the `HomeScreen` voice-monitoring block entirely.~~ **Done in S01** — it imported `expo-av`, which SDK 57 removed (defect 37), so deleting it was the cheapest way through the upgrade. Real hot-word detection is still S18, on an on-device wake-word engine.
- [ ] Remove the ~30 lines of stale-closure deliberation left in `HomeScreen`, and fix the shake threshold comment (says 3.5 g, code is 6.0 — pick one, justify it with a measurement)
- [ ] **Defect 11:** One score scale. **0–100 everywhere, higher = safer, named `safety_score`.** Delete the 0–10 `crime_score` and the percent variants. Add a test.
- [x] **Defect 12:** ~~De-duplicate `EmergencyContact`~~ — done in S01b; re-point at the contract type when S03 lands.
- [ ] **Defect 14:** Make `MapScreen`'s SOS button call the same path as `HomeScreen`'s. Extract one `useSOS()` hook; both screens consume it.
- [ ] **Defect 16:** Export `routeService` from the services barrel.
- [ ] **Defect 10 (frontend half):** route all Nominatim traffic through the S05 backend proxy.
- [ ] Surface the evidence photos S06 started persisting

---

## S08 — Frontend refactor

**Suggested owner:** Nakib. **Prototype:** the reporting flow works identically, from components a quarter the size.

- [ ] Decompose `AddReportScreen.tsx` (2,220 lines) into `features/reporting/` — `CategoryPicker`, `AiAnalysisPanel`, `LocationPicker`, `IncidentDateTime`, `useReportDraft`. The AI panel alone is ~580 lines of JSX; it becomes its own component with its own tests.
- [ ] Move all existing screens into the `features/` layout from §5
- [ ] Jest: `useSOS`, `useReportDraft`, score-scale conversion, `AiAnalysisPanel` rendering of each fusion state (crime / no-crime / degraded / error)
- [ ] `frontend/CLAUDE.md` — conventions, feature-folder rules, contract mirror location
- [ ] `tsc --noEmit` clean, `eslint` clean

### Phase 1 exit criteria

- [ ] Every defect in §1 is fixed, deleted, or has a `PROGRESS.md` entry explaining why it is deferred
- [ ] Fresh clone builds and runs on both machines, backend and app
- [ ] One score scale across the whole stack, verified by a test
- [ ] No endpoint returns `pass`
- [ ] Benchmark recorded: path risk scoring before vs. after the PostGIS rewrite

---

# PHASE 2 — Risk Surface & Safety Routing

**S09 – S13.** Goal: the colloquial-Bangla geocoding problem is solved (the concept document's stated primary technical risk), and routing/map run on the risk-flag contract end to end.

Sequenced geocoding-first because it is the highest-risk item in the whole project. If it fails, we want to know in Phase 2, not Phase 5.

---

## S09 — Ingestion framework

**Suggested owner:** Arafat. **Prototype:** `python -m app.ingestion.run` pulls real articles from three sites into `raw_documents`.

- [ ] `ingestion/sources/base.py` defines `Source.fetch() -> list[RawDocument]`
- [ ] `fetcher.py` owns politeness: `robots.txt`, per-host rate limits, conditional GET, exponential backoff, persistent cache. **Nothing downstream ever fetches directly.**
- [ ] First three sources — Bangla news sites with stable markup. One module each; adding a fourth must require touching only one new file.
- [ ] `ingestion/store.py` — `RawDocument` persistence, idempotent on `doc_id`
- [ ] **Start the corpus** (background activity): target ≥500 articles, ≥200 with hand-annotated location references. This is the eval set for everything in Phases 2, 3 and 5 — a first-class deliverable, not a by-product.
- [ ] `backend/app/agents/CLAUDE.md` — agent conventions, contract locations, the registry pattern

---

## S10 — Bangla gazetteer

**Suggested owner:** Nakib. **Prototype:** `gazetteer.lookup("মিরপুর ১০ গোলচত্বর")` returns coordinates.

**Build the schema and the review workflow before bulk entry.** Bulk entry continues as a background activity after this sprint.

- [ ] `data/gazetteer/` schema — Bangla landmark names → coordinates + radius, with provenance and a review flag per entry
- [ ] Seed the pilot zone by hand: `golchattar`, `mor`, `chourasta`, `bazar`, `stand`, `more`, numbered sectors, and the Mirpur / Jatrabari / Shahbagh-class landmarks
- [ ] Fuzzy matching: transliteration variants, common misspellings, Bangla ↔ Latin script
- [ ] `scripts/gazetteer_review.py` — add, review, and audit entries without hand-editing JSON
- [ ] Lookup API + unit tests on the annotated slice of the corpus

---

## S11 — Geolocation Agent

**Suggested owner:** Arafat. **Prototype:** `scripts/eval_geolocation.py` prints a real accuracy number against the annotated corpus.

- [ ] Cascade, cheapest first:
  1. Exact + fuzzy gazetteer match
  2. LLM disambiguation (`MODEL_JUDGMENT`, `effort="high"`) with the relevant gazetteer slice in a **cached** system prompt
  3. Nominatim via the S05 proxy
  4. `method="unresolved"` → **the incident is discarded** (§4 invariant, concept doc §12)
- [ ] `tests/invariants/test_unresolved_never_guessed.py`
- [ ] **Accuracy harness** — `scripts/eval_geolocation.py`: top-1 accuracy, median error in metres, unresolved rate, broken down per method. **Record the baseline in `PROGRESS.md`; every later change reports a delta against it.**
- [ ] Replace `StubGeolocationAgent` by binding the real one
- [ ] Lands in `app/agents/geolocation/` with `cron` declared in-module

**Sprint exit:** ≥80% top-1 accuracy within 500 m on the annotated corpus; unresolved rate <15%; zero guessed coordinates.

---

## S12 — Risk-aware routing

**Suggested owner:** Nakib. **Prototype:** request a route across Dhaka; the top result demonstrably avoids a seeded flag.

Runs entirely on `RISK_SURFACE_IMPL=seeded`. No dependency on S09–S11.

- [ ] `routing/scorer.py` — path scoring over the `RiskSurface` protocol
- [ ] Multi-route generation — OSRM alternatives, each scored, ranked by a composite that is **documented and tunable in settings**, not a magic constant
- [ ] `LegacyRegionalSurface` — wrap the existing `crime_risk_model.json` behind the protocol as the cold-start fallback. Nothing else in routing knows it exists.
- [ ] Verify `RISK_SURFACE_IMPL=seeded` and `=legacy` both work with **zero changes in `routing/`** — if either needs one, fix the contract now
- [ ] Integration test: seeded flag on a known corridor ⇒ top route avoids it
- [ ] `backend/app/routing/CLAUDE.md`

---

## S13 — Explanations & risk map

**Suggested owner:** Arafat. **Prototype:** the concept document's §6 worked example, on a phone, end to end.

- [ ] `routing/explain.py` — plain-language explanations built *only* from `RiskFlag.mobility_statement` + source count. Concept doc's target: *"fire reported near Bangshal, roads likely blocked, three sources."* Template-driven, no LLM in the request path, framing guard applied.
- [ ] `features/risk-map/` — flag overlay with radius circles, severity colour, **a clear visual distinction between `confirmed` and `unconfirmed`** (a product requirement from concept doc §9, not a style choice), tap-for-explanation
- [ ] `features/routing/` — route comparison: safety, distance, duration, the explanation, and *why this route over that one*
- [ ] Integration test: seeded flag ⇒ route avoids it ⇒ the explanation names it

### Phase 2 exit criteria

- [ ] The concept document's §6 worked example is reproducible end to end against seeded data, including the explanation text
- [ ] Geolocation accuracy baseline recorded
- [ ] Real Geolocation Agent bound; `routing/` required **zero** changes across all three surface implementations
- [ ] An ingestion run produces persisted `RawDocument`s from three sources

---

# PHASE 3 — Live Risk & Verification

**S14 – S18.** Goal: real risk, extracted from real sources, verified, reaching a real user's phone.

---

## S14 — Live Risk Agent

**Suggested owner:** Nakib. **Prototype:** a scheduled run turns this morning's news into candidate flags on the map.

- [ ] Live Risk Agent (`cron`: every 10–15 min). Poll sources → `LLMClient.extract(schema=ExtractedIncident, model=MODEL_BULK)` → geolocate → emit candidate flags. **Idempotent:** re-running over the same documents must not duplicate.
- [ ] `prompts/live_risk_v1.md`
- [ ] Extraction eval against the S09 corpus: precision and recall per `IncidentKind`. **A prompt change without an eval delta is not reviewable.**
- [ ] Cost per run recorded, with cache-hit rate

---

## S15 — Rumour Guard

**Suggested owner:** Arafat. **Prototype:** four outlets reporting one fire collapse into one flag, promoted to `confirmed`.

The subtlest correctness requirement in the system.

- [ ] **Semantic dedup** — `sentence-transformers` embeddings + a tuned similarity threshold, so four outlets reporting one fire collapse to one `event_key` rather than four corroborations. Gets its own labelled test set of known-duplicate clusters.
- [ ] **Promotion policy** — `unconfirmed` → `confirmed` requires ≥2 *independent* `source_id`s. Independence is explicit: syndicated wire copy is one source. Maintain a source-independence map.
- [ ] **Unconfirmed tier** — published at reduced weight, visibly distinct. Never suppressed, never promoted silently.
- [ ] `tests/invariants/test_single_source_never_confirmed.py` (§4)
- [ ] Replace `StubRumourGuard`
- [ ] **Flip `RISK_SURFACE_IMPL` to `db`** and confirm routing and the map carry real agent output

**Sprint exit:** on a replayed 48-hour window of real articles, ≥90% flag precision (concept doc §10), and dedup collapsing known clusters correctly.

---

## S16 — Push notifications

**Suggested owner:** Nakib. **Prototype:** a real phone gets a push with a real mobility statement.

- [ ] Finish `notification.service.ts`; EAS project id; server-side send
- [ ] Per-category user preferences
- [ ] **Alert fatigue is a listed risk (concept doc §12):** conservative thresholds and a documented rate cap per user per hour, from day one, with a test
- [ ] Every alert carries its explanation and source count

---

## S17 — Background location & geofence alerting

**Suggested owner:** Arafat. **Prototype:** walk toward a seeded flag, get a notification before reaching it.

- [ ] `expo-task-manager` + `expo-background-fetch`, battery-conscious. The `app.json` permissions have been declaring this capability with nothing behind it since the beginning.
- [ ] Retention window from the S03 registry applied to stored locations
- [ ] Geofence alerting — crossing into an active flag radius notifies with the mobility statement and source count. Debounced; no repeat for the same flag.
- [ ] Measured battery impact recorded

---

## S18 — Trips & hot words

**Suggested owner:** Nakib. **Prototype:** start a trip, see live progress, complete it.

- [ ] `app/trips/` + migration: start, destination, planned route, checkpoints, status. **Journey Guardian's substrate, built a phase early on purpose** — S22 inherits a working trip model instead of building one under time pressure.
- [ ] `features/journey/` — start/end a trip, live progress, ETA
- [ ] **Hot words, done properly.** Delete the Supabase-only dead loop. On-device wake-word detection, user-configurable phrases, no continuous upload. **If no library meets the privacy bar, ship a prominent manual SOS and say so in `PROGRESS.md` — do not ship a fake.**
- [ ] `/voice/analyze` either works against real hot words or is removed

### Phase 3 exit criteria

- [ ] `RISK_SURFACE_IMPL=db` carries real agent output into routing and alerts
- [ ] Flag precision measured on real data and recorded
- [ ] Alert rate cap verified by test
- [ ] No continuous audio upload anywhere in the app
- [ ] A real device receives a push within 60 s of a flag appearing on its corridor

---

# PHASE 4 — Scoring, Decay & Journey Guardian

**S19 – S23.** Goal: the map breathes — risk appears, ages, and disappears unattended — and the guardian watches a trip without crying wolf.

---

## S19 — Decay engine

**Suggested owner:** Arafat. **Prototype:** a flag's severity visibly decreasing over simulated time.

- [ ] `scoring/decay.py` — `severity(t) = severity_0 · 0.5^((t − observed_at)/half_life) · time_profile[hour]`. Pure, total, exhaustively unit-tested, boundaries included.
- [ ] Per-kind defaults from §6.1, in one reviewed table
- [ ] **Time-of-day profiles** — concept doc §5.6. Derive from the chronic corpus where data supports it; hand-set with a written rationale where it does not. **Document which is which.**

---

## S20 — `DbRiskSurface` & expiry

**Suggested owner:** Nakib. **Prototype:** leave the system running overnight; stale flags are gone in the morning with no intervention.

- [ ] `DbRiskSurface` — decay applied **at query time in PostGIS**, not in Python
- [ ] It is in the request path, so it gets a latency budget: **`score_path` p95 < 150 ms** on real flag volume. Benchmark on a full-overview Dhaka route; record the number.
- [ ] Expiry job — flags past `expires_at` become `expired` and leave the surface. Concept doc §6: *"No manual cleanup, no stale red zone."*
- [ ] `tests/invariants/test_every_flag_decays.py`, `test_no_flag_outlives_expiry.py` (§4)

**Sprint exit:** the §6 worked example runs on wall-clock time — flag appears at 14:26 unconfirmed, promotes at 14:31, decays below threshold and disappears by 17:45, unattended.

---

## S21 — Admin observability

**Suggested owner:** Arafat. **Prototype:** one page that tells you whether the agent fleet is healthy.

- [ ] Flag counts by status / kind / age
- [ ] Agent run history with status, duration, items in/out, errors
- [ ] LLM cost and cache-hit rate per agent run
- [ ] Geolocation accuracy trend against the committed baseline
- [ ] This is for us, not for users — a simple authenticated page is enough

---

## S22 — Journey Guardian: anomaly detection

**Suggested owner:** Nakib. **Prototype:** a deliberate off-route detour is detected, and a jam is correctly *not* flagged.

The most safety-sensitive component in the system. Concept doc §5.7 and §9 are requirements, not suggestions.

- [ ] Anomaly detection — unexpected stop, off-route deviation, no movement
- [ ] **Check context before acting:** live traffic, the user's own route history, time of day. The common case is a jam, a detour, or a dead battery.
- [ ] Runs against the S18 trip model
- [ ] Replay tests over recorded real trips from both of our commutes

---

## S23 — Journey Guardian: graded escalation

**Suggested owner:** Arafat. **Prototype:** a full escalation chain, exercised end to end, in a controlled test.

- [ ] `trips/escalation.py` — the state machine:
  `normal → anomaly_detected → check_in_sent → check_in_repeated → contacts_notified → full_sos`
- [ ] Every transition past `check_in_sent` requires a **recorded non-response with a timestamp.** No step may be skipped. An explicit state machine, not conditionals scattered through a service.
- [ ] Low-friction check-in — one-tap "I'm fine" from the notification, no app open required
- [ ] `tests/invariants/test_escalation_requires_nonresponse.py`, `test_no_escalation_skips_a_step.py` (§4)
- [ ] `features/journey/` guardian UI — current state, escalation history, per-user sensitivity
- [ ] **Start the self-trial** (background activity): instrument false check-ins and run it on both of our real commutes. Concept doc §10 targets <1 per user per week. **Two weeks of data before anyone outside the two of us sees this feature.**

### Phase 4 exit criteria

- [ ] Decay runs unattended; no stale flags after 72 h of continuous operation
- [ ] `score_path` p95 < 150 ms on real flag volume
- [ ] Journey Guardian self-trial running, with data accumulating
- [ ] Admin page shows a healthy fleet at a glance

---

# PHASE 5 — Historical, Forward-Looking & Casework

**S24 – S29.** Goal: all eight agents live, and the loop closes — incidents become official records that improve the map.

The Guardian self-trial from S23 continues in the background through this phase. Do not ship the Guardian until it has its two weeks.

---

## S24 — Chronic Risk Agent

**Suggested owner:** Nakib. **Prototype:** a nightly run that surfaces real repeat blackspots from archives.

- [ ] Chronic Risk Agent (`cron`: nightly). Archive mining at scale for repeat blackspots over months.
- [ ] **Use the Batch API** — 50% cost on latency-insensitive work — with `MODEL_BULK`
- [ ] Blackspot aggregation — spatial clustering of historical incidents into persistent flags (`CHRONIC`, 90-day half-life)
- [ ] Must **reconcile with the existing police-statistics regional model rather than double-counting it**

---

## S25 — Legacy surface retirement & cost model

**Suggested owner:** Arafat. **Prototype:** a documented comparison showing chronic flags match or beat the legacy model.

- [ ] Compare `LegacyRegionalSurface` against chronic flags on the pilot zone; record the comparison
- [ ] Retire or subsume the legacy surface, with the justification written down
- [ ] **Cost model:** measured ৳/day for all perception agents at pilot-zone volume, extrapolated to city scale
- [ ] Per-agent budget caps in settings

---

## S26 — Scheduled Risk Agent

**Suggested owner:** Nakib. **Prototype:** tomorrow's risk map, today.

**The concept document's clearest differentiator — no competing product looks forward.**

- [ ] Scheduled Risk Agent (`cron`: daily, forward-looking). Announcements of processions, shutdowns, exam days, gatherings → tomorrow's risk map.
- [ ] **Forward-dated flags** — `observed_at` in the future, activating and expiring on schedule. **Verify the decay engine handles this**; it was designed for past events.
- [ ] **Mobility framing matters most here.** Processions are surfaced as "road blocked, expect delay" and never characterised. `assert_mobility_safe()` runs on every one of these flags, and this agent gets **its own framing test set**.

---

## S27 — Casework Agent

**Suggested owner:** Arafat. **Prototype:** a General Diary draft in Bangla, from a real report, with the correct thana.

**This is the concept document's closed loop** — the thing no competitor does.

- [ ] `app/casework/gd_service.py` — drafts the formal General Diary in proper Bangla from an incident report. `MODEL_JUDGMENT`, `effort="high"`, structured output into the `GDDraft` contract.
- [ ] **Thana identification** — correct police station from incident coordinates and jurisdiction, not just nearest-by-distance
- [ ] **Evidence bundling** — report, photos, geolocation, timestamps, into a reviewable document
- [ ] `prompts/casework_v1.md`, versioned

---

## S28 — Casework UI & Bangla review

**Suggested owner:** Nakib. **Prototype:** five drafts, reviewed and approved by a native Bangla speaker.

- [ ] `features/casework/` — draft review, edit, approve, export (PDF), submission tracking
- [ ] **Mandatory human review before submission.** A generated legal document is a draft until a person approves it. **It must be structurally impossible to submit unreviewed** — enforce it in the state machine, not the UI.
- [ ] **Bangla quality review** — a native-speaker review pass on ≥20 drafts across incident types before this ships to anyone. An LLM-drafted legal filing in imperfect Bangla damages users and the project.
- [ ] `CASEWORK_ENABLED` stays `false` until that review passes

---

## S29 — Crowd verification

**Suggested owner:** Arafat. **Prototype:** an unconfirmed flag promoted by nearby users.

- [ ] Request confirmation from users physically near an unconfirmed flag (concept doc §5.5)
- [ ] Rate-limited, privacy-preserving, abuse-resistant: proximity proof, one request per user per flag, reputation weighting
- [ ] Asynchronous by design — it is an abuse surface, and async is the defensible version
- [ ] This closes the concept document's "Deferred to roadmap" list

### Phase 5 exit criteria

- [ ] All eight concept-document agents exist, scheduled, and observable
- [ ] Chronic flags cover the pilot zone; legacy surface retired or justified
- [ ] Forward-dated flags activate and expire correctly
- [ ] GD drafts pass native-speaker review
- [ ] Guardian self-trial complete: <1 false check-in per user per week
- [ ] Measured ৳/day for the full agent fleet

---

# PHASE 6 — Production Hardening

**S30 – S37.** Nothing new. Everything made trustworthy.

---

## S30 — Privacy & retention enforcement

**Suggested owner:** Nakib. **Prototype:** data past its retention window is verifiably gone.

- [ ] The nightly purge against the S03 registry: location history, raw documents, expired flags, trip traces. §4 invariant goes from registry to enforced.
- [ ] Written data inventory: what we hold, why, for how long, who can read it
- [ ] A real privacy policy — app stores require one anyway
- [ ] `tests/invariants/test_retention_actually_deletes.py`

---

## S31 — Agent resilience & chaos testing

**Suggested owner:** Arafat. **Prototype:** kill any single dependency; the rest of the fleet keeps running.

- [ ] Every agent fails independently without degrading the others (concept doc §5)
- [ ] Chaos-test it: kill the LLM, kill a source, kill PostGIS, corrupt a feed. Assert the others keep running.
- [ ] **Source abstraction proof** — concept doc §12 lists social-media access restriction as a risk. Remove a source entirely and confirm the system degrades rather than breaks.

---

## S32 — Observability & cost controls

**Suggested owner:** Nakib. **Prototype:** the §10 success metrics, live on a dashboard.

- [ ] Sentry (already in the stack, unused), structured logging, flag lifecycle metrics
- [ ] **LLM cost controls** — per-agent budget caps enforced, cache-hit monitoring (`usage.cache_read_input_tokens`), token accounting per run, alerting on anomalous spend. **A silent cache invalidator in a nightly batch job is expensive; monitor it.**
- [ ] Concept doc §10 success metrics instrumented: time-to-alert, flag precision, false check-in rate, GD completions, alternative-route acceptance

---

## S33 — Load testing

**Suggested owner:** Arafat. **Prototype:** pilot-zone volume and 10× it, with numbers.

- [ ] Pilot-zone volume and 10×
- [ ] Identify and fix the first three bottlenecks
- [ ] Record the ceiling

---

## S34 — Offline capability & battery

**Suggested owner:** Nakib. **Prototype:** put the phone in airplane mode; the app still helps.

- [ ] Cached map tiles, last-known risk surface, queued reports, queued SOS. **Safety apps fail at the worst time if they need connectivity.**
- [ ] **Battery audit** — measured drain with background tracking on. The README's 5%/hour target is currently unverified; measure it, then meet it or restate it.

---

## S35 — Performance & accessibility

**Suggested owner:** Arafat. **Prototype:** budgets set, measured, met.

- [ ] Map with hundreds of flags, route calculation latency, cold start — set budgets, measure, fix
- [ ] Screen reader support, contrast, touch targets, scalable text. **A safety app that excludes users with disabilities fails its own premise.**

---

## S36 — Bangla localisation & SMS fallback

**Suggested owner:** Nakib. **Prototype:** the whole app in Bangla; an SOS that works with no data connection.

- [ ] Full `bn` UI, not just Bangla content. Concept doc §13 claims "built for Bangla"; the current app is English-only.
- [ ] SMS fallback — CloudWaveBD primary, Twilio fallback. **Configured since the beginning, never implemented, and it is the channel that works when data does not.**

---

## S37 — Store readiness

**Suggested owner:** Arafat. **Prototype:** signed builds, both platforms, ready to submit.

- [ ] iOS and Android release builds
- [ ] Store listings, screenshots, permission rationales, review notes explaining background location and the safety use case
- [ ] Crash-free rate instrumented; target >99.5%

### Phase 6 exit criteria

- [ ] Retention job verified: data past its window is actually gone
- [ ] Agent fleet survives chaos testing
- [ ] All §10 success metrics instrumented and reporting
- [ ] Release builds pass internal review on both platforms
- [ ] Battery and performance budgets met and recorded

---

# PHASE 7 — Pilot & Operate

**S38 onward.**

---

## S38 — Pilot preparation

**Suggested owner:** Nakib.

- [ ] **Operational runbook** — agent failure, bad flag, LLM outage, cost spike, data incident. Who does what, with what command.
- [ ] **On-call rotation.** Relay makes this natural: a week each, with an explicit "neither of us is available" plan.
- [ ] Zone selection — one Dhaka zone where the gazetteer is dense and flag precision is proven. **Not city-wide** (concept doc §11).

## S39 — Pilot launch

**Suggested owner:** Arafat.

- [ ] Recruit 20–50 pilot users; weekly structured feedback
- [ ] **Flag-precision review loop** — sample confirmed flags weekly, label, feed corrections back into prompts and thresholds

## S40+ — Operate & expand

- [ ] **Institutional engagement** (concept doc §10) — aggregated anonymised blackspot data to traffic authorities and city corporations. **Only after precision is proven;** a bad blackspot report to an authority is worse than none.
- [ ] Expansion — second Dhaka zone, then Chattogram, then district towns. **Gazetteer density is the gate, not engineering capacity.**

---

## 8. Risk Register

Concept document §12 risks, plus the delivery risks relay introduces.

| Risk | Severity | Mitigation | Sprint |
|---|---|---|---|
| **Bangla landmark geocoding fails** (doc's primary technical risk) | Critical | Sequenced first in Phase 2. Hand-seeded gazetteer; LLM fallback; **unresolvable discarded, never guessed**; accuracy harness with a committed baseline | S10–S11 |
| **False flags from rumour** | Critical | Multi-source requirement; semantic dedup with its own labelled test set; unconfirmed tier; crowd verification; precision measured on replayed real data | S15, S29 |
| **Political or communal misreading of flags** | Critical | Mobility-only framing enforced in code (`framing.py` is the sole writer), its own test set for the Scheduled Risk Agent, invariant test on every PR | S03, S26 |
| **Journey Guardian false positives** | High | Context check before acting; graded escalation with recorded non-response; two-week self-trial before any external user; <1/user/week measured | S22–S23 |
| **Alert fatigue** | High | Conservative thresholds; documented per-user rate cap from day one; explanation attached to every alert | S16 |
| **Social media access restrictions** | High | Source-agnostic ingestion interface; proven by removing a source and confirming graceful degradation | S09, S31 |
| **Stale risk accumulation** | High | Mandatory `half_life_hours` with a schema `CHECK`; decay at query time; automatic expiry; invariant tests | S02, S19–S20 |
| **LLM cost at scale** | Medium | Sonnet for bulk extraction, Opus for judgment; prompt caching with hit-rate monitoring; Batch API for nightly archive work; per-agent budget caps; measured ৳/day | S25, S32 |
| **GD drafts are legally or linguistically wrong** | High | Mandatory human review, structurally enforced; native-speaker review of ≥20 drafts before release; `CASEWORK_ENABLED=false` until then | S28 |
| **Baton drops — nobody holds the trunk** | **High (relay-specific)** | If you cannot take your turn within 48 h of it being free, say so and the other takes a second turn. An idle trunk is the one failure mode relay has that parallel does not. | §3.2 |
| **Context lost at handoff** | **High (relay-specific)** | `PROGRESS.md`, enforced by the `handoff-log` CI job. Agents read it first, write it last. | §3.3 |
| **Broken trunk handed over** | **High (relay-specific)** | The Prototype Gate (§3.4). Cut scope rather than hand over broken. The receiving person runs `check.sh` before starting and refuses a red baton. | §3.4 |
| **Serialized velocity** | Medium (accepted) | Inherent to relay and chosen deliberately — our hours don't overlap, so parallel bought nothing. §11 sizes the project honestly on one person's throughput. | — |
| **Background activities starve** | Medium (relay-specific) | Corpus, gazetteer and the Guardian trial are explicitly off-baton (§3.6) so the person *not* holding it has useful work | §3.6 |
| **Scope creep from a strong concept doc** | Medium | Phase exit criteria gate progress; "Deferred to roadmap" stays deferred until Phase 5 | all |

---

## 9. Appendix A — Environment variables

All belong in `.env.example` as they are introduced, so neither of us is ever missing a key after a handoff.

Everything under *live now* is already set on both `.env` files and is read by
running code. Everything below it is declared ahead of the sprint that uses it.

```bash
# =========================================================================
# live now (Phase 0) -- the app does not work without these
# =========================================================================

# --- Supabase, backend ---
SUPABASE_URL=                      # REQUIRED: jwks.py fetches signing keys from
                                   # {SUPABASE_URL}/auth/v1/.well-known/jwks.json
SUPABASE_SERVICE_ROLE_KEY=         # server-side only; bypasses RLS
DATABASE_URL=                      # postgresql+asyncpg://...  port 5432, NOT 6543
JWT_SECRET_KEY=                    # legacy HS256 fallback only; ES256 needs no secret

# --- Supabase, frontend ---
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
EXPO_PUBLIC_API_BASE_URL=          # http://<LAN-IP>:8000/api/v1 -- run.ps1 detects it

# --- SMTP (S01) ---
# REQUIRED FOR SOS. email_service.py is the only alert channel, so with these
# empty an SOS reports success to the user and delivers nothing. Gmail needs an
# App Password, not the account password.
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
FROM_EMAIL=

# =========================================================================
# declared ahead of use
# =========================================================================

# --- LLM (S04) ---
ANTHROPIC_API_KEY=                 # or use `ant auth login`
LLM_MODEL_JUDGMENT=claude-opus-5-5
LLM_MODEL_BULK=claude-sonnet-5-5
LLM_MONTHLY_BUDGET_USD=            # hard cap, S32

# --- Risk surface (S04) ---
RISK_SURFACE_IMPL=seeded           # seeded | legacy | db

# --- Agents (S09+) ---
AGENTS_ENABLED=                    # comma-separated; empty = all
LIVE_RISK_CRON=*/12 * * * *
CHRONIC_RISK_CRON=0 3 * * *
SCHEDULED_RISK_CRON=0 5 * * *
INGESTION_USER_AGENT=Meridian/1.0 (+https://meridian.app/bot)

# --- Rumour Guard (S15) ---
# 0.82 was declared here before anything measured it. MEASURED in D05 against
# all-MiniLM-L6-v2 on the extraction model's English summaries, 0.82 merges 1 of 18
# known duplicate pairs -- the guard would be a no-op. 0.72 is the highest threshold
# with zero false merges on data/eval/dedup/clusters.json. Re-run
# `scripts/eval_dedup.py` after any change to DEDUP_MODEL or to what is embedded.
DEDUP_SIMILARITY_THRESHOLD=0.72
DEDUP_WINDOW_HOURS=6
DEDUP_MODEL=sentence-transformers/all-MiniLM-L6-v2
MIN_SOURCES_FOR_CONFIRMED=2

# --- Routing (D06) ---
# http://osrm:5000 inside the compose network. An unset or empty value falls back to
# the public demo server and warns on every request -- that is defect 7, and it is
# loud rather than silent.
OSRM_BASE_URL=http://osrm:5000

# Route scoring. S12 asks for a composite "documented and tunable in settings, not a
# magic constant"; the reasoning for each of these is in app/core/config.py and the
# arithmetic in app/routing/scorer.py.
ROUTE_CORRIDOR_RADIUS_M=150     # how far from the road a flag still counts
ROUTE_SAFETY_WEIGHT=0.7         # share of the ranking that is safety, rest is duration
ROUTE_PENALTY_FALLOFF=0.5       # geometric falloff per additional flag, worst first
ROUTE_DETOUR_TOLERANCE=1.0      # 1.0 = a route twice as long scores 0 on duration
ROUTE_CHRONIC_WEIGHT=0.35       # MEASURED. At 1.0 every Dhaka route scored 16.7/100
ROUTE_CONGESTION_FACTOR=0.35    # CALIBRATION, not a measurement. Check it against a
                                # journey you know: OSRM gives free-flow (54.8 km/h
                                # measured across central Dhaka) because an OSM extract
                                # has no traffic data at all.

# Nominatim proxy (D06, defect 10). A genuine identifying agent is a policy
# requirement, not a nicety.
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
NOMINATIM_USER_AGENT=Meridian/1.0 (+https://github.com/ArafatBytes/Meridian)
NOMINATIM_CACHE_TTL_SECONDS=86400
OSRM_PROFILE=driving
ROUTE_SAFETY_WEIGHT=0.7

# --- Alerting (S16) ---
MAX_ALERTS_PER_USER_PER_HOUR=3
EXPO_PROJECT_ID=

# --- Journey Guardian (S23) ---
GUARDIAN_CHECKIN_TIMEOUT_SECONDS=300
GUARDIAN_ESCALATION_STEPS=3

# --- Privacy (S03 registry, S30 enforcement) ---
LOCATION_RETENTION_DAYS=30
RAW_DOCUMENT_RETENTION_DAYS=180
TRIP_TRACE_RETENTION_DAYS=14

# --- Feature flags ---
POLICE_ROUTING_ENABLED=false       # until real contact data lands (S05)
CASEWORK_ENABLED=false             # until native-speaker review passes (S28)
```

---

## 10. Appendix B — Definition of Done

A task is done when all of these are true. No exceptions, including for "small" changes.

1. Code merged to `main` via a squash-merged PR
2. Unit tests for the happy path and the failure paths
3. `ruff` + `mypy` clean (backend) or `tsc --noEmit` + `eslint` clean (frontend)
4. Any §4 invariant it touches has a passing test
5. New env vars in `.env.example` **and** §9
6. New contracts mirrored in `frontend/src/types/contracts/`, with all consumers updated **in the same sprint**
7. Migrations are forward-only and run clean on a fresh DB via `./scripts/seed.sh --fresh`
8. If it is in a request path, it has a measured latency number in `PROGRESS.md`
9. If it calls an LLM, it has an eval delta in `PROGRESS.md`
10. The checkbox in this file is ticked, in the commit that did the work
11. **The `PROGRESS.md` entry is written and `CURRENT STATE` is updated** (Rule 3)

---

## 11. Appendix C — Sprint sequence

One sprint = one relay turn = one person's stretch of work ending in a push. Typically 3–6 Claude Code sessions, roughly a week of part-time work.

Owners alternate as a default. Swap freely — `PROGRESS.md` records who actually took each one.

**Where we actually are:** S00 and S01 are done (S01 grew three unplanned
addenda — S01b dockerisation, S01c malware removal, S01d the SDK 57 upgrade and
real auth). The app has run end to end on a device. **S02 is next.**

| # | Sprint | Phase | Suggested owner | Prototype at handoff |
|---|---|---|---|---|
| S01 | Unblock the repository | 0 | Arafat | Clean clone launches the app — **✅ done** (+ S01b/c/d) |
| S02 | DB foundation & ADRs | 0 | Nakib | `seed.sh --fresh` builds the schema |
| S03 | Contracts, policy & invariants | 0 | Arafat | Framing guard rejects a bad statement |
| S04 | Stubs, fixtures & modularization | 0 | Nakib | 200 seeded flags queryable |
| S05 | Backend defects | 1 | Arafat | Routing on local OSRM, benchmarked |
| S06 | Multi-person pose & evidence | 1 | Nakib | Two-person photo → real interaction |
| S07 | Frontend defects | 1 | Arafat | Correct markers, one SOS path, no bg audio |
| S08 | Frontend refactor | 1 | Nakib | Reporting works from small components |
| S09 | Ingestion framework | 2 | Arafat | Real articles in `raw_documents` |
| S10 | Bangla gazetteer | 2 | Nakib | Bangla landmark → coordinates |
| S11 | Geolocation Agent | 2 | Arafat | A real accuracy number |
| S12 | Risk-aware routing | 2 | Nakib | Top route avoids a seeded flag |
| S13 | Explanations & risk map | 2 | Arafat | **§6 worked example on a phone** |
| S14 | Live Risk Agent | 3 | Nakib | Today's news → flags on the map |
| S15 | Rumour Guard | 3 | Arafat | Four reports → one confirmed flag |
| S16 | Push notifications | 3 | Nakib | Real push to a real phone |
| S17 | Background location & geofence | 3 | Arafat | Walk toward a flag, get warned |
| S18 | Trips & hot words | 3 | Nakib | Start, track, complete a trip |
| S19 | Decay engine | 4 | Arafat | Severity decreasing over time |
| S20 | `DbRiskSurface` & expiry | 4 | Nakib | **Stale flags gone by morning** |
| S21 | Admin observability | 4 | Arafat | Fleet health at a glance |
| S22 | Guardian: anomaly detection | 4 | Nakib | Detour caught, jam ignored |
| S23 | Guardian: graded escalation | 4 | Arafat | Full escalation chain exercised |
| S24 | Chronic Risk Agent | 5 | Nakib | Real blackspots from archives |
| S25 | Legacy retirement & cost model | 5 | Arafat | ৳/day for the fleet |
| S26 | Scheduled Risk Agent | 5 | Nakib | **Tomorrow's risk map, today** |
| S27 | Casework Agent | 5 | Arafat | A GD draft with the right thana |
| S28 | Casework UI & Bangla review | 5 | Nakib | Five native-speaker-approved drafts |
| S29 | Crowd verification | 5 | Arafat | Nearby users promote a flag |
| S30 | Privacy & retention | 6 | Nakib | Expired data verifiably gone |
| S31 | Resilience & chaos testing | 6 | Arafat | Fleet survives any single failure |
| S32 | Observability & cost controls | 6 | Nakib | Success metrics live |
| S33 | Load testing | 6 | Arafat | The ceiling, with numbers |
| S34 | Offline & battery | 6 | Nakib | Airplane mode still helps |
| S35 | Performance & accessibility | 6 | Arafat | Budgets met |
| S36 | Bangla localisation & SMS | 6 | Nakib | Full `bn` UI; SOS without data |
| S37 | Store readiness | 6 | Arafat | Signed builds, both platforms |
| S38 | Pilot preparation | 7 | Nakib | Runbook + on-call |
| S39 | Pilot launch | 7 | Arafat | 20–50 real users |

**39 sprints to pilot.** At one sprint per person per week in relay, that is roughly nine to ten months part-time. The two phases that will overrun are **Phase 2** (the gazetteer is manual work that does not compress) and **Phase 5** (Bangla legal drafting needs review cycles you cannot schedule away). Plan for that rather than discovering it.

> The Guardian self-trial starting in S23 needs two weeks of real commuting, which no sprint can contain. It runs as a background activity (§3.6) through Phase 5 and gates the Guardian's release.

---

## 12. What this plan deliberately does not do

Stated so these are decisions rather than oversights:

- **It does not rewrite the AI vision stack.** The YOLOv9c + MediaPipe + CLIP fusion engine is good work, it is not on the concept document's critical path, and it keeps earning its place as the assisted-reporting front end. S06 fixes the unreachable multi-person path; nothing else changes.
- **It does not migrate off Supabase.** ADR 0001 draws the line between Supabase-direct CRUD and FastAPI; both stay. A migration would cost two sprints and buy nothing the product needs.
- **It does not build a web dashboard.** S21's admin page is for us. Institutional engagement in Phase 7 starts with exported reports; a dashboard is a product decision to make after a pilot, with evidence.
- **It does not implement real-time collaborative verification.** Crowd verification in S29 is asynchronous and rate-limited on purpose — it is an abuse surface, and async is the defensible version.
- **It does not promise national coverage.** Gazetteer density gates expansion, and that is manual work. One zone, proven, then the next.
- **It does not parallelize.** Chosen deliberately in §2.1: our hours do not overlap, so parallel branches would cost us merge complexity in exchange for wall-clock compression we cannot collect.
