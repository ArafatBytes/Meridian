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

*Last updated: 2026-10-08 · by: Arafat · after: D05 (closed on a device)*

| | |
|---|---|
| **Last sprint completed** | **D05 — ✅ CLOSED.** All 11 steps of [`docs/walkthroughs/D05.md`](docs/walkthroughs/D05.md) passed on a real device, first run, no issues — including the promotion and the reset. D01–D04 all closed |
| **NEXT SPRINT** | **D06 — Routing, explanations, and the reason why** (scheduled Oct 16–17) → [DEMO_PLAN.md](DEMO_PLAN.md) §D06. ⚠️ **It assumes the OSRM graph exists and it does not** — see Background activities |
| **Baton holder** | **free** |
| **Trunk** | `develop` · D05 committed and pushed |
| **Build status** | 🟢 **GREEN.** 250 backend tests pass (23 new), `mypy --strict` clean on 83 files, `tsc` clean, ESLint 0 errors. Pre-existing and untouched: 2 failures in `tests/test_crime_vision.py` (D07's) |
| **Slack** | D05 was scheduled Oct 15 and built Oct 8 — **seven days ahead.** The OSRM graph (§9 item 2) is **still not started** and D06 assumes it is built. It is now the only thing standing between the slack and D06 |
| **Phase** | 0 — Foundation & Contracts |

### ✅ Verification is now visible, not just stored

- **The map carries the tier.** Hollow + dashed + `?` for a single-source claim; solid +
  filled + source count for a corroborated one. The radius circle splits the same way.
- **The sheet carries the provenance.** Which publishers, a **Confirmed** time (or
  `time not recorded`, never a substituted `observed_at`), and the consequence stated:
  shown and counted at **60% weight**, never hidden.
- **The promotion is repeatable on demand** — `python -m app.agents promote-demo`,
  through the production merge path, `--reset` to rehearse again.

### 🔴 The finding of the sprint: a planned constant was wrong

`DEMO_PLAN.md` §9 declared `DEDUP_SIMILARITY_THRESHOLD=0.82`. Measured on
`all-MiniLM-L6-v2` against the text the system actually embeds, **0.82 merges 1 of 18
known duplicate pairs** — D05 would have shipped as a **no-op that looked implemented**:
four outlets would still have produced four unconfirmed pins, and nothing in a green
test suite would have said so. Now **0.72**, the highest threshold with zero false
merges. `scripts/eval_dedup.py` + `data/eval/dedup/clusters.json` make it reproducible.

**And the classes are not separable.** Lowest true duplicate 0.503, highest false pair
0.718 — and the second account of the real Mohakhali fire scores **0.718**, identical to
the worst false pair. Recall is **~56% by choice**, precision 100% on the labelled set.
That asymmetry is deliberate: a missed merge costs a duplicate pin, a false merge puts a
`confirmed` badge on an event that did not happen. It is also exactly why the scripted
replay exists rather than hoping two outlets phrase a fire alike mid-demo.

### ⚠️ One thing D06 must not miss

**`RiskFlag.confidence` is carried but not yet consumed by routing.** D06 has to score
with `app.scoring.decay.effective_severity(severity_now, confidence)`, not with
`severity_now` — otherwise an unconfirmed rumour bends a route exactly as hard as a
corroborated fact and the whole tier is decoration. There is a test pinning the ordering
it should produce. This is the easiest thing in D06 to get wrong and the failure is
invisible.

### System state

| Subsystem | State |
|---|---|
| Rumour Guard | ✅ **Live.** Semantic dedup, promotion, independence policy, measured threshold |
| Verification tier on device | ✅ Map markers, radius circles, sheet rows, weight stated in words |
| Live ingestion | ✅ Reads 3 outlets every 15 min; **only Channel 24 has ever yielded a document** |
| Risk surface | ✅ `db` (and `seeded` for the offline path); both satisfy the protocol, test asserts it |
| Migrations | ✅ 4 applied, forward-only, through `scripts/migrate.py` |
| Agents live | **3 of 8** — Live Risk, Expiry Sweep, Rumour Guard |
| Routing | ⚠️ Public OSRM demo server, flat 30 km/h, ignores `confidence` — **all D06** |
| Vision | ⚠️ `pose_analysis: null` always; 3 of 6 crime classes unreachable — **D07** |
| Known defects | **18 open of 44** — see [plan §1](IMPLEMENTATION_PLAN.md) |

### ⏳ Still open, unchanged by this sprint

- **B0: credential rotation and the git-history rewrite** from the 7 October incident.
- **§7.1, the image-analysis reasoning layer, blocks D07, due 17 October.** There is no
  Anthropic key, so §7.1's "local detection plus Claude vision" needs rewording to a
  provider that exists.
- **`LLM_CHAIN_GEO`'s Groq fallback** — 95.6% with 1 fabrication, or 93.3% with none and
  no network. Recommendation is to drop it. Owner's call.
- **Beat 1 rests on one source.** Ekattor and Independent have never produced a document.
- **Social media / official feeds** — now backlogged as **B11a**, deliberately.

### 🧵 Background activities (off-baton, §9)

| Activity | Owner | Status |
|---|---|---|
| **OSRM graph (D06)** | — | ❌ **not started. Now the critical path** — D06 is next and assumes it exists |
| Eval set (D07) | Arafat | 2 of 30–40 images |
| Dedup clusters (D05) | Arafat | 8 clusters hand-written; replace with real `summary_en` as the corpus grows |
| Native Bangla reader (D08) | — | not arranged |
| Credential rotation (B0) | Arafat | in progress |

### ▶️ RESUME HERE

**1. Build the OSRM graph. This is now the critical path and nothing else is.** D06 is
next, it assumes `osrm-data/bangladesh-latest.osrm` exists, and the multi-gigabyte
download plus `osrm-extract` / `osrm-partition` / `osrm-customize` is hours of
wall-clock that **no coding agent can compress**. Seven days of slack evaporate the
moment D06 starts without it. Commands are in `docker-compose.yml`'s `osrm` service
comment and in §9 item 2. Whoever is not holding the baton should start this today.

**2. Re-run D01–D04 on the device before D06 hands over.** §3's second gate, and it was
**not** done for D05 — D05's own 11 steps passed, but the earlier walkthroughs were only
*read* for breakage, not re-run. One real breakage was found that way (`D01.md`'s rough
edges claimed D05's work was still outstanding) and corrected. Two notes if you do re-run
them: **sign in at least an hour beforehand** so D01's SOS exercises a stale session
(that is how D04 found beat 9 was dead), and expect circles where D01 and D02 say
"pins".

**3. Then D06** ([DEMO_PLAN.md](DEMO_PLAN.md) §D06). **Read the `confidence` warning
above before writing any route scoring** — it is the easiest thing in D06 to get wrong
and the failure is invisible.

**Then D06** ([DEMO_PLAN.md](DEMO_PLAN.md) §D06). Read the `confidence` warning above
before writing any route scoring.

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

## D05 — Verification you can see

**Owner:** Arafat · **Date:** 2026-10-08 · **Branch:** working tree on `develop` · **Merge:** _pending_

### Shipped

**The map no longer treats every claim as equal.** A flag one outlet reported is drawn
**hollow, dashed, with a `?`**; a flag two independent publishers agree on is drawn
**solid, with the source count on it**. Tap either and the sheet says which publishers,
when we decided to believe it, and — for an unconfirmed one — that it is counted at
**60% weight rather than hidden**. Then one command promotes a flag while the map is
open, and another puts it back.

- **`app/agents/rumour_guard.py`** — four gates, all required: same `kind`, overlapping
  radii (capped at 3 km), `observed_at` within 6 hours, then cosine similarity on the
  extraction model's English summary. The first three are SQL and nearly free, so the
  embedding only runs on the rows they let through.
- **`app/policy/independence.py`** — who counts as a separate publisher, and what an
  unconfirmed flag is worth. `_SAME_OWNER` is the Track B seam, empty and documented.
- **`app/agents/promote_demo.py`** — `python -m app.agents promote-demo`, through the
  production merge path, with `--dry-run` and `--reset`.
- **`components/RiskFlagMarker.tsx`** — the tier, legible without tapping.
- **`scripts/eval_dedup.py`** + **`data/eval/dedup/clusters.json`** — the labelled
  cluster set S15 asked for, which is what caught the threshold being wrong.

### Files

- **Added:** `app/agents/rumour_guard.py`, `app/agents/promote_demo.py`,
  `app/policy/independence.py`, `scripts/eval_dedup.py`,
  `data/eval/dedup/clusters.json`, `tests/invariants/test_rumour_guard.py`,
  `migrations/versions/20261008140000__risk_flags_confirmed_at.sql`,
  `frontend/src/components/RiskFlagMarker.tsx`, `docs/walkthroughs/D05.md`
- **Changed:** `app/contracts/risk.py` (**contract change**, below),
  `app/scoring/{decay,fixture,surface_db,surface_seeded}.py`,
  `app/agents/{live_risk,__main__}.py`, `app/core/config.py`,
  `tests/invariants/test_single_source_never_confirmed.py`,
  `frontend/src/types/contracts/risk.ts`, `frontend/src/services/risk.service.ts`,
  `frontend/src/components/RiskFlagSheet.tsx`,
  `frontend/src/screens/Map/MapScreen.tsx`, `DEMO_PLAN.md`,
  `IMPLEMENTATION_PLAN.md` (§9 threshold only)

### CONTRACT CHANGE

- **Changed:** `app/contracts/risk.py` — `RiskFlag` gains `confirmed_at: datetime | None`
  and `confidence: float` (0–1, derived from `status`, default 1.0).
- **Breaks:** nothing. Both have defaults, so an older producer still validates.
- **Updated in this sprint:** both `RiskSurface` implementations produce them;
  `DbRiskSurface`'s column list and `SeededRiskSurface`'s loader carry them;
  `risk.service.ts` maps them off the wire with a `?? ` fallback.
- **TS mirror updated:** yes — `frontend/src/types/contracts/risk.ts`.

### Migrations

- `20261008140000__risk_flags_confirmed_at.sql` — adds `confirmed_at timestamptz` (null),
  plus `idx_risk_flags_kind_status` for the candidate lookup. **Not back-filled, and no
  CHECK tying it to `status`**: the 31 confirmed fixture flags have no moment of
  promotion, so such a constraint would make a valid seed unloadable, and filling the
  column with `observed_at` would claim we confirmed each event the instant it happened.

### Decisions

1. **`severity_now` is NOT damped by confidence.** The obvious implementation of
   "unconfirmed at reduced weight" is to multiply inside `severity_at()`, and it is
   wrong: `severity_now` is the decay story the sheet narrates — *"74 when observed, 31
   now, 42% remaining"* — and damping it makes that arithmetic lie on most flags. So
   `confidence` is a separate field and `decay.effective_severity()` is the helper that
   combines them. **D06 must use it or the tier is decoration**, and there is a test
   pinning the ordering it should produce (a single-source fire still outranks a
   corroborated minor delay).
2. **One `SourceRef` per publisher.** Three constraints interact —
   `confirmed → source_count >= 2`, `jsonb_array_length(sources) <= source_count`, and
   the D01 test demanding confirmed flags cite *distinct publishers*. Keeping one ref
   per publisher makes `source_count == len(sources) == independent publishers`, so all
   three hold for live data for the same reason they hold for the fixture. A
   same-outlet follow-up therefore does not inflate corroboration; it is still kept in
   full in `extracted_incidents`.
3. **The guard declines when it cannot judge.** No usable summary, no model, no
   candidate, nothing similar enough — all fall through to "insert as its own
   unconfirmed flag", which is the pre-D05 behaviour. The asymmetry is the point: a
   missed merge costs a duplicate pin, a wrong merge puts a `confirmed` badge on an
   event that did not happen.
4. **A missing embedding model is not fatal.** `embeddings_available()` returns False
   and logs loudly that dedup is off for the process. A 90 MB download failing must not
   take ingestion down, and D04's offline path has no model at all.
5. **No pgvector, no embedding column.** Candidates are re-embedded at comparison time.
   That is affordable *because* the three cheap gates run first — a typical run compares
   one summary against zero to three. At a thousand flags an hour a vector column would
   be right; at twelve a run it would be a schema dependency bought for nothing.
6. **The marker replaced the native pin rather than being added to it.** `pinColor`
   carries exactly one variable and D04 spent it on severity. `tracksViewChanges={false}`
   is mandatory with a custom marker view — without it every pan re-rasterises ~60
   bitmaps — and the `key` carries the fields that change the drawing, so React
   replaces markers instead of mutating snapshotted ones.
7. **The scripted promotion goes through the real merge function.** `promote-demo`
   builds a `DuplicateMatch` by hand (we are asserting the source belongs to a chosen
   flag, not asking whether two articles match) and then calls
   `rumour_guard.merge_into()`. Nothing in it writes `status='confirmed'`, and an
   invariant test asserts only `rumour_guard.py` may.
8. **The synthetic source is labelled, visibly.** `demo_second_source` at
   `meridian.invalid`. A synthetic corroboration must be distinguishable from a real
   outlet without anyone having to remember that it is synthetic. `--reset` removes only
   that id and recomputes from what is left, so it cannot strip real provenance — and it
   demotes *conditionally*, so a flag that gained a genuine second publisher keeps it.

### Measurements

**The threshold was measured, and the plan's declared value was wrong.**
`scripts/eval_dedup.py`, 18 labelled duplicate pairs and 6 hard negatives:

| threshold | duplicates merged | recall | false merges |
|---|---|---|---|
| 0.70 | 13 / 18 | 0.72 | **2** |
| **0.72** | **10 / 18** | **0.56** | **0** |
| 0.82 *(planned)* | **1 / 18** | **0.06** | 0 |

At §9's declared **0.82 the guard merges essentially nothing** — D05 would have shipped
as a no-op that looked implemented, and no test would have said so.

**The classes are not separable.** Lowest true duplicate **0.503**, highest false pair
**0.718** — and the second account of the real Mohakhali fire scores **0.718**, the same
as the worst false pair. "Two reports of one fire in Bangshal" and "two fires in Bangshal
hours apart" read identically in one line. 0.72 clears the worst negative by **0.002**,
which is a coincidence rather than a margin.

**Accumulation helps both directions.** The guard compares against *every* summary
already on the flag. A third account of the Mohakhali fire scores **0.736** against the
accumulated pair (merges); a different fire near Mohakhali rail gate scores **0.595**
against the same text (does not).

**Promotion, end to end:** `status=confirmed`, `source_count=2`,
`confirmed_at=2026-10-08T16:23:54Z`, `confidence=1.0`, served in the contract shape.
`--reset` → `unconfirmed`, 1, null, 0.6.

**Gates:** 250 backend tests pass (23 new), 2 pre-existing `test_crime_vision.py`
failures untouched. `mypy --strict` clean on **83 files**. `tsc` clean, ESLint 0 errors.

### Deliberately NOT done

- **Nothing committed.** Working tree.
- **The device run.** D05's gate. The walkthrough is written and every step was
  exercised against the live database and the real model, but §0 is explicit that a
  walkthrough not run on a phone has not closed a sprint.
- **The independence check** — same-owner outlets and syndicated copy. `DEMO_PLAN.md`
  §D05 pre-declared it as the first cut, to Track B. `_SAME_OWNER` is the seam and it is
  empty: guessing Bangladeshi media ownership from memory would be worse than admitting
  the gap. **Two outlets owned by one house currently count as two sources.**
- **`RISK_SURFACE_IMPL` was not flipped** (S15's last bullet). It is already `db` and
  has been since D01; there was nothing to flip.
- **No `demo_D05` in `smoke.sh`** — best-effort per §3, and what is worth asserting here
  needs a live database and the model.
- **Routing does not consume `confidence` yet.** That is D06's first ten minutes, and it
  is written into the D05 plan entry and the walkthrough's *Rough edges* so it cannot be
  missed.
- **Did not touch D04's `live_replay.json`.** The captured flag is still the weak
  severity-31 one; re-capturing is a D04 follow-up, not D05 scope.

### Known broken / rough edges

- **Recall ~56%.** Real corroboration is missed about half the time, leaving a duplicate
  pin and an unconfirmed flag. Accepted in exchange for zero false merges.
- **The 0.002 margin.** Improving this needs a better signal — embedding the location
  alongside the summary, or a cross-encoder — not a different number.
- **The eval clusters are hand-written** in the extraction model's style, because live
  ingestion has produced one flag so far. Format matches real `summary_en`, so swapping
  in real data later is a straight substitution.
- Two `test_crime_vision.py` failures remain, untouched, D07's territory.

### Gotchas for the next agent

- **Re-run `scripts/eval_dedup.py` after touching `DEDUP_MODEL` or what gets embedded.**
  The threshold is a property of the model *and* the text. A multilingual model, or
  embedding Bangla headlines instead of English summaries, invalidates 0.72 entirely.
- **Do not "restore" 0.82 from `DEMO_PLAN.md` §9.** A test fails if you do, and §9 is
  now corrected with the reasoning.
- **`severity_now` is not the decision value.** Use
  `decay.effective_severity(severity_now, confidence)`. This is the single easiest thing
  in D06 to get wrong, and getting it wrong is invisible — routes just quietly treat
  rumours as facts.
- **Only `rumour_guard.py` may write `status='confirmed'`.** An invariant test scans
  `app/` for the literal. If you need to confirm a flag, go through `merge_into()`.
- **`tracksViewChanges={false}` on any custom `Marker`.** Without it the map stutters
  visibly at ~60 pins, and the cause is not obvious from the symptom.
- **asyncpg leaves a bare parameter's type unresolved.** `:now + interval '30 minutes'`
  parses as interval arithmetic and fails with *operator does not exist: timestamp with
  time zone > interval*. Write `cast(:now as timestamptz) + interval '…'`.
- **The container does not pick up `.env` on `restart`.** After the D04 offline test the
  api container was still holding `nowhere.invalid` while the file on disk was correct;
  `migrate.py` could not connect. `docker compose up -d --force-recreate api worker`.

### RESUME HERE

See `CURRENT STATE` at the top of this file.

### Prototype Gate

- [x] 1 · `check.sh` green
- [x] 2 · Migration written and applied; `seed.sh` unaffected
- [x] 3 · **App builds and launches — D05.md's 11 steps all passed on a real device**, first
      run, no issues found
- [x] 4 · `smoke.sh` unchanged and passing; no `demo_D05` (relaxed, §3)
- [x] 5 · This entry + `CURRENT STATE` overwritten
- [x] 6 · New settings documented in `config.py` and plan §9
- [x] 7 · Nothing half-migrated — contract, both surfaces and the TS mirror moved together

---

## D04b — D04's device gate: three defects, two of them older than D04

**Owner:** Arafat · **Date:** 2026-10-08 · **Branch:** working tree on `develop` · **Merge:** _pending_

Not a sprint. This is the device run that closes D04, written as its own entry because the previous
one is append-only and because what the run found belongs next to the claim it falsified.

### Shipped

**D04 is closed.** [`docs/walkthroughs/D04.md`](docs/walkthroughs/D04.md) passed on a device, live and
offline — all 12 live steps and O1–O6. The map now carries a flag extracted from a real Bangla news
article published this morning, with its headline, its outlet and a working link to the article, and
the same flag survives the database and the extraction key being taken away.

Ishraq's D04 entry below is accurate about everything it claims. What it could not know is that the
pipeline it verified had never produced output, because the thing discarding the output was in D03's
gazetteer, not in D04.

### Files

- **Changed:** `backend/app/agents/live_risk.py` (`PLACE_GENERIC_TAIL`, `_without_generic_tail()`,
  `place_candidates()`), `backend/tests/invariants/test_live_flags_are_unconfirmed.py` (+3 tests),
  `frontend/src/services/api.service.ts`, `frontend/src/services/auth.service.ts`,
  `frontend/src/screens/Home/HomeScreen.tsx`
- **Added:** `backend/data/fixtures/live_replay.json` — the offline demo's beat 1
- **Docs:** `docs/walkthroughs/D04.md` (header, step 6, O2, O3, O5, two new sections),
  `DEMO_PLAN.md` (§1, §D04, §8), `IMPLEMENTATION_PLAN.md` (defects 42–44)

### Decisions

1. **Fixed the gazetteer matcher rather than the extraction prompt.** The prompt already tells the
   model to drop filler and it does; the problem is that `বাস টার্মিনালে` is not filler, it is part of
   the place's name. Loosening the prompt to ask for *vaguer* answers would trade precision for
   recall across every future extraction. Stripping trailing place-*type* nouns is deterministic,
   testable, and cannot invent a name.
2. **Rejected a prefix-span fallback, which was the obvious fix.** It worked on Mohakhali and also
   resolved the fabricated `গুলশান ৯৭ গোলচত্বর` to Gulshan — exactly the fabrication D03's eval set was
   built to catch, reintroduced by the fix for a different defect. The generic-tail version reduces
   that phrase to `গুলশান ৯৭`, which matches nothing. **The thing that makes this safe is D03's
   number-identity rule, not anything D04 added** — worth knowing before anyone "simplifies" either.
3. **Stripped from the end only.** Bangla puts the specific name first, so the head is the identity
   and the tail is the category. Candidate order is as-written → filler-stripped → tail-stripped, so
   `যাত্রাবাড়ী চৌরাস্তা` and `কারওয়ান বাজারে` resolve to *themselves*, not to their prefixes. A test
   pins that, because it is the property that keeps this from being a recall-for-precision trade.
4. **Made `supabase.auth.getSession()` the single source of the access token.** The valid token was
   there all along. Two parallel stores — Supabase's own session in AsyncStorage and a hand-rolled
   SecureStore cache — is the defect; deleting the second one is the fix, not adding expiry checks to
   it. The SecureStore *writes* in `saveAuthData()` are left in place with a comment, because
   removing them means touching the login and register flows, which was out of scope for a test run.
5. **Changed SOS's token read as well, beyond the reported 401.** Flagged to the owner before doing
   it. Without it the fix is half-applied: `HomeScreen` would still send the token
   `authStore.initialize()` captured at launch. SOS is beat 9 and it was the more serious half.
6. **Re-queued one `raw_documents` row** by clearing `extracted_at`, with the owner's explicit
   consent, so the already-consumed Mohakhali article would be re-read by the fixed matcher. Scoped
   to one `doc_id` and guarded on `rowcount == 1`; the other two extracted documents were judged
   irrelevant correctly and re-reading them would have spent Gemini quota for nothing. This is also
   the lever `D10` can pull to make the newspaper button produce a visible pin on stage.
7. **Did not fake the replay's freshness.** The capture is stuck at 4.1 hours old and therefore at
   severity 31 forever, which is a weak pin. Hand-editing `observed_offset_hours` would fix the optics
   and break the provenance: the article's real publication time is one tap away in the browser.
   Recorded in `D04.md` as a thing to improve by capturing earlier, not by editing.

### CONTRACT CHANGE

None.

**One signature changed:** `AuthService.getAuthToken()` no longer consults SecureStore. Anything that
needs a token must call it (or `supabase.auth.getSession()`) at the moment of use — a token held in
React state or a Zustand store goes stale in an hour. That is defect 43's whole shape.

### Migrations

None. One data write, item 6 above.

### Env vars added

None.

### Measurements

**The gazetteer fix**, measured through `resolve_news_place()`:

| Location text | Before | After |
|---|---|---|
| `মহাখালী বাস টার্মিনালে` | unresolved | **Mohakhali 1.00** |
| `রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়` | Mirpur-10 Circle | Mirpur-10 Circle |
| `যাত্রাবাড়ী চৌরাস্তা` | Jatrabari Mor | Jatrabari Mor |
| `কারওয়ান বাজারে` | Karwan Bazar 0.97 | Karwan Bazar 0.97 |
| `গুলশান ৯৭ গোলচত্বর` *(fabricated)* | refused | **refused** |
| `উত্তরা সেক্টর ১১` *(ambiguous)* | refused | **refused** |
| `বাজারে` *(category only)* | refused | **refused** |

**The first live news flag this project has produced:**

```
listed 481 → relevant 3 → documents_read 1 → incidents 1 → published 1,  0 errors
Road blocked near Mohakhali.   fire · unconfirmed · 1 source
channel24 · রাজধানীতে এসি বাসে অগ্নিকাণ্ড · real https:// article URL
severity_0 70.0 → severity_now 39.98 at publish, 31.3 four hours later · half-life 3.5 h
```

**The newspaper button, eight consecutive runs:** `listed` 480 → 494, `relevant` pinned at **3**,
`fetched` 0, `published` 0 every time. Nothing new to read, no quota spent. A tap changing nothing is
the normal case, not a failure.

**Gates:** backend 222 passed / 1 skipped / 2 failed (both pre-existing in `tests/test_crime_vision.py`
— verified by stashing the change and re-running), `tsc` clean, jest 45/45, ESLint 0 errors on all
three changed frontend files.

### Deliberately NOT done

- **Nothing committed.** Seven changed files plus `live_replay.json` are in the working tree.
- **Did not touch `Ekattor TV` or `Independent TV`.** They listed 173 articles today and passed **0**
  through the relevance filter, and `raw_documents` has never held a document from either. Their
  headlines genuinely contained no road incidents, so this is not provably a defect — but **the
  three-source claim currently rests on one source, and it is Channel 24, the Playwright one.**
  Worth a deliberate look before the 24th; it is the single point of failure behind beat 1.
- **Did not fix the orange collision.** `CRIME_COLORS.theft` is `#FF9800` and
  `RISK_SEVERITY_BANDS` High is `#F57C00`. A judge cannot tell a crime report from a risk flag by
  colour. Raised with the owner, left alone.
- **Did not add a `demo_D04` to `smoke.sh`** — best-effort per `DEMO_PLAN.md` §3, and the things worth
  asserting need a live Supabase and a network.
- **Did not revisit the open `LLM_CHAIN_GEO` question** from the D04 entry below. Still the owner's.

### Known broken / rough edges

- **The replay flag is permanently 4.1 h old and severity 31.1** — one barely-yellow pin among 48
  blue-grey fixtures. Re-run `export-replay` when a fresher news flag exists; it captures all live
  flags, so a newer one joins the file.
- **The live Mohakhali flag expires 2026-10-08 22:49 UTC.** After that, live beat 1 needs new news.
- Two `tests/test_crime_vision.py` failures remain, untouched, D07's territory.

### Gotchas for the next agent

- **A walkthrough re-run reproduces the steps, not the state.** Defect 43 needed a session older than
  an hour. No number of `D01.md` re-runs would have found it, because step 1 of every walkthrough is
  signing in. **For auth-sensitive steps, sign in the day before.** This is the limit of §3's
  regression gate and it is now defect 44.
- **Do not read an access token from React state, a store, or SecureStore.** Call
  `supabase.auth.getSession()` at the point of use. One hour is shorter than a debugging session.
- **Celery does not hot-reload.** `backend/app` is bind-mounted into `meridian-worker`, so a change
  to agent code looks applied and the 15-minute schedule keeps running the old module until
  `docker compose restart worker`.
- **In PowerShell, `curl` is an alias for `Invoke-WebRequest`** and throws instead of printing a
  status. Use `curl.exe`, or `(Invoke-WebRequest <url>).StatusCode`.
- **An unparseable `DATABASE_URL` kills the API at import**, before FastAPI exists, so `/health`
  returns nothing rather than an error. An *unreachable* one is fine — `lifespan()` catches it and
  logs `⚠️ Database not available`, which is the offline path working as designed.
- **`--force-recreate api` does not touch `meridian-worker`**, which keeps its old environment and
  carries on ingesting through an "offline" test.
- **Finding a news flag among 212 fixtures is a search, not a tap.** Ask
  `GET /risk/flags` for the coordinates first, and do not use the D03 search box to navigate there —
  its marker renders over the pin, at identical coordinates.

### RESUME HERE

See `CURRENT STATE` at the top of this file.

### Prototype Gate

- [x] 1 · `check.sh` green
- [x] 2 · Schema unchanged; no migration
- [x] 3 · **App runs on a device — D04's walkthrough passed live and offline**
- [x] 4 · `smoke.sh` unchanged and passing; no `demo_D04` (relaxed, §3)
- [x] 5 · This entry + `CURRENT STATE` overwritten
- [x] 6 · No new env vars
- [x] 7 · Nothing half-migrated

---

## D04 — Today's news, on the map

**Owner:** Farhan Ishraq (with Claude Code) · **Dates:** 2026-10-08 · **Branch:** `ishraq-dev` ·
**Source sprints:** S09, S14, S04 · **Plan:** [DEMO_PLAN.md](DEMO_PLAN.md) D04

All 14 checkboxes done. **The walkthrough has not been run on a device**, so the sprint is not closed —
see CURRENT STATE. Everything below was verified against the live publishers, Gemini and Supabase.

### Shipped

You can now open the map, see when the news was last read, tap **fetch news now**, and get flags
extracted from today's Bangla news; tap one and see the outlet, the headline as published, how long ago
— and open the article.

| | |
|---|---|
| Ingestion | `app/ingestion/` — `fetcher.py` (the only thing that touches a publisher: honest User-Agent, robots.txt, 3 s/host or Crawl-delay, bounded retries, Playwright lazily), `store.py` (`raw_documents`, dedup on URL hash and content hash, the retry queue), `sources/` (one parser for the Ekattor/Independent TV CMS, one for Channel 24) |
| Sources | **Ekattor TV, Independent TV** — Google News sitemaps, server-rendered bodies (`div.jw_article_body`). **Channel 24** — daily sitemap (headline in the URL), body rendered by JavaScript, read with Playwright (`div.details-content-items`), falling back to the static headline + lead. Selection evidence in `sources/__init__.py` |
| Agent | `app/agents/live_risk.py` — list → relevance filter → read → extract (Gemini, `NewsExtraction`) → gazetteer → `unconfirmed` flag + an `extracted_incidents` row for every incident, published or discarded |
| Registry | `app/agents/registry.py` — discovers `AGENT` in every `app/agents/*.py`, builds the beat table from each `cron`, and `run_agent()` owns the session, the `agent_runs` row and an overlap guard. `python -m app.agents run <name> [--dry-run]` |
| Schedule | `worker` container: `celery … worker -B --concurrency 1`. Live Risk every 15 min, expiry sweep (`app/agents/expiry_sweep.py`, D02's script on a schedule) every 30. The two phantom beat entries are deleted |
| API | `GET /api/v1/ingestion/status` (last run; `mode: replay` when seeded), `POST /api/v1/ingestion/run` (signed in; 202; runs in-process, the guard makes a double tap a no-op) |
| Offline | `python -m app.agents export-replay` writes live flags to `data/fixtures/live_replay.json` in fixture form; `SeededRiskSurface` serves it, re-anchored to process start |
| App | Status pill moved bottom-left (it had been hidden under the search card since D03) with "news N min ago", refresh, fetch-news-now; flag sheet shows outlet name, `N min ago`, the headline as a link |
| Tests | `tests/invariants/test_live_flags_are_unconfirmed.py` (64, most of them one parametrised test over every kind × impact), `tests/test_ingestion_sources.py` (9) |

### Decisions

1. **The sources, from the owner's list of ten.** Only Ekattor and Independent TV serve article text
   in HTML; Channel 24 needs a browser but has the most Dhaka (`capital`) coverage. Jamuna answers
   robots.txt itself with 403 — read as "no crawlers", and respected. Evidence per site in
   `app/ingestion/sources/__init__.py`.
2. **Headline filter before fetch.** Incident vocabulary in the headline, a non-excluded desk
   (`international`, `country`, `sports` …) and published in the last 12 h. It decides what is worth a
   request, never what is true. At 04:25 Dhaka it passed 4 of 367.
3. **Places are resolved gazetteer-only**, as D03's handoff advised: free, deterministic, 0
   fabrications. News phrasing broke exact matches (`রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়`), so
   the prompt asks for the bare name and `place_candidates()` removes a fixed list of filler words —
   it may remove words, never substitute a name; a test pins that.
4. **No model-extracted time.** Free-tier models turn "গতকাল সন্ধ্যায়" into instants badly; the
   article's publication time anchors decay.
5. **Discard reasons are explicit:** `low_confidence` (< 0.5), `unresolved_location`, and `rejected`
   for an event with `mobility_impact = none`. Every discard is a row in `extracted_incidents`.
6. **`severity_hint` nudges, it does not decide** — `kinds.SEVERITY_HINT_FACTOR` (0.6 / 1.0 / 1.3 on
   the reviewed baseline), with its reasoning, rather than numbers at the call site.
7. **The flag's radius is the wider of the kind's reach and the place's own radius.** A fire resolved
   only to "Mirpur" is claimed over Mirpur, not over 400 m of it — honest about where we are unsure.
8. **Offline replay is a captured fixture, not the document cache.** `raw_documents` lives in Supabase,
   so "replay from the cache with the network off" cannot work; and replaying extraction would need the
   model. The capture is real flags in fixture form — no prose, `seed-live-` keys, re-anchored on load
   — through the exact loader and checks D02 built. The seeder never loads it (the live originals are
   already in the database).
9. **"Pull to refresh" is a button.** A map has no scroll to pull. "Fetch news now" exists because
   waiting up to 15 minutes on stage is not a plan; it runs in the API process (always up when the app
   is), and the registry's guard skips a run while another is in flight.
10. **Headlines are shown exactly as published**, as quoted provenance. The product's own claim is
    only the framed statement; the framing guard covers that and not the outlet's words.
11. **Gemini only on EXTRACT, no Groq fallback.** gpt-oss-120b scored 15.6% on Dhaka places in D03,
    and a rate-limited run loses nothing: documents stay queued (`extracted_at is null`).

### CONTRACT CHANGE

- **Changed:** `app/contracts/agents.py` — `AgentContext.db: AsyncSession | None = None`.
- **Breaks:** nothing; no `BaseAgent` existed before D04.
- **Updated in this sprint:** both agents and the registry, which is the only constructor.
- **TS mirror updated:** not applicable — agent contracts are not mirrored.

### Migrations

- `20261008120000__raw_documents_extracted_at.sql` — `raw_documents.extracted_at` and a partial index.
  "Has the model read this?" cannot be answered from `extracted_incidents`, because most articles yield
  no rows. **Applied to the owner's Supabase** (via `migrate.py sql --version`, before the line-ending
  fix below made `up` usable again); `status` now shows all three applied, 0 pending.

### Env vars added

- `LLM_CHAIN_EXTRACT=gemini:gemini-3.5-flash-lite` and `GEMINI_KEY_EXTRACT_ONE=` — in `.env.example`.
  The owner's key arrived as `IQ_GEMINI` and was renamed in `backend/.env`; the client only discovers
  `<PROVIDER>_KEY_<FEATURE>_*`.

### Measurements

| | |
|---|---|
| Live run, 04:25 Dhaka | 367 listed · 4 relevant · 4 read (Channel 24 via Playwright) · 0 incidents — correct for the hour |
| Run time | ~40 s, almost all of it politeness delays and one render |
| Publish path (rolled back) | news phrasing → `Mirpur-10 Circle`, `unconfirmed`, trigger-derived expiry, served by `DbRiskSurface`; fabricated place → `unresolved_location` |
| Tests | invariants + ingestion: **193 passed, 1 skipped** (replay not captured) — invariants 121 → 185 · `mypy --strict` 80 files clean |
| Frontend | `tsc` clean · ESLint 0 errors / 106 warnings, none added (MapScreen 6 before, 6 after) · jest 45/45 |

### Found while building, not planned

- **Independent TV's "headlines" were photo captions.** Its sitemap lists `image:title` before
  `news:title`; the parser took the first `title`. Image and video extensions are now skipped, with a
  regression test. Found by printing what the filter saw, not by a test.
- **The risk status pill was invisible.** It shared `top` with the search card (`zIndex: 10`). Moved.
- **Migration "drift" that was line endings — fixed in `scripts/migrate.py`.** `status` reported
  `20261007120100` as CHANGED and `up` refused to run for everyone. The ledger holds the **CRLF** hash
  of `20261007120000` (`8575ba…`) and the **LF** hash of `20261007120100` (`45302f…`) — each is exactly
  the committed content, checksummed in checkouts with different line endings (`core.autocrlf=true`
  on Windows; LF in a container or a freshly written file). D04's own migration would have hit the
  same trap on its next checkout. `Migration.matches()` now accepts either form while new rows record
  the LF form; an edited statement is still drift (`tests/test_migrate_checksum.py`, 3 tests). No
  ledger row was touched. The live schema had also been compared column by column and CHECK by CHECK
  against the file before the cause was found — it matches.

### Deliberately NOT done

- **No device run** — the gate. And no replay captured: at the hour of building there were no live
  flags to capture.
- **No Groq fallback on EXTRACT, no LLM tier for places** — Decisions 3 and 11.
- **No per-flag `time_profile`.** Kind defaults apply, as before.
- **No `prompts/live_risk_v1.md` file.** The prompt is a constant in `live_risk.py`, like D03's, and
  `PROMPT_VERSION` names it. A file adds indirection without adding a diff the constant does not have.
- **No extraction eval (S14 asks for one).** There is no annotated corpus yet; the corpus is background
  work. The first live days' `extracted_incidents` rows are the natural start of one.
- **`run.ps1` was not changed** — its `docker compose up -d` already starts `worker`.
- **The two pre-existing `ruff format` diffs** in `app/llm/models.py` and `app/scoring/fixture.py`
  are not D04's lines and were left.

### Gotchas for the next agent

1. **Rebuild once (`run.ps1 -Rebuild`)** — the image gained Chromium in its own layer.
2. **`.env` edits need `docker compose up -d --force-recreate api worker`.** Both read `env_file` at
   create time.
3. **An empty news map at night is correct.** Check `python -m app.agents run live_risk --dry-run`'s
   metrics before suspecting the code.
4. **`DEBUG=true` makes logs enormous** (SQLAlchemy echo, including article bodies). Filter on
   `app.agents`.
5. **Git Bash rewrites `/tmp/...` arguments to `docker exec`** into Windows paths. Prefix commands with
   `MSYS_NO_PATHCONV=1`, or use PowerShell.
6. **`backend/.env` stays committed** — the owner confirmed it for this private repo. The B0 rotation
   note at the top still applies, now including the EXTRACT key.

### Prototype Gate

- [x] It runs — backend end to end against live sources; app `tsc`/ESLint/jest clean
- [x] `mypy --strict` clean on `app`; `ruff` clean on every D04 file
- [x] Invariant tests: 64 new (121 → 185), all passing
- [x] `docs/walkthroughs/D04.md` written, with expected results and fallbacks
- [ ] **`docs/walkthroughs/D04.md` run on a real device, live and offline** ⏳
- [ ] **D01–D03 walkthroughs re-run** ⏳ (owner said they were checked before D04 began)
- [ ] **Replay captured and committed** ⏳ needs Dhaka daytime

---

## D02 — The surface breathes

**Owner:** Nakib · **Dates:** 2026-10-07 · **Source sprints:** S04, S19, S20 · **Plan:** [DEMO_PLAN.md](DEMO_PLAN.md) D02

All 14 checkboxes written. **The walkthrough has not been run on a device, so this sprint is not
closed** — see the banner in CURRENT STATE. Everything below is verified against the backend.

### Shipped

**`app/scoring/` is now the package the plan described.** Six modules, each with one job:

| Module | What it owns |
|---|---|
| `kinds.py` | Per-kind half-life, radius and baseline severity. The reviewed table S19 asks for, with the concept document's §5.6 range recorded beside each value so a later change is an argument rather than a guess. |
| `decay.py` | `severity(t) = severity_0 · 0.5^(elapsed/half_life) · profile[hour]`. Pure, total, no wall clock. Four hand-set time-of-day profiles with written rationales. |
| `chronic.py` | The chronic baseline, derived from `scripts/crime_risk_model.json` — real published Bangladesh Police unit statistics. |
| `fixture.py` | The single reader of `data/fixtures/risk_flags.json`, shared by the seeder and the seeded surface. |
| `surface_db.py` | `DbRiskSurface`, now computing `severity_now` per read. |
| `surface_seeded.py` | `SeededRiskSurface` — the fixture, with no database in the request path at all. |

`get_risk_surface()` in `__init__.py` is the only place that chooses between them, on
`RISK_SURFACE_IMPL`. The endpoint holds a `RiskSurface` and cannot tell which one it got, which is what
makes the offline demo path an environment variable rather than a branch.

**The fixture went from 22 entries to 204, plus 8 derived chronic rows = 212 flags.** Grouped by
commuting corridor — Mirpur Road, Kazi Nazrul Islam Avenue, Rokeya Sarani, Airport Road, Progoti
Sarani, the Gulistan–Jatrabari axis — because D06 routes around them and a corridor with one flag on it
cannot be routed around. Several are deliberately clustered so an alternative route has a reason to
exist. All ten incident kinds, 69 confirmed and 143 unconfirmed, six deliberately pre-expired.

**A compact entry form is what makes 204 entries maintainable.** An entry is one line:
`half_life_hours` and `radius_m` default from `kinds.py`, and `sources` is generated from
`source_count` when absent, picking distinct `sample_*` publishers stably by `zlib.crc32(event_key)` —
`hash()` would have been salted per process and churned the generated SQL on every run.

**`severity_now` is a new required field on `RiskFlag`**, mirrored in
`frontend/src/types/contracts/risk.ts` in the same commit. Required rather than optional on purpose: a
surface that forgot to compute it would otherwise serve a complete, valid, entirely plausible response
in which nothing ever faded.

**The expiry sweep is `scripts/sweep_expired_flags.py`**, and it is housekeeping rather than
enforcement. Whether a flag is served is decided on read against the stored `expires_at`, so a flag
retires itself whether or not the sweep has ever run. A job that *decided* liveness would mean the
surface was only correct as often as the job ran. It sets `status = 'expired'` and does not DELETE — an
expired flag is the evidence that the surface retires things on its own, which is beat 5's claim. Not a
Celery beat yet because there is no worker; `sweep_expired()` is the function D04's registry registers.

**Frontend:** `components/RiskFlagSheet.tsx` (beat 2's container — severity then vs now, % remaining,
half-life, time left, source strip), and a `__DEV__`-only "as of" bar on `MapScreen` with six presets.
Pins and circles now colour by `severityNow`, so a flag visibly fades as the clock moves.

### Decisions

**1. `severity_now` is computed in Python, not in PostGIS.** A departure from S20's "decay applied at
query time in PostGIS", and the one to revisit if route scoring later needs decay inside a spatial
query. The time-of-day profile is a 24-element lookup against the Dhaka-local hour; in SQL that is a
24-branch `CASE` or a jsonb index into a column that is null on every row today, either way duplicating
`decay.py` in a second language in the request path. The decay formula already has two implementations
it cannot avoid — Python for the seeded surface, SQL for `expires_at` — and a third in the hot path to
save an exponent per row on a result set capped at 500 is a bad trade. PostGIS still does the spatial
test and the liveness filter, which are the parts that need an index. Written out in
`surface_db.py::_row_to_flag`.

**2. The time-of-day multiplier does not affect expiry.** `severity_at()` applies it; `expires_at_for()`
does not. An event does not end because it is 4 a.m. Keeping it out also preserves the equivalence both
surfaces lean on: un-modulated severity crosses the serve threshold at exactly `expires_at`, so "still
served" and "still above threshold" are one statement, which is why the endpoint can filter on a stored
column and still be honest about severity. `test_expiry_is_exactly_where_severity_crosses_the_threshold`
pins it.

**3. Forward-dated flags decay from `valid_from`, not `observed_at`.** A procession announced on Tuesday
for Friday must not arrive already three days decayed. `decay_anchor()` is the one line that makes D09
work, and `elapsed_hours()` clamps at zero so a flag whose window has not opened reads at full severity
rather than at an amplified value from a negative exponent.

**4. The chronic layer drops the eight `… Range` rows and keeps the seven metropolitan units.**
`Dhaka Range` has a 100 km radius and a `normalized_risk` of 100.0 — the dataset maximum — and it
geographically *contains* DMP, whose own figure is 58.9. Emitting both double-counts the same reported
crimes and blankets the map at maximum severity. The rule is: the most specific unit covering a point
wins, and the aggregate is not a second opinion. For the demo zone that is one flag, DMP, 20 km, 58.9.

**5. The chronic layer is seeded rows, not a third surface class.** A `CompositeRiskSurface` was the
first design and it was deleted before it was written: chronic flags are flags, the table already
stores them, and `DbRiskSurface` serves them with no new code. The seeded surface gets the same rows
because both read `fixture.py`.

**6. A chronic flag is `unconfirmed` with `source_count = 1`.** It would be tempting to call a
government statistic confirmed, and the CHECK constraint would reject it — one source cannot produce a
confirmed flag, and that rule has no exception for official data. Leaving the layer honestly
unconfirmed is the correct reading of it.

**7. The "as of" control is six preset buttons, not a slider.** `@react-native-community/slider` is not
installed and adding a dependency for a dev-only affordance is the wrong trade; a dragged value also
fires a request per frame. Presets are more repeatable on stage. D09 promotes it to a real
forward-looking control over the same parameter.

**8. Circles are not drawn above a 5 km radius.** The chronic flag is 20 km. A translucent disc larger
than the viewport is a tint, not information, and it makes every other flag harder to read while
implying a precision the data does not have. The pin is drawn alone and the sheet states the radius in
words. Kind-agnostic, because "a circle bigger than the screen says nothing" is true whatever produced
it.

**9. `KIND_LABELS` in the sheet maps `clash` to "Disruption", not "Clash".** The kind is an internal
routing decision; the product does not characterise events to users. This is `framing.py`'s commitment
restated in the one place a client could break it, and an unmapped kind falls back to "Disruption"
rather than to its raw value, so adding an `IncidentKind` cannot leak a new word onto a screen.

### Found while building, not planned

**`seed_risk_flags.py --sql` crashed outside `backend/`, and the owner found it, not a test.**
`get_risk_surface()` was first written into `app/scoring/__init__.py`, so **every** import from the
package pulled in `app.core.config.settings` — whose `DATABASE_URL` and `JWT_SECRET_KEY` have no
defaults, so importing it raises unless a `.env` is discoverable from the current directory. The
seeder imports `app.scoring.fixture` to turn a JSON file into SQL text. It touches no database and
needs no credentials, and it worked from `backend/` and nowhere else. Moved to
`app/scoring/factory.py`; `__init__.py` is now docstring-only and says why. `fixture.py`, `decay.py`,
`kinds.py` and `chronic.py` are importable with no configuration at all.

Worth noting how it surfaced: 86 tests, `mypy --strict` and `ruff` all passed, because pytest runs
with `backend/` as the working directory. The failure needed someone to run the documented command
from the documented directory — which is the same lesson as D01's three device bugs, one layer down.

**`route_service._get_regional_risk()` is wrong on its own terms, not just a double count.** It takes
the **maximum** `normalized_risk` across every overlapping unit, and the dataset holds both
metropolitan units and the ranges containing them — so every point in Dhaka scores 100.0 from
`Dhaka Range` instead of 58.9 from `DMP`. Every route in the city has been scored against a regional
risk of 100 since the method was written. D06 deletes it; it now carries a comment saying so and
pointing at `chronic.py` for the reasoning.

**The framing invariant had a blind spot, and D02 would have driven through it.** The AST check in
`test_no_flag_text_bypasses_framing.py` caught keyword arguments, assignments and attribute
assignments — but **not a string key in a dict literal**. Before D02 the only producers of
`mobility_statement` outside `framing.py` lived in `scripts/`, which that test does not scan. D02 moved
row-building into `app/scoring/fixture.py`, which builds dicts, so a hand-written statement under
`app/` would have walked straight past the one test whose job is to prevent exactly that. The detector
was strengthened to catch dict keys, and the three legitimate modules were then added to
`ALLOWED_WRITERS` with their reasons. Strengthening the check rather than excluding the new modules is
the point: the cheap fix was available and it was the wrong one.

**`.\scripts\seed.sh` does not run in PowerShell, and it fails by doing nothing.** Found when the owner
ran the documented command and the regenerated fixture file still held the previous sprint's 22 flags.
PowerShell cannot execute a `.sh`: the command returns at once, prints nothing, exits cleanly, and
changes nothing — indistinguishable from success, and the failure mode is a stale fixture whose
timestamps are hours old, which on a map looks like a broken product rather than a stale file. Every
`.sh` in `scripts/` has this problem; only `run.ps1` is native. The walkthrough and RESUME HERE now
give PowerShell-native commands. A `seed.ps1` would be the real fix and is not in D02's scope.

**`.env` changes need `docker compose up -d --force-recreate api`, not `restart`.** Compose reads
`backend/.env` when the container is *created*, so `docker compose restart api` silently keeps the old
values — which would make the `RISK_SURFACE_IMPL` switch look like it did not work. Written out in the
walkthrough's *Switching the surface* section.

**There is no database container, and the walkthrough said there was.** `docker-compose.yml` runs the
API and Redis; the database is Supabase and it is remote. The original step 15 said "stop the database
container", which is not a thing. Corrected to breaking `DATABASE_URL` instead.

**The offline claim was asserted before it was checked, and it turned out to be true but narrow.** The
endpoint declares `db: AsyncSession = Depends(get_db)`, so a session is constructed on every request
whatever the surface is. `seeded` works only because SQLAlchemy connects lazily *and* the seeded surface
never runs a statement — **191 flags served against a `DATABASE_URL` pointing at a non-existent host.**
Anything that made `get_db` connect eagerly would break the offline path while leaving it looking fine,
so `test_the_seeded_surface_serves_with_no_reachable_database` now pins it, with the `db` case as a
control so it cannot pass by the database happening to be up.

### Measurements

Seeded surface, Dhaka bbox `23.70,90.33 → 23.90,90.50`:

| | |
|---|---|
| Flags in the fixture | 204 hand-built + 8 derived chronic = **212** |
| Live now / +3h / +6h / +12h / +24h / +48h / +30d | **191 / 149 / 137 / 108 / 64 / 28 / 24** |
| Confirmed / unconfirmed | 69 / 143 |
| Incident kinds represented | 10 of 10 |
| Severity range | 4.3 – 75.0 |
| Shortest / longest half-life | 1h (road accident) / 2160h = 90 days (chronic) |
| Chronic baseline, Dhaka (DMP) | 58.9/100 over a 20 km radius |
| Invariant tests | **86 passing**, 36 new in D02 |
| `mypy --strict` | clean, 59 files |
| `ruff` | clean on every file D02 wrote |
| Frontend | `tsc` clean · 0 ESLint errors, 6 warnings (all pre-existing) · jest 45/45 |

**The number for Q&A:** 191 flags now, 108 in twelve hours, 24 in a month — unattended, no cleanup job.
That is "no stale red zones" as a measurement rather than a claim.

### Deliberately NOT done

- **No Celery beat for the sweep.** There is no worker in `docker-compose.yml` and the beat schedule
  still points at two modules that do not exist. A task registered against a broken schedule looks
  scheduled and never runs, which is worse than a script somebody runs. D04 builds the registry.
- **No `LegacyRegionalSurface`.** `surface_db.py` lists it as a Track B implementation; the chronic
  layer made it unnecessary for now, since the police model reaches the surface as rows.
- **`route_service._get_regional_risk()` not deleted.** It is a D06 checkbox and deleting it today
  would change route scores in a sprint that does not test routing.
- **No independence check on sources.** D05, and pre-declared as the first thing to cut there.
- **No per-flag `time_profile` written anywhere.** The column exists and the contract carries it; every
  flag falls back to its kind default. D04's extraction is the first thing that might set one.

### Gotchas for the next agent

1. **Restarting the backend with `RISK_SURFACE_IMPL=seeded` resets every flag to fresh.** Fixture
   offsets are relative and resolved once per process, at first load. That is deliberate — resolving per
   request would move `observed_at` forward between two requests and nothing would ever appear to decay
   — but it will confuse you mid-rehearsal. `reset_cache()` does it on purpose; nothing over HTTP can.
2. **`.\scripts\seed.sh` does not run in PowerShell, and it fails silently.** PowerShell cannot
   execute a `.sh`: the command returns at once, prints nothing and changes nothing, which reads
   exactly like success. Call the Python directly (see RESUME HERE) or use Git Bash. Every `.sh` in
   `scripts/` has this problem; only `run.ps1` is native.
3. **Regenerate `3-fixtures.sql`; never reuse one.** Same reason. An old file seeds a map of entirely
   expired flags, which looks exactly like a broken product rather than a stale file.
4. **`SERVE_THRESHOLD = 5.0` exists in two places and must stay in two places** — `decay.py` and the
   SQL trigger in migration `20261007120000__risk_flags`. The migration is checksummed and immutable, so
   the Python side is the one that can drift. `test_expiry_matches_the_sql_trigger_arithmetic` has
   hand-computed expectations taken from the trigger, not from the Python, so it cannot be satisfied by
   changing both sides at once.
5. **Two of the eight chronic units expire immediately.** Barishal (4.76) and Rangpur (4.30) normalise
   below the serve threshold. Correct, and a little odd to read in the seed output.
6. **Do not compute decay on the device.** The TS contract says so in a comment. A client that halved
   severity itself would disagree with the server about when a flag vanishes.
7. **`severity_now` is required on `RiskFlag`.** Anything new that constructs one — a test, an agent,
   D04's extraction — has to supply it. The two surfaces are the only producers today.

### Prototype Gate

- [x] It runs
- [x] `mypy --strict` clean on `app/scoring`, `app/contracts`, `app/policy`
- [x] `ruff` clean on every file this sprint wrote
- [x] 86 invariant tests passing
- [x] Frontend `tsc` clean, 0 ESLint errors, jest 45/45
- [x] `docs/walkthroughs/D02.md` written, with expected results at every step
- [x] **`docs/walkthroughs/D02.md` run on a real device — iPhone, Expo Go, every step passed**
- [x] `docs/walkthroughs/D01.md` re-run and still passing
- [x] 212 flags applied to Supabase

---

## D01 — Schema, contracts, framing, first pins, and an SOS that leaves a record

**Owner:** Nakib · **Dates:** 2026-10-07 · **Source sprints:** S02, S03, S05, S07 · **Plan:** [DEMO_PLAN.md](DEMO_PLAN.md) D01

The first sprint of the resequenced finale track, and the first to ship under the §0 rule that every
sprint must end in something visible on a phone. **All 20 checkboxes done. Walkthrough run on an
iPhone; every step passed.**

### Shipped

**Migrations and the runner**

- `backend/scripts/migrate.py` — forward-only, sha256-checksummed, `schema_migrations` ledger. Refuses
  to run if an applied migration's file has changed. Three commands: `status`, `up`, `sql`.
- `migrate.py sql` emits paste-ready SQL **with the ledger insert included**, for a database that will
  not take a direct connection. This is how the schema actually reached Supabase, because `psql` is not
  installed on the owner's machine.
- `20261007120000__risk_flags.sql` — PostGIS `GEOGRAPHY(POINT, 4326)`, GiST index, `(status,
  expires_at)` index, partial index on the validity window, and **seven CHECK constraints**, two of
  which are ethical invariants at schema level: `half_life_hours > 0`, and `status <> 'confirmed' or
  source_count >= 2`.
- `20261007120100__ingestion_and_agent_runs.sql` — `raw_documents`, `extracted_incidents`,
  `agent_runs`. Created now, written in D04: the schema is the cheap part, and this means D04 is a
  sprint about scrapers rather than scrapers *and* migrations.
- `scripts/seed.sh` rewritten — baseline, then versioned migrations, then fixtures, then verify. Plus
  `--sql`, which writes numbered files to `.seed-sql/` to paste by hand.

**Contracts and policy**

- `app/contracts/{risk,surface,agents}.py` — plan §6.1–6.3. `mypy --strict` clean.
- `frontend/src/types/contracts/{risk,crime}.ts` — hand-mirrored. No generator; a drift check is B2.
- `app/policy/framing.py` — `to_mobility_statement()`, `assert_mobility_safe()`, 95 banned terms
  across four groups including Bangla. **The only writer of `RiskFlag.mobility_statement`.**

**The risk surface**

- `app/scoring/surface_db.py` — `DbRiskSurface`, raw parameterised PostGIS SQL. `ST_Intersects` on a
  geography column, verified to use the GiST index rather than a sequential scan.
- `GET /api/v1/risk/flags?bbox=&as_of=` — contract shape, four classes of bad bbox rejected with 422.
- `backend/data/fixtures/risk_flags.json` — 22 Dhaka flags, structured fields only, all 10 incident
  kinds, 8 confirmed / 14 unconfirmed, **2 deliberately already expired**.
- `backend/scripts/seed_risk_flags.py` — derives every statement through `framing.py` at load time,
  validates against the table's constraints first so a bad entry is reported by name.

**Frontend**

- Risk overlay on `MapScreen`: pins coloured by severity in four bands, each inside a radius circle,
  plus a status pill showing the flag count or the reason there is none.
- `src/services/risk.service.ts` — snake_case to camelCase in one place.
- **Defect 3 closed**, and it was two bugs: `CRIME_COLORS` was keyed `'Theft'` while the database
  stores `'theft'`, *and* no marker was ever passed a `pinColor` at all. The authority is now
  `types/contracts/crime.ts`, with `CRIME_COLORS` typed `Record<CrimeCategory, string>` so a missing
  colour is a compile error.

**SOS**

- **Defect 35 closed.** Every trigger writes to `sos_incidents`. Verified on live Supabase: email
  delivered, row written, coordinates un-swapped, `delivered=true`.
- `contacts_notified` holds contact **ids**, not email addresses — the addresses already live in
  `emergency_contacts`, and duplicating personal data into a second table with its own lifetime buys
  nothing. Data minimisation applied where it happened to be free.

**Build and tests**

- `requirements.txt` split into `requirements/{base,ai,agents,dev}.txt` — **defect 15**. The old file
  carried a 2 GB vision stack alongside FastAPI and had pytest, ruff and mypy commented out, which is
  why `check.sh` skipped them.
- `tests/invariants/` — 34 tests over two invariants: mobility framing, and one source never confirmed.

### Found by running it on a phone — three bugs nothing else caught

**1. The map had never rendered on iOS.** All three map screens passed `provider={PROVIDER_GOOGLE}`
unconditionally, which forces a Google Maps SDK that **Expo Go for iOS does not ship**. `MapView`
mounted, laid out and drew nothing: a white rectangle, no error, no warning, markers invisible on top.
`app.json` also carried the literal string `"YOUR_GOOGLE_MAPS_API_KEY"` for both platforms. Fixed with
`MAP_PROVIDER` in `src/components/MapComponent.tsx` — Apple Maps on iOS, Google on Android — and the
placeholders removed, because they would have broken an Android development build in the same silent
way.

**2. One SOS froze the entire API for 2m34s.** `email_service.send_sos_alert` was `async def` but
called `smtplib` **synchronously**. Blocking code on the event loop does not block one request, it
blocks every request: `/health` timed out and `GET /risk/flags` could not be served for the duration.
Fixed with `asyncio.to_thread` for both the send and the attachment encode, plus a 120-second socket
timeout — `smtplib` otherwise inherits the system default, which is usually none. The evidence clip was
also 16.45 MB for 10 seconds at default iPhone quality; now capped at ~2 MB. **Owner approved going
outside D01 for this**, because a 2.5-minute freeze is not a passing walkthrough step.

**3. PostGIS was unreachable for every ORM write.** geoalchemy2 emits PostGIS functions
**unqualified**, and Supabase installs PostGIS into `extensions`, so any insert into a geography column
failed with `function st_geogfromtext(unknown) does not exist`. Latent since S01 and undetectable,
because nothing had ever written to a geography column — `sos_incidents` was empty (that *was* defect
35) and `user_locations` still is. Fixed by setting `search_path=public,extensions` on the engine in
`app/core/database.py`, which also covers `endpoints/tracking.py`.

### Decisions

1. **`expires_at` is derived by a database trigger, and there is no Python copy of the formula.** A
   GENERATED column was tried first and Postgres rejects it: `timestamptz + interval` is STABLE, not
   IMMUTABLE. The trigger overwrites whatever a caller supplies, so "derived, never hand-set" is
   structural rather than a convention. One rule, one implementation.
2. **The trigger takes `greatest(decay-derived, valid_to)`**, which is what lets D09's forward-dated
   flags work with no schema change and no contract change on its single day.
3. **`as_of` is threaded from day one** and turned out to be functional, not a placeholder: it filters
   on `expires_at`, so flags genuinely drop out as the instant advances. D02 adds severity-on-read.
4. **Fixtures store structured fields only.** No `mobility_statement` anywhere in the file; the seeder
   raises if it finds one and an invariant test checks it. 200 rows arrive in D02 — that is 200 chances
   to smuggle prose past the framing guard.
5. **Sample data is marked as sample.** Every `source_id` is `sample_*` and every URL uses a `sample:`
   scheme. Fabricated links that looked like real Prothom Alo articles would 404 if a judge tapped one.
6. **~250 lines were written and then deleted**, on the owner's call, as unneeded indirection:
   `app/scoring/provider.py` (a factory over one class), `app/scoring/decay.py` (nothing called it),
   and `score_point` / `score_path` with `PointRisk` / `PathRisk` (no caller until D06). The protocol
   now declares only what something implements. D02 and D06 add the rest when there is a second
   implementation and a caller.
7. **ADR 0003 stayed out of D01**, as [ADR 0005](docs/adr/0005-finale-reordering.md) decided. Dropping
   `public.users` would have broken SOS: `endpoints/sos.py` still auto-provisions into it on every
   trigger. Track B (B1).

### Migrations

| Version | Name | Applied to the owner's Supabase |
|---|---|---|
| `20261007120000` | `risk_flags` | ✅ by hand via `.seed-sql/2-migrations.sql` |
| `20261007120100` | `ingestion_and_agent_runs` | ✅ same |

Both idempotent. Both validated against a throwaway PostGIS 16 container from an **empty** database
before they went near Supabase, with every CHECK confirmed to reject bad data.

### Measurements

| | |
|---|---|
| Seed flags / live / already expired | 22 / 20 / 2 |
| Flags served at now, +6h, +12h, +48h | 20 / 16 / 10 / 4 |
| Invariant tests | 34 passing |
| `mypy` across the whole backend | **0 errors, 54 files** |
| `ruff` on D01's own files | clean; **0** new findings in pre-existing files |
| Frontend | `tsc` clean · ESLint 106 warnings / 0 errors (budget raised 105→106 for one effect) · jest 45/45 |
| SOS evidence clip | 16.45 MB → **~2 MB** |
| SOS end to end | 2m34s with the API frozen → **seconds, API responsive** |
| `backend/venv` size | 2.1 GB, which is why `backend/.dockerignore` now exists |

### Deliberately NOT done

- **`app/llm/client.py` → D03**, its first consumer. `anthropic` is installed; the module is not
  written. Nothing in D01 or D02 needs an LLM.
- **No `RISK_SURFACE_IMPL` switch, no `SeededRiskSurface`** — D02, when there are two surfaces.
- **No severity decay in Python** — D02. See decision 1 for why there is no second copy of the formula.
- **The SOS video is not retained.** Attached to the email, then deleted. Retaining footage recorded
  under duress needs a bucket, a retention window and an access policy. The row records *that* a video
  was attached.
- **Flags do not reload on pan.** One fetch per recentre over a ~39 km box. A region-change handler on
  a controlled `region` prop risks the map fighting the user's finger. D04 adds pull-to-refresh.
- **`4-verify.sql` was not extended** to cover D01's tables; `seed.sh` asks `risk_flags` directly
  instead.
- **ADRs 0001/0002/0004 not written** — Track B (B1), as ADR 0005 scheduled.

### Known broken / rough edges

- **`./scripts/check.sh` is not fully green: ~320 ruff findings in pre-existing code.** This is newly
  *visible*, not newly broken — with no `backend/venv`, the ruff step was **skipped**, and a skip
  printed like a pass. D01's files are clean and D01 added zero. Track B (B3, B5).
- **The backend cannot start without the full ~2 GB AI stack**, because `api/v1/api.py` imports the
  vision endpoints eagerly even though D01 touches none of them. Track B (B3).
- **iOS and Android now show different maps** (Apple vs Google). Matching them needs a paid Google key
  *and* a development build. A cost decision, not an engineering one. **Pick the demo device and
  rehearse on it.**
- **`endpoints/tracking.py` is still unexercised.** It uses the same geoalchemy2 path that was broken
  until the `search_path` fix, so it is *probably* fine now. "Probably" is the honest word.
- **The SOS progress bar is partly simulated** and capped at 98%. That cap is what made a working SOS
  look hung — the upload had finished and the server was mid-SMTP. The stage label is now honest; the
  percentage is still indicative.

### Gotchas for the next agent

1. **Do not add a Python implementation of the expiry formula.** The trigger owns it. If you need the
   serve threshold, mirror `5.0` with a comment on both sides, or read it from the database.
2. **Do not put `mobility_statement` in the fixture.** The seeder raises and an invariant test fails.
   Set `mobility_impact` and `place`.
3. **Do not weaken `framing.py`'s banned list to make something pass.** If the guard rejects your text,
   the text is wrong. That is the whole mechanism.
4. **Regenerate `3-fixtures.sql`; never reuse one.** Its timestamps are relative to generation, so an
   old file seeds a map where everything has already expired.
5. **Pass `as_of` with a `Z` suffix, not `+00:00`.** A literal `+` in a query string decodes to a
   space and you get a 422 that looks like a date-parsing bug.
6. **Never call `smtplib` or any blocking library straight from an `async def`.** One SOS proved what
   that costs. `asyncio.to_thread` exists.
7. **`backend/venv` is 2.1 GB and inside the Docker build context.** `backend/.dockerignore` keeps it
   out. Do not delete that file.
8. **Editing an applied migration is an error, not a shortcut.** `migrate.py` compares checksums and
   refuses. Write a new migration.

### Prototype Gate

| Check | State |
|---|---|
| `check.sh` green | 🟡 mypy, tests and frontend green; ruff carries a pre-existing backlog — see above |
| `seed.sh --fresh` works | 🟡 needs `psql`, which is not installed. The `--sql` path works and is what was used |
| App launches on a device | ✅ iPhone, Expo Go |
| `smoke.sh` passes | ⏭️ relaxed to best-effort until 24 Oct per ADR 0005 §Decision 5 |
| **`docs/walkthroughs/D01.md` run on a device** | ✅ **every step passed** |
| This file updated | ✅ |
| `.env.example` + plan §9 | ⏭️ relaxed to best-effort until 24 Oct |
| Nothing half-migrated | ✅ ledger matches disk |


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
