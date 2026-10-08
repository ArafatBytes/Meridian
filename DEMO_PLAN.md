# Meridian — Finale Plan (24 October 2026)

**This document governs the order of work until the finale. It governs nothing else.**

| | |
|---|---|
| **Authority** | The sprint sequence, until 24 Oct 2026. Supersedes [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) §11. |
| **Not the authority for** | *What* a task means. Every `D` sprint below cites its source sprint in the long plan; that text is still the specification. |
| **Why this exists** | [docs/adr/0005-finale-reordering.md](docs/adr/0005-finale-reordering.md) |
| **Companion** | [PROGRESS.md](PROGRESS.md) is still the handoff log and is still read first. |

**Nothing has been deleted from the long plan.** This is a reordering. §5 is a coverage table that
maps all 39 original sprints into either the demo track or Track B, so that the claim is checkable
rather than asserted. If you cannot find an item in §5, that is a bug in this document.

> **Agents: read [PROGRESS.md](PROGRESS.md), then this file, then the cited sprint in
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).** The cited sprint is your task specification.
> This file tells you which one, and in what order.

---

## 0. The rule this plan is built around

**Every sprint ends with something you can show on a phone.**

Not "the backend works". Not "the tests pass". A thing you can hold, tap, and watch do something it
could not do two days ago.

This is the first-order constraint, above sprint tidiness and above architectural sequencing. It
exists because the opposite approach has a specific, known failure: build everything, wire the
interface last, and arrive at the demo with a great deal working and nothing to point at. Work that
is invisible on the device is **indistinguishable from work that does not exist** — to a judge, and
to you when you are deciding on the 22nd what to cut.

Three consequences, and they are not negotiable:

1. **Thin UI first, depth later.** A sprint that produces data ships the screen that renders it, in
   the same sprint, even if that screen is crude. A pin on a map beats a populated table.
2. **Every sprint delivers `docs/walkthroughs/D<nn>.md`** — a numbered play-script you run on a real
   device, as the user, with expected results at each step. Format: [`docs/walkthroughs/README.md`](docs/walkthroughs/README.md).
3. **No walkthrough, no handoff.** It is a Prototype Gate item, at the same level as "it runs".

The payoff compounds: by D10 the nine-minute stage script is **assembled** from nine walkthroughs
you have each already run, not written from nothing in the last 48 hours.

---

## 1. The 17 days

Each row is a sprint. The **Showable** column is the point of the row — it is what you will be able
to do on the device that evening.

| Sprint | Dates | Showable on a phone at the end | Source |
|---|---|---|---|
| **D01** | Oct 7–8 | Risk-flag pins on the map, coloured by severity. Crime markers finally have colours. Trigger SOS and see it **recorded**. | S02, S03, S05, S07 |
| **D02** | Oct 9–10 | 200 flags across Dhaka. Tap one: severity, half-life, time left. Watch one decay and vanish. | S04, S19, S20 |
| **D03** | Oct 11–12 | Type **"Mirpur 10 golchattar"**. The map flies there and tells you how it resolved it. | S10, S11, S04 |
| **D04** | Oct 13–14 | Pull to refresh: flags from **today's real news**, each with its headline and outlet. — **✅ closed Oct 8** | S09, S14, S04 |
| **D05** | Oct 15 | Unconfirmed flags look different. Tap one: the sources listed. Watch a promotion happen. | S15 |
| **D06** | Oct 16–17 | Ask for a route through a flagged corridor. Get alternatives, each with a plain-English reason. | S12, S13, S05, S07 |
| **D07** | Oct 18–19 | Photograph a two-person scene. Get a real interaction read. See the evidence photo stored. | S06 |
| **D08** | Oct 20–21 | Turn a report into a **Bangla General Diary** draft. Correct thana. Cannot submit unapproved. | S27, S28 |
| **D09** | Oct 22 | Move the map to **tomorrow** — a procession already flagged. SOS history screen. | S26, S05, S07 |
| **D10** | Oct 23 | **Feature freeze.** The whole nine-minute script, three times, on the device. | new |
| — | **Oct 24** | **Finale** | — |

**There is no slack in this schedule.** Stated deliberately. The mitigations are: D02's fixture makes
beats 1–5 work without live agents, D04 caches every document so the venue network cannot break
beat 1, and **D10 contains no feature work at all** — it is rehearsal and hardening only, which is
what gives the preceding sprints somewhere to overflow into.

**Pre-declared cuts, in the order they get taken:** D05's independence check (§D05), then D07's
classifier claim (§8). Push notifications and geofencing are already out — they are **B6a**.

---

## 2. The target: what the judges see

The nine-minute sequence. **Build toward this, not toward the checklist.** It is the concept
document's §6 worked example plus the two differentiators it closes on. Every beat traces to the
sprint that makes it real *and* to the walkthrough that proves it.

| # | Beat | Built in | Proven by |
|---|---|---|---|
| 1 | Open the map on Dhaka. A live risk surface: confirmed and unconfirmed flags, severity by colour, each one aging. | D01, D02, D04 | `D01`, `D02`, `D04` |
| 2 | Tap a flag. Provenance: *three independent sources, confirmed 14:31, 3-hour half-life, 42% severity remaining.* | D02, D04, D05 | `D02`, `D05` |
| 3 | Type **"Mirpur 10 golchattar"**. It resolves. Explain that Google cannot do this. | D03 | `D03` |
| 4 | Request a route through a flagged corridor. An alternative is offered with a plain-language reason: *fire reported near Bangshal, roads likely blocked, three sources.* | D06 | `D06` |
| 5 | Show a flag whose severity has decayed below threshold and disappeared on its own. **No stale red zones.** | D02 | `D02` |
| 6 | Report an incident with a photo. The vision stack analyses it, names what it found, and the evidence is persisted. | D07 | `D07` |
| 7 | Generate the **Bangla General Diary** from that report. Correct thana. Human review gate that cannot be bypassed. | D08 | `D08` |
| 8 | Show **tomorrow's** map: an announced procession already flagged, before it happens. | D09 | `D09` |
| 9 | Trigger SOS. Email delivered, **and here is the record** — the loop closed. | D01, D09 | `D01`, `D09` |

Beats 3, 5, 7 and 8 are the ones no competitor has. If time runs short, protect those four over
polish anywhere else.

---

## 3. Working rules for the 17 days

Carried over from [CONTRIBUTING.md](CONTRIBUTING.md) and plan §2, with the changes below.

**Unchanged:**
- One writer at a time. The trunk is a baton.
- Every push runs. Not compiles — runs.
- `PROGRESS.md` entry in the same commit as the work. CI enforces it.
- Forward-only migrations.
- `app/llm/client.py` is the only module that may import `anthropic`.
- Mobility framing. Verification before publication. Decay on every flag.

**Added — the two gates that matter most here:**
- **`docs/walkthroughs/D<nn>.md`, written and actually run on a device, in the same commit as the
  sprint.** A sprint with no walkthrough has not ended. See §0.
- **Every *previous* walkthrough still passes.** Re-run them before you hand over. If your sprint
  broke one, fix it or update it in the same commit. These are the regression suite that matters,
  because they are the demo. This is the gate that catches a D01-style silent breakage before the
  23rd rather than on it.

**Relaxed until 24 October** (per ADR 0005 §Decision 5):
- The per-sprint `demo_D<nn>` function in `scripts/smoke.sh` is best-effort. The walkthrough replaces
  it as the demo-of-record.
- `.env.example` and plan §9 bookkeeping is best-effort.

**Tightened:**
- **A `D` sprint that overruns its dates is cut, not extended.** Push what runs, write down what you
  dropped, hand over. The next sprint's dates do not move. This is the only mechanism that keeps
  24 October real, and it is the rule most likely to be broken.
- **Cut depth, never the screen.** When a sprint is running out of time, ship the crude version of
  the UI and cut the backend sophistication behind it. A rough screen with real data is demoable; a
  sophisticated service with no screen is not.

---

# 4. The demo track

---

## D01 — Schema, contracts, first pins, and an SOS that leaves a record
**Oct 7–8 · source: S02, S03, S05, S07**

**Showable:** open the app, go to the map, and see **risk-flag pins that were not there before**,
coloured by severity. The existing crime-report markers finally render in colour instead of grey.
Then trigger an SOS and **see a row appear in the incident history** — the alert used to vanish.

**Gate:** `docs/walkthroughs/D01.md` passes on a real device, and `./scripts/seed.sh --fresh` builds
the schema from zero.

- [x] `scripts/migrate.py` + `schema_migrations` table — forward-only timestamped SQL *(S02)*
- [x] Migration: **`risk_flags`** — PostGIS `GEOGRAPHY(POINT, 4326)`, GiST index on location, index
      on `(status, expires_at)`, **`CHECK (half_life_hours > 0)`**. The check is the decay invariant
      at schema level; it is not optional *(S02)*
- [x] **`valid_from` / `valid_to` on `risk_flags`, nullable, in this migration.** D09's forward-dated
      flags need them. Adding them now costs nothing; adding them in D09 would mean a schema change
      *and* a contract change on D09's single day — and per CONTRIBUTING.md a contract change means
      updating every consumer and the TypeScript mirror
- [x] Migration: `raw_documents`, `extracted_incidents`, `agent_runs` *(S02)*
- [x] `scripts/seed.sh` — rebuild a dev DB from migrations + fixtures in one command, for real *(S02)*
- [x] `app/contracts/{risk,agents,surface}.py` — the shapes from plan §6.1–6.3, **plus `valid_from`
      and `valid_to` on `RiskFlag`** *(S03)*
- [x] `frontend/src/types/contracts/` — hand-mirrored TypeScript *(S03)*
- [x] `app/policy/framing.py` — `to_mobility_statement()`, `assert_mobility_safe()`, banned-term
      list. **Flag text is only ever written here** *(S03)*
- [x] `backend/tests/invariants/` with **two** tests: mobility framing, and one source can never
      produce a `confirmed` flag *(S03)*
- [x] `requirements.txt` → `requirements/{base,ai,agents,dev}.txt`, with every dependency the demo
      track needs added now — **defect 15** *(S04)*
- [x] **A minimal `DbRiskSurface` behind the `RiskSurface` protocol.** D01 renders *through the
      protocol*, not around it, so D02 can add `SeededRiskSurface` and the scoring engine behind the
      same seam with no client rework and nothing orphaned
- [x] **`GET /api/v1/risk/flags?bbox=&as_of=`** — flags in the contract shape, through the protocol.
      **`as_of` is accepted and threaded from day one** even though it does nothing until D02; it is
      what D02's time control and D09's forward-looking view both hang off
- [x] **~20 seed flags, loaded into `risk_flags` by `seed.sh`.** The full 200 is D02
- [x] ⚠️ **Fixtures store structured fields only — never `mobility_statement`.** `kind`, `severity`,
      `location`, `half_life_hours`. The statement is **derived through `framing.py` at load time**.
      A fixture containing hand-written flag prose violates the framing invariant this sprint ships
      a test for, and the cheap way out would be to weaken the test. Do not take it
- [x] 📱 **`MapScreen` risk overlay — thin.** Pins plus a radius circle, colour by severity. No detail
      sheet yet, no filtering. Just: they are on the map and they are the right colour
- [x] 📱 **Defect 3 — `CRIME_COLORS` to lowercase keys matching the DB enum**, derived from the
      contract type so it cannot drift again. *Every crime marker currently renders with no colour.*
      Moved forward from D06 because it is an hour of work and it is visible *(S07)*
- [x] **Defect 35 — SOS leaves no audit trail.** `trigger_sos` never inserts into `sos_incidents`,
      and `_save_video` deletes the clip after attaching it. After a verified delivery the table
      still holds zero rows. Fits here because it is migration-adjacent work, it is beat 9's
      foundation, and it gives this sprint a second visible result *(S05)*
- [x] **`docs/walkthroughs/D01.md` must include a full SOS trigger.** SOS is the only feature that
      currently works end to end. From here on, every walkthrough re-run protects it
- [x] `mypy --strict` clean on `app/contracts`, `app/policy`
- [x] 📄 `docs/walkthroughs/D01.md`
- [x] **Not planned, found by running the walkthrough on a phone — both fixed:**
      the map was a **blank white page on iOS** (`PROVIDER_GOOGLE` forces a Google Maps SDK that Expo
      Go for iOS does not ship), and **one SOS froze the entire API for 2m34s** (`smtplib` called
      synchronously inside `async def`, blocking the event loop for every request). Neither was
      detectable from a green test suite. This is §0 earning its place

> **Two things deliberately *not* in this sprint, and why:**
>
> **`app/llm/client.py` → D03**, its first consumer. Nothing in D01 or D02 needs an LLM.
>
> **ADR 0003 (collapse the user tables) → Track B (B1).** It was originally here on the reasoning
> that *"`risk_flags` inherits the choice"* — but **risk flags come from news and have no
> `user_id` at all**, so nothing in the demo track depends on it. Meanwhile dropping `public.users`
> would break live code: [`endpoints/sos.py`](backend/app/api/v1/endpoints/sos.py) creates rows in
> it on every SOS and [`endpoints/voice.py`](backend/app/api/v1/endpoints/voice.py) imports the
> model. Executing it in D01 would have broken beat 9 on 8 October, invisibly, until the 23rd.

---

## D02 — The surface breathes
**Oct 9–10 · source: S04, S19, S20**

**Showable:** 200 flags across Dhaka. **Tap one** and see what kind it is, its severity *right now*,
its half-life and how long it has left. Drag the **"as of" control** forward and watch a flag fade
and then disappear on its own.

**Gate:** `docs/walkthroughs/D02.md` passes on a device — including the decay step, which must be
demonstrable in under a minute, not over three hours. D01's walkthrough still passes.

> **This is the most valuable sprint in the track and the one to protect.** The fixture makes beats
> 1, 2, 4 and 5 demoable *even if live ingestion never lands*. Spend real time on it.

- [x] **`SeededRiskSurface` + `data/fixtures/risk_flags.json` — ~200 hand-built flags across
      Dhaka**, behind the protocol D01 established. Mixed kinds, severities and half-lives; confirmed
      and unconfirmed; several already expired; **several deliberately placed on common commuting
      corridors** so D06 has something to route around *(S04)*
- [x] ⚠️ **Same fixture rule as D01: structured fields only, statement derived through
      `framing.py`.** 200 rows is 200 chances to smuggle prose past the invariant
- [x] `RISK_SURFACE_IMPL` switch — `seeded` or `db` *(S04)*
- [x] **Risk Scoring Engine** — severity, spatial radius and half-life per event kind, to the concept
      document §5 table: accident ~1h, fire ~3–4h, clash ~6–12h, announced event = duration, chronic
      blackspot = months *(S19)*
- [x] **Time-of-day modulation** — the same flag scores differently at 03:00 and 15:00 *(S19)*
- [x] **Decay engine** — severity as a function of elapsed time and half-life, **computed on read**
      rather than by a cron job that can fall behind *(S19)*
- [x] **One source of truth for expiry.** Severity is computed; `expires_at` is *derived* from
      `half_life_hours` and never hand-set (plan §6.1 says so). The sweep deletes, it does not decide
- [x] **Expiry** — flags below threshold stop being served, and are swept *(S20)*
- [x] Fill in the real `DbRiskSurface` behind D01's minimal one; a test asserts **both** surfaces
      satisfy the protocol *(S04, S20)*
- [x] Wire `scripts/crime_risk_model.json` (1,105 rows of real Bangladesh Police unit statistics) in
      as the **chronic baseline layer** — close to free, and it gives the demo a chronic layer
      without S24's archive mining
- [x] ⚠️ **Note for D06:** `route_service._get_regional_risk()` *already* applies this same model.
      Once it is in the surface, that method must go, or regional risk is counted twice
- [x] 📱 **Flag detail sheet.** Tap a pin: kind, mobility statement, severity now, half-life, time
      remaining, confirmed/unconfirmed. Beat 2's container — D04 and D05 fill in the rest
- [x] 📱 **An "as of" time control, dev builds only**, driving D01's `as_of` parameter. This is what
      makes decay *showable*. Without it, beat 5 means standing on stage saying "trust me, in three
      hours this will fade." D09 promotes it to a real forward-looking control
- [x] 📄 `docs/walkthroughs/D02.md`
- [x] **Not planned, found while building this sprint:**
      `route_service._get_regional_risk()` takes the **maximum** `normalized_risk` across every
      overlapping police unit, and the dataset contains both metropolitan units *and* the ranges that
      contain them — so every point in Dhaka scores 100.0 from `Dhaka Range` instead of 58.9 from
      `DMP`. The chronic layer drops the range rows for that reason and says so. The method is now
      both a double count *and* wrong on its own terms; D06 deletes it and it carries a comment
      saying so.
- [x] **Also found:** the framing invariant's AST check caught keyword arguments and assignments but
      **not a string key in a dict literal**. Before D02 the only producers of `mobility_statement`
      outside `framing.py` lived in `scripts/`, which that test does not scan — so a hand-written
      statement in a dict under `app/` would have walked straight past it. The detector was
      strengthened rather than the new modules being quietly excluded

---

## D03 — Bangla search that actually works
**Oct 11–12 · source: S10, S11, S04**

**Showable:** a search box on the map. Type **"Mirpur 10 golchattar"**, or `গোলচত্বর`, or
"Jatrabari chourasta" — the map flies there and a chip tells you whether it came from the gazetteer
or the LLM. Type a place that does not exist and it says so rather than guessing.

**Gate:** `docs/walkthroughs/D03.md` passes on a device, the accuracy number is recorded in it, and
D01–D02 still pass.

> The concept document calls this **the primary technical risk**. It is also demo beat 3 — and in the
> first draft of this plan, no sprint built the search box. That is why §0 exists.

- [x] **`app/llm/client.py` + `app/llm/models.py`** — install `anthropic`; every call returns a
      validated Pydantic model; the invariant test asserts this is the only importer. **Lands here
      because the Geolocation Agent's fallback is the first thing in the track that needs an LLM** *(S04)*
- [x] `mypy --strict` clean on `app/llm` *(S04)*
- [x] `data/gazetteer/` — seed **one zone**, Dhaka central, 150+ landmark entries: Bangla and
      romanised forms, aliases, type, coordinates. The concept document's own mitigation is "seeded
      manually for the pilot zone" — do not attempt national coverage *(S10)*
- [x] Loader + fuzzy match across romanisation variants (golchattar / golchotor / গোলচত্বর) *(S10)*
- [x] `GeolocationAgent` — gazetteer first, **LLM fallback second**, discard third *(S11)*
- [x] **Invariant: unresolvable locations are discarded, never guessed.** A wrong pin is worse than
      no pin, the concept document commits to this, and a judge may well test it *(S11)*
- [x] `method` on every result: `gazetteer`, `llm` or `unresolved` *(S11)*
- [x] **`POST /api/v1/geo/resolve`** — text in, coordinates plus `method` out
- [x] 📱 **Search box on `MapScreen`**, with a resolution-method chip on success
- [x] 📱 **An explicit "could not resolve that place" state.** This is the discard invariant made
      visible, and it is a better answer to a judge than a silent failure
- [x] **A real accuracy number** on a held-out set of ~50 references. "We did not measure it" is the
      worst available answer in Q&A *(S11)*
- [x] 📄 `docs/walkthroughs/D03.md` — **run end to end on an iPhone, all 14 steps passed.** Running
      it found two defects that `tsc`, ESLint and Jest could not: the container started without
      `openai` because the image cached its dependency layer, and route mode had no reachable exit
      (its close button sat under the route card and `toggleRouteMode` is the only way out, so a
      reload was the only escape). Both fixed
- [x] **Deviation from this plan's own wording, and why:** the first item says *install `anthropic`*.
      This project has no Anthropic key — `ANTHROPIC_API_KEY` is in `.env.example` and absent from
      `.env`, so §7.1's claim that "the key is already configured" was wrong. The LLM tier runs on the
      free Gemini and Groq endpoints instead, both of which serve the OpenAI Chat Completions wire
      format, so `openai` is the SDK and one client reaches either provider by changing a base URL.
      The invariant is unchanged in substance — one module, one seam, every response validated — and
      `tests/invariants/test_only_llm_client_calls_models.py` enforces it against whichever SDK is in
      use rather than against the name `anthropic`. Configuration is **per feature**, not global:
      `LLM_CHAIN_GEO` picks the models and `GEMINI_KEY_GEO_*` / `GROQ_KEY_GEO_*` the keys, so D04's
      ingestion loop cannot spend the daily quota D03's search box needs.
- [x] **Not planned, found while building:**
      the matcher resolved **"Sector 11" to "Sector 10"** at 0.89 confidence — one character apart,
      two places 2 km apart. Numbers are now identity rather than spelling: digits must match exactly,
      letters may be misspelt. Separately, the gazetteer was **refusing "Farmgate" and "Motijheel"**
      because OpenStreetMap lists them in two layers ~270 m apart and the duplicate check ignored
      distance, so the discard invariant was failing in the direction that costs a real place.
- [x] **Also found, by the eval set rather than by a test:**
      the LLM tier **overturned the gazetteer's ambiguity refusals.** "Sector 11" is Uttara's and
      Bashundhara's, 10 km apart; the gazetteer declined and the model then answered Uttara's with
      confidence. Our own guard was bypassable by the weaker tier beneath it. A refusal for ambiguity
      now short-circuits before the LLM is asked, and "we have never heard of this" stays distinct
      from "we refuse this on purpose".

---

## D04 — Today's news, on the map
**Oct 13–14 · source: S09, S14, S04**

**Showable:** pull to refresh. **New flags appear, extracted from real Bangla news published today**,
and tapping one shows the headline and the outlet it came from.

**Gate:** `docs/walkthroughs/D04.md` passes on a device, **and passes again with the network off**,
replaying from the document cache. D01–D03 still pass.

- [x] Ingestion framework behind a **source-agnostic interface** — the concept document's own
      mitigation for social-media access restrictions *(S09)*
- [x] Three Bangla news sources: `BeautifulSoup` where static, `Playwright` where not *(S09)* —
      Ekattor TV and Independent TV (one CMS, static), Channel 24 (Playwright)
- [x] `raw_documents` persistence, deduplicated on URL and content hash *(S09)*
- [x] Polite collection: `User-Agent`, rate limits, robots respected. Being blocked mid-rehearsal is
      a self-inflicted wound *(S09)*
- [x] LLM extraction into `extracted_incidents`: kind, location reference, time, severity hint,
      source. A validated model out of `app/llm/client.py`, never raw text *(S14)* — no
      model-extracted time: the article's publication time is the anchor
- [x] `LiveRiskAgent` — extraction, then `GeolocationAgent`, then `risk_flags`, on a 10–15 minute
      cadence *(S14)* — every 15 minutes; gazetteer-only place resolution
- [x] ⚠️ **Every flag this sprint produces is `unconfirmed`.** Rumour Guard is D05, and D01's
      invariant test already forbids one source producing a `confirmed` flag. Writing `confirmed`
      here would trip it — correctly
- [x] Celery schedule registry; delete the two phantom beat entries *(S04)*
- [x] `agent_runs` populated: started, finished, documents seen, flags produced, errors *(S14)*
- [x] **Cache every fetched document, and make the cache replayable.** The demo must be able to run a
      known-good ingestion offline. Do not let a hotel network decide whether beat 1 works —
      documents cached in `raw_documents`; the offline replay is a captured flag fixture
      (`live_replay.json`), because `raw_documents` lives in Supabase, which is offline too
- [x] 📱 **Source strip in the flag detail sheet** — headline, outlet, time. Beat 2, half of it
- [x] 📱 **A "last updated" indicator and pull-to-refresh** on the map, so ingestion is visible as an
      event rather than inferred from pins changing — a refresh button, since a map has no scroll to
      pull, plus "fetch news now"
- [x] 📄 `docs/walkthroughs/D04.md` — **run end to end on a device, live and offline; all 12 live
      steps and O1–O6 passed (Arafat, 2026-10-08). D04 is closed.** The offline pass served the
      captured replay with `DATABASE_URL` pointed at a dead host and the extraction key removed
- [x] **Not planned, found by running it on a phone — and this is §0 earning its place twice over,
      because two of the three were not in D04's code at all:**

      **(a) Live ingestion had never published a single flag.** The agent, the sources, the extraction
      and the audit trail all worked; the gazetteer was throwing the results away. A real Mohakhali
      bus fire was extracted at **0.95 confidence** and discarded as `unresolved_location`, because
      the extraction prompt asks for *"the most specific place name"*, the model correctly answered
      `মহাখালী বাস টার্মিনালে`, and the gazetteer resolves `মহাখালী` at 1.00 and that phrase at
      nothing — **the most specific answer was the least resolvable one.** `PLACE_FILLER` could not
      help: `বাস` and `টার্মিনালে` are part of the name, not wrapping around it. Fixed with
      `PLACE_GENERIC_TAIL` — generic place-*type* nouns stripped from the end only, longest match
      first. **The discard invariant survived**, which was the hard part: a prefix fallback was tried
      first and rejected because it resolved the fabricated `গুলশান ফ৭ গোলচত্বর` to Gulshan, and
      what saves the chosen fix is **D03's number-identity rule**. Three regression tests pin it

      **(b) ⚠️ Beat 9 was silently dead, and had been since D01.** Every authenticated backend call
      401'd about an hour after sign-in — the symptom D04 surfaced was the newspaper icon failing with
      `No refresh token`. `api.service.ts` read the access token from a `SecureStore` copy written once
      at sign-in and never refreshed; Supabase tokens last an hour; and the 401 recovery path POSTed to
      the backend's `/auth/refresh`, a `# TODO` stub whose signature did not even match the request.
      All the while the Supabase client held a valid token (`autoRefreshToken: true`).
      **`HomeScreen` SOS had the same bug** — it read `useAuthStore().token`, captured once at
      `initialize()` — so an SOS from an older session uploaded the video and *then* got a 401. It
      passed every time anyone tested it because `D01.md` is run just after signing in. Fixed by making
      `supabase.auth.getSession()` the only token source in all three read paths. **This is exactly the
      cross-sprint silent breakage §8 row 3 predicts**, and the only reason it was caught before the
      23rd is that D04 happened to need a token on a stale session

      **(c) The walkthrough's own offline instructions bricked the API**, and its O5 claim was wrong.
      `D04.md` is corrected: O2 now says to preserve the `DATABASE_URL` shape and change only the
      host (an unparseable URL raises in `create_async_engine` at *import*, so nothing answers
      `/health`), O3 names `⚠️ Database not available` as the success signal, and O5 no longer claims
      the replayed flag is "fresh again" — `observed_offset_hours` preserves the flag's age, so a
      capture taken late in a flag's life replays weak forever
- [x] **Also found, and worth knowing before the stage:** a tap on the newspaper icon normally changes
      **nothing**, and that is correct. Across eight consecutive runs `listed` climbed 480 → 494 while
      `relevant` stayed pinned at **3**, all already in `raw_documents` and skipped on URL —
      `fetched: 0, published: 0`, no quota spent. Step 4's "**if** the outlets published something" is
      doing more work than it looks. **§D10 must decide** whether to narrate that honestly or to clear
      `extracted_at` on one document before the demo so the tap produces a visible pin
- [x] **Step 6 was not a procedure.** It said news flags *"look like any other flag; tap pins until
      the Source line names an outlet"* — with 212 fixture flags on the map. Pin colour encodes
      decayed severity, not provenance; crime-report markers are a second unrelated colour scheme;
      and fixture flags are `unconfirmed` too, so nothing narrows it visually. `D04.md` now has a
      *Finding the news flag* section that asks the backend for the coordinates first

---

## D05 — Verification you can see
**Oct 15 · source: S15**

**Showable:** unconfirmed flags are **visually distinct** — hollow, dashed. Tap a confirmed one and
it lists the sources that confirmed it. Run the replay and **watch an unconfirmed flag become
confirmed** when the second source arrives.

**Gate:** `docs/walkthroughs/D05.md` passes on a device, including the promotion, which is the §6
worked example's 14:26 → 14:31 transition. D01–D04 still pass.

> **One day, and it is the tightest sprint in the track.** Embedding thresholds are fiddly to tune.
> The cut is pre-declared below rather than improvised at midnight.

- [ ] `sentence-transformers` semantic deduplication across sources, so four outlets reporting one
      fire collapse into one event rather than four corroborations *(S15)*
- [ ] Multi-source threshold promotes to `confirmed`; below it, `unconfirmed` at reduced weight *(S15)*
- [ ] **The invariant test from D01 now runs against real data**, not a stub *(S15)*
- [ ] Promotion path: `unconfirmed` → `confirmed` on a second independent source *(S15)*
- [ ] 📱 **Confirmed vs unconfirmed rendered differently on the map** — not just a field in a sheet.
      The tiering is an ethical commitment; it should be legible at a glance
- [ ] 📱 **Source count badge** on the pin, source list and confirmation time in the sheet *(S15)*
- [ ] 📱 A **scripted replay** that performs the promotion on demand, for the stage
- [ ] 📄 `docs/walkthroughs/D05.md`

**Cut this first if the day runs out → Track B, after B6a:**

- [ ] Independence check — same-owner outlets and syndicated copy must not count twice *(S15)*.
      *Distinct publishers are enough for the demo; this is the rigorous version, and it is the
      honest answer to give in Q&A if asked.*

---

## D06 — Routing, explanations, and the reason why
**Oct 16–17 · source: S12, S13, S05, S07**

**Showable:** ask for a route through a flagged corridor. Get **ranked alternatives**, each with a
safety score and **one sentence of plain English** saying why it is being suggested.

**Gate:** `docs/walkthroughs/D06.md` passes on a device, against a **local** OSRM. D01–D05 still pass.

- [ ] **Local OSRM** — honour `OSRM_BASE_URL`, stop using the public demo server — **defect 7**.
      *Today the demo depends on a stranger's rate limiter.* Highest-value reliability fix in the
      track. **The compose service already exists** (`profiles: [osrm]`), but the
      `osrm-data/bangladesh-latest.osrm` graph does not — **that build is §9 background work and
      should already be done by the time this sprint starts** *(S05, S04)*
- [ ] Use OSRM's own durations instead of a flat 30 km/h, and add the walking profile — **defect 7** *(S05)*
- [ ] `_calculate_path_risk` becomes a **PostGIS spatial query** against `risk_flags`, instead of
      all-rows-then-a-Python-loop — **defect 8** *(S05)*
- [ ] Route scoring through the `RiskSurface` protocol, so seeded and live both work *(S12)*
- [ ] ⚠️ **Delete `route_service._get_regional_risk()`.** D02 moved the police-statistics model into
      the surface as the chronic layer. Leaving this method counts regional risk twice and the
      symptom is a plausible-looking score that is quietly wrong
- [ ] Honour `avoid_high_crime_zones` and `max_crime_score`, accepted and silently ignored today —
      **defect 6** *(S05)*
- [ ] **One score scale: 0–100, higher means safer, named `safety_score`** — the scale the D01
      contract already fixed. Delete the 0–10 `crime_score` and the percent variants. Add a test —
      **defect 11** *(S07)*
- [ ] **Explanation generation through `app/policy/framing.py`** — mobility framing only, never a
      safety or political characterisation. "Road blocked", "heavy crowd", "expect delay" *(S13)*
- [ ] Nominatim through a backend proxy with a real `User-Agent` and a Redis cache — **defect 10** *(S05, S07)*
- [ ] 📱 **Route comparison card** — alternatives ranked, each with `safety_score`, duration, and the
      trade-off stated: *4 minutes longer, avoids two flagged corridors* *(S12)*
- [ ] 📱 **The explanation on screen, attached to the route**, not in a log. Beat 4 *(S13)*
- [ ] 📱 Flagged corridors visibly highlighted along the rejected route, so the comparison reads
      without narration *(S13)*
- [ ] 📄 `docs/walkthroughs/D06.md`

---

## D07 — Crime detection from an image, for real
**Oct 18–19 · source: S06**

**Showable:** photograph a staged two-person scene in the report flow. Get a **real interaction
assessment** instead of `pose_analysis: null`, and see the **evidence photo stored** and visible in
the report detail screen afterwards.

**Gate:** `docs/walkthroughs/D07.md` passes on a device, and the reachability table in the eval
output shows **6 of 6** crime classes reachable. D01–D06 still pass.

> **Owner decision, against plan §12.** The long plan parks this work as off the critical path. It is
> here because beat 6 should be real. Note what that means: today **`harassment`, `theft` and
> `vandalism` are structurally unreachable** — no input can produce them — so demoing the classifier
> without this sprint fails in the open.
>
> **Blocked on §7.1 — the reasoning-layer decision must be made by 17 October.**

- [ ] **Defect 29 — port off `mp.solutions`.** `mediapipe==1.1.0` removed the namespace
      `pose_detection_service.py` is built on, so the import raises and `pose_service` is left
      `None`. **Pose analysis has never run**; every response carries `pose_analysis: null` *(S06)*
- [ ] **Defect 5 — multi-person.** The `PoseLandmarker` port takes `num_poses`, which resolves this
      at the same time. `analyze_interaction` currently always short-circuits *(S06)*
- [ ] **Defect 30 — close the vocabulary gap.** The engine scores 21 object signals; YOLOv9c emits
      COCO's 80 classes and 11 of those signals are not members (`gun`, `blood`, `broken window`,
      `damaged property`, `graffiti`, `crowbar`, `spray paint`, `money`, `door`, `window`,
      `building`). **Requires §7.1** *(S06)*
- [ ] **Defect 13 — persist evidence.** Report photos are analysed and then discarded. D08 needs them
      as GD attachments, so this is a dependency now, not a nicety *(S06)*
- [ ] Re-run `scripts/eval_crime_vision.py`, commit a new baseline. **3-of-6 → 6-of-6 is itself a
      strong Q&A answer** *(S06)*
- [ ] Grow the eval set enough to make the number meaningful — it holds 2 seed negatives today.
      30–40 images defends a claim; 60 was the original target *(S06, §9)*
- [ ] 📱 **Evidence photos surfaced in the report detail screen** *(S07)*
- [ ] 📱 **The analysis result shown to the reporting user** — what was detected, what it concluded,
      how confident. The pipeline is the strongest inherited asset in the repo and it is currently
      invisible to the person using it
- [ ] 📄 `docs/walkthroughs/D07.md`

---

## D08 — Casework Agent: the Bangla General Diary
**Oct 20–21 · source: S27, S28**

**Showable:** open a report you filed, tap **generate GD**, and get a formal Bangla General Diary
draft naming the correct thana. Edit it. Try to submit without approving — **the app will not let
you.** Export the PDF.

**Gate:** `docs/walkthroughs/D08.md` passes on a device, and a native Bangla speaker has read three
drafts and signed off. D01–D07 still pass.

> The long plan calls the closed loop **"the decisive differentiator"**, and this is the cheapest
> high-value sprint in the track: one LLM call, one template, one lookup, one review screen.

- [ ] GD template in formal Bangla, structured from the real form *(S27)*
- [ ] Thana identification from incident coordinates, over `police_stations.csv` *(S27)*
- [ ] `CaseworkAgent` — report plus evidence plus geolocation becomes a draft, through
      `app/llm/client.py` with a validated output model *(S27)*
- [ ] **Mandatory human review. It must be structurally impossible to submit an unreviewed draft —
      enforced in the state machine, not the UI.** A generated legal document is a draft until a
      person approves it, and this is the single most likely thing for a judge to press on *(S28)*
- [ ] ⚠️ **Embed a Bengali-glyph font in the PDF export.** Default PDF base fonts have no Bengali
      coverage, so the output renders as empty boxes — and it will look fine on screen right up to
      the moment you export. Budget time for this; it is the classic trap in this task
- [ ] 📱 **`features/casework/`** — draft review, inline edit, approve, export to PDF *(S28)*
- [ ] 📱 **The review gate visible as a gate** — a disabled submit with a stated reason, not a hidden
      button. The safeguard is a selling point; show it working
- [ ] **A native speaker reads at least three drafts.** Formal Bangla that is subtly wrong is worse
      on stage than an English placeholder. **This is a gate, and it depends on a person — arrange
      them in §9, not on the 20th** *(S28)*
- [ ] 📄 `docs/walkthroughs/D08.md`

---

## D09 — Tomorrow's map, and the loop closed
**Oct 22 · source: S26, S05, S07**

**Showable:** move the map's time control to **tomorrow**. An announced procession is **already
flagged**, before it has happened. Then open the SOS history screen and show the record of an alert
that was actually delivered.

**Gate:** `docs/walkthroughs/D09.md` passes on a device. D01–D08 still pass. **This is the last
sprint that ships a feature.**

- [ ] `ScheduledRiskAgent` — read published announcements of processions, shutdowns, exam days and
      large gatherings; emit **forward-dated** flags using the `valid_from` / `valid_to` columns D01
      already created, so **no migration and no contract change is needed today** *(S26)*
- [ ] Mobility framing is non-negotiable here. Processions and gatherings are "road blocked" or
      "heavy crowd", never characterised politically *(S26, invariant)*
- [ ] 📱 **Map time control, promoted from D02's dev-only version to a real forward-looking one**,
      over the same `as_of` parameter. **No competing product looks forward. This is beat 8** *(S26)*
- [ ] 📱 Forward-dated flags visually distinguished from live ones — a scheduled risk is a different
      claim from a current one
- [ ] 📱 **Defect 14 — `MapScreen`'s SOS button is still a `// TODO` alert** while `HomeScreen`'s is
      real. Extract one `useSOS()` hook; both screens consume it *(S07)*
- [ ] 📱 **SOS history screen**, over the audit trail D01 started writing. Beat 9's second half: the
      alert was delivered *and here is the record*. This is what "closing the loop on public data"
      looks like to a judge *(S05)*
- [ ] 📄 `docs/walkthroughs/D09.md`

---

## D10 — Feature freeze, hardening, rehearsal
**Oct 23 · source: new**

**Showable:** the entire nine-minute script, three times, without an unplanned intervention.

**Gate:** three clean timed runs on the real device, plus the failure drills.

> **No new features. None.** Every feature task has been pulled back into D09 or earlier precisely so
> that this day contains nothing but hardening — which is also what gives the earlier sprints
> somewhere to overflow into. If something is not working when D10 starts, it is **cut from the
> script**, not fixed here.

- [ ] **`docs/walkthroughs/FINALE.md` — assembled from `D01`–`D09`**, not written from scratch. This
      is the payoff of the §0 rule
- [ ] **Offline demo path.** `RISK_SURFACE_IMPL=seeded`, replayable ingestion cache, local OSRM, a
      recorded fallback video. Assume the venue network fails
- [ ] **Three full rehearsals on the real device.** Time them. Nine minutes is the target
- [ ] **Failure drills:** kill the network, kill Redis, kill the LLM key. The demo should degrade to
      the seeded surface and keep going. Rehearse the sentence you say while it does
- [ ] Decide and document the police-routing position — §7.2 *(S05)*
- [ ] Q&A numbers ready: geolocation accuracy (D03), flag precision (D05), vision reachability (D07),
      time-from-incident-to-alert (D04)
- [ ] **Write down what was cut**, and the honest one-line answer for each. Judges ask; a prepared
      "measured, scheduled, here is the figure" beats improvisation every time
- [ ] Impact presentation, against concept document §10 success metrics

---

# 5. Coverage: where every original sprint went

**The point of this table is falsifiability.** ADR 0005 claims nothing was dropped. If a sprint below
has no destination, the claim is false and this document needs fixing — treat that as a bug, not an
inconvenience.

| Original | Title | Destination |
|---|---|---|
| S01 | Unblock the repository | ✅ done. Remainder (delete `agent/Arafat`, credential rotation, history rewrite) → **B0** |
| S02 | DB foundation & ADRs | Migrations + `seed.sh` → **D01**. ADR documents 0001/0002/0004 **and the ADR 0003 migration** → **B1** |
| S03 | Contracts, policy & invariants | Contracts, framing, TS mirror, 2 invariant tests → **D01**. Retention registry, full invariant suite, drift CI → **B2** |
| S04 | Stubs, fixtures & modularization | Requirements split + minimal `DbRiskSurface` → **D01**. Fixture + `SeededRiskSurface` + scoring → **D02**. **LLM client → D03**. Celery registry → **D04**. OSRM graph → **§9**. Endpoint auto-discovery, config package, frontend de-barrelling, theme deletion → **B3** |
| S05 | Backend defects | **Defect 35 → D01**. Defects 6, 7, 8, 10 → **D06**. SOS history → **D09**. Defect 17 → **D10** (decision) / **B4** (real data). Defect 2 (`pydub`) → **B4** |
| S06 | AI vision: multi-person pose & evidence | **D07**, in full |
| S07 | Frontend defects | Defect 3 → **D01**. Defect 11 → **D06**. Evidence photos → **D07**. **Defect 14 → D09**. Defect 16, `HomeScreen` cleanup, shake threshold → **B5** |
| S08 | Frontend refactor | **B6** |
| S09 | Ingestion framework | **D04** |
| S10 | Bangla gazetteer | **D03** (one zone). National density → **B7** |
| S11 | Geolocation Agent | **D03** |
| S12 | Risk-aware routing | **D06** |
| S13 | Explanations & risk map | Overlay → **D01**, detail sheet → **D02**, explanations → **D06** |
| S14 | Live Risk Agent | **D04** |
| S15 | Rumour Guard | **D05**. Independence check → **D05 if time, else B6a-adjacent** |
| S16 | Push notifications | **B6a** *(moved out of the demo track — beat 8 does not need it)* |
| S17 | Background location & geofence | **B6a** *(same)* |
| S18 | Trips & hot words | **B8** |
| S19 | Decay engine | **D02** |
| S20 | `DbRiskSurface` & expiry | **D01** (minimal) + **D02** (real) |
| S21 | Admin observability | **B9** |
| S22 | Guardian: anomaly detection | **B10** |
| S23 | Guardian: graded escalation | **B10** |
| S24 | Chronic Risk Agent | **B11**. Chronic *layer* is covered in D02 by the existing police-statistics model |
| S25 | Legacy retirement & cost model | **B12** |
| S26 | Scheduled Risk Agent | **D09** |
| S27 | Casework Agent | **D08** |
| S28 | Casework UI & Bangla review | **D08** |
| S29 | Crowd verification | **B13** |
| S30 | Privacy & retention | **B14** |
| S31 | Resilience & chaos testing | **B15** |
| S32 | Observability & cost controls | **B16** |
| S33 | Load testing | **B17** |
| S34 | Offline & battery | **B18** |
| S35 | Performance & accessibility | **B19** |
| S36 | Bangla localisation & SMS | **B20** |
| S37 | Store readiness | **B21** |
| S38–S40+ | Pilot & operate | **B22** |

Phase exit criteria in the long plan are untouched and still apply to Track B.

---

# 6. Track B — the continuation sequence

**This is the rest of the plan, in the order to do it in.** It starts the moment the demo track
finishes or the finale passes, whichever comes first. Every entry keeps its original task text in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — the source sprint is cited, go read it there.

The ordering principle: **debt that compounds comes first, then the deferred agents, then production
hardening, then the pilot.** That is the same shape as the original plan; only the demo-critical work
has been lifted out of it.

| # | Work | Source | Why here |
|---|---|---|---|
| **B0** | Delete `agent/Arafat`. **Rotate credentials. Rewrite history to drop the payload from `db6c42f`.** Untrack both `.env` files. | S01, S01c | **Do this first regardless.** Owner actions, outstanding since 7 Oct, and the history rewrite must happen before this repo is ever made public. |
| **B1** | ADR documents `0001-data-plane`, `0002-auth`, `0004-migrations`. **Plus: execute ADR 0003** — collapse the three user tables, and update `endpoints/sos.py`, `endpoints/voice.py` and `models/` in the same sprint. | S02 | Moved out of D01: `risk_flags` has no `user_id`, so nothing in the demo track needed it, while dropping `public.users` **would have broken SOS** — `sos.py` creates rows in it on every trigger. This is a code change, not just a migration, which is exactly why it does not belong in a two-day sprint with nine other things. |
| **B2** | Full invariant suite, `app/privacy/retention.py` registry, contract-drift CI check | S03 | The two invariants shipped in D01 are the two judges ask about. These are the other five. |
| **B3** | Endpoint auto-discovery, `app/config/` package, frontend service de-barrelling, delete `theme/colors.ts` + `darkTheme.ts` (**defect 16**) | S04 | Structural cleanup with no user-visible effect — exactly why it waited. |
| **B4** | **Defect 2** (`speech_service` `NameError` — `pydub` import commented out), **defect 17** (real thana contacts for `police_stations.csv`) | S05 | Defect 2 blocks speech-to-text entirely. Defect 17 is what lets `POLICE_ROUTING_ENABLED` ever be true. |
| **B5** | **Defect 16** (export `routeService` from the services barrel), remove the ~30 lines of stale-closure deliberation in `HomeScreen`, reconcile the shake threshold (comment says 3.5 g, code says 6.0 — pick one and justify it with a measurement) | S07 | Small, real, and the shake threshold is a correctness question, not a style one. |
| **B6** | Frontend refactor — feature directories under `src/features/`, `src/components/` reduced to shared primitives | S08 | The demo track adds screens fast. This is the sprint that pays for that. |
| **B6a** | **Push notifications, background location, geofence alerting, alert-fatigue thresholds.** Plus D05's independence check if it was cut. | S16, S17, S15 | **Cut from D09 during the §8 review.** Beat 8 needs only the Scheduled Risk Agent and the time control, and keeping these in a single-day sprint was what forced feature work into D10. Sits between B6 and B7 rather than renumbering sixteen rows. |
| **B7** | Gazetteer density beyond the demo zone | S10 | Gates geographic expansion. Manual work that does not compress — start it as background early. |
| **B8** | Trips model and on-device hot-word detection | S18 | Prerequisite for B10. `sos_hot_words` rows are written and read by nothing until this lands. |
| **B9** | Admin observability — fleet health at a glance | S21 | Once eight agents run on schedules, you cannot operate them without this. |
| **B10** | **Journey Guardian** — anomaly detection, then graded escalation | S22, S23 | Deferred by the concept document itself. **Its two-week self-trial should start as a background activity as soon as B8 lands** — no sprint can contain it. |
| **B11** | Chronic Risk Agent — newspaper archive mining at scale | S24 | The chronic *layer* already exists from D02's police-statistics model; this is what makes it real. |
| **B12** | Legacy surface retirement and the ৳/day cost model | S25 | Needs a full agent fleet to measure. |
| **B13** | Crowd verification — asynchronous, rate-limited | S29 | An abuse surface. The async version is the defensible one; do not rush it. |
| **B14** | Privacy and retention enforcement — expired data verifiably gone | S30 | The concept document commits to data minimisation. This is where the commitment becomes testable. |
| **B15** | Agent resilience and chaos testing | S31 | Eight agents, each able to fail without breaking the others — the concept document's §5 claim, verified. |
| **B16** | Observability and cost controls, success metrics live | S32 | The concept document §10 metrics, instrumented. |
| **B17** | Load testing — the ceiling, with numbers | S33 | |
| **B18** | Offline capability and battery | S34 | |
| **B19** | Performance and accessibility budgets | S35 | |
| **B20** | Full `bn` localisation and SMS fallback for SOS | S36 | A Bangla-first product with an English-only UI is a gap worth closing before a pilot. |
| **B21** | Store readiness — signed builds, both platforms | S37 | Also where the **NirapodPoint → Meridian rename** must finally complete: `frontend/ios/NirapodPoint.xcodeproj` and `com.nirapodpoint.app` are still the native identifiers. |
| **B22** | Pilot preparation, pilot launch, operate and expand | S38–S40+ | The original plan's Phase 7, unchanged. |

**B0 is not optional and is not last.** It is listed first because it is outstanding owner action on
a live security incident, and because deferring it has already cost more than doing it would have.

---

# 7. Open decisions

Two, and the first one blocks a demo sprint.

**7.1 — The reasoning layer for image analysis. Blocks D07. Needs a decision by 17 October.**

`PROGRESS.md` records this as deliberately deferred pending an Arafat–Nakib conversation: local-only,
local plus Claude vision, or Claude-only. Defect 30 cannot be closed without choosing, because the
vocabulary gap *is* the decision.

*Recommendation: **local detection plus Claude vision as the reasoning layer.*** YOLOv9c keeps doing
what it is good at — fast, free, local object and person detection — and its detections plus the
image go to Claude for the classification judgment. This closes the 11-signal vocabulary gap
immediately without training anything or swapping detectors, which is the only option that fits
inside two days. Costs an API call per analysis, and the key is already configured.

**7.2 — Police routing. Decide in D10.**

Either seed real thana contacts for the demo zone, or leave `POLICE_ROUTING_ENABLED=false` and be
ready to say why. Do not demo it against 606 rows of `noorlabib@iut-dhaka.edu`.

---

# 8. What will actually go wrong

Stated now so they are recognised rather than discovered.

| Risk | Why it is likely | Mitigation |
|---|---|---|
| **The schedule slips.** ~140 checkboxes in 17 days with zero slack. | The one-sprint-per-week estimate in the long plan was not arbitrary. The bet is that coding agents change it, and that bet is untested. | **D10 holds no feature work**, so it absorbs overflow. Plus the cut-don't-extend rule and **cut depth, never the screen** (§3). |
| **The UI slice gets deferred "just this once."** | It is always the fastest thing to drop at 1 a.m., and the cost is invisible until the 23rd. | §0 makes the walkthrough a gate. A sprint with no walkthrough has not ended. This is the rule the whole plan rests on. |
| **A sprint silently breaks an earlier one.** | Nine sprints touching one app in 17 days. The D01 draft of this plan dropped `public.users` while `sos.py` still wrote to it — beat 9 would have died on 8 October and surfaced on the 23rd. **This has now actually happened once:** D04 found that SOS had been 401ing on any session older than an hour since D01, undetected because `D01.md` is always run just after signing in. | §3's second gate: **every previous walkthrough still passes before you hand over.** That is the regression suite — and note it was not enough here. A walkthrough re-run reproduces the *steps*, not the *state*; this bug needed a stale session. **When re-running D01, sign in at least an hour beforehand, or sign in on the previous day.** |
| **Live ingestion is unreliable on the day.** Scrapers break, sites block, networks fail. | Beat 1 depends on D04 working at a specific minute in a specific room. | D02's fixture plus D04's replayable cache. D04's gate requires a successful run **with the network off**. |
| **The gazetteer and the OSRM graph are long poles.** Manual and slow, neither compressible by an agent. | The concept document names the gazetteer the primary technical risk; the OSRM graph is a multi-gigabyte download plus preprocessing. | Both are §9 background work, started **now**, off the baton, during D01–D02. |
| **Bangla output is subtly wrong, or renders as boxes.** | Formal legal Bangla is not validatable by eye the night before, and PDF base fonts have no Bengali glyphs. | Native-speaker sign-off is a D08 *gate*. The font is an explicit D08 task. Arrange the reviewer in §9. |
| **D07 overruns.** Three defects in a stack whose pose path has never executed. | There is no prior run to regress against. | Take §7.1 by the 17th. If D07 slips, cut beat 6 to "report and persist" and drop the classifier claim. |
| **A judge asks about something the demo quietly avoids.** | Honest answers exist for every gap, but only if prepared. | D10's cut list and Q&A numbers. "Measured, scheduled, here is the figure" beats improvisation. |

---

# 9. Start now, off the baton

Four things can start today without holding the trunk, per plan §3.6. **Three of them are on the
critical path and none can be accelerated by a coding agent later.**

1. **The gazetteer — D03.** 150 Dhaka-central landmarks, Bangla and romanised, with coordinates.
   Pure data entry. Whoever is not holding the baton should be doing this.
2. **The OSRM graph — D06.** Download the Bangladesh OSM extract and run `osrm-extract` /
   `osrm-partition` / `osrm-customize` into `osrm-data/`. The compose service is already written and
   waiting for the file. Multi-gigabyte download, long preprocessing, no code, no baton — and D06
   assumes it is done.
3. **The eval set — D07.** 30–40 images. Currently 2.
4. **Line up a native Bangla speaker for D08**, for the 20th or 21st. It is a gate on that sprint and
   it depends on someone else's calendar.

Items 1–3 are data files only. Item 4 is a conversation. None of them touch code.
