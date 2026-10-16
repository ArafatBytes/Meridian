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
| 9 | Medium | Three user tables: `auth.users`, `public.profiles` (app), `public.users` (backend). `create_users_table.sql` and `models/user.py` define incompatible shapes. **Fixed 2026-10-15.** `public.users` had **no dependents** — every `user_id` FK points at `auth.users`, `gd_drafts` included — so the only live symptom was that `sos.py` derived the alert's name from the email local part: *"EMERGENCY: mdarafat1661 needs help"*. It now reads `profiles.name` → *"EMERGENCY: Arafat Ullah needs help"*, verified on the three real accounts. Model, relationships and ORM FKs deleted; the table dropped by migration `20261015160000`, applied the same day. | **S05 ✅** |
| 10 | Medium | Nominatim called from the device with no `User-Agent`, against their usage policy — and from **five** call sites with no caching, so the per-IP limit was spent separately by every phone. Now `app/geo/nominatim.py` behind `GET /geo/search` and `GET /geo/reverse`: one identifying agent, one shared Redis cache (**471 ms cold → 52 ms warm**, 24 h TTL). Kept separate from `/geo/resolve`, which is allowed to refuse. | **D06 ✅** |
| 11 | Medium | Three crime-score scales coexist: 0–100, 0–10, and percent. One scale now — **`safety_score`, 0–100, higher is safer.** `RouteSegment.crime_score` deleted, the card renders `71/100` rather than `70.6% Safe`, and a test asserts the response carries exactly one risk scale so a second cannot return quietly. | **D06 ✅** |
| 12 | Low | `EmergencyContact` declared twice in `types/index.ts` with different shapes | **S01b ✅** — re-point at the contract type in S03 |
| 13 | Low | Report photos are analysed then discarded — evidence is never persisted | S06 |
| 14 | Low | `MapScreen` SOS button is still a `// TODO` alert while `HomeScreen`'s is real | S07 |
| 15 | Low | `Pillow`, `pandas`, `pytest` commented out in `requirements.txt` but used by code, scripts, tests | S04 |
| 16 | Low | `theme/colors.ts` + `theme/darkTheme.ts` are dead; `routeService` not exported from the services barrel | S04 / S07 |
| 17 | Low | All 607 rows of `police_stations.csv` share one email and phone. **Closed 2026-10-15 — the row asked the wrong question.** §7.2/ADR 0007 had already made the contact columns permanently unused (no police API to transmit to), so real contacts would have enabled nothing. The half that *is* read was fixed instead: scoped to the 51 Dhaka city thanas, five unverified coordinates made nameable-but-not-rankable, out-of-Dhaka points refused, duplicate spellings made deterministic. ⚠️ **Corrected same day:** the first close also made police emailing *refused by the data*, which was wrong — the owner had put their own address in every row in order to test routing, and §7.2's "nothing to transmit to" was about **filing**, not notifying. `POLICE_ROUTING_ENABLED=true` now and an SOS emails the single nearest Dhaka city thana to the caller's live coordinates. | **S05 ✅** |
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
- [x] ~~Write `docs/adr/0002-auth.md` itself~~ **Done 15 Oct in B1.** It describes
      what was in place — and what was *not*: writing it surfaced **defect 56**,
      an unauthenticated token-minting endpoint that made every protected
      endpoint reachable. The code had landed ahead of the ADR, and the gap
      between them was the defect

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

- [x] ~~`docs/adr/0001-data-plane.md` — the Supabase-direct vs FastAPI rule. Proposal: **Supabase for user-owned CRUD; FastAPI for anything agentic, geospatial, or multi-user.** Write down which tables each may write.~~ **Written 15 Oct (B1).** The proposal is adopted as-is, because the code had already converged on it: the client writes `profiles`, `emergency_contacts`, `sos_hot_words` and `crime_reports` directly, and nothing else. The ADR names the three properties that put a table on the FastAPI plane (agentic, geospatial, multi-user), assigns all 16 tables, and argues RLS — not a FastAPI ownership check — is the enforcement point for user-owned rows. It also rules that **`endpoints/users.py`, `crimes.py` and `tracking.py` are dead and must go**: every operation they name is user-owned CRUD the client already does Supabase-direct, and a `pass` handler with a `response_model` is a 500, not a 404. ⚠️ Deleting those three is still outstanding — see the cleanup item in S06
- [x] ~~`docs/adr/0002-auth.md` — Supabase remains the IdP. Document the JWT path and **migrate off the shared HS256 secret** to Supabase JWKS verification (new projects default to asymmetric keys; the current `HS256` + `verify_aud=False` setup is fragile)~~ **Written 15 Oct (B1) — and writing it found defect 56, a live authentication bypass.** The row's instinct was right and understated: the HS256 fallback was not merely "fragile", it was what made a forged token verify. `/auth/login` minted accepted tokens for any email with no credential check. See **Defect 56** for the measurement and the three-part fix; the ADR carries the decision and the `JWT_SECRET_KEY` consequence
- [x] ~~`docs/adr/0003-user-identity.md` — collapse three user tables to one. Proposal: `auth.users` is identity, `public.profiles` is the only profile table, delete `public.users`, point `emergency_contacts.user_id` and `crime_reports.user_id` at `auth.users(id)` — **Defect 9**. ⚠️ **This proposal is now executed in everything but the document. Only the ADR is outstanding.** `emergency_contacts.user_id` and `crime_reports.user_id` *already* reference `auth.users(id)`, as does every other user-owned table; `public.profiles` is already the only profile table; and **`public.users` was deleted outright on 2026-10-15** — code and table, migration `20261015160000` applied. See **Defect 9 (code half)** in S05. So this row is reduced to writing down a decision that has already been made and shipped — which is still worth doing, because the belief that `sos_incidents` depended on the mirror survived in three documents for weeks precisely because nobody had written the ADR.~~ **Written 15 Oct (B1)** as `docs/adr/0003-user-table-collapse.md` — the filename differs from the row because the decision is about tables, not about identity in general, which is ADR 0002's subject. It records the execution, names the ORM-`ForeignKey`-read-as-schema mistake that blocked it for weeks, and carries the new finding that **the drop does not stay dropped**: `public.users` reappeared hours later from another checkout's `create_all`
- [x] ~~`docs/adr/0004-migrations.md` — forward-only timestamped SQL + runner, and why not Alembic~~ **Written 15 Oct (B1).** Promotes `migrate.py`'s module docstring to a decision and adds the three things operating it has taught, each of which cost real time: a **duplicate version number is skipped for ever** (`up` applies by version, not checksum — ADR 0003's migration nearly shipped with Nakib's `journey_deadline` timestamp); the **ledger can name migrations whose files are not in this repo** (three `journeys` rows, so a mystery version is a question, not corruption); and a **drop is not final while another checkout declares the model**
- [ ] `scripts/migrate.py` + `schema_migrations` table
- [ ] Migration: `risk_flags` with PostGIS `GEOGRAPHY(POINT, 4326)`, GiST index on location, index on `(status, expires_at)`, and **`CHECK (half_life_hours > 0)`** (§4 decay invariant, at the schema level)
- [ ] Migration: `raw_documents`, `extracted_incidents`, `agent_runs`
- [ ] Migration: execute ADR 0003
- [ ] `scripts/seed.sh` — rebuild a dev DB from migrations + fixtures in one command, for real this time

**Gate:** drop the dev DB, run `seed.sh --fresh`, get a complete schema.

---

## S03 — Contracts, policy & invariants

**Suggested owner:** Arafat. **Prototype:** `mypy --strict app/contracts` clean; invariant tests running in CI.

- [x] ~~`app/contracts/{risk,agents,surface,trips,casework}.py` — §6~~ **Five of five shapes, two of the filenames different.** `risk.py`, `agents.py`, `surface.py` as listed, plus `community.py` and `news_crime.py` which the row did not anticipate. **No `trips.py`** — the trips model is still unbuilt (S18/B10), so a contract for it would describe nothing. **No `casework.py`** — casework's shapes live in `app/schemas/casework.py` because they are request/response bodies for one endpoint pair rather than objects several subsystems agree on, which is what this package is for
- [x] ~~`frontend/src/types/contracts/` — hand-mirrored TypeScript, plus a CI check that flags drift~~ **Done in B2, 15 Oct.** The mirrors existed; the drift check is `tests/invariants/test_contracts_do_not_drift.py` (38 tests) and CI job **3b `contract-drift`**. ⚠️ **It compares the `*Wire` interfaces in `frontend/src/services/`, not the camelCase types in `types/contracts/`** — the latter are the client's *domain* model and are allowed to differ, as `NewsCrimeIncident`'s `latitude`→`lat` mapping does on purpose. Proven to catch the real failure: renaming `RiskFlag.source_count` on the server leaves `tsc` at **exit 0** and is caught only here
- [x] ~~`app/policy/framing.py` — `to_mobility_statement()`, `assert_mobility_safe()`, banned-term list~~ **Shipped** — `test_no_flag_text_bypasses_framing.py` is its invariant
- [x] ~~`app/privacy/retention.py` — the retention registry, with every existing location-bearing table declared~~ **Done in B14**, all 21 tables
- [ ] 🟡 **`backend/tests/invariants/` exists (24 files) and runs on every change — but NOT in CI.** The `invariants` job installs `pytest pytest-asyncio` and no application dependencies, so it has never been able to import `app.*`; the `backend` job's pytest step has the same gap. The suite runs in the `api` container instead. **Found and documented in B2, deliberately not half-fixed** — the files reach `app.agents`, `app.ingestion` and `app.llm`, so making CI collect them means `requirements/agents.txt`, which means `sentence-transformers` and torch. That is a runtime-cost decision, not a one-line patch. The drift check in job 3b is independent of it on purpose: pydantic-only imports, 15 packages, genuinely runs
- [x] ~~`mypy --strict` passes on `app/contracts/`~~ **Already true and already enforced** — `pyproject.toml` has had `app.contracts.*` under `strict = true` since S03 and CI's mypy step runs with that config. The box was simply never ticked; verified clean on 6 source files

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
- [ ] ⏭️ Endpoint auto-discovery replaces `api.py`'s manual includes; `models/__init__.py` auto-import — **B3, skipped by the owner 15 Oct, and the auto-discovery half should not be revived as written.** `api.py`'s explicit list is the one place where publishing a public route is a decision somebody makes, and defect 56 was a registered route nobody had looked at handing out accepted tokens for any email. A loader that publishes whatever is in `endpoints/` makes that easier; the honest version of this want is a **test** that fails when a module exists but is never registered. See the B3 row in `DEMO_PLAN.md`.
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

- [x] **Defect 2:** ~~Fix `speech_service`. Either restore `pydub` + document the ffmpeg dependency, or (preferred) drop format conversion and send the device's m4a/webm straight through.~~ — **closed 2026-10-15 by deleting it, which neither option anticipated.** Both assumed a caller. By the time this was reached there was none: B8 had moved dictation on-device (`features/voice/dictate.ts`) *because* this endpoint was broken, and `features/voice/privacy.test.ts` asserts no audio-upload path remains. Repairing it would have meant shipping ffmpeg and Google Cloud credentials to restore a feature the product had deliberately abandoned on privacy grounds, and keeping a live audio-upload route with nothing calling it. **Deleted:** `POST /ai/speech-to-text`, `GET /ai/supported-languages` (a hardcoded 15-language list advertising Bengali support that was never wired), `GET /ai/health` (reported only on the speech client and named a provider that did not exist), `app/services/ai/speech_service.py`, `tests/test_speech_service.py`, seven `GOOGLE_CLOUD_*`/`SPEECH_*` settings read by that one file, and `google-cloud-speech` + `google-cloud-storage` + `pydub` from `requirements/ai.txt` — `google.cloud` had exactly one importer and evidence photos go to Supabase Storage. **No test was added, deliberately:** the `NameError` is unreachable once the code is gone, and a test asserting a deleted route 404s pins an absence rather than a behaviour. 601 → 600 backend tests, the one removed being the dead speech test itself.
- [x] **Defect 6:** ~~Honour `avoid_high_crime_zones` and `max_crime_score`, or delete them from the schema.~~ — **already closed; this box was never ticked.** `routing/scorer.py`'s `passes_filters` says *"Both are honoured now"*, and keeps the awkward names on purpose: they are public request fields, so renaming them to match defect 11's single scale would break any client already sending them. Found 2026-10-15 while auditing the backlog.
- [ ] **Defect 7:** `OSRMClient` — read `OSRM_BASE_URL`, prefer the local container, fall back to the demo server with a loud warning, add the `foot` profile alongside `driving`, use OSRM's own `duration` instead of a flat 30 km/h.
- [x] **Defect 8:** ~~Replace the Python double loop with a PostGIS query (`ST_DWithin` against the path as a `LINESTRING`).~~ — **already closed in D06; this box was never ticked.** `contracts/surface.py:89` names itself the fix: `flags_near_path` sits on the *protocol* rather than inside `DbRiskSurface`, so `routing/` works unchanged on every surface, and the docstring records why a bounding box was not an acceptable substitute — *"a 12 km route across Dhaka has a bounding box containing most of the city's flags, almost none of which are on it."* ⚠️ The before/after benchmark this row asked for was never recorded. Found 2026-10-15 while auditing the backlog.
- [x] **Defect 9 (code half):** ~~delete `models/user.py`'s table and the `sos.py` auto-provisioning block~~ — **done 2026-10-15. The audit below is what the fix was built from; one step is left and it is the owner's to run.**

      **Fixed:** `sos.py` now reads the alert's name from `profiles.name` via `_display_name()`; the auto-provisioning block, `app/models/user.py`, four `relationship("User", ...)` declarations and five `ForeignKey("users.id")` columns are gone. **Proved on live data** — the three real accounts now resolve to `Arafat Ullah`, `Nakib Saleh`, `Farhan Ishraq`, where the mirror table still holds `full_name='mdarafat1661'` and `'nakib1990saleh'`. 16 new invariant tests (`test_sos_alert_names_the_person.py`), **660 pytest**, no new lint findings.

      **The fallback is the whole email address, never a part of one.** An address is a true, complete identifier a contact may recognise and is visibly an address; a local part reads as a name and is not one. A missing `profiles` row is logged, and never raises — an SOS is not the moment to refuse to send an alert over a display string.

      ✅ **Migration applied by the owner in the Supabase SQL Editor, 2026-10-15. `public.users` is gone and defect 9 is fully closed.** Verified after the fact: table absent, orphan trigger gone, **all user data intact** (`profiles` 3, `crime_reports` 8, `emergency_contacts` 2, `sos_incidents` 17, `sos_hot_words` 2, `gd_drafts` 4, `gd_profiles` 1), and the three accounts still resolve to their real names.

      **Two follow-ups the drop needed, both done:**

      **The ledger had no row for it.** Pasting the file into the SQL Editor applies the schema change but skips the `schema_migrations` insert that `migrate.py sql` would have bundled — so `status` read `pending` on a migration that had run, and `up` would have tried it again. Recorded with `migrate.py mark 20261015160000 --yes`, the command built four hours earlier for **defect 55**, which is the first time it has been used for the thing it was written for. `applied_by='marked'`.

      **The retention tripwire fired, and that is how the dead entry got deleted.** `app/privacy/retention.py` had classified `users` as an explicitly temporary `KEEP`. The moment the drop landed, `test_the_registry_does_not_describe_tables_that_do_not_exist` failed with *"retention rules for tables that no longer exist: ['users']"*. The entry is removed and the reason it left is recorded in place. Nobody had to remember.

      ✅ **The `init_db` trap is closed in practice, not just in theory.** The API was restarted after the drop: `create_all` ran, logged *"Database tables created successfully"*, and **the table did not come back.** That is the verification the whole model deletion existed for.

      **660 pytest, 0 skipped, 0 failed.**

      ---

      **The audit the fix came from. Both halves of the old framing were wrong.**

      **The schema half already happened, without this box ever being ticked.** `public.users` has **no dependents left**. Every user-owned table references `auth.users(id)` directly in `migrations/supabase/SCHEMA.sql` — `crime_reports` (84), `emergency_contacts` (126), `sos_hot_words` (155), `sos_incidents` (205), `user_locations` (234) — and the last holdout, `gd_drafts.user_id`, was repointed from `public.users` to `auth.users` by `migrations/versions/20261010160000__gd_profiles_on_auth_users.sql`, which also created `gd_profiles` on `auth.users` from the start. Nothing joins to `public.users`. Nothing needs a row in it. **Dropping the table is no longer blocked on ADR 0003**, so this does not have to wait for B1.

      **But one live consequence remains, and it lands in the emergency email.** `sos.py:57-69` auto-provisions the row with `full_name = email.split("@")[0]`, and that derived string is the **only** name the SOS alert ever uses: `email_service.py` puts it in the subject (`EMERGENCY: {user_name} needs help`) and five times in the body, including the instruction *"Try calling {user_name}."* So an emergency contact is told to call a person identified by an email local part. This is not hypothetical — migration `20261010160000` already recorded the live evidence while fixing the GD form for the same reason: *"one row reads `nakib1990saleh`, an email local part."*

      **It never self-heals.** The block only runs when the row is absent, and nothing syncs `profiles` → `public.users` afterwards. Editing your name in `EditProfileScreen` updates `profiles` and leaves the SOS email saying the old derived string forever.

      **The real name is right there.** `profiles.name` is written at registration (`frontend/src/services/auth.service.ts:42`) and is user-editable. The fix is to read it instead of inventing one — one query in one file, plus dropping the auto-provision.

      **What is *not* a consequence, checked so the row does not get re-inflated:** `password_hash = "supabase_managed"` is read by nothing — `core/security.py:decode_token` verifies Supabase tokens through JWKS, and `verify_password` is imported by `endpoints/auth.py` and never called; `users.hot_words` has **zero readers** (B8 reads `sos_hot_words`); and the five `ForeignKey("users.id")` declarations still in `app/models/` are model-vs-schema drift only, because SCHEMA.sql builds the database, not the models.

      **Two findings worth keeping beyond this defect.**

      **`init_db()` would have undone the drop.** `core/database.py` runs `Base.metadata.create_all` on **every API start**, inside a try/except that logs *"Database not available"* and continues. While `models/user.py` existed, dropping the table in Supabase would have been reversed by the next restart and the swallowed exception would have hidden why. Deleting the model is a prerequisite for the migration, not a tidy-up after it — `test_create_all_cannot_recreate_the_mirror` asserts `Base.metadata` agrees, and the live boot log now lists six tables with `users` absent.

      **The migration's first version number was already taken.** `20261015120000` is `journey_deadline`, applied `by=nakib` with **no file in this repository**, alongside `20261015140000` (`journey_leash`) and `20261014150000` (`journeys`). `migrate.py up` applies by version, so that file would have been treated as already applied and **skipped forever** — defect 55's failure exactly, caught only because the checksum differed. Renumbered to `20261015160000`. Three hand-applied migrations with no committed files is B10 in progress on the shared database: **do not drop `journeys`, do not build on its shape.**
- [ ] **Defect 10 (backend half):** `/geo/search` + `/geo/reverse` proxy with a compliant `User-Agent`, Redis cache, and rate limit. **First real use of Redis.**
- [x] **Defect 17:** ~~Replace `police_stations.csv` placeholder contacts with real data.~~ — **closed 2026-10-15, and not by obtaining contacts. The row asked the wrong question.**

      **§7.2 had already made the contact columns permanently irrelevant and nobody re-read this row afterwards.** ADR 0007 closed police routing on 10 Oct for a reason that has nothing to do with data quality: **there is nothing to transmit to.** Bangladesh Police has no public API, no developer portal and no partner process, and a cognizable offence cannot be closed online in any case — the applicant must appear at the thana with a printed copy. So real per-thana emails would not have enabled anything. This row sat "blocked on data" for a deliverable that had been cancelled.

      ⚠️ **That paragraph is half right, and the wrong half cost a working feature.** "Nothing to transmit to" is true of **filing a case** and false of **sending an email**. §7.2 reasoned from the first to the second without noticing they are different acts, this row repeated it, and the close then built a refusal on top. Corrected by the owner the same day. Filing still cannot be automated, which is exactly why the thana is named on the GD; notifying the nearest thana of an SOS needs no API, no portal and no partner process, and now happens.

      What *is* read is the half that matters: **station names and coordinates**, which is what names the thana on a General Diary. The owner supplied a far better file on 15 Oct — **43 rows sourced from DMP's own find-your-local-police map, plus 3 from OpenStreetMap** — and that is where the work went.

      **Scoped to Dhaka city.** `thana.py` now loads only `district == "Dhaka"`, which is **exactly the 51 DMP thanas** — verified that the column contains no Dhaka-district upazila stations (no Savar, Keraniganj, Dhamrai, Nawabganj, Dohar), because the filter is only correct if that holds, and a test now fails if a re-export breaks it. Previously all 607 rows were loaded, Sherpur included.

      **A station can now be named without being located, and five are.** Five Dhaka rows are labelled `legacy — unverified` by the file itself, and their coordinates do not survive checking **against the file's own trusted rows** — the row called `Turag` sits 1.7 km from Rampura, `Hatirjheel` 4.4 km from Pallabi, `Cantonment` 1.4 km from Shah Ali. All five are real thanas. They stay in the review-screen picker, because somebody filing in Turag must be able to find it, and are excluded from distance ranking, because a pin 4 km into the wrong neighbourhood is how a GD reaches the wrong officer-in-charge. **44 locatable, 49 nameable.** Driven by the `coord_source` column, not by anyone's recollection of Dhaka geography: upgrade a row's label and it becomes locatable with no code change.

      **Outside Dhaka it now refuses instead of guessing.** Once the list is Dhaka-only, the nearest station to Chattogram is a DMP thana **200.9 km** away, and the old code would have returned it with a confident name. `MAX_PLAUSIBLE_KM = 25` is derived, not picked: sweeping a 101×101 grid over the project's own gazetteer box, the furthest any point in Dhaka sits from a locatable station is **14.6 km**.

      **Duplicates.** `Gandaria`/`Gendaria` and `Bhatara`/`Vatara` are co-located spelling variants and `Hazaribagh`/`Vatara` had exact duplicate rows. Exact duplicates dropped; **both spellings kept**, because the picker is searched by the name the user knows and dropping one makes that thana unfindable for half the people who need it. Ranking is sorted so co-located variants always resolve to the same name — a signed document must not say `Gandaria` one run and `Gendaria` the next.

      ~~**The declined fallback, implemented — and better than proposed.** The alternative offered on 15 Oct was to rewrite the placeholders as explicit `unknown`. Not needed: **607 rows sharing one address is already an explicit enough statement of not-known**, so `sos_service._check_contacts_are_per_station` measures it and `_get_nearby_police_emails` refuses **even with `POLICE_ROUTING_ENABLED` forced true** — verified by test. The data is the gate, not a boolean one edit away from being flipped.~~ ⚠️ **Reversed hours later, by the owner asking why the SOS was not reaching the nearest station.** This was the one wrong move in the close, and it is worth keeping visible: the owner had said *"I have set the email and number field as my email and my number just to test it"* — which is somebody wiring up a destination they can watch — and the code answered by refusing to use it. **A gate the data's owner cannot open is not a safety feature.** The flag is the gate; `_check_contacts_are_per_station` now logs the shared address on every send instead of blocking it. The hazard it was built for is defect 31's — routing on while the column held a *stranger's* address — and that is addressed by the column holding the owner's own.

      **What the routing actually does now.** `_nearest_police_station` asks `casework.thana.nearest_thana` for the single closest Dhaka city station to the live SOS coordinates and adds that one address. One station, not the old 5 km radius: central Dhaka has six or seven thanas inside 5 km, and six stations each assuming another is responding is worse than one being told. Sharing `nearest_thana` is the point — the thana emailed and the thana printed on the GD are the same station by construction, so the alert reaches the thana the victim will later walk into. Verified live: Dhanmondi coordinates → `Dhanmondi Police Station` 0.66 km; Uttara → `Uttara Police Station` 2.36 km; Jashore → **none**, 132.8 km, refused. `_haversine_distance` was deleted with it — it was the second copy of the formula in the repo, and two copies is how the two answers drift apart.

      **The README was not the thing claiming it — the SOS screen was.** This row said *"the README should not claim it"*. The stronger claim was a stat tile on `SOSFlow`: **"Police stations nearby: 0"**, shown on every SOS ever sent, telling the user at the worst moment the app has that it had searched for police near them and found none. It had never looked. The tile is back now that it *does* look, but as a **name** rather than a count — `Police station: Dhanmondi Police Station`, or `None in range` outside Dhaka city. A count of 1 is not reassuring and a `0` invites "there are no police near you"; a name is a fact the person can act on. `policeStation: string | null` replaces `policeStationsFound` on `SosResult`, fed by a new `police_station` field on `/sos/trigger` (the endpoint has no `response_model`, so it passes through).

      **684 pytest** (+24 in `test_thana_lookup_is_dhaka_city.py`), **427 jest**, `tsc` clean, no new lint findings — `sos_service.py` went 11 → 10 as `_haversine_distance` left. ⚠️ **The contact columns are still not real DMP data** — they are the owner's own address and number — and that is now load-bearing rather than harmless: with routing on, the only inbox an SOS can reach is theirs. **Put real per-thana addresses in the CSV before anyone outside the team relies on this**; the code needs no change for it. **Do not invent or infer thana phone numbers to close that** — a wrong number in a safety app during an emergency is the worst failure in this repo, and a plausible-looking one is worse than an obvious placeholder. ⚠️ **An SOS from outside Dhaka city emails no station**, by design and by the owner's instruction to use Dhaka city rows only. Testing from Jashore will show `None in range`; widening to all 606 rows is a one-line scope change in `thana.py` if nationwide routing is ever wanted.
- [ ] **Defect 35:** Persist `SOSIncident` on trigger, and keep the evidence. Measured after a verified-delivered SOS: `sos_incidents` held **0 rows**, and `_save_video` writes the clip to a temp file, attaches it, then `os.remove`s it. So the README's "incident logged in database" is false and the only copy of the video is in the recipient's inbox. Needs: a row written before the send (so a failed send is still recorded), the clip uploaded to Storage with a `media_ref`, and a status field that can distinguish delivered / failed / cancelled / false alarm.
- [x] ~~**Cleanup:** delete `crime_ai.py` (dead duplicate). Delete or implement the `auth.py` / `crimes.py` / `users.py` / `tracking.py` stubs per ADR 0001 — a `pass` endpoint in a public API is worse than no endpoint.~~ **Done 15 Oct, and the last clause of this row was the understatement of the project.**

      `crime_ai.py` was **already gone** — deleted in an earlier sprint with this box never ticked, which is now the fifth time that has happened here (see also defects 6, 8, 29+5, 30 and all of B5).

      All four endpoint modules deleted, with their `include_router` lines and their orphaned schemas (`schemas/auth.py`, `user.py`, `crime.py`, `tracking.py` — no other importer). **`auth.py` was not a stub**: `/auth/login` and `/auth/register` returned signed, accepted tokens for any email with no credential check. See **Defect 56**. The other three were genuinely `pass`, which is still a **500** rather than a 404 — `pass` returns `None` and `None` against a non-optional `response_model` raises. Verified after: `/users/me`, `/crimes/nearby`, `/tracking/check-danger-zone` → **404**; `/sos/history` → **401**; `/risk/flags` → **422**. Nothing in the client changed, which is the evidence they were dead.

      `tests/invariants/test_no_endpoint_is_a_stub.py` generalises the rule instead of naming the four: it **parses every handler** under `endpoints/` and fails on any whose body is only a docstring and/or `pass`/`...`, so it catches the *next* one. An explicit `raise NotImplementedError` passes — a deliberate answer a client can handle is not the failure. It also refuses any router mounted on `/auth`, `/users`, `/crimes` or `/tracking`, since ADR 0001 puts those on the Supabase-direct plane, and it has a test feeding the detector five known bodies so that "can this check still fail?" is answered rather than assumed.

---

## S06 — AI vision: multi-person pose & evidence

**Suggested owner:** Nakib. **Prototype:** a two-person photo produces a real interaction analysis for the first time.

- [x] **Defects 29 + 5:** ~~Port `pose_service.py` to `mediapipe.tasks.python.vision.PoseLandmarker`.~~ — **closed by a decision not to port, and this box was never ticked.** `requirements/ai.txt` records it: *"Porting it was the plan until the obvious question — 33 landmark coordinates do not describe a crime."* mediapipe, ultralytics, torch, torchvision, transformers, safetensors, onnxruntime, scipy, opencv-python and pandas were all dropped, and a vision-language model took their place. Dropping them *"is what makes the backend deployable on a free tier at all."* `app/` no longer contains a pose path to port. Found 2026-10-15 while auditing the backlog.
- [x] **Defect 30:** ~~Close the vocabulary gap — 11 of 21 object signals are not COCO classes, so `harassment`, `theft` and `vandalism` cannot be returned by any input.~~ — **closed by the same decision as 29 + 5, and this box was never ticked.** The row's three options were "find a model that emits it, re-express the gate, or delete the signal"; the answer was to delete the *vocabulary*. `requirements/ai.txt`: *"A vocabulary gap is not closeable by adding signals. The vision-language model has no fixed vocabulary, and it returns people_count too, which was the last thing YOLO was for."* The principle this row stated — **a gate that cannot fire is worse than no gate, because it reads as coverage** — is why the fixed-vocabulary detector went rather than the gates. Found 2026-10-15 while auditing the backlog.
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
- [x] ~~Remove the ~30 lines of stale-closure deliberation left in `HomeScreen`.~~ — **already gone; verified 2026-10-15.** `HomeScreen.tsx` is 472 lines and contains exactly one mention of staleness, a three-line note explaining why `readZones` runs on every focus rather than on mount (the tab navigator keeps the screen mounted, so returning from the Guardian screen would otherwise show stale state). That is an explanation, not deliberation — keep it. ~~Fix the shake threshold comment (says 3.5 g, code is 6.0 — pick one, justify it with a measurement)~~ **settled in Guardian (11 Oct): it is a user setting.** Neither number was right to hard-code — shake magnitude in g varies by handset — so the Guardian screen pairs it with a **live accelerometer reading** and a stepper, and the measurement is taken by the person whose phone it is. 6.0 g is the default because that is the value that had actually run on a device; 3.5 g is reachable by putting a phone down firmly.
- [ ] **Defect 11:** One score scale. **0–100 everywhere, higher = safer, named `safety_score`.** Delete the 0–10 `crime_score` and the percent variants. Add a test.
- [x] **Defect 12:** ~~De-duplicate `EmergencyContact`~~ — done in S01b; re-point at the contract type when S03 lands.
- [ ] **Defect 14:** Make `MapScreen`'s SOS button call the same path as `HomeScreen`'s. Extract one `useSOS()` hook; both screens consume it.
- [x] **Defect 16:** ~~Export `routeService` from the services barrel.~~ — done 2026-10-15, with `RouteRequest` and `RouteResponse` beside it. **`Location` was deliberately left out:** `route.service.ts` declares one, the location domain has its own, and `Location` is a global in the DOM lib — a barrel is the worst place to make a name that generic ambiguous. Three other services (`casework`, `geo`, `sos`) are also absent from the barrel; that is the same class of gap but not what this defect named, so it is recorded here rather than silently folded in. The `theme/colors.ts` half of defect 16 is **also done, and this line claimed otherwise until 15 Oct** — `theme/colors.ts` and `theme/darkTheme.ts` were deleted in commit `f0a83de`, found already gone when B3 was read for consent. `theme/theme.test.ts` carries the reason they had survived: a missing theme key is a runtime `undefined` that React Native silently ignores rather than erroring, so two unexported colour objects could sit beside `palette.ts` with nothing complaining. That file now asserts the keys the screens actually read, including the `error`/`textPrimary` aliases, so the legacy `theme.ts` cannot lose one quietly. **Defect 16 is closed in full.**
- [ ] **Defect 10 (frontend half):** route all Nominatim traffic through the S05 backend proxy.
- [ ] Surface the evidence photos S06 started persisting

#### Found by the first Android build, 11 Oct — all fixed

These are logged because the *reason* they existed is reusable: **this app had only ever been
built for iOS, through Expo Go.** Expo Go reads `app.json` at runtime and ignores the `plugins`
block, so nothing that only runs during `prebuild` had ever executed. Nine days of green device
walkthroughs told us nothing about any of it.

- [x] **Defect 45:** ~~`app.json` declares five asset files that do not exist~~ — `notification-icon.png`, three `.wav` sounds and `favicon.png`. `assets/` holds two markdown guides and nothing else. Present since D01 (`8da3480`); the first `prebuild` failed on it. **Fixed:** the references are gone, and the code no longer names `sos_alert.wav` either — an unbundled sound name falls back to the default *silently*, which looks like it worked.
- [x] **Defect 46:** ~~`android.usesCleartextTraffic` is not in the SDK 57 schema and was silently ignored~~ — **the one that would have cost the finale.** The debug manifest adds cleartext for you, so a *release* build would have blocked every call to `http://<lan-ip>:8000`: no flags, no SOS, no routing, in front of judges, from a build that worked an hour earlier. **Fixed** via the `expo-build-properties` plugin; verified present in the main manifest.
- [x] **Defect 47:** ~~No Google Maps API key, so the Map tab crashed on Android~~ — `react-native-maps` uses **Apple Maps on iOS** (no key) and **Google Maps on Android** (key required, in the manifest). **Fixed:** `app.json` → `android.config.googleMaps.apiKey`.
- [x] **Defect 48:** ~~`@react-native-voice/voice` declares `jcenter()`, which Gradle 9 removed~~ — the package was in `package.json`, imported nowhere, and autolinked anyway. It also exposes no way to refuse network speech recognition, which is why B8 built on `expo-speech-recognition` instead. **Fixed:** uninstalled.
- [x] **Defect 49:** ~~`SOSCameraModal`'s countdown was never reset, so every SOS after the first in an app session failed~~ — `if (!visible) return null` is an early return *inside* the component, so hiding the modal does not unmount it and `useState(10)` never re-initialises. After one SOS `countdown` sat at 0 forever, and the next call to `startRecording` tripped `stopRecording()` milliseconds later. Survived D01–D09 because one SOS per session is how anyone tests it. **Fixed:** reset on open, seeded from the constant.
- [x] **Defect 50:** ~~`useSOS()` was mounted in three screens, giving two or three shake listeners~~ — the root is a bottom-tab navigator, which keeps visited screens alive, so one shake opened two camera modals and sent two alerts. **Fixed:** one controller in `features/guardian/GuardianProvider`, consumed through `useSosController()`.
- [x] **Defect 51:** ~~`startRecording` ran twice, throwing `IllegalStateException: A recording is already in progress`~~ — `onCameraReady` fires more than once (changing a capture prop reconfigures the session), and both calls read `isRecording` from **state**, i.e. their own render's closure, so both saw `false`. **Fixed** with a ref written synchronously before any `await`.
- [x] **Defect 52:** ~~A camera failure killed the entire SOS~~ — `/sos/trigger` has always taken the video as optional (`video: Optional[UploadFile] = File(None)`); the client never used that path. **Fixed:** a failed recording now sends location only and says so on screen. This is what makes SOS work at all on hardware that cannot record.

#### Was "still open" — now empty. 53 closed by a second device, 54–55 by code

- [x] **Defect 53:** ~~**CameraX never delivers a video frame to `VideoCapture` on the Vivo V2344 (Unisoc `ums9230`).**~~ — **closed 2026-10-15: it is that one handset, not the code.** The owner ran SOS on a second Android phone and **video captured, uploaded and arrived attached to the alert email.** That was the step this row asked for in its own last line — *"next step is data, not code: try a second Android handset"* — and the data came back on the side of the code.

      The Vivo finding stands exactly as measured and is not retracted: at `Quality.LOWEST`, `Quality.SD` and the 1080p default the recording runs its full ten seconds, audio is captured throughout, the encoder is configured correctly, and `Recorder` logs *"waiting for video keyframe"* 43 times a second for the entire duration. What changed is the *scope* of the claim. One device could not distinguish "our capture code is wrong" from "this SoC's CameraX is wrong", and a second device settles it: **Unisoc `ums9230` driver behaviour, upstream of anything in this repo.**

      **No code change, and none is wanted.** The remaining lever is still CameraX's `PreviewView` implementation mode (`TEXTURE_VIEW`, which expo-camera does not expose as a prop), and a native patch to work around one SoC is not worth carrying. Defect 52 is what makes this survivable and it is the right permanent answer: a failed recording sends **location only and says so on screen**, so the alert goes out on hardware that cannot record. That degradation is now a tested product behaviour rather than a workaround for an open defect.

      ⚠️ **The claim to make is still conditional** — *"location to emergency contacts in seconds, plus a video clip where the hardware supports it"* — because the fleet has one confirmed device that cannot record. Demo on the phone that works.
- [x] **Defect 54:** ~~**`crime_reports` and `risk_flags` have no pipeline between them**~~ — **fixed, with one correction to the proposed bridge.** The mechanism was right: Rumour Guard's logic applied to user reports, N independent reports, same area, same window. The destination was not. A report cluster cannot be a `risk_flag`: a flag is a *mobility* claim, `MobilityImpact`'s six values are all about traffic flow (a corner where people were robbed is not a road that is blocked), and `policy/framing.py` bans `theft`, `robbery`, `assault` and twenty more from any published flag text — *"a risk flag is the product's own published claim about a place, and it does not get to say any of this."* Promoting into `risk_flags` would have needed a new kind, a wider `MobilityImpact` and a loosened framing guard: three changes to the table whose correctness this project has invested most in.
      So the pipeline ends in a **sibling** table, `community_clusters`, reusing the mechanism (dedup identity, corroboration count, decay, derived expiry, the sweep) without diluting the contract. What it publishes is a count and a recency — *"3 independent reports within 200 m in the last 6 days"* — which states what the system knows and never characterises the place. Precedent: `scoring/chronic.py` already puts police crime statistics on the map as a framed claim.
      Also fixed, same commit: `crime_reports.status` allowed `('pending','verified','investigating','resolved')`, mixing a trust question nothing could answer with a casework question `gd_drafts` already owns — every user saw "Pending" forever beside an unreachable `✓`. It is now `('filed','withdrawn','removed')`, `verified` is dropped, and **the self-verify hole is closed**: `crime_reports_update_own` granted UPDATE on your own row and `status` was a column on it, so three lines of Supabase client code self-awarded `verified = true`. Table-level UPDATE is revoked from `authenticated` and granted back column by column, omitting `status`, `user_id` and `created_at`. Reports are also private to their author now (SELECT was `using (true)`; `MapScreen` read every report ever filed, unbounded in time and space). **S29 / B13.**
- [x] **Defect 55:** ~~`migrate.py status` reports two of D08's migrations as `pending` when they are applied.~~ — **closed 2026-10-15.** `status` now reads `applied` for all 11.

      **Verified before marking, not assumed.** Marking a migration that did *not* run is worse than the false `pending` it fixes: the schema change is skipped forever and the ledger claims otherwise. Evidence both had run — `gd_drafts` exists and only `20261010120000` creates it; `gd_profiles` exists and only `20261010160000` creates it; and `public.users` has **no** `gd_*` columns, which is right because the first migration adds them and the second drops them again after moving the profile to `gd_profiles`. The absence was the confirmation, which is the opposite of how it first read.

      **A `mark` command now exists, because the root cause was that it did not.** `ledger_insert`'s docstring argued that bundling the ledger insert into the `sql` paste was *"why there is no separate 'mark this as applied' command"*. That assumption is what cost five days: the paste is one step whose last line is the ledger insert, so an operator runs the DDL, sees it succeed and closes the tab. The only recovery was `up`, which re-runs. `mark VERSION` refuses a version with no file on disk (the checksum has to come from somewhere), refuses one already recorded, and without `--yes` prints the `create`/`alter` lines and exits 1 without connecting. It records `applied_by='marked'` so the ledger distinguishes this from a real run.

      **A test caught a flaw in the fix itself:** the first version connected to the database *before* checking `--yes`, so being told what the command would do required `DATABASE_URL` — making the safe path the harder one. Reordered. 3 tests added (600 → 603), covering the two refusals and the argparse wiring, on the principle that a handler argparse never reaches is the same as no fix.

      ⚠️ **One drift remains and it is not this defect** — see the `journeys` finding in `PROGRESS.md`.

#### Found by writing an ADR, 15 Oct — and it was the worst defect in the repo

**B1 was three documents and no code. Writing one of them found a live
authentication bypass.** That is the entire argument for ADR documents, made
accidentally and better than any argument for them could have been: the fault
had been sitting in `endpoints/auth.py` since the inherited application, through
every sprint, every device walkthrough and 684 passing tests, because **nothing
ever called it.**

- [x] **Defect 56:** ~~`POST /api/v1/auth/login` returns a valid, accepted access token for any email, with no credential check — an unauthenticated bypass of every protected endpoint.~~ — **found and fixed 2026-10-15 while writing ADR 0002.**

      `/auth/login` and `/auth/register` were registered, unauthenticated, and minted `create_access_token({"sub": "user_id", "email": request.email})`. `verify_password` was imported in that file and never called. Both sat under a `# TODO: Implement login logic` comment, which is why they read as harmless stubs — **they were not stubs, they returned working credentials.**

      **Measured end to end before touching anything**, because "is it actually exploitable" is the only question that matters: the forged token passed `verify_supabase_token`, and `get_current_user` returned `{'user_id': 'user_id', 'email': 'attacker@example.com'}`. So every endpoint behind that dependency was reachable without credentials — `/sos/trigger`, which emails a police station as of the same day, and `/ai/*` and `/casework/*`, which spend LLM budget per call.

      **Three independent faults, all three fixed rather than the cheapest one.** (1) The backend could *mint*: `create_access_token`/`create_refresh_token` signed with `JWT_SECRET_KEY`, contradicting the whole reason for moving to JWKS in defect 33. (2) The verifier accepted **HS256** whenever that secret was set — so what the backend could sign, the backend would trust, and `.env` is committed deliberately here, so the secret is not secret. (3) The **`aud` claim was not required**: `options={"verify_aud": True}` with `audience="authenticated"` accepted a token carrying no `aud` at all. Fault 3 alone would have blocked the bypass.

      Deleted: `endpoints/auth.py`, its `include_router` line, `schemas/auth.py`, and the four helpers `create_access_token`/`create_refresh_token`/`verify_password`/`get_password_hash`. Narrowed: `_ALLOWED_ALGORITHMS = {"ES256", "RS256"}`, refused on the algorithm alone before any key lookup. Added: `options["require"] = ["exp", "aud", "sub"]`. Also removed `JWT_ALGORITHM` (which defaulted to `"HS256"`), `ACCESS_TOKEN_EXPIRE_MINUTES` and `REFRESH_TOKEN_EXPIRE_DAYS` — they described a backend that issues sessions.

      **Verified both directions.** Forged token now `REFUSED: Unsupported token algorithm: HS256`; `create_access_token` raises `ImportError`. And legitimate auth is intact: `/sos/history`, `/notifications/config` and `/users/me` all return **401** for missing *and* malformed tokens, API boots clean. The client was never affected — `api.service.ts` has always refreshed through `supabase.auth.refreshSession()`, and its comment already said `/auth/refresh` was a stub that *"would have 422'd even if it were implemented"*.

      `tests/invariants/test_the_backend_cannot_mint_a_token.py` (10 tests) asserts **structure, not behaviour** — no module under `app/` may call `jwt.encode`, the four helpers must not exist by name, no `/auth` route may be registered, both deleted files must stay deleted, symmetric and `alg: none` tokens must raise, and the required-claims list must survive. Behaviour tests cannot catch this class: the bypass survived *because* it was never exercised, the same reason defect 31's unconditional police routing went unnoticed. One of those tests reads `JWT_SECRET_KEY`'s callers via **`ast` rather than a text scan**, after the first version flagged `core/security.py` — whose docstring merely *explains* the deleted helpers. Prose about a credential is not use of it, and a check that cannot tell the difference gets suppressed instead of fixed.

      ⚠️ **`JWT_SECRET_KEY` survives and its name now lies.** Its only remaining reader is `agents/report_corroboration.py`, as the HMAC key behind B13's `reporter_ref`. **Rotating it silently re-pseudonymises every reporter** — one person who reported twice becomes two people, and corroboration counts change. It is closer to a schema constant than a credential; a rename belongs with a migration that touches `community_clusters`.

#### Found by B9's fleet status, 15 Oct — two agents nobody was watching

⚠️ **Numbering note: there are two "Defect 56"s already** — the auth bypass above and a
`Glass` double-padding entry in the UI list below. Pre-existing collision, left alone rather
than renumbered because other documents cite both. These two start at **57**.

The pattern both share is the one B9 exists for: **a failing agent writes an `agent_runs` row
and nothing else.** No alert, no empty-output warning, and until this sprint nothing read that
table back. Writing the status command took an afternoon and found a feature that had never
worked once.

- [x] **Defect 57:** ~~`report_corroboration` has never completed a single successful run. 38
      runs, 0 `ok`, `community_clusters` empty — and three documents describe B13 as landed.~~
      — **found and fixed 2026-10-15, within minutes of B9's first output.**

      `crime_reports.incident_date_time` is `timestamp without time zone`. The agent bound
      `since = ctx.now - CLUSTER_WINDOW`, which is timezone-aware, and **asyncpg refuses to
      encode an aware datetime into a naive column** — it raises while binding, before the
      statement is sent, so the run died on its first query every hour on the hour.

      **The near miss that makes this worth reading:** the agent already handled this column
      correctly *on the way out*. `_rows_to_candidates` reads it back as UTC, with a comment
      explaining that it has to, because it is compared against `auth.users.created_at`. The
      author understood the mismatch and handled one direction of it. Only the bound parameter
      was missed, and no test exercised `run()` against a real column type.

      Fixed by converting the window boundary to naive UTC — the **same reading**
      `_rows_to_candidates` applies, so the boundary and the rows inside it are interpreted
      identically. **Not** fixed by migrating the column to `timestamptz`, which is the correct
      long-term remedy and is deliberately deferred: `crime_reports` is written Supabase-direct
      by the client under ADR 0001, so changing its type is a migration against a table another
      checkout is writing to, and that does not belong inside a bug fix.

      **Verified:** first successful run in the agent's history — `status: ok`, 8 reports in the
      window, 2 eligible, 0 clusters published. Zero clusters is **correct, not a second bug**:
      publishing needs two independent reporters within 200 m and 14 days, and the two eligible
      reports are not co-located. `tests/invariants/test_report_corroboration.py` gained a guard
      that drives `run()` through a recording session and asserts the bound parameter is naive;
      proven to fail on the reverted code before being kept.

- [ ] **Defect 58:** `rumour_guard.merge_into` violates `risk_flags_sources_match_count`
      whenever a flag accumulates articles from two **commonly-owned** outlets. **Found
      2026-10-15 by B9's status output; diagnosed, not fixed — it needs a decision that is not
      mine to take.**

      The constraint is `jsonb_array_length(sources) <= source_count`, and its comment states
      the premise: *"A flag may cite fewer SourceRefs than its source_count (Rumour Guard can
      count a corroboration it does not keep the full text of) but never more."*

      `merge_into` appends **one `SourceRef` per article** but sets `source_count =
      len(independent_publishers(...))`, and `policy/independence.py` collapses commonly-owned
      outlets into one owner. Its own docstring is the proof: `independent_publishers(
      ["dhaka_tribune", "bangla_tribune"])` → `{'tribune_group'}`. **Two refs, count of one, and
      the constraint demands refs ≤ count.** So independence grouping pushes the count *below*
      the number of refs, which is the exact direction the constraint forbids — the premise is
      inverted, not mistyped.

      `merge_into`'s docstring also says *"One `SourceRef` per publisher"*, which is what the
      constraint encodes and **not what the code does** — it appends per `source_id`. The
      docstring, the constraint and the code hold three different beliefs.

      **It fails closed, which is why this is a defect and not an incident.** The `UPDATE`
      raises, the flag keeps its previous `sources` and `status`, and the run reports `partial`.
      Nothing is falsely confirmed; corroboration from commonly-owned outlets is silently lost.
      Observed live on flag `cf6152a74071` at `source_count = 6`.

      **Three ways out, and the choice changes what the flag sheet means — owner's call:**
      (a) collapse `sources` to one ref per owner on merge, which satisfies both the constraint
      and the docstring but **discards the second outlet's URL**, and a judge tapping the source
      strip sees fewer links than there are articles; (b) relax the constraint, which gives up
      the protection against `source_count` drifting away from the list it summarises — the
      thing it was added for; (c) keep every ref and add a separate column for the cited count,
      which is honest and is a migration plus a contract change plus the `RiskFlagWire` mirror.
      **(a) is the smallest and (c) is the most truthful.** Worth noting that the *badge* a judge
      reads says "Confirmed — N sources" where N is the independent count, so (c) would let the
      sheet show "3 articles from 2 independent outlets", which is the most accurate claim this
      system can make and is strictly better than what it says today.

#### Found on a phone, 13 Oct — the UI defects live navigation surfaced

All four were found from screenshots rather than from a gate, which is the thing they have in
common: **none of them breaks anything.** `tsc`, `jest` and `eslint` were green through every
one. A control whose label is invisible still works; a card that covers the map still renders.
That is why they survived, and why the three that generalise now have tests.

- [x] **Defect 56:** ~~`Glass` was padded twice on the route planner~~ — `style` lands on the
      **shell** and the `padding` prop on the **inner content box**, so a `padding` in the style
      is applied *in addition to* the prop. `styles.searchBox` set `padding: space.lg` while the
      component was also passed `padding={space.lg}`, so the content was inset **32pt on every
      side instead of 16** — 64pt of vertical whitespace, about a quarter of the card's height,
      spent on nothing. Introduced by the glassmorphic migration, whose note read *"what stays
      is the padding and the elevation"*: true of the elevation, already supplied by the prop
      for the padding. **Fixed**, and pinned by a test that brace-matches the style body — a
      first attempt sliced to the next `},` and reported a false positive on a one-line style.
- [x] **Defect 57:** ~~The selected mode and the selected route were invisible~~ — `profileChipActive`
      set `backgroundColor: t.brandStrong` and `profileChipTextActive` set `color: t.brandStrong`:
      text painted in its own background colour. The same pair existed on the route card's tabs,
      and the active tab's `100/100` was additionally drawn in `safetyColour`, i.e. green on
      blue. **Fixed** to `t.onBrand`; the safety colour moved to the *inactive* tabs, where it
      sits on a soft fill and is more useful anyway — comparing the options you have not picked
      is what that row is for. **Pinned** by a source scan over the `*Active`/`*Selected`
      convention, verified to fail on both originals.
- [x] **Defect 58:** ~~The snapped-position marker never appeared~~ — `tracksViewChanges={false}`
      from the first render. A `Marker` with React children takes its bitmap from the child on a
      native draw pass, and with tracking off from the start that snapshot can happen before the
      child has drawn. **`RiskFlagMarker` already documents this at length and it was
      reintroduced anyway**, and it was worse there: a flag marker's `key` changes on the next
      `as of` tap so a blank snapshot recovers itself, while there is one follow dot whose
      content never changes, so it would have stayed blank for the whole walk — showing as a
      route trimming perfectly with no dot on it. **Fixed** by extracting `FollowMarker` with the
      same settle (`onLayout` + two frames + a timeout backstop), pinned by four tests.
- [x] **Defect 59:** ~~The expanded route card covered the whole map~~ — and it took **two**
      fixes. `maxHeight: '76%'` was a guess that held until the route planner grew past a quarter
      of the screen, at which point the details covered the fields that produced them; capping it
      against the *measured* search-card height fixed the overlap, and the card then grew to fill
      exactly the gap, which is still a screen with no map on it. **Clearing the control above
      you is not the same as leaving the map visible.** A route card that hides the route is the
      one thing it must never do — the point of opening the details is to read them against the
      line on the map. **Fixed** with two constraints: never reach the search card, and always
      leave a band of map (16% of the window, floor 120pt). Nothing is lost, because the expanded
      body is already a scroll view.



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

- [x] ~~Finish `notification.service.ts`; EAS project id; server-side send~~ **Done in B6a.** The service was rewritten: its four Android channels were created and then never used (`getChannelId()` had no call sites, so every notification landed on the fallback channel), it wrote the push token to `SecureStore` where nothing read it, and `getDangerColor()` graded severity on the legacy **0–10** scale. Server-side send is `app/alerts/` + the `alert_dispatch` agent. ⚠️ The EAS project id is a **slot in `app.json`, not a value** — `eas init` and the FCM upload are account work, written out in `docs/walkthroughs/B6a.md` Part 2
- [x] ~~Per-category user preferences~~ **Done in B6a.** `notification_preferences`, three categories cut by what somebody would plausibly silence separately, plus a severity floor, quiet hours and a self-imposed cap. Chronic alerts default **off**
- [x] ~~**Alert fatigue is a listed risk (concept doc §12):** conservative thresholds and a documented rate cap per user per hour, from day one, with a test~~ **Done in B6a.** `MAX_ALERTS_PER_USER_PER_HOUR=3`, enforced in one pure function, 33 tests in `tests/invariants/test_alert_fatigue.py`. Phase 3's exit line is `test_the_fourth_alert_in_an_hour_is_refused`
- [x] ~~Every alert carries its explanation and source count~~ **Done in B6a.** Both in the body text, and `tests/invariants/test_alert_text_is_framed.py` asserts the body is the forwarded `mobility_statement` plus byte-identical boilerplate — nothing composed about a place
- [ ] ⚠️ **NOT DONE: verified on a device.** Expo Go cannot receive Android push (removed SDK 53), so this needs a development build. B6a.md Part 1 verifies everything except delivery on Expo Go today

---

## S17 — Background location & geofence alerting

**Suggested owner:** Arafat. **Prototype:** walk toward a seeded flag, get a notification before reaching it.

- [x] ~~`expo-task-manager` + `expo-background-fetch`, battery-conscious. The `app.json` permissions have been declaring this capability with nothing behind it since the beginning.~~ **Done in Guardian (11 Oct).** `expo-task-manager` only — **no** `expo-background-fetch`, and that is the design: `Location.startGeofencingAsync` hands circles to Android's `GeofencingClient` and **the OS does the detection**, waking a headless task on a crossing. A JS polling loop would be suspended by Android and is the fastest way to drain a phone; the OS fuses GPS with wifi and cell and batches wake-ups across every app that asked
- [x] ~~Retention window from the S03 registry applied to stored locations~~ **Not applicable, by design.** No location history is stored at all — the geofence handler needs no position, only the region identifier the OS hands back, and `push_devices.last_location` holds a single overwritten point. `public.user_locations` is still written by nothing. There is no retention surface here to govern, which is the better answer than a window on one
- [x] ~~Geofence alerting — crossing into an active flag radius notifies with the mobility statement and source count. Debounced; no repeat for the same flag.~~ **Done.** Watched at radius **+ 250 m** so the warning arrives while there is still a junction to turn at; the notification forwards the server-framed `mobility_statement` verbatim plus the source count; six-hour per-zone debounce with suppressed crossings written to a user-visible log, so "it stayed quiet correctly" is distinguishable from "it never fired". **Local** notification, not a push — detection is on the phone
- [ ] ⚠️ **NOT DONE: measured battery impact recorded.** Needs a day of real use on a charged phone, which no amount of code gets you. The design argument is that the OS's own geofencing is far cheaper than a JS location loop, but that is an argument, not a measurement
- [x] ~~⚠️ **NOT DONE: verified on a device.** `docs/walkthroughs/GUARDIAN.md`, which runs entirely on the phone~~ **Done 15 Oct**, against a **seeded flag** (`scripts/seed_flag_here.py`) rather than an outdoor walk. Steps 1–5 of GUARDIAN.md Part 1 all passed: the *"all the time"* permission, the zone watch registering, the crossing firing the headless task, the notification carrying the mobility statement, the six-hour debounce suppressing the repeat, and both outcomes appearing in the history log. A seeded flag is the real geofence — Android does not know or care who wrote the row — so this closes the box the row was asking about. Step 6 (the pocket walk) stays optional and unrun, which leaves the **+250 m margin unmeasured at walking pace**; the battery box above is independent and stays open

---

## S18 — Trips & hot words

**Suggested owner:** Nakib. **Prototype:** start a trip, see live progress, complete it.

- [ ] `app/trips/` + migration: start, destination, planned route, checkpoints, status. **Journey Guardian's substrate, built a phase early on purpose** — S22 inherits a working trip model instead of building one under time pressure. ⚠️ **Still not built.** B8 did the hot-words half only; this is the half B10 depends on
- [ ] `features/journey/` — start/end a trip, live progress, ETA. ⚠️ **Still not built**
- [x] ~~**Hot words, done properly.** Delete the Supabase-only dead loop. On-device wake-word detection, user-configurable phrases, no continuous upload. **If no library meets the privacy bar, ship a prominent manual SOS and say so in `PROGRESS.md` — do not ship a fake.**~~ **Done in B8.** On-device via `expo-speech-recognition` with `requiresOnDeviceRecognition`, and — the part that matters — the app **refuses to listen** when `supportsOnDeviceRecognition()` is false rather than accepting the library's silent fallback to network recognition, pointing at the manual SOS button instead. Picovoice Porcupine was the intended engine and its free tier ended 30 Jun 2026. **Armed sessions, not an always-on wake word**, and the UI says which. `src/features/voice/privacy.test.ts` asserts the privacy properties by reading the source, because the failure is a missing option that no running app can show you
- [x] ~~`/voice/analyze` either works against real hot words or is removed~~ **Removed in B8.** It ignored the caller's stored phrases for a hardcoded list and returned `trigger: false` unconditionally. Matching is on-device, so an endpoint for it would mean uploading audio. `speech.service.ts` and `useVoiceRecorder.ts` went with it — **zero audio upload paths remain in the app**
- [ ] ⚠️ **NOT DONE: verified on a device.** `expo-speech-recognition` is a native module, so this needs a development build (the same one B6a needs) and Android 13+

### Phase 3 exit criteria

- [ ] `RISK_SURFACE_IMPL=db` carries real agent output into routing and alerts. ⚠️ The **seam** is done — `alert_dispatch` reads through `RiskSurface`, so alerts work on `db` and `seeded` alike — but live ingestion yields almost nothing, so in practice this still carries fixture output. Deferred by the owner, 10 Oct
- [ ] Flag precision measured on real data and recorded. Blocked on the same thing
- [x] ~~Alert rate cap verified by test~~ **Done in B6a.** `tests/invariants/test_alert_fatigue.py::test_the_fourth_alert_in_an_hour_is_refused`, plus `test_six_qualifying_flags_produce_three_alerts_not_six` for the within-sweep case a per-flag loop gets wrong
- [x] ~~No continuous audio upload anywhere in the app~~ **Done in B8**, and now **zero** audio upload paths of any kind: `/voice/analyze`, `speech.service.ts` and `useVoiceRecorder.ts` are deleted, and hot-word matching is on-device. `src/features/voice/privacy.test.ts` asserts it mechanically
- [ ] A real device receives a push within 60 s of a flag appearing on its corridor. ⚠️ **The code is there and the cadence is right** — `alert_dispatch` runs `* * * * *`, which is why that is the cadence — but it is **unverified on a device**: Expo Go cannot receive Android push, so this needs the development build in `docs/walkthroughs/B6a.md` Part 2 §E step 7

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

🟢 **Delivered as B9, 15 Oct.** Two of the five boxes below are done, one was answered
differently from how it was asked, and the two that remain are cost and accuracy trends.

- [ ] Flag counts by status / kind / age
- [x] ~~Agent run history with status, duration, items in/out, errors~~ — **`python -m app.agents
      status`**, over the `agent_runs` rows that had been written since D01 and read by nothing.
      Per agent: state, last-run age, cadence, last status, items in/out, 24-hour run and failure
      counts, error text, and a written diagnosis for a stuck or late agent rather than a column
      the reader has to interpret. Exits 1 on `late`/`problem` so it is usable as a health check.
      **Logic in `app/agents/health.py`, not in the CLI**, which is what let the same measurement
      feed a second reader without the two ever disagreeing.
- [ ] LLM cost and cache-hit rate per agent run
- [ ] Geolocation accuracy trend against the committed baseline
- [x] ~~This is for us, not for users — a simple authenticated page is enough~~ — **half right,
      and the owner corrected the other half.** The operator half is a terminal command, not a
      page: there is no admin UI to host one in, and an authenticated web page would have been a
      new surface to secure for an audience of two. But *"not for users"* did not survive
      contact with the question users actually have. **`GET /api/v1/agents/status` and a System
      Status screen under Profile → Safety** answer *"is what I am looking at current"*, which
      the app previously could not answer at all — a quiet map and a map that is quiet because
      nothing has run look identical. The user payload is narrower than the CLI's on purpose
      (no error text, no item counts, no failure tallies; see `AgentHealthReport`'s docstring),
      and the endpoint **is** authenticated, unlike `/ingestion/status`, which is open because
      *"it describes public news, not a user"* — fleet health describes the deployment.

      ⚠️ **This row's real yield was not the readout.** Its first output showed
      `report_corroboration` at 38 runs and 0 successes — **defect 57**, B13's agent, which had
      never worked, leaving `community_clusters` empty while three documents called B13 landed.
      It also surfaced **defect 58**, a `risk_flags` constraint violation in `rumour_guard`'s
      merge. Both were invisible because a failed agent writes an `agent_runs` row and nothing
      else: no alert, no empty-output warning, and no reader.

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

**Partly delivered early, from the other direction.** B13 built corroboration over *user
reports* rather than confirmation of *news flags* — `app/agents/report_corroboration.py`,
`app/policy/community.py`, `community_clusters`. Async by design (an hourly agent, nothing
synchronous), and it needed no new UI affordance, which is what made it safe to land before
the demo. What remains below is the half that asks a user a question.

- [ ] Request confirmation from users physically near an unconfirmed flag (concept doc §5.5)
- [x] Asynchronous by design — it is an abuse surface, and async is the defensible version
- [x] Abuse controls, as far as they can honestly go: distinct accounts only
      (`independent_reporters`), one report per account per cluster, and an account-age gate
      measured against the *incident* rather than the filing time, so waiting a day is not a
      way around it. Written up plainly in `policy/community.py` — it makes a manufactured
      cluster expensive and auditable, not impossible.
- [ ] **Proximity proof.** The remaining tier, and a deliberate privacy trade:
      `push_devices.last_location` is a single overwritten point, and requiring it would
      decline reports from anyone who filed from home.
- [ ] **Phone verification gate.** `users.phone` and `users.is_verified` exist and
      `eligible_reporters()` is the seam, but registration does not verify a phone today, so
      requiring it would publish nothing at all.
- [ ] **Reporter reputation weighting.** Needs ground truth about which past reports were
      real. There is none.
- [ ] This closes the concept document's "Deferred to roadmap" list

---

## S30 — Source breadth & news-sourced crime

**Delivered 2026-10-14, out of sequence,** from an owner R&D request about widening the
ingestion pipeline. Two halves: more publishers, and a third publishing surface.

### Half one — three publishers became nine

The pipeline read **three sources, all television channels**. That was a quiet weakness
rather than a neutral fact: `status = 'confirmed'` needs two or more *independent*
publishers, and Dhaka TV newsrooms follow each other and run the same agency copy. A
measured dry run showed the problem exactly — **0 relevant articles across all three** in
one window, while the six added sources found a factory fire reported by four of them.

- [x] **Prothom Alo, Jugantor, Bangla Tribune, Ittefaq, Samakal, Dhaka Tribune.**
      Sixteen candidates surveyed against robots.txt, a machine-readable listing of
      *recent* articles, and whether the body is in the HTML. The ten rejections are
      recorded in `app/ingestion/sources/__init__.py` with their reasons, because the next
      person to go looking will otherwise spend the afternoon rediscovering them.
- [x] **English publishers, and the measurement that justified them.** Of the 1022
      gazetteer entries, **1010 (98.8%) carry a `name_en`** against 816 (79.8%) with a
      `name_bn` — romanised place names resolve *better* than Bangla ones. `INCIDENT_WORDS_EN`
      and English place filler/tail lists were added alongside the Bangla ones.
- [x] ~~An English article parsed correctly and stored nothing~~ — `bangla_paragraphs`
      drops every paragraph with no Bangla character in it, which is right for a Bangla
      article and deletes an English one in full. `article_body(paragraphs, language=)`.
- [x] ~~`\b(?:...)\w*` matched *Jamuna* for `jam`~~ — a leading word boundary plus a suffix
      wildcard hands back exactly the false positives the boundary exists to stop. Every
      inflection is now written out and the pattern closes with `\b`. **Caught by the test
      written for that case**, which is the only reason it was not shipped.
- [x] ~~Desk names: `sport` and `foreign`~~ — the exclusion list had `sports` and
      `international`, and Dhaka Tribune files at `/sport/` while Bangla Tribune files at
      `/foreign/`. Both found on the first live run.
- [x] **The extraction queue is round-robin, and that is a correctness fix, not fairness.**
      Concatenating nine publishers and cutting to `MAX_EXTRACTIONS_PER_RUN` means the first
      publisher fills the budget every run — so a *second* outlet's account of this
      morning's fire is never extracted in the same pass, and **nothing can ever reach
      `confirmed`** however many outlets are added. The obvious diagnosis would have been
      "Rumour Guard is too strict", which would have been wrong. `interleave()`.
- [x] **`_SAME_OWNER` partly filled.** Dhaka Tribune and Bangla Tribune are one house;
      adding both while letting them corroborate each other would manufacture agreement
      rather than find it. The rest stays empty — guessing Bangladeshi media ownership is
      still worse than admitting the gap.
- [x] ~~A comma-separated qualifier never resolved~~ — "Road No 1 in Lake Circus,
      Kalabagan" was discarded although `Kalabagan` resolves on its own. Segments are now
      candidates, tried *after* the whole phrase so a precise entry always wins.

### Half two — news-sourced crime, published as attributed citations

**An owner decision, recorded as one:** news-sourced crime is published, *"because they are
coming from news which are verified."* The design that makes that honest is attribution.

- [x] **`news_crime_incidents`** — a third sibling of `risk_flags` and `community_clusters`,
      never a row in either. Not a flag, because `MobilityImpact`'s six values are all about
      traffic flow and `framing.py` bans the vocabulary. Not a cluster, because a cluster's
      trust comes from *several anonymous accounts agreeing* and this one's comes from
      *attribution* — one row type whose trustworthiness is explained two ways is the thing
      to avoid.
- [x] **`app/policy/attribution.py`** — the only writer of the published sentence, with a
      guard that is a different *shape* from `framing.py`'s rather than a weaker version:
      a **positive requirement** (it rejects a statement that does not name its publisher),
      plus bans on characterising the place and on naming any group. `framing.NAMED_GROUPS`
      is shared verbatim — one list, two policies, never relaxed.
- [x] **The database enforces it too.**
      `check (statement like '% reported by %')`. Three layers for one rule, as with
      `risk_flags_confirmed_needs_two_sources`, because this is what a judge will press on
      and the strongest honest answer is that the database will not store the violation.
      Verified against a throwaway PostGIS container: seven refusal cases rejected, the
      well-formed row accepted, `expires_at` derived to 18 days.
- [x] **One model call, two lists.** `NewsExtraction` gained `crimes`; the free tier is a
      few hundred requests a day and asking each article twice would halve the throughput of
      both. The lists share a model call and *nothing else* — separate tables, guards, decay
      and API.
- [x] **`extracted_crimes`**, a separate audit trail, because `extracted_incidents`'
      `kind` CHECK and NOT NULL `mobility_impact` are mobility-only. Writing a robbery there
      would mean a false `'none'` in a column meaning "traffic was not affected" — crime
      back inside the mobility vocabulary by the back door.
- [x] **Crime Guard** (`app/agents/crime_guard.py`) — the corroboration gate, reusing Rumour
      Guard's embedding, similarity and distance rule. The one real difference is a **48-hour
      window** against mobility's 6: a mugging is reported when police confirm it, picked up
      the next morning, and run again when a suspect is arrested. Six hours would turn one
      incident into three pins that look like a pattern.
- [x] **Decay is the answer to the obvious objection.** Five-day half-life, so an incident
      falls below the serve threshold about eighteen days after the report. A crime map that
      never forgets becomes a permanent judgement about a neighbourhood, which §9 rules out.
      Radius capped at 1 km against `risk_flags`' 20.
- [x] **Route scoring**, at 0.35 for one publisher and 0.7 for two or more independent ones
      — above a community cluster's 0.6 ceiling and below a confirmed flag's 1.0. A named
      masthead is a stronger single source than an anonymous one and still weaker than
      several sources agreeing; the ordering *is* the claim, expressed as arithmetic.
- [x] **A fourth marker shape.** The map already spent round (flags), square (scheduled) and
      pill (clusters), so this is a **diamond**, coloured by category rather than by severity
      band — what was reported is a fact about an article, how bad the place is is not.
- [x] `tests/invariants/test_news_crime_is_attributed.py` — 27 cases, including a source
      scan proving nothing but the policy module composes the sentence. **Verified to fail**
      by reintroducing a composed statement, then pass once removed.

### What this half deliberately does NOT do

- [ ] ⚠️ **No fixture, so the offline demo serves an empty layer.** A fabricated row here
      would be a made-up crime report *attributed to a real newspaper*, which is worse on a
      stage than an empty layer.
- [x] ~~⚠️ **Gazetteer coverage is the limiting factor, and it is a real gap.**~~ The first
      live dry run extracted two crimes and geocoded neither: `Satmasjid Road` was **not in
      the gazetteer at all**, in either script, and it is a major Dhanmondi road. The feature
      was correct — "discarded, never guessed" held — and the data was the limit.
      **Closed by B7 below, the same day:** the harvest had never asked OpenStreetMap for a
      `highway`, so roads were absent by construction. `Satmasjid Road` now resolves, with a
      1,154 m radius measured from the road's own extent.

### Rejected during this sprint, with reasons

- [ ] ~~Google Maps Routes API for live traffic~~ — ToS §3.2.3 forbids scraping, caching and
      "creating content from Google Maps Content" independently; polling corridors and
      storing deltas breaches all three. A licensed provider whose terms permit storage
      (Mapbox matches OSM, which OSRM already runs on) is the only legitimate path, and it
      costs money. **Not built.**
- [ ] ~~Facebook page scraping~~ — Meta ToS prohibits it; *Meta v. Bright Data* resolved only
      the contract claim and the tortious-interference claim survived. Operationally fragile,
      and philosophically backwards: adding a firehose of unverified panic to feed a rumour
      filter is solving a problem you created. **Not built.**
- [ ] ~~YouTube bulletins + Whisper~~ — off-the-shelf Whisper is ~79% WER on Common Voice
      Bengali and 11–25% fine-tuned, and what we would extract from the transcript is *place
      names*, the rare proper nouns ASR gets wrong and the gazetteer needs near-exactly. The
      same bulletins are published as text on the same sites. **Not built.**
- [ ] ~~LLM-assigned `confidence_score`~~ — confidence is derived structurally from
      independent publisher count. `geo/agent.py` records why a model's self-reported
      confidence is not trusted: 12.6 km off at 0.78, invented coordinates at 0.95.

---

### Phase 5 exit criteria

- [ ] All eight concept-document agents exist, scheduled, and observable
- [ ] Chronic flags cover the pilot zone; legacy surface retired or justified
- [ ] Forward-dated flags activate and expire correctly
- [ ] GD drafts pass native-speaker review
- [ ] Guardian self-trial complete: <1 false check-in per user per week
- [ ] Measured ৳/day for the full agent fleet

---

## B14 — privacy and retention enforcement

**Delivered 2026-10-15.** The concept document's §9 makes one testable privacy promise:
*"Location history is retained only as long as operationally necessary."* HTTPS and JWT, the
clause's other two parts, were already provable from the transport and the auth middleware.
This one had nothing behind it — no table declared a window, nothing deleted anything, no test
could fail.

- [x] **`app/privacy/retention.py` classifies all 21 tables** — 6 with a delete window, 15
      `KEEP` with an argument. `KEEP` is expressed in the same structure as a window on purpose:
      a reader can then tell "indefinite, deliberately" from "nobody got to it". A test requires
      a `KEEP` reason to be more than a few words and caught two of my own thin ones.
- [x] **The tripwire is the load-bearing test, not the windows.**
      `test_every_table_in_the_database_is_classified` reads the **live schema** and fails on
      anything unclassified. That is how `journeys` surfaced: per-user origin and destination —
      exactly what §9 names — in a table this repository has no code for, applied by hand, no
      committed migration, accumulating rows that afternoon. A sweep written from the models
      would have missed it entirely.
- [x] **Expiry and deletion are kept separate, and a test enforces it.**
      `agents/expiry_sweep.py` marks rows `expired` and keeps them *"because an expired row is
      the evidence that the surface retires things on its own"*. `test_the_expiry_sweep_marks_
      rather_than_deletes` asserts it issues no `DELETE`, so that distinction cannot erode.
- [x] **4 of 6 windows are `PROPOSED`**, and `scripts/purge_expired.py` refuses them without
      `--force`. A retention period is a decision about somebody else's data; a window that
      follows from existing code is `DERIVED`, the rest await sign-off. A test asserts the
      PROPOSED set is non-empty, so nobody can quiet the script by flipping a basis.
- [x] **A real `DELETE` outside the registry — and the first version of the test was wrong
      about it.** It forbade every `DELETE FROM` on a registered table and caught
      `alerts/service.py::delete_device`, which is a privacy *feature*: sign-out erases a
      delivery address because the user asked not to be contacted. The rule is now **clock-driven
      deletes belong in the registry, user-initiated ones belong in the feature and are
      allowlisted with a reason** — plus a test that fails if an allowlisted file stops deleting.
- [x] **Eight date columns are timezone-naive** (`crime_reports` ×3, `sos_incidents` ×2,
      `user_locations.timestamp`, `users` ×2) while the rest of the schema is `timestamptz`.
      Comparing one to an aware cutoff makes asyncpg type the parameter naive and fail. They are
      read as UTC **explicitly in the SQL**, not by trusting the session TimeZone — a window that
      changed meaning with a server setting would be the wrong kind of quiet.
- [x] **The purge is proved, not assumed.** Every window is longer than the project is old, so
      "nothing is overdue" passes by arithmetic and proves nothing about deletion. So
      `test_the_purge_predicate_really_removes_an_overdue_row` plants a year-old `agent_runs`
      row, confirms it counts as overdue, deletes it with the script's own predicate, asserts it
      is gone, **rolls back**, and re-queries on a fresh connection to prove nothing reached live
      data.
- [ ] ⚠️ **The windows need sign-off**, and three carry a second decision with them:
      `sos_incidents` holds references to Storage video, so deleting the row leaves the footage;
      `gd_drafts` does not yet distinguish filed from unfiled; `raw_documents` is read by
      `content_hash` dedup — and *was* also read by B6b's provenance page, which would have
      started lying once rows aged out. **B6b was declined on 15 Oct and will not be built**, so
      that half of the concern is gone and `raw_documents`' window is now a dedup question only.
- [ ] ⚠️ **`emergency_contacts` is the least comfortable `KEEP` in the registry.** Those people
      never consented — the user entered them. That argues for a window and against one at once:
      the data is not the user's to keep forever, and an SOS finding no contact because a timer
      expired is the feature failing at the only moment it matters.
- [ ] ⚠️ **Account deletion is not built**, and `users`, `profiles` and `gd_profiles` all defer
      to it. A window is the wrong instrument for a profile the user fills in once so they need
      not retype it under stress; a cascade is the right one.

**Deliberately not done: the purge is not scheduled.** No `beat_schedule` entry, by decision —
a cron job deleting user data on a window nobody agreed to is the precise failure this module
exists to prevent. **Nothing has been purged.** The dry run reports 0 rows past every window,
which is true today and will stop being true. Also not done: the migration that would make the
timestamp columns consistent.

---

## B11a — the institutional tier (official feeds third)

**Delivered 2026-10-15**, after a feasibility survey the owner asked for before any build —
which was the right order, because **three of the four bodies publish nothing a machine can
read, and establishing that is most of the deliverable.**

- [x] **The survey.** `app/ingestion/sources/dmp_news.py` carries the table. DMP News is
      WordPress: RSS with the article in `content:encoded`, per-category feeds, a 37-page
      sitemap. Fire Service: firefighter joining notices and tenders, `/pages/news` is the DG's
      newspaper op-ed, no incident feed. DNCC: Durga Puja cheque distribution, an e-trolley
      tender, officer postings. DSCC: meeting notices, municipal tax deadlines, WASA bill
      verification. The three government sites run one national-portal CMS with no RSS or API
      and administrative notice boards. **The institutional tier assumed by the three-tier
      standard is largely not machine-readable in Bangladesh.** Say that rather than implying
      the work is pending.
- [x] **The crime category, not traffic.** Both exist. Nine of ten traffic items are the daily
      enforcement counter (`ট্রাফিক আইন লঙ্ঘনে ডিএমপির ২৭৯৯ মামলা`) — a statistic that would
      spend a slot of `MAX_EXTRACTIONS_PER_RUN` to be rejected. The crime feed names Dhaka
      thanas directly: যাত্রাবাড়ী, তুরাগ, উত্তরা, শাহবাগ, রমনা.
- [x] **Registered last in `SOURCES`,** for the reason the harvest layers are ordered: least
      proven source, `live_risk` ingests in order, a slow government host must cost the eight
      established publishers nothing.
- [x] **`read` makes no request.** The body arrives in the feed, so `list_recent` keeps it and
      `read` consumes it — one request per listing, not one per article. Falls back to fetching,
      because a feed that stops carrying bodies must degrade rather than return nothing.
- [x] 🔴 **"DMP is authoritative" could not be done as first decided, and the reason is a
      database constraint.** The owner's first choice was to let one DMP report reach
      `confirmed`, on the sound reasoning that a newspaper reprinting a police release adds no
      independent verification. `confirmed` is enforced by
      `risk_flags_confirmed_needs_two_sources: CHECK ((status <> 'confirmed') OR (source_count
      >= 2))`, so such a row is rejected on insert. Both workarounds are worse than what they
      buy: a migration weakening the CHECK, while
      `tests/invariants/test_single_source_never_confirmed.py` asserts it from the *original*
      migration's text and would keep passing over the hole; or `source_count = 2` for one
      source, which `risk_flags_sources_match_count` permits and which is false data.
      **Resolved as weight on 15 Oct:** `AUTHORITATIVE_PUBLISHERS` makes `confidence()` return
      1.0 instead of `UNCONFIRMED_WEIGHT`, so an official report is not discounted as a rumour.
- [x] **Reopened and decided the other way on 16 Oct, for every publisher, with a
      measurement.** Of 19 flags built from live news, **15 had a single source** — so the
      two-publisher rule left 79% of the surface drawn as a hollow pin and scored at 0.6,
      including a Prothom Alo report of a fire. The owner's position: all ten publishers were
      hand-picked against stated criteria and a national newsroom does not invent a fire, so
      treating one as an anonymous claimant is the thing that is wrong.
      `confirmed` now means **"a vetted newsroom or institution published this, or two
      independent publishers agreed"** (`VETTED_PUBLISHERS`), and
      `20261016150000__a_vetted_newsroom_is_confirmation.sql` replaces the CHECK.
      **The cost, recorded:** corroboration was also the only independent check on *our own
      extraction* — two newsrooms read separately landing on the same kind, place and six-hour
      window. What remains against a mis-extraction is `MIN_CONFIDENCE`, the gazetteer's
      refusal to guess, and the mobility filter. `unconfirmed` now means a **community
      report**, which is the distinction users most need drawn.
- [x] **The authoritative set has a tripwire, because it is dangerous in the direction
      `_SAME_OWNER` is not.** An ownership entry can only *reduce* what we confirm; an
      authority entry *increases* a single source's weight, with no permissive default. One
      member, asserted to be one member, and widening it is a decision about a named
      institution.
- [x] **A police unit is not a place.** The prompt already said *"never the police station"*
      and that was insufficient: **a Dhaka thana is also a neighbourhood.**
      `ডিএমপির অভিযানে গ্রেফতার ৫৩০` self-discards because "DMP" resolves to nothing;
      `যাত্রাবাড়ী থানার বিশেষ অভিযানে গ্রেফতার ১৭` does not, because যাত্রাবাড়ী resolves at
      1.2 km — a thana-wide sweep would have been pinned as one crime at one spot.
- [ ] ⚠️ **Still open: the other two thirds of B11a** — RSS beyond DMP, Telegram, and the
      social-media half the concept document promises in five places. **Until that lands, do
      not say the system reads social media.**

**Deliberately not done:** the traffic category (a statistics ticker); no attempt at Facebook
or Instagram page scraping; no change to `MAX_EXTRACTIONS_PER_RUN` despite a tenth source.

---

## D04 — the relevance filter, measured

**Delivered 2026-10-15.** B7 lifted the gazetteer ceiling; this is the other one.
`live_risk.is_relevant` decides from a headline alone whether an article is worth fetching,
and nobody knew what it was doing. The documented *"~1% of ~390 articles"* was stale on both
counts: a real collection listed **2,622 and passed 167 (6.4%)**.

**A pass rate is not a quality measure.** 1% could be a correctly tight filter or most of
Dhaka in the bin, so the first deliverable was `scripts/measure_relevance_filter.py`, not a
tweak. `collect` lists every sitemap (no bodies — cheap and polite) and records each ref with
the verdict and which sub-matcher fired; `score` reports precision and recall against hand
labels. 417 headlines labelled: all 167 passed, plus a random 250 of 2,455 rejected.

| | before | after |
|---|---|---|
| precision | 0.31 | **0.43** |
| recall (reweighted) | 0.47 | **0.68** |
| missed incidents in the labelled set | 6 | 4 |
| backend tests | 603 | **609** |

- [x] **Recall has to be reweighted, and the first version of this script lied.** It reported
      **0.90**. Labelling is stratified — the passed set is labelled in full because precision
      depends on all of it, the rejected set is sampled — so the raw ratio compares 167-of-167
      against 250-of-2,455 and under-counts misses tenfold. Reweighting by each stratum's rate
      gives 0.47. `score` now prints the reweighted figure, the estimated population miss
      count, and the unweighted ratio labelled *"do not quote it"*, because 0.90 is the
      comfortable number and it would have ended the investigation.
- [x] **No geographic gate existed.** 115 of 167 passed articles were not Dhaka incidents.
      `names_elsewhere` is a **negative** list on purpose: requiring a Dhaka place name is the
      natural design and rejects `ফুটপাতে মারধর`, `বাড্ডায় গৃহবধূর মৃত্যু`,
      `পল্লবীতে ইজিবাইক চালক হত্যা` — Dhaka copy names the locality, not the city — and a miss
      is the expensive error because the article is never fetched and leaves no
      `discarded_reason`. `DHAKA_MARKERS` overrides, so `ঢাকা ময়মনসিংহ মহাসড়কে দীর্ঘ যানজট`
      stays. Tongi, Gazipur, Savar and Keraniganj are **not** listed: the gazetteer decides
      distance, not a headline keyword.
- [x] **`country`/`countries` were excluded as if they meant "foreign"** — they are the
      domestic দেশ desk. Blocked 3 of 6 misses, all inside the pilot box. **The worse cost was
      corroboration and nothing measured it:** the Tongi fire was filed under `capital` by
      some publishers and `country` by others, so `confirmed` was unreachable however many
      papers carried it. A section filter correlated with the publisher caps the corroboration
      ceiling silently.
- [x] 🔴 **ড়, ঢ় and য় each have two Unicode spellings and one never matched.** Precomposed
      (U+09DC/U+09DD/U+09DF) or base-plus-nukta (U+09BC): identical on screen, unequal as
      strings. **1,568 of 2,622 headlines used a precomposed form** while 17 keywords were
      written decomposed — `চাপায়`, `কুপিয়ে`, `ছিনিয়ে`, `ধাওয়া`. Cost on one sample: 17
      headlines including **`বারিধারায় গাড়িচাপায় নির্মাণশ্রমিকের মৃত্যু`**, a worker killed
      by a car in Baridhara, inside Dhaka, plus two truck fatalities. Never fetched, never
      logged. NFC is the right target *because* these letters are composition-excluded, so NFC
      decomposes rather than composes — which also makes NFD and NFC identical here, and made
      the first regression test vacuous until its own premise guard failed.
      **The gazetteer was already immune** (`gazetteer.py:98` runs everything through NFKC);
      the filter did raw `in` tests. Same corpus, same letters, one normalised.
- [x] **`LOOKBACK` deliberately unchanged at 12 h.** Four remaining misses report "too old",
      which reads as a signal to widen it. Their ages are 40.8 h, 40.3 h, 35.0 h and 15.3 h,
      and the agent runs **every 15 minutes** — three would have been caught when fresh. They
      are snapshot artefacts, so the measured 0.68 is **pessimistic** for the running system.
      24 h tested directly: +1 true positive, +2 false positives, precision unchanged.
- [ ] ⚠️ **The remaining 72 false positives mostly need the article body.** Ministers visiting
      hospitals, court testimony about old attacks, fact-checks of mugging videos, LPG strike
      statements. The extraction stage already rejects these. The headline-level wins are done;
      the next lever is the extraction prompt, not this filter.

**Deliberately not done:** no change to `MAX_EXTRACTIONS_PER_RUN` or the free-tier budget; no
LLM in the filter (it runs on thousands of headlines per run); no attempt to label the full
2,622, since a stratified sample with honest reweighting beats a rushed exhaustive pass.

---

## B7 — Gazetteer density

**Delivered 2026-10-14, out of sequence,** immediately after S30, because S30 ended by
naming this the ceiling on the whole pipeline. Track B item, from DEMO_PLAN.md: *"Gazetteer
density beyond the demo zone. Gates geographic expansion."*

**1,022 entries became 6,054.** The gazetteer is the only thing that turns a place name in
an article into coordinates — every agent calls `resolve_place(..., allow_llm=False)`, so a
place this file does not know is an article thrown away. "Discarded, never guessed" working
correctly and the surface being empty are the same observation, and this is the bill.

### What was missing, measured rather than guessed

- [x] **Roads, which were absent by construction.** The old harvest asked OpenStreetMap for
      places, junctions, markets and terminals and *never for a `highway`*. The entry count
      by kind had no `road` line at all — not few, none. So the single most common way a
      Bangla crime report names a location could not resolve, which is why S30's first live
      extraction geocoded neither of its two results. **3,241 road entries now.**
- [x] **The box stopped inside the city.** `23.70–23.90 / 90.33–90.50` cuts off Uttarkhan,
      Dakshinkhan and Turag in the north and Demra, Matuail and Kadamtali in the south, all
      of which are Dhaka. Now `23.66–23.94 / 90.30–90.54`, covering both city corporations.
      Savar, Narayanganj city and Gazipur city stay outside on purpose: they are different
      cities, and `in_pilot_box` is also the sanity gate the LLM tier is checked against, so
      widening it weakens that gate everywhere.
- [x] **Eleven new layers**, each with a reason: `town` (Tongi and the urban fringe are
      `place=town`, never requested before — which is why a fire four publishers covered
      could not be placed), `police` (crime reporting is organised by thana), `water`,
      `bridge`, `campus`, `hospital`, `park`, `mall`, `stop`, and more `place` values.
- [x] **Layers deliberately refused**, recorded in `HARVESTS`: `amenity=school` and
      `place_of_worship` (~1,100 and ~1,200 in the box, names generic — "Government Primary
      School" identifies nothing and gives the fuzzy matcher a thousand near-identical
      strings to score on every lookup), and `boundary=administrative` (thana polygons whose
      names duplicate the `place` nodes while their centroids sit up to 2 km away, so every
      one would collide with a known neighbourhood at a distance that makes both ambiguous —
      turning "Dhanmondi" from resolving into refused).

### A road is a line and this file stores points

That gap is the whole difficulty and it is not solved by pretending otherwise. OSM splits one
road into many `way`s; `out tags center` gives each one's centre, which is enough to measure
the road's extent without fetching geometry. Those centres are chained into one entry per
road per locality.

The chain distance was chosen by measuring 1,570 major-road segments at four thresholds:

| chain | entries | pinnable | refused | names split across clusters |
|---|---|---|---|---|
| 900 m | 550 | 399 | 141 | 47 of 472 |
| 1,500 m | 507 | 411 | 86 | 27 |
| 2,500 m | 491 | 418 | 62 | 15 |
| **4,000 m** | **478** | **419** | **48** | **6** |

- [x] ~~A tight chain distance protects against merging two roads that share a name~~ — it
      does not; it shreds long ones. At 900 m, Begum Rokeya Sharani came out as six pieces,
      Mirpur Road as five and Dhaka–Cumilla Highway as four. Those pieces then share a name
      while sitting kilometres apart, so `resolve_collisions` refuses all of them: the right
      answer for Mirpur Road, reached by accident, at the cost of five junk entries each and
      of also losing shorter roads like DIT Road.
- [x] **The radius is the measured half-extent, and a road that will not fit under the
      ceiling is refused rather than clamped into looking precise.** One constant does both
      jobs. Above 1,500 m a point and a radius cannot describe the road honestly — Mirpur
      Road is ~8 km, so a midpoint pin would be 4 km from the event. This also closes the
      opposite hazard: chaining 4 km *could* merge two different roads sharing a name, but
      any such merge spans over 3 km and is therefore refused, so the worst a surviving merge
      can do is put the pin within the 1,500 m its own radius claims. **155 roads refused on
      this rule.**
- [x] **The same clustering was then needed verbatim for water,** which is the useful
      generalisation: *OSM fragments large features, and fragmentation looks exactly like
      ambiguity.* Hatirjheel arrived as three objects all named হাতিরঝিল হ্রদ, so all three
      were refused and "Hatirjheel" fell through to a 300 m *park* 2.5 km away — a wrong pin
      produced by holding more data about things near the lake than about the lake.
      `cluster_fragments` now serves both.

### Three defects the new data revealed rather than caused

- [x] ~~`_subset_hit` never enforced "numbers are identity"~~ — `_fuzzy_hit` has refused a
      number mismatch since D03 because "Sector 11" and "Sector 10" are 0.89 similar and 2 km
      apart. A *token subset* can mismatch far more wildly and still pass: `{sector, 11}` is a
      subset of `{road, 11, sector, 1}`, so **`Sector 11` resolved to a road in Sector 1 and
      reported 0.90**. Harmless with no roads in the file; a **fabrication** with 3,241 of
      them, and the eval caught it as one.
- [x] ~~An ambiguity refusal could be overturned by a lower tier~~ — the module docstring
      already asserts this about the LLM tier, and it was not true *inside* the gazetteer.
      Two entries carry the exact name "Sector 11" 10 km apart, so `_exact_hit` correctly
      declined, and then `_subset_hit` answered anyway. Falling through treats "we know this
      name is ambiguous" as "we have never heard of it", which are opposite facts.
- [x] ~~Entries outside the pilot box~~ — a bbox filter on a `node` returns only nodes
      inside it, which is why this never arose before; a bbox filter on a `way` or `relation`
      returns everything that *intersects*, and `out center` then reports a centre that can
      be well outside. **21 pieces**, among them `Padma Bridge Rail Link`, which is not in
      Dhaka at all.

### The matcher had to be indexed, not merely grown

`resolve_place` is on a request path (`/geo/resolve`), and both scanning tiers called
`normalise`, `tokens` and `numbers` on every name of every entry on every lookup, with
`difflib` over all of them. **13.6 ms per query at 1,022 entries**, so roughly 80 ms at six
thousand. Names are now precomputed once at load with a token inverted index, a number
bucket, and an exact length band before `difflib` is touched.

- [x] **Verified equivalent, not assumed:** the indexed matcher was diffed against the
      unindexed one over **4,362 queries** — every name and alias in the file, each with a
      token dropped and a character transposed, plus the eval set — with **0 mismatches**,
      before any semantic change was made. 20× faster at the old size.

### Results

| | before | after |
|---|---|---|
| entries | 1,022 | **6,054** |
| road entries | **0** | **3,241** |
| accuracy on real places (53-case held-out set) | 93.3% | **95.6%** |
| fabrications | 0 | **0** |
| wrong pins | 0 | **0** |
| coverage of 193 real Dhaka references | 71% | **84%** |
| of those, named roads | 15% | **61%** |
| backend tests | 559 | **601** |

- [x] `scripts/probe_gazetteer_coverage.py` + `data/eval/geocoding/coverage.json` — a
      **coverage** measure over 193 references written the way a news desk writes them
      (roads, thanas, the outer city, and a landmark set carried as a regression check). It
      deliberately does **not** check *where* the point is: that is
      `data/eval/geocoding/baseline.json`, and inventing ground truth for 193 places would be
      worse than an honest coverage count. The two are complementary.

### Deliberately not done

- [ ] ⚠️ **`Sector 10` went from HIT to MISS, and that is correct.** The widened box brought
      a *second* Sector 10 into scope, so the name is genuinely ambiguous now and is refused.
      The eval case was written when only one was in the box. Resist "fixing" it by weakening
      the ambiguity rule.
- [ ] ⚠️ **Coverage went 86% → 84% when the number-identity rule was added**, because 2%
      were false matches. Accuracy rose at the same time. That trade is the point, and the
      two numbers must be read together.
- [ ] **21 of 193 references still resolve to nothing**, mostly minor roads and the outer
      fringe. Aliases are the remaining lever and they are hand work; `aliases.json` now
      documents the maintenance a re-harvest requires.
- [ ] **`stop` is the weakest layer and the slowest to fetch** — a bus stop is named after
      the place it serves, so `_drop_borrowed_names` strips most of them again. 418 entries
      for three of its four tiles taking longer than every other layer put together. A future
      harvest may reasonably drop it.

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

# --- Alerting (S16; shipped in B6a) ---
PUSH_ENABLED=false              # delivery off until the Expo + Firebase setup in
                                # docs/walkthroughs/B6a.md Part 2 is done. With it
                                # off the dispatcher still runs, still applies the
                                # cap and still writes the ledger -- it just logs
                                # what it would have sent. On without credentials
                                # means an endpoint that reports success while Expo
                                # rejects every message.
MAX_ALERTS_PER_USER_PER_HOUR=3  # verified by tests/invariants/test_alert_fatigue.py
ALERT_RADIUS_M=500              # wider than ROUTE_CORRIDOR_RADIUS_M (150) on
                                # purpose: that asks "is this on this road", this
                                # asks "is this near enough to matter to someone
                                # standing here"
EXPO_PROJECT_ID=                # must MATCH frontend/app.json extra.eas.projectId
EXPO_ACCESS_TOKEN=              # only for Expo's "enhanced security" mode

# --- Journey Guardian (S23) ---
GUARDIAN_CHECKIN_TIMEOUT_SECONDS=300
GUARDIAN_ESCALATION_STEPS=3

# --- Privacy (S03 registry, S30 enforcement) ---
LOCATION_RETENTION_DAYS=30
RAW_DOCUMENT_RETENTION_DAYS=180
TRIP_TRACE_RETENTION_DAYS=14

# --- Feature flags ---
POLICE_ROUTING_ENABLED=true        # SOS emails the nearest Dhaka thana (defect 17; code default false)
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
