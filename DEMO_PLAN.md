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
| **D05** | Oct 15 | Unconfirmed flags look different. Tap one: the sources listed. Watch a promotion happen. — **✅ closed Oct 8** | S15 |
| **D06** | Oct 16–17 | Ask for a route through a flagged corridor. Get alternatives, each with a plain-English reason. — **✅ closed Oct 9** | S12, S13, S05, S07 |
| **D07** | Oct 18–19 | Photograph a two-person scene. Get a real interaction read. See the evidence photo stored. | S06 |
| **D08** | Oct 20–21 | Turn a report into a **Bangla General Diary** draft. Correct thana. Cannot submit unapproved. | S27, S28 |
| **D09** | Oct 22 | Move the map to **tomorrow** — a procession already flagged. SOS history screen. The headlines behind the map, as cards. — **✅ closed Oct 10** | S26, S05, S07 |
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
| 7 | Generate the **Bangla General Diary** from that report. Correct thana. Human review gate that cannot be bypassed. Then show both exits — print the DMP form, or copy the narrative into the police's own app. **We draft; a person files.** | D08 | `D08` |
| 8 | Show **tomorrow's** map: an announced procession already flagged, before it happens — and the announcement itself, as a card on the news page. | D09 | `D09` |
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
>
> ⚠️ **Both reasons expired, and the blocker is now cleared (2026-10-15).** `endpoints/voice.py`
> was **deleted in B8**, so that importer is gone. And the remaining one never held the table up:
> no FK anywhere points at `public.users` — `gd_drafts` was the last and migration
> `20261010160000` repointed it at `auth.users` — so `sos.py` writing rows into it was a *habit*,
> not a dependency. What it was actually supplying was the **display name for the alert email**,
> and it supplied `email.split("@")[0]`. ✅ **Defect 9 fixed the same day:** the name comes from
> `profiles.name`, and the model is deleted — which also matters because `init_db()`'s
> `create_all` runs on **every API boot** and would otherwise have recreated the table after any
> drop. ✅ **The table was dropped the same day** (migration `20261015160000`) and **stayed
> dropped across an API restart**, which is the proof that mattered.

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
      `.env`, so §7.1's then-claim that "the key is already configured" was wrong — one of the two
      reasons that recommendation was retired on 9 October. The LLM tier runs on the
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

### Addendum, 14 Oct — nine publishers, and crime that names its source

D04 shipped reading **three** sources, and all three were television channels. That is not a
neutral fact about breadth: `confirmed` requires two or more *independent* publishers, and TV
newsrooms in Dhaka follow each other and run the same agency copy. A dry run on 14 Oct found
**0 relevant articles across all three** in one window. Beat 2's *"three independent sources"*
was a fixture promise the live pipeline was unlikely to keep.

- [x] **Six publishers added** — Prothom Alo, Jugantor, Bangla Tribune, Ittefaq, Samakal and
      Dhaka Tribune. The same dry run after: **2766 articles listed, 83 relevant**, and a
      Tongi factory fire carried by four of them in one pass. That is beat 2 becoming
      reachable from live data rather than from the fixture.
- [x] **English is now read as well as Bangla**, which also *improves* geolocation rather than
      straining it: at S30 that was 1010 of the 1022 gazetteer entries (98.8%) carrying a
      `name_en` against 816 (79.8%) with a `name_bn`. **B7 widened the gap and so strengthened
      the argument:** of 6,054 entries, **5,858 (96.8%) carry a `name_en` and only 2,535
      (41.9%) a `name_bn`**, because OpenStreetMap tags most Dhaka roads in English alone.
      Reading English is now the difference between finding a road and not.
- [x] **The extraction queue is round-robin.** Concatenating nine publishers and cutting to
      the free-tier budget meant the first filled it every run, so a second outlet's account
      of the same event was never extracted in the same pass — and **no flag could ever reach
      `confirmed`**. Worth knowing before demonstrating beat 2.
- [x] **Dhaka Tribune and Bangla Tribune are one house** and are recorded in `_SAME_OWNER` so
      they do not corroborate each other. If asked how independence is judged, that is the
      honest answer: distinct owners where we know them, distinct publishers otherwise, and
      the gap is written down.
- [x] **A third surface: news-sourced crime, as attributed citations.** On the owner's
      decision. *"Robbery reported by Prothom Alo, 2 days ago"* — never *"there was a
      robbery"* and never *"this area is dangerous"*. `app/policy/attribution.py` is the only
      writer and the database refuses any statement without `' reported by '` in it.
      A fourth marker shape (diamond) so it cannot be confused with a flag, a cluster or the
      user's own report.
- [x] **`S30_APPLY_IN_SUPABASE.sql` has been run** — applied and verified in Supabase on
      14 Oct. The crime half can write.
- [x] ~~**The crime layer will probably be empty on stage.**~~ **Closed by B7, 14 Oct.** The
      reason this row gave was that the first live run extracted two crimes and geocoded
      neither, because `Satmasjid Road` was not in the gazetteer in either script. **It is
      now** — the harvest had never asked OpenStreetMap for a single road, and B7 added 3,241
      of them, `Satmasjid Road` among them at a measured 1,154 m radius. The ingestion beat
      runs `live_risk` every 15 minutes, so the layer accumulates on its own.
- [ ] ⚠️ **It can still be thin, for a smaller and different reason.** The gazetteer now sets
      a far higher ceiling than it did, but what is *published* still depends on what the nine
      publishers actually report in the window before the demo. Check the layer on the day
      rather than assuming it. *"We discard a location we cannot resolve rather than guess
      it"* remains the right thing to say about the ones that are still refused — and B7 made
      that answer sharper, not weaker: a long arterial like `Mirpur Road` is **deliberately**
      refused because a pin at the midpoint of 8 km of road would be wrong by kilometres.

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

- [x] `sentence-transformers` semantic deduplication across sources, so four outlets reporting one
      fire collapse into one event rather than four corroborations *(S15)* — `app/agents/rumour_guard.py`.
      Four gates, all required: same `kind`, overlapping radii (capped at 3 km), `observed_at` within
      `DEDUP_WINDOW_HOURS`, then cosine similarity. The first three are SQL and nearly free, so the
      embedding only ever runs on the handful of rows they let through. **No pgvector and no embedding
      column** — candidate summaries are re-embedded at comparison time, which is affordable precisely
      because the cheap gates run first
- [x] Multi-source threshold promotes to `confirmed`; below it, `unconfirmed` at reduced weight *(S15)* —
      `app/policy/independence.py`. Weight is **0.6**, exposed as `RiskFlag.confidence` and derived by
      the surfaces exactly as `severity_now` is. ⚠️ **`severity_now` is deliberately not damped by it:**
      that value is the decay story the sheet narrates ("74 when observed, 31 now, 42% remaining") and
      multiplying it would make that arithmetic wrong. Decisions want
      `decay.effective_severity(severity_now, confidence)` — **D06 must use it, or the tier is decoration**
- [x] **The invariant test from D01 now runs against real data**, not a stub *(S15)* — a fourth layer in
      `test_single_source_never_confirmed.py`: the promotion arithmetic, a check that `status` and
      `source_count` are written in one statement (the CHECK compares them), an AST-ish scan asserting
      **only** `rumour_guard.py` may write `status='confirmed'`, and an `integration` test that counts
      *distinct publishers* in every confirmed row in the live database rather than trusting
      `source_count` to agree with itself
- [x] Promotion path: `unconfirmed` → `confirmed` on a second independent source *(S15)* — one
      `SourceRef` per publisher, so `source_count == len(sources) == independent publishers` and all
      three `risk_flags` constraints stay true of live data for the same reason they are true of the
      fixture. **A same-outlet follow-up does not inflate corroboration**; it is still kept in full in
      `extracted_incidents`. `confirmed_at` is stamped once, on the transition
- [x] 📱 **Confirmed vs unconfirmed rendered differently on the map** — not just a field in a sheet.
      The tiering is an ethical commitment; it should be legible at a glance — new
      `components/RiskFlagMarker.tsx`: **solid filled dot with the source count** vs **hollow dashed
      ring with a `?`**, and the radius circle carries the same split (solid/stronger vs dashed/fainter).
      Two channels for one distinction, because colour is already spent on severity
- [x] 📱 **Source count badge** on the pin, source list and confirmation time in the sheet *(S15)* —
      the count is *on* the pin. The sheet gained a **Confirmed** row (rendering `time not recorded`
      rather than substituting `observed_at`) and a footnote stating the consequence: shown and counted
      at 60%, never hidden. The badge no longer hard-codes "1 source" — D05 makes
      *unconfirmed with 2 sources* a real state
- [x] 📱 A **scripted replay** that performs the promotion on demand, for the stage —
      `python -m app.agents promote-demo`, with `--dry-run` and `--reset` so it is rehearsable. It runs
      **through `rumour_guard.merge_into()`**, the production path; the injected source is
      `demo_second_source` at `meridian.invalid`, labelled so it cannot be mistaken for an outlet
- [x] 📄 `docs/walkthroughs/D05.md` — **all 11 steps passed on a real device, first run, no issues
      found (Arafat, 2026-10-08), including the promotion and the reset. D05 is closed.** Notably the
      device run found nothing the backend verification had missed — worth recording, because D04's
      run found three defects and the contrast is the useful signal
- [x] **Previous walkthroughs re-checked for breakage (§3's second gate).** D05 replaced the map
      marker, which falsified a statement in `D01.md`'s *Rough edges* — it listed "no distinction
      between confirmed and unconfirmed" as a rough edge **scheduled for D05**, so D05 delivering it
      made that text wrong. `D01.md` steps 6 and 8 and that bullet are corrected, and `D04.md`'s
      *Finding the news flag* now notes that shape narrows the search without solving it
- [x] **Deviation from this plan's own §9, and it is the finding of the sprint:**
      `DEDUP_SIMILARITY_THRESHOLD=0.82` was declared before anything measured it. Measured on
      `all-MiniLM-L6-v2` against the text this system actually embeds — the extraction model's one-line
      English summaries — **0.82 merges 1 of 18 known duplicate pairs.** D05 would have shipped as a
      no-op that looked implemented: four outlets would still have produced four unconfirmed pins, and
      nothing in a green test suite would have said so. Now **0.72**, the highest threshold with zero
      false merges on the labelled set. `scripts/eval_dedup.py` + `data/eval/dedup/clusters.json` are
      the harness S15 asked for, so the number is reproducible and re-tunable
- [x] **Also found, and it constrains what can be claimed:** the classes are **not separable**. Lowest
      true duplicate 0.503, highest false pair 0.718 — and the second account of the real Mohakhali fire
      scores **0.718**, identical to the worst false pair. No threshold divides them, because "two
      reports of one fire in Bangshal" and "two fires in Bangshal hours apart" read the same in one
      line. **Recall is ~56% by choice**, precision 100% on the labelled set, and that asymmetry is why
      the scripted replay exists rather than hoping two outlets phrase a fire alike mid-demo. A test
      asserts the near-miss so a future improvement gets recorded instead of silently absorbed

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

- [x] **Local OSRM** — honour `OSRM_BASE_URL`, stop using the public demo server — **defect 7**
      *(S05, S04)* — new `app/routing/osrm.py`. The graph was built in §9 and the service now
      reads the setting. **The fallback to the demo server is deliberately loud**: it logs on
      every request and `RouteResponse.engine` carries `local` / `public-demo` /
      `straight-line`, so a degraded answer is visible on the card rather than only in a log.
      D10's failure drills exercise that path
- [x] Use OSRM's own durations instead of a flat 30 km/h, and add the walking profile —
      **defect 7** *(S05)*. Measured: Bangshal→Mirpur-10 is **14 min** from the road graph
      against **25 min** under the old assumption. ⚠️ **The walking profile is honest, not
      finished** — OSRM answers `/foot/` from whatever graph it has, and ours is `car.lua`, so
      it returned *7.03 km in 9 minutes*. 47 km/h presented as a walk is a false statement on
      a screen, so the duration is recomputed at 4.8 km/h and the path caveat is shown to the
      user. A second `foot.lua` graph is the real fix and is not demo-critical
- [x] `_calculate_path_risk` becomes a **PostGIS spatial query** against `risk_flags`, instead
      of all-rows-then-a-Python-loop — **defect 8** *(S05)*. What it replaced was
      `select(CrimeReport)` with **no spatial predicate at all** — every row in the table, then
      a nested loop over every path point. Now one `ST_DWithin` against an `ST_MakeLine` of the
      route, on `geography` so the radius is metres
- [x] Route scoring through the `RiskSurface` protocol, so seeded and live both work *(S12)* —
      **and S12's "fix the contract now" clause was needed.** The protocol gained
      `flags_near_path`, implemented by both surfaces. Scoring against `flags_in_bbox` would
      have worked and been quietly wrong: a 12 km route's bounding box covers most of Dhaka, so
      it would score against flags kilometres from any road on it. The corridor is the
      question, so the corridor is the query. `app/scoring/geometry.py` holds the shared
      point-to-segment maths, because the two surfaces must agree
- [x] ⚠️ **Delete `route_service._get_regional_risk()`** — done, and the reasoning is recorded
      in the module docstring now the code is gone. D02 moved the same police statistics into
      the surface as chronic flags, so applying them here again was a double count; it also
      took `max()` across overlapping units including the ranges that contain them, so every
      point in Dhaka scored **100.0 from `Dhaka Range`** rather than 58.9 from `DMP`
- [x] Honour `avoid_high_crime_zones` and `max_crime_score`, accepted and silently ignored
      today — **defect 6** *(S05)*. Both honoured, with one decision written down: **a filter
      that would reject every route is relaxed, not applied** — everything is returned
      best-first with `filter_relaxed: true`, because answering "no acceptable route" to
      someone asking how to get home is the worst available answer. Verified both directions
- [x] **One score scale: 0–100, higher means safer, named `safety_score`** — **defect 11**
      *(S07)*. `RouteSegment.crime_score` (0–10, and really just the route score repeated per
      point) is deleted, and the card renders `71/100` rather than `70.6% Safe`. A test asserts
      the response carries exactly one risk scale, so a second cannot come back quietly
- [x] **Explanation generation through `app/policy/framing.py`** — mobility framing only
      *(S13)* — new `app/routing/explain.py`. Assembles from each flag's `mobility_statement`
      plus the source count; **no LLM in the request path** (templates, instant, reviewable);
      and the guard runs on the **finished** string, because concatenation is where a banned
      term could be assembled from individually safe parts. `MAX_EXPLANATION_LENGTH` is
      separate from `framing.MAX_STATEMENT_LENGTH` and says why
- [x] Nominatim through a backend proxy with a real `User-Agent` and a Redis cache —
      **defect 10** *(S05, S07)* — `app/geo/nominatim.py` plus `GET /geo/search` and
      `GET /geo/reverse`. **All five direct `nominatim.openstreetmap.org` calls are gone from
      the app.** Cache measured at **471 ms cold → 52 ms warm**, TTL 24 h. Kept deliberately
      separate from `/geo/resolve`: that path is allowed to refuse, and D03 found the hard way
      that a tier which answers everything will overturn a deliberate refusal if they share a
      code path
- [x] 📱 **Route comparison card** — alternatives ranked, each with `safety_score`, duration,
      and the trade-off stated *(S12)* — new `components/RouteComparisonCard.tsx`, replacing
      ~45 lines of inline JSX whose "description" was a three-way ternary on the list index
- [x] 📱 **The explanation on screen, attached to the route**, not in a log. Beat 4 *(S13)*
- [x] 📱 Flagged corridors visibly highlighted along the rejected route *(S13)* — two styles:
      solid for flags on the route you are viewing, **dashed and faint** for flags only the
      other route passes. Switching tabs swaps them, which is what makes the comparison read
      without narration
- [x] 📄 `docs/walkthroughs/D06.md` — **steps 1–11 passed on a real device (Arafat,
      2026-10-09); the run found three things, all fixed, and the walkthrough now has 13
      steps. D06 is closed.**
- [x] **Found by running it — (a) the walking profile had no UI control.** Step 12 read
      *"switch the profile to walking, **if the UI exposes it**"* and it did not: D06 shipped
      the backend profile and no screen for it. That is §3's *"cut depth, never the screen"*
      failure, committed by the sprint that quotes the rule. A **Driving / Walking toggle** is
      now in the plan card and re-requests on tap, because a mode switch needing a second tap
      reads as broken
- [x] **(b) `14 min` for `12.6 km` was not believable, and the reader was right to stop at
      it.** That is **54.8 km/h across central Dhaka** — median segment speed 56 km/h, max
      106. **OSRM is not wrong**: `car.lua` speeds come from `maxspeed` tags and road-class
      defaults, and an OSM extract contains no traffic data at all, so **this cannot be fixed
      "from the road graph"** however it is rebuilt. The proper fix is
      `osrm-customize --segment-speed-file` and needs a traffic source this project lacks —
      Track B. D06 ships `ROUTE_CONGESTION_FACTOR = 0.35`, which brings that route to **39
      min, ~19 km/h**, preserves relative differences between roads so the ranking stays
      meaningful, and is labelled `in traffic (est.)` on the card. A test asserts it cannot
      reorder routes. ⚠️ **It is a calibration from one reading, not a measurement**
- [x] **(c) A single route rendered as one tab with no comment**, which reads like the
      alternatives failed to load rather than like an answer. The card now says *"Only one
      sensible route exists between these points, so there is nothing to compare"* — true
      when the road network offers one way through and nothing on it was worth a detour
- [x] **Not planned, and it is the finding of the sprint: the chronic layer had to be
      down-weighted.** Scored at full weight, a 12.6 km Dhaka crossing passing three chronic
      flags scored **16.7/100** — every route in the city scored about the same,
      `max_crime_score` therefore rejected all of them so defect 6's filter was meaningless,
      and the ranking reflected *historical coverage* rather than today's events. That is
      exactly the **"stale red zones"** failure demo beat 5 exists to disclaim and concept
      document §9 commits against. `ROUTE_CHRONIC_WEIGHT=0.35` brings the same route to
      **68.6** and lets a live event move the number
- [x] **Also found: OSRM will not reliably give alternatives, so beat 4 cannot depend on it.**
      Across five Dhaka pairs, three returned two routes and two returned one. So D06 generates
      a flag-avoiding detour itself (`app/routing/alternatives.py`): a waypoint pushed
      perpendicular to the route, clear of the flag's radius plus the corridor. **Chronic flags
      are not detour targets** — they cover most of Dhaka, so "avoiding" one means avoiding the
      city — and the candidate is **discarded unless it actually clears the flag**, because
      OSRM snaps a waypoint to the nearest road and that is sometimes the road we were leaving
- [x] **Three bugs the new tests caught, all of which read as working code:**

      **(a) `SeededRiskSurface.flags_near_path` raised on every call.** `zip(x, x[1:],
      strict=True)` — offset slices always differ by one, so `strict=True` is always a
      `ValueError`. The same pattern was in `alternatives._clears`. **That is the offline demo
      path**, so D10's failure drill would have died on it.

      **(b) The detour generator could not handle a flag *on* the route** — the commonest case
      there is. It pushed away from the flag *towards the nearest path vertex*, so a flag on a
      vertex gave zero distance and no waypoint at all. Now perpendicular to the route's
      heading, which always exists, with both sides tried.

      **(c) An alternative was claiming to avoid flags while being strictly worse.** Option 2
      of the Dhanmondi→Gulshan pair is 2 minutes slower and passes five flags to the
      recommended route's three — and it does avoid two, so the literal count was 2. Printing
      that alone is true and misleading. An alternative may now claim "avoids N" **only when
      it is actually safer**
- [x] **The framing invariant was strengthened rather than excluded.** `RouteFlag` and
      `route_service` legitimately *forward* `mobility_statement`, which tripped
      `test_only_framing_writes_mobility_statement`. Adding them to `ALLOWED_WRITERS` is the
      designed mechanism — but an allowlist entry could silently become a *composing* one, so a
      new check verifies every forwarding module assigns only an attribute, name or subscript.
      Validated against four construction forms; it immediately caught that `row[...]` is a
      read, which forced the definition of "forward" to be stated rather than assumed

### Addendum, 13 Oct — the route now follows you

D06 answered *"which route should I take, and why"*. It stopped at the moment the user starts
walking: the line was drawn once and never moved again, so the screen that mattered most — the
one you look at while actually on the road — was the least alive in the app.

Built after D06 closed, on the owner's request, in `frontend/src/features/navigation/`:

- [x] **The route trims as you move.** The travelled stretch goes faint, the remaining stretch
      stays full strength, and a snapped dot sits on the line beside the platform's own raw fix
      — when the two separate, that gap *is* the GPS error, made visible rather than hidden
- [x] **Turn-by-turn with real road names.** `steps=true` on the OSRM request, carried through
      `OsrmStep` → `RouteStep` → the banner. The honest half is the fallback: OSM has no `name`
      tag for a large share of Dhaka's lanes, so the phrasing degrades named manoeuvre →
      unnamed manoeuvre → pure geometry, and **never says "onto" with nothing after it**.
      ⚠️ Step names deliberately do **not** pass through `policy/framing.py` — that guard bans
      `jatiya`, `awami` and `political`, which appear in ordinary Dhaka road names. A road's
      name is a fact published by OSM, not this product's claim about a place, and running it
      through a guard built for a different purpose would silently drop real street names
- [x] **An ETA from measured speed, not from the road map.** Smoothed, with Android's `null`
      and negative speed sentinels discarded rather than averaged in, falling back to the
      route's own pace below 0.5 m/s — `remaining ÷ 0` is infinity, and a naive live-speed ETA
      reads nonsense at every traffic light. Both route notes now say where the number comes
      from, because *"not a measured walking duration"* had stopped being true on the one
      screen where it mattered
- [x] **Automatic re-routing**, after ~14 s of sustained off-route and no more than once every
      25 s. ⚠️ **Recorded as an owner decision over a recommendation**: the argument against is
      that the route being followed was *chosen*, from a comparison that explained what it
      avoids, and replacing it silently discards the only thing separating this from a maps
      app — at the moment the user can least afford to look at the screen. The delay and the
      cooldown carry that argument instead of a refusal, and the manual button stays
- [x] **Two failures that are invisible in a straight-line test**, both pinned by the 71 tests
      in `progress.test.ts`. **Teleporting:** the obvious "closest point on the whole polyline"
      breaks the moment a route comes near itself — an out-and-back, a loop round a block, a
      flyover — so one sideways wobble puts you kilometres ahead and the app says you have
      nearly arrived. The search is windowed to ±400 m **measured along the route**, not in
      vertices, because OSRM vertex density varies from 5 m to 600 m. **The line growing back:**
      jitter made progress decrease and the route twitched while standing still; progress is
      monotonic, and a real reversal reads as off-route rather than as a redraw
- [ ] ⚠️ **Not verified on a device by the author.** The owner ran it on an iPhone through Expo
      Go and it works; nothing here has been walked by whoever wrote it. Two constants are
      expected to need tuning against a real walk: `SPEED_SMOOTHING` and `AUTO_REROUTE_AFTER_MS`
- [ ] ⚠️ **`backend/tests/invariants/test_turn_by_turn.py` is written and has never run** — the
      backend's dependencies are not installed on the Windows host. Run it in the container

#### And the thing this surfaced: D06 had never used the local routing engine

A route card read *"Routed by a public demo server — the local routing engine did not answer."*
True, and it had been true for days. The `osrm` service sits behind a compose profile and
`scripts/run.ps1` only passed `--profile osrm` when asked, so **every route since the graph was
built came from `router.project-osrm.org`** — rate-limited, over the internet, and with **no
detour alternatives possible at all**, because `fetch_routes_via` deliberately has no demo
fallback. D06's own beat-4 comparison could not have appeared.

`run.ps1` and `run.sh` now start it whenever its graph is on disk (testing `.osrm.cell_metrics`,
which `osrm-customize` writes last, so a half-finished build does not start a crash-looping
container), and the run prints which engine actually answered. The fallback was always loud in
the logs; it is now loud where someone starting the stack will see it.

---

## D07 — Crime detection from an image, for real
**Oct 18–19 · source: S06 · decided by [ADR 0006](docs/adr/0006-d07-vision-pipeline.md)**

**Showable:** photograph a staged scene in the report flow. In about three seconds the card says
**what is visible** — cues, people count, one plain sentence — and **proposes** a category the
reporter confirms or overrides. The card names **which engine answered**. The photo is **stored** and
visible in the report detail screen afterwards.

**Gate:** `docs/walkthroughs/D07.md` passes on a device, and `eval_crime_vision.py` reports the three
new numbers — **false-accusation rate**, abstention rate, description faithfulness — over **≥30
images**, committed as the baseline. D01–D06 still pass.

> **The gate is that the number exists and can be said out loud, not that it clears a bar.** A
> threshold invented on the 9th is a threshold defended on the 24th. What must be true is that a
> judge asking *"how often is it wrong about a crime?"* gets a measured figure.

> **§7.1 is resolved — [ADR 0006](docs/adr/0006-d07-vision-pipeline.md), accepted 2026-10-09.** The
> model reports **cues**; our code maps cues to a candidate category; **the reporter confirms, so the
> filed category is always human.** Measured that day: Gemini Flash Lite **≈2.0s**; local
> `qwen3-vl:4b-instruct-q4_K_M` **≈8–9s on a photo it has not seen**, identical cue answers.
>
> ⚠️ **The local tier's original 2.61s was an Ollama prompt-cache hit** — the same image called
> repeatedly. Re-measured over six distinct images it is **≈8.2s**, of which **4.8s is
> vision-encoder prefill that does not shrink when you shrink the image** (tested 1024 / 768 / 512 /
> 384px — the prompt stays ~1,150 tokens at every size). This does not change the decision; it makes
> **replay matter more**, because the rehearsed photos are exactly the ones that must not cost nine
> seconds on stage. See ADR 0006, *Correction*.
>
> **Most of this sprint is subtraction.** Defects 29 and 5 close by **deleting** the pose stack, not
> porting it: 33 landmark coordinates do not describe a crime, and the path has never once executed.
> Defect 30 closes because a VLM has no fixed vocabulary to be short of.
>
> ✅ **First detection evidence, 10 October.** Four staged positives tested: **4 of 4 detected with
> the correct category, 0 false accusations** on the benign pair. Getting there needed a fix — the
> original five cues caught only one of the four, and **the models were not at fault.** They
> described a car fuel cap being forced, goods going into a bag, and two people pulling one bag,
> all accurately; no cue covered any of them. That is the **same vocabulary gap this sprint was
> written to close**, reproduced at smaller scale in our own question list. Now seven cues, and
> only `fraud` is beyond a photograph.
>
> ⚠️ Six images is still a small set, and all four positives are **staged stock photos** (watermarked
> previews — eval use only, not publishable), not real Dhaka street scenes.

**The seam first — three gaps that each failed silently** *(done)*

- [x] **`replay` spelled `replay:crime_vision_replay.json`.** `chain()` in `app/llm/client.py` drops
      any entry without a colon with a warning, so a bare `replay` parsed as malformed and **the
      tier silently would not have existed.** `replay` is now a `PROVIDERS` row with a fixture
      branch inside `complete()`, so chain-walking stays in one place as ADR 0006 assumes
- [x] **`Provider.key_prefix` is now `str | None`.** It was a non-optional `str`, and `keys_for()`
      builds `f"{key_prefix}{feature}_"` — so Ollama, which needs no key, found none and logged *"no
      key is set — skipping"*. **The local tier would have dropped out and the demo would have
      quietly run cloud-only.** A keyless provider now yields one sentinel
- [x] **`complete()` can send an image** — optional `image_data_url` switches the user turn to a
      parts list, and `complete_with_engine()` returns *which tier answered*. **Verified on both
      providers:** `response_format: json_schema`, `strict: true` plus an `image_url` part is
      honoured exactly by Flash Lite *and* Ollama, every run, **no fallback branch needed**. It is
      the *looser* `json_object` that fails on Ollama — 48 tokens, required fields missing,
      `scene: "football stadium"` where the enum allows four. **Strict schema is required, not
      preferred**
- [x] **`OLLAMA_BASE_URL` is `127.0.0.1` by default and `host.docker.internal` in compose.** A fresh
      connection per call to `localhost` on Windows cost a flat **2.3s** per request, independent of
      payload size — IPv6 resolution against an IPv4-bound service. Set in compose's `environment:`
      rather than `.env`, the same reason Redis is: one value stays correct both inside and outside
      the container
- [x] `FEATURE_CRIME` in `KNOWN_FEATURES`, `LLM_CHAIN_CRIME` in `app/core/config.py`, and
      **`GEMINI_KEY_CRIME_ONE`** on its own account — free quota is per project, and the 2026-10-09
      probe spent D04's `EXTRACT` quota, which is exactly what the per-feature split exists to
      prevent. *Named `CRIME`, not ADR 0006's `VISION`, to match the key.* ⚠️ `--force-recreate`,
      not `restart`: compose reads `.env` at create time

**The pipeline** *(done)*

- [x] `CrimeCues` and the cue prompt — seven cues each `yes` / `no` / `unclear`, plus
      `people_count`, `scene`, and one sentence capped at 200 characters. **Grouped fine-grained
      cues, not crime names**: ASK-HINT measures over **20 AUC points** from that choice alone, same
      model, no training. The cue fields are declared *before* `description` so the model commits to
      each answer before writing prose that could talk it into a different one
- [x] **The cue → category mapping, in our code** — `app/vision/mapping.py`. **Only a definite
      `yes` proposes anything**; `unclear` never does. Three of the eight categories are **not
      proposable from a photo** and say why: theft (over before the photo exists), fraud (a document,
      not a scene), robbery (theft plus force — the force is visible, the theft is not, so we propose
      `assault`, the part that can be seen). Verified across 9 cue combinations
- [x] Cross-check against the report **text** — agrees / disagrees / silent, English and Bangla.
      `silent` is its own value because most reports will not mention it, and silence is not
      disagreement. It never changes the proposal: two independent accounts, and collapsing them
      would hide the one case worth seeing
- [x] **Confidence is three bands, not a number.** `strong` means two independent cues agree,
      `weak` means one. The old card printed figures like `0.73` from weights nobody had validated,
      and *"what does 73% mean?"* is a fair question with no answer
- [x] **Defect 30 — `/ai/crime-detection/analyze` rewired.** Dropped `include_pose_analysis`,
      `include_scene_analysis`, `use_ml_fusion`, `confidence_threshold` and the `model_loaded` 503.
      Now requires auth (401 without a token) and returns `engine`. `/crime-detection/status` reports
      which tiers are configured; `/supported-crimes` reports 5 proposable and 3 not, with reasons.
      **`crime_ai.py`, the unregistered duplicate, is deleted rather than left as a trap**
- [x] **The replay tier** — `python -m app.agents export-vision-replay` →
      `data/fixtures/crime_vision_replay.json`, keyed by a content hash of the *prepared* bytes.
      Stores the **model's own fields only**; the category is re-derived at read time, so changing
      our rules needs no recapture. Capture runs with the replay tier filtered out of its own chain,
      or every later capture would re-freeze a stale answer. **Measured: 0.58s with the cloud dead**
- [x] **`engine: gemini | replay | ollama` on the response**, and stored on the report in
      `vision_analysis`. D06's loud fallback, D05's *"say what it is"*. ⚠️ **The card's badge
      shows *live* and *on this device* but is hidden for `replay`** — owner's decision,
      10 October. Because the badge still appears in the other two cases, its absence on a
      rehearsed photo reads as live. The stored answers are real model outputs and `engine`
      is still recorded; it is only off the screen. See ADR 0006, *The replay tier*

**Defect 13 — the evidence photo** *(done)*. There was **no storage write anywhere in this repo**:
`S3_BUCKET_NAME` / `S3_VIDEO_BUCKET` were settings with no code behind them, and `sos_service.py`
records a deliberate decision *not* to retain the SOS clip to avoid needing a bucket. D08 needs
these photos as GD attachments.

- [x] `migrations/versions/20261009120000__report_evidence_photo.sql` — `evidence_photo_path` and
      `vision_analysis` on `crime_reports`, which had **no image column at all**, plus a partial
      index for D08's lookup. Applied and verified
- [x] **Private `report-evidence` bucket**, JPEG only, 10 MB cap. Reads go through
      `/ai/crime-detection/evidence-url`, which signs for an hour **and checks the path belongs to
      the caller** — the service-role key bypasses row security, so without that check any logged-in
      user could sign any path they guessed. Verified: round-trip returns identical bytes, unsigned
      URL refused, another user's path **403**
- [x] **The backend uploads, not the app.** `prepare()` resizes to ≤1024px and re-encodes, which is
      what strips EXIF — including the phone's GPS tags. Those bytes only exist server-side, so an
      app-side upload would have stored the original *with* the coordinates we deliberately did not
      ask for
- [x] **The filed category is stored alongside the proposed one.** The case where the machine was
      wrong and a human caught it is the one most worth being able to look back at
- [x] 📱 **Evidence photo on the report detail screen**, with the sentence and the engine *(S07)*

**Subtraction, and the measurement** *(done)*

- [x] **Deleted 2,658 lines across 8 files** — `crime_vision_service.py` (771),
      `crime_decision_engine.py` (755), `pose_detection_service.py` (390),
      `scene_classification_service.py` (341), `crime_ai.py` (227), `train_crime_model.py`,
      `download_models.py`, `test_crime_vision.py`. Plus **491 lines of pose/scene/fusion UI and 51
      dead styles** from `AddReportScreen.tsx`
- [x] **Dropped from `requirements/ai.txt`:** `ultralytics`, `torch`, `torchvision`, `mediapipe`,
      `transformers`, `safetensors`, `onnxruntime`, `opencv-python`, `scipy`, `pandas`. Vision needs
      nothing beyond `Pillow`, already in `base.txt`. **This is what makes the backend deployable on
      a free tier at all.** ⚠️ The image keeps them until `docker compose build api`
- [x] **YOLOv9c dropped entirely, not kept behind a flag** — a decision taken during the sprint,
      against this plan's earlier wording. The VLM already returns `people_count`, and in
      measurement both models got it exactly right (2 and 4). Keeping it meant ~700 MB of weights
      and 2 GB of dependencies for a number we already have, plus a second code path to debug
- [x] **Reachability table retired from `scripts/eval_crime_vision.py`.** "6 of 6 reachable" is
      trivially true once a VLM can name any category — a gate that cannot fail is worse than no
      gate. Replaced with **false-accusation rate** ← *the Q&A number* — plus abstention rate,
      detection rate, and the descriptions printed for a human to read. Runs with the replay tier
      **excluded**, so a rehearsed photo can never answer its own exam. Baseline committed;
      `--compare` exits non-zero on a regression
- [x] 📱 **Result card rewritten** — the sentence, all seven cues *including the `no`s* (showing only
      the hits would make an abstention look like a crash), the suggested category with its reason,
      the engine badge, and confirm / override. Auto-fill only fires when our rules proposed
      something, and never overwrites a description already typed
- [x] 📄 [`docs/walkthroughs/D07.md`](docs/walkthroughs/D07.md) — written, with everything verified
      without a device recorded in it

**Found on the device, 9–10 October, and fixed**

- [x] **The first five cues caught only one of four staged photos — and the models were right.**
      They described a car fuel cap being forced, goods going into a bag, and two people pulling
      one bag, all accurately. No cue covered any of them. Widened `forced_entry` past building
      openings and added `struggle_over_property` and `goods_concealed`; **theft and robbery became
      proposable at `weak` confidence.** 4 of 4 after the change
- [x] **The abstention nudge in the prompt was costing the local tier.** *"Use `unclear` whenever
      you are not sure"* was obeyed literally by the 4B model, which answered `unclear` to all seven
      cues on three scenes it had just described correctly. Rebalanced so each answer has a job:
      local 2 of 4 → 3 of 4, cloud unchanged, 0 false accusations either way
- [x] **A dead network cost ~70s before the offline tier was reached.** The OpenAI SDK retries
      connection errors twice by default and our chain is already the retry, so one Gemini attempt
      became three hangs — past the app's 60s limit, so the phone gave up on answers the backend
      went on to produce correctly. `max_retries=0`, and a per-provider timeout because a cloud call
      and a laptop GPU want opposite things: **cloud 15s, ollama 120s.** Measured 70s → 15s
- [x] **`scripts/run.ps1` pinned a stale LAN IP.** It read `$env:HOST_LAN_IP` before detecting, and
      wrote that same variable itself — and `$env:` persists for the whole PowerShell session, so a
      second run in the same window reused the first run's address and never looked at the network
      again. Moving from a router to a phone hotspot then left the app calling an IP that no longer
      existed while **Metro printed the correct one**, because Metro detects its own. Now detects
      first, rejects any override naming an address this machine does not hold, and says so

**Still open**

- [ ] ⚠️ **Finish the walkthrough on a device.** Steps 1–8 are done — analysis, the card, storage
      and the detail screen all ran on a real phone. Steps 9–10, the offline beats, have been
      exercised but not signed off as a clean run. Per §0 a sprint with no device run has not ended
- [ ] ⚠️ **The replay tier cannot match a photo that came through the phone.** `expo-image-picker`
      runs at `quality: 0.8` with `allowsEditing: true`, so every pick is re-encoded and croppable
      and the content hash never equals the one captured from the file on disk. Replay therefore
      serves server-side analysis only. **Left as-is deliberately** — the local tier is fast and
      correct now, so replay is belt-and-braces rather than load-bearing. The fix, if it is ever
      wanted, is to capture from the real request path instead of from disk
- [ ] ⚠️ **Grow the eval set to 30–40 images.** Now 6 — 2 benign, 4 staged positives — reading
      **0% false accusations, 100% detection, 100% correct category**. Real numbers at last, but a
      small set of watermarked stock photos: eval use only, not publishable. §9.3, and still the gate
- [ ] ⚠️ **The local tier is weaker than cloud**: 3 of 4 on the same positives, and it misread one
      outdoor scene as indoor and a bag strap as *"possibly a weapon"*. Fine as the offline
      fallback; do not describe the two tiers as equivalent on stage
- [ ] ⚠️ **Run the staged photos through the cloud tier by 17 October.** Gemini's safety filter
      **cannot be disabled** through the OpenAI-compatible endpoint, so it **may refuse** a staged
      violent photo. The knife photo has now gone through it without refusal, which is encouraging
      and not conclusive
- [ ] ⚠️ **`npx expo start` wants the network for account checks**, so the app will not start once
      the internet is off. Start Expo *before* killing it, or use `npx expo start --offline`. Worth
      a `-Offline` switch on `run.ps1` before D10
- [ ] Re-capture the replay fixture **after the final rehearsal** —
      `python -m app.agents export-vision-replay`. The four photos in it now are test images, not
      signed-off demo ones
- [ ] `docker compose build api` to actually reclaim the dropped gigabytes

---

## D08 — Casework Agent: the Bangla General Diary
**Oct 20–21 · source: S27, S28 · decided by ADR 0007**

**Showable:** open a report you filed, tap **generate GD**, and get a formal Bangla General Diary
draft naming the correct thana. Edit it. Try to approve without reading — **the app will not let
you.** Export the PDF, or copy the narrative straight into the police's own Online GD app.

**Gate:** `docs/walkthroughs/D08.md` passes on a device, and a native Bangla speaker has read three
drafts and signed off. D01–D07 still pass.

> The long plan calls the closed loop **"the decisive differentiator"**, and this is the cheapest
> high-value sprint in the track: one LLM call, one template, one lookup, one review screen.

**What the research changed** — `docs/reference/gd-formats.md`, ADR 0007:

> **We draft; a person files.** There is no Bangladesh Police API, no partnership, and no way to get
> one in fourteen days — and a cognizable offence (assault, robbery, theft, burglary: *every*
> category D07 proposes) cannot be closed online anyway. The applicant must appear at the thana.
>
> **One narrative serves both routes.** The official DMP form is a frame around one blank space, and
> the Online GD app's `অন্যান্য আবেদন` → `সাধারন ডায়রী করার আবেদন` path is **two fields**: the type,
> and one `বিবরণ` box. Both want the same formal Bangla paragraph. No second template.
>
> **The state machine has no `filed` state.** It ends at `ready_to_file`. We add a *"GD number (if
> filed)"* the user types back in — which closes the loop truthfully and makes Meridian their case
> record.

- [x] **GD profile — the one genuine addition.** The DMP form requires জাতীয় পরিচয় পত্র নং, পিতা,
      মাতা, ঠিকানা (স্থায়ী) **and** ঠিকানা (বর্তমান) as separate fields. We store none of them and
      they are not guessable. Collected once, reused. **Not in the original plan; budget for it**
- [x] GD template on the real DMP frame, in formal Bangla — `docs/reference/dmp-gd-form.pdf`
      transcribed in `docs/reference/gd-formats.md`. Use the form's own spelling (সাধারণ ডাইরী) *(S27)*
- [x] Thana identification from incident coordinates, over `police_stations.csv` *(S27)*. **Show the
      thana name only — never the email or phone columns**, which are one placeholder repeated 606
      times. See §7.2, now closed
- [x] `CaseworkAgent` — report plus geolocation becomes a draft, through `app/llm/client.py` with a
      validated output model *(S27)*
- [x] `LLM_CHAIN_GD=gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b` — measured, ADR 0007.
      Keys `GEMINI_KEY_GD_ONE`, `GROQ_KEY_GD_ONE`
- [x] ⚠️ **Offline tier: measured, and there is none.** `qwen3-vl:4b` was run on the same three
      scenarios on 10 Oct. It writes **কাকুরির মর** for Kakrail mor and **মুটি জেলার শাপলা চট্টার**
      for Motijheel Shapla Chattar, destroyed a year (`০৯ অক্টোবর ২৮`), invented an address that
      appears nowhere in the report, and took 7–13s against the cloud tier's 1.8s. **And the
      automated checks called four of those six runs "clean"** — which is the sharpest argument
      there is for why the native-speaker sign-off is a gate. **With no network, drafting fails
      with a message and saves nothing.** If D10 wants beat 7 offline, the answer is a replay
      fixture, not a local model. **Open for D10**
- [x] **Nothing the vision model proposed may enter the narrative as fact.** The confirmed category
      may select the template; D07's cue outputs may not become sentences. A false complaint is
      punishable, and the person signing it is the user
- [x] **Mandatory human review. It must be structurally impossible to approve an unreviewed draft —
      enforced in the state machine, not the UI.** A generated legal document is a draft until a
      person approves it, and this is the single most likely thing for a judge to press on *(S28)*
- [x] ⚠️ ~~**Embed a Bengali-glyph font in the PDF export.**~~ **Avoided rather than solved.** The
      PDF is printed on the device through `expo-print`, which renders HTML with Android's own text
      stack — the one already drawing Bangla everywhere else in the app. No font to embed, no
      shaping library, no PDF dependency in the backend. The trap is real; we stepped around it
- [x] 📱 **`features/casework/`** — draft review, inline edit, approve, export to PDF *(S28)*
- [x] 📱 **The review gate visible as a gate** — a disabled approve with a stated reason, not a
      hidden button. The safeguard is a selling point; show it working
- [x] 📱 **Two exits and a card.** **Print** → the full PDF on the DMP frame, signature line blank.
      **Copy** → the narrative alone, for pasting into `বিবরণ`. **Where else to take this** → 999,
      109, PCSW `01320-000888`, CID Cyber `01320010148`, keyed off the category
- [ ] **A native speaker reads at least three drafts.** Formal Bangla that is subtly wrong is worse
      on stage than an English placeholder. **This is a gate, and it depends on a person — arrange
      them in §9, not on the 20th.** The narrative is now the *entire* product in both routes, so
      this reviewer is load-bearing in a way they were not when the plan was written *(S28)*
- [x] 📄 `docs/walkthroughs/D08.md` — written and **run on a device, 10 Oct**
- [x] 🔴 **D08 walkthrough run on the device, 10 Oct — all steps passed.** §0 satisfied
- [x] 🔴 **The native-speaker gate — met 10 Oct.** Nakib (native speaker) read all three scenarios
      in `backend/data/eval/gd_drafts.md` and signed off: formal enough for a thana, nothing stated
      that the complainant did not say, no offence or section of law named. The automated checks
      were also clean (no invented numbers, no repeated form line, 96–100% Bangla, ~1.8s) — but
      those cannot see bad Bangla, which is why this gate needed a person.
      **Re-run it if the prompt in `app/casework/draft.py` changes:** the sign-off is on the
      wording that prompt produces, not on the feature
- [x] **Dhaka thana coordinates fixed from the police's own site.** `dmp.gov.bd/find-your-local-
      police/` carries a Google Maps embed per station; resolving each embed gives the station's
      marker. **46 of 51 verified, 43 of them from DMP itself**, with `coord_source` recording
      which source each row came from. Where DMP and OSM both have a point, 18 of 22 agree within
      62 m. Dhanmondi 27 → Dhanmondi 0.66 km; Paltan → Paltan 0.10 km; Mugda → Mugda 0.05 km
- [ ] 5 Dhaka thanas still unverified — **Cantonment, Turag, Uttarkhan, Hatirjheel, Bhashantek**.
      None has a map embed on the DMP page and none is mapped in OSM. The thana picker covers them
- [ ] 💡 **This also unblocks "find the nearest police station"** as a feature, which was not
      viable this morning. **Outside D08** — raise it separately

**Found while building, 10 October — two defects no amount of prompting fixed:**

> **The model cannot copy a 15-digit IMEI.** Across five attempts Gemini produced
> `35209900171481`, `35099001761481` and `3352099001761481` for `352099001761481` — a digit dropped,
> dropped again, and one added. Telling it not to convert to Bangla numerals did not help, because
> the problem is copying a long digit string at all. **So the model no longer does that job:**
> `_repair_identifiers` substitutes the complainant's own string back in, and where it cannot do so
> unambiguously it adds a line to the review screen instead of guessing. A wrong IMEI is a stolen
> phone that can never be traced.
>
> **`crime_reports.category` could not be read through the ORM at all.** The model mapped it by
> enum *name* (`THEFT`) while every row holds the *value* (`theft`) — the frontend writes reports
> straight to Supabase in lowercase. Any ORM read raised `LookupError`. It stayed invisible because
> the handlers in `endpoints/crimes.py` are still `pass` stubs, and **D08 is the first code in the
> project to read a report back through SQLAlchemy.**

---

## D09 — Tomorrow's map, and the loop closed — ✅ CLOSED
**Oct 22 · built and closed Oct 10 · source: S26, S05, S07**

**Showable:** move the map's time control to **tomorrow**. An announced procession is **already
flagged**, before it has happened. Then open the SOS history screen and show the record of an alert
that was actually delivered.

**Gate:** ✅ **met.** `docs/walkthroughs/D09.md` passed on a device, every step. D01-D08 still
pass. **This was the last sprint that ships a feature.**

- [x] `ScheduledRiskAgent` - reads published announcements of processions, shutdowns, exam days and
      large gatherings; emits **forward-dated** flags using the `valid_from` / `valid_to` columns
      D01 already created, so **no migration and no contract change** *(S26)*. Hourly cron at
      `20 * * * *`, offset from D04's so the two do not contend for the same free-tier quota.
      Verified end to end against live sitemaps: 390 listed, 1 announcement, fetched, read, 0 events
      published - correctly, because the article stated no hour
- [x] **The model is never asked for an instant.** It answers `day` (today / tomorrow / day_after)
      and an integer `start_hour`; `_window()` does the arithmetic from the article's own
      publication date in Dhaka time. This is D08's IMEI lesson applied before it cost anything -
      a free-tier model asked for `2026-10-11T10:00:00+06:00` gets it wrong quietly
- [x] Mobility framing is non-negotiable here. Processions and gatherings are "road blocked" or
      "heavy crowd", never characterised politically *(S26, invariant)*. The framing invariant
      caught the new agent as an unjustified writer of `mobility_statement` and made it be
      allowlisted with a reason - the guard working, not a nuisance
- [x] 📱 **Map time control, promoted from D02's dev-only version to a real forward-looking one**,
      over the same `as_of` parameter. **No competing product looks forward. This is beat 8**
      *(S26)*. Relabelled in words at the far end - `Tomorrow`, `+2 days` - and the status line now
      names the instant and counts the *scheduled* flags. The dev label said "N flags left", a decay
      framing that had this control's direction backwards once it started looking forward
- [x] 📱 Forward-dated flags visually distinguished from live ones - a scheduled risk is a different
      claim from a current one. **Shape, because every other channel was already spent:** colour
      carries severity, fill and ring style carry verification, so a scheduled flag is a rounded
      square. The two questions are independent and the map shows both at once
- [x] 📱 **Defect 14 - `MapScreen`'s SOS button was a `// TODO` alert** that confirmed an SOS and
      then claimed contacts had been notified. Extracted `useSOS()` + `SOSFlow`; both screens
      consume them *(S07)*. `HomeScreen` went 580 to 319 lines. A straight extraction, not a
      rewrite - the shake threshold's 6.0-versus-3.5 discrepancy was carried over untouched,
      because changing a trigger inside a refactor is two changes with one of them tested (B5)
- [x] 📱 **SOS history screen**, over the audit trail D01 started writing. Beat 9's second half: the
      alert was delivered *and here is the record* *(S05)*. Reachable from the profile menu - three
      routes have sat declared-but-unregistered in `ProfileStackParamList` since D01, so declaring
      one is not shipping it
- [x] **`GET /sos/history`** - it did not exist; `endpoints/sos.py` had exactly one route. Scoped to
      the caller in the WHERE clause, not filtered afterwards. Tolerates all three shapes
      `contacts_notified` has had, because an audit trail that cannot render its own oldest rows is
      not one
- [x] ~~**And `sos_incidents.user_id` -> `public.users` needs a migration like D08's**~~ -
      **withdrawn 10 Oct, on reading the code properly. No migration, and D09 needed no contract
      change.** The value written to it is `current_user["user_id"]`, the Supabase JWT's `sub` -
      **the auth user id**. **D08's defect was a value mismatch; this never was one**
      > ⚠️ **Corrected 2026-10-15.** This row said *"the column does reference the `public.users`
      > mirror"* and credited the auto-provisioning in `trigger_sos` with making the key
      > satisfiable. **Both are wrong, and the right answer is simpler.** `sos_incidents.user_id`
      > has referenced **`auth.users(id)`** since `SCHEMA.sql` was first committed in `2d924a2`
      > and that line has never been edited (`git log -L 203,207`). The 10 Oct reading came from
      > `app/models/sos.py`'s `ForeignKey("users.id")` — the ORM declaration, which does not build
      > the Supabase schema. So the key was always satisfiable because it pointed at the right
      > table, **not** because anything provisioned a mirror row. The conclusion held; the reason
      > given for it did not. See the re-scoped **Defect 9** in `IMPLEMENTATION_PLAN.md`.
- [x] 🔴 **Found by building: nothing stopped a scheduled flag being served before its window
      opened.** `decay.elapsed_hours` clamps a negative age to zero, so tomorrow's procession would
      have sat on tonight's map at *full* severity - and bent tonight's routes around a road that is
      currently clear. Fixed as a `valid_from` floor in **both** `surface_db._LIVE_PREDICATE` and
      its Python mirror `decay.is_live`, with an invariant asserting both still say it. D01 built
      every other part of forward-dating; this was the one piece nobody could have specified before
      a forward-dated flag existed
- [x] 🔴 **Found by building: the fixture had zero forward-dated flags**, so beat 8 had nothing to
      show at all. Three `seed-scheduled-*` entries added - a confirmed procession, an unconfirmed
      one, and a works notice spanning both the `Tomorrow` and `+2 days` presets. Measured on the
      seeded surface: **192 flags at `Now` with 0 scheduled, 67 at `Tomorrow` with 3**
- [x] 🔴 **Found on a device: three overlay collisions on the map, two of them older than D09.**
      Every overlay is absolutely positioned and three were placed by independent guesses that
      happened to intersect: the new time control lay across the top of the 80pt **SOS** button; the
      **report** and **route** buttons started at `insets.top + 32` while the search card runs to
      about `insets.top + 46` *with a higher zIndex*, so the card covered the top of both; and the
      risk badge had no right bound, so a long label ran under the SOS button. Fixed by naming the
      button sizes and **deriving** the positions from them - the styles now read `width: SOS_SIZE`,
      so growing a button moves its neighbours instead of being covered by them - and the search
      card's height is measured with `onLayout` rather than assumed, because `PlaceSearch` grows
      when it has a result. Verified by checking every overlay rectangle for intersection
- [x] 🔴 **Found on a device: the news page counted a statistics table as a news article.**
      `chronic.py` cites `police.gov.bd/.../crime_statistic_comparative_statement` on every derived
      chronic flag - a genuine `https://` link - so the header read **`1 real of 30` on a day when
      no news article had been ingested at all.** A permanent +1 from a statistics page makes the
      one number this screen exists for unreadable: is "1 real" an article, or the stats page again?
      The whole **chronic layer is now excluded** - a statistics table is not news, and the citation
      still appears on the chronic flag's own sheet as that layer's provenance. 30 cards to 25,
      and the counter now reads the truth: **0**
- [x] 📄 `docs/walkthroughs/D09.md` - **passed on a device, every step, 10 Oct**
- [x] 📱 **News page - the headlines behind the map, as cards.** Built 10 Oct. Two tabs over the
      same `as_of` parameter: **Today** (what was read) and **Tomorrow** (what was announced).
      Frontend only - `GET /risk/flags` already returns `sources[]` on every flag, so this regroups
      what the map already had. Reached by tapping the risk badge, which already reads
      "... - news 4 min ago" and so is the thing on screen that most looks like it should open it
- [x] 📱 **And it is the ingestion dashboard**, which is why it looks the way it does. The header
      carries the agent's own last-run numbers and every card is counted as *n real of m* with
      sample headlines labelled `Sample data`. Ingestion is thin and the fix is next phase; a page
      that presented fixture headlines as a day's work would make it impossible to tell whether a
      day had worked. **The number to watch is "real of".** Today 10 Oct: **0 real of 25** on the
      `db` surface, **1 real of 26** on `seeded` - the one difference being the single genuine
      article in the replay fixture, which `seed_risk_flags.py` does not load (`include_replay=False`)
- [x] 🔴 **Found by building it: my own "22 of 207 flags carry a headline" was wrong.**
      `fixture.py::_generated_sources` invents a reference for every seeded flag that did not spell
      its own out, so the Today tab came out at **274 cards, 272 of them reading
      `Sample report - Mirpur 10`**, with the two real articles invisible among them. Those are not
      articles - the generator's own comment says the titles are deliberately implausible so that
      nobody mistakes the fixture for a news archive - so `isGeneratedPlaceholder` leaves them off.
      **274 cards to 31.** The 22 hand-written sample headlines stay, labelled, because they do read
      like reporting
- [x] ⚠️ **Raised, and both halves now addressed — the gazetteer by B7 on 14 Oct, the relevance
      filter by D04 on 15 Oct. Read the measured numbers below, not the guesses above them.**
      The original reading, kept because it is what prompted the work: live news ingestion was
      producing almost nothing, and it is older than D09. Recent `live_risk` runs read `in=0 out=0`: of ~390 articles listed per run the
      relevance filter passes about **1%** — *both figures were stale. A real collection on
      15 Oct listed **2,622 articles** across the nine publishers and passed **167 (6.4%)**.* —
      and those few are already stored, so the queue is empty.
      Of 24 documents ever read, the model found 4 incidents and the gazetteer rejected 3. **Beats 1
      and 2 therefore run on the seeded surface, not on live news.** That is defensible on stage -
      `RISK_SURFACE_IMPL` is the switch and the agent is real - but it should be a decision rather
      than a discovery. Widening the sources is **B11a**; loosening the filter and growing the
      gazetteer are **D04** and **B7**. ~~**Outside D09's scope; needs a call**~~
      **The call was made and both halves are done, 14 Oct.** S30 widened nine publishers from
      three and added the news-crime surface; **B7** then took the gazetteer from 1,022 entries
      to **6,054**, which is the half this row blamed — *"the gazetteer rejected 3 of 4"* was
      the symptom of a file holding **zero roads**. Held-out accuracy went 93.3% → **95.6%**
      with 0 fabrications, and coverage of 193 real Dhaka references 71% → **84%**.

      **D04, 15 Oct — the filter half, measured rather than loosened.** 417 hand-labelled
      headlines: **precision 0.31 → 0.43, recall 0.47 → 0.68**. Three causes, all fixed.
      (1) **No geographic gate existed at all** — of 167 articles passed, 115 were not Dhaka
      incidents (Ukraine, Saudi Aramco, Rangpur, Sajek, Delhi). It asked "is this an incident?"
      and never "is it here?". (2) **`country`/`countries` were excluded as if they meant
      "foreign"** when they are the domestic দেশ desk — which also silently capped
      **corroboration**, because the Tongi fire was filed under `capital` by some papers and
      `country` by others, so a `confirmed` flag was unreachable however many outlets carried
      it. (3) 🔴 **Bangla writes ড়/ঢ়/য় two ways in Unicode and one never matched** — 1,568 of
      2,622 headlines used the precomposed form while 17 keywords were written decomposed,
      including `চাপায়` (run over) and `ছিনিয়ে` (snatched). That had been losing real Dhaka
      road deaths with no trace: `বারিধারায় গাড়িচাপায় নির্মাণশ্রমিকের মৃত্যু` was never
      fetched. **If asked on stage why coverage is thin, these are the honest answers and they
      are measured, not estimated.** `LOOKBACK` was deliberately left at 12 h — see PROGRESS.
      ⚠️ The remaining 72 false positives mostly need the article body, not the headline.

> **The news page we are *still* not building — the discard pile.** The headline list above
> ships. This is the other one. `extracted_incidents` carries
> `discarded_reason` - `unresolved_location`, `duplicate`, `rejected`, `low_confidence` - and its
> migration calls the null-`flag_id` rows "the audit trail for *discarded, never guessed*". A page
> showing **what we read and what we threw away, and why** is a stronger claim than a headline list,
> and no competing product can show its own discard pile. It needs a new endpoint over
> `raw_documents` + `extracted_incidents`, a new contract and a TypeScript mirror. **Parked as
> B6b**, which costs nothing, because the data is being written either way. The measurement above
> makes it a *better* page than the headline list: three of four extracted incidents were discarded,
> and that is the honest story of how this pipeline behaves. The page that shipped shows what was
> published; this one would show what was refused.

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
- [x] ~~Decide and document the police-routing position — §7.2~~ **closed early, 10 Oct, ADR 0007
      (`false`: nothing to transmit to), then revised by the owner on 15 Oct to
      `POLICE_ROUTING_ENABLED=true`.** The position now: we cannot *file* with the police, which
      is why the thana is named on the GD — but we can *notify* the nearest thana of an SOS, and
      that needs no API. See §7.2's second addendum *(S05)*
- [ ] Q&A numbers ready: geolocation accuracy (D03), flag precision (D05), **vision
      false-accusation rate (D07)**, time-from-incident-to-alert (D04)
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
| S09 | Ingestion framework | Framework, politeness, `raw_documents`, three Bangla **newspaper** sources → **D04**. **Social media, official feeds and the rest of the concept document's live source categories → B11a** — these were never built, and until 2026-10-08 this row claimed D04 covered S09 in full, which was the kind of error §5 exists to catch |
| S10 | Bangla gazetteer | **D03** (one zone). Density across both Dhaka city corporations → **B7, done 14 Oct** (1,022 → 6,054 entries, 3,241 roads). National density beyond Dhaka is still **B7**'s open remainder |
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
| S29 | Crowd verification | **B13 — partly delivered** |
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
| **B1** | ✅ **DONE, 15 Oct — four ADRs written, and writing one of them found the worst defect in the repo.** `0001-data-plane`, `0002-auth`, `0003-user-table-collapse`, `0004-migrations`. **Reading the auth path end to end for ADR 0002 surfaced defect 56: `POST /api/v1/auth/login` returned a valid, accepted token for any email, with no credential check** — `verify_password` imported and never called, under a `# TODO` comment that made it read like a stub. Measured before touching it: the forged token reached `get_current_user`, so every protected endpoint was open, including `/sos/trigger` and the LLM routes. Three independent faults (the backend could mint; HS256 was accepted; `aud` was not required) all fixed the same day, with a 10-test structural invariant — structural because the bypass survived **by never being exercised**, which no behavioural test can catch. **This row's whole value turned out to be the reading, not the writing.** The other three ADRs mostly ratified what the code already did; 0001 additionally condemns `endpoints/users.py`/`crimes.py`/`tracking.py` as dead, and 0004 records the three operational lessons (duplicate version numbers are skipped for ever; the ledger names files this repo does not have; a drop does not stay dropped while another checkout declares the model). ~~ADR documents `0001-data-plane`, `0002-auth`, `0004-migrations`. **Plus: execute ADR 0003** — collapse the three user tables, and update `endpoints/sos.py` and `models/` in the same sprint. 🟡 **Re-scoped 2026-10-15: ADR 0003's migration is already done; only the document and a one-file code change are left.** | S02 | Moved out of D01: `risk_flags` has no `user_id`, so nothing in the demo track needed it, while dropping `public.users` **would have broken SOS** — `sos.py` creates rows in it on every trigger. This is a code change, not just a migration, which is exactly why it does not belong in a two-day sprint with nine other things. ⚠️ **That reasoning expired, and the row is now almost done.** Audited against the live schema on 15 Oct: **no FK points at `public.users`** (every user table → `auth.users`; `gd_drafts` was the last and migration `20261010160000` moved it), and `endpoints/voice.py` was deleted in B8. So the migration half of ADR 0003 had happened piecemeal without this row being ticked. ✅ **Defect 9's real symptom is fixed the same day** — `sos.py` derived the alert's name from the email local part (*"EMERGENCY: mdarafat1661 needs help"*) and now reads `profiles.name` (*"EMERGENCY: Arafat Ullah needs help"*), verified against the three live accounts; the model, its relationships and the ORM FKs are deleted. The table itself was dropped the same day (migration `20261015160000`, applied in the Supabase SQL Editor; verified gone, all user data intact, and still gone after an API restart). **What is left of B1 is the three ADR documents and nothing else.** ADR 0003 is now a record of a decision already executed — still worth writing, because the false belief that SOS depended on the mirror survived in three documents for weeks precisely because nobody had written it down.~~ *(That last sentence was the argument for writing these documents. Defect 56 is the proof of it.)* |
| **B2** | ✅ **DONE, 15 Oct — and two of its three parts were already finished.** ~~Full invariant suite~~ **24 files**, grown sprint by sprint rather than in one pass. ~~`app/privacy/retention.py` registry~~ **done in B14**, all 21 tables. The part that was genuinely missing is the **contract-drift CI check**: `tests/invariants/test_contracts_do_not_drift.py` (38 tests) plus CI job **3b `contract-drift`**. It compares each Pydantic contract against the **`*Wire` interface** that mirrors it — not the camelCase types in `types/contracts/`, which are the client's domain model and differ on purpose — and each `Literal`/`StrEnum` against the client's union. **Proven to catch the failure it exists for:** renaming `RiskFlag.source_count` on the server leaves `tsc` at **exit 0**, the request still succeeds, and the zone sheet renders a blank where "3 sources" belongs; only this check fails. Six of its tests feed the comparator known-broken input, because a check that cannot fail is worse than none. ⚠️ **Finding: the `invariants` CI job has never been able to run** — it installs no application dependencies, so it cannot import `app.*`, and neither can the `backend` job's pytest step. Documented in `ci.yml` rather than half-fixed: the suite reaches `app.agents`/`app.ingestion`/`app.llm`, so collecting it in CI means torch. The 684 tests do run in the `api` container on every change. Job 3b is pydantic-only (15 packages) specifically so it does not inherit that problem. | S03 | The two invariants shipped in D01 are the two judges ask about. These are the other five. |
| **B3** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Endpoint auto-discovery, `app/config/` package, frontend service de-barrelling, ~~delete `theme/colors.ts` + `darkTheme.ts` (**defect 16**)~~. **Three findings from reading it, recorded so nobody re-derives them:** (1) the **theme quarter is already done** — both files were deleted in commit `f0a83de` and `theme/theme.test.ts` now guards the keys the screens read, so **defect 16 is closed in full**; (2) **endpoint auto-discovery should not be built as written.** `api.py`'s manual `include_router` list is the one place where publishing a public route is a decision somebody makes, and it is where the ADR 0001/0002 reasoning for there being no `/auth` router lives. **Defect 56 was a registered route nobody had looked at returning an accepted token for any email** — auto-discovery makes that class of failure *easier*, because dropping a file into `endpoints/` would publish it with no sign-off. S04 wrote this row before that was known. If the real worry is a module that exists but is never registered, that is a **test**, not a loader. (3) The remaining two parts are near-zero gain: the services barrel has **three** consumers and removing it also removes the defect-16 reasoning written into it, while `core/config.py` is one `Settings` class of **82 fields** whose 517 lines are mostly the comments explaining why each flag exists — splitting one pydantic class into a package needs mixin inheritance, turning one readable file into five with a resolution order to trace. | S04 | Structural cleanup with no user-visible effect — exactly why it waited. **And on reading, a quarter was done, a quarter would reduce safety, and the rest rearranges readable code without removing a trap.** |
| **B4** | ✅ **DONE, 15 Oct.** ~~**Defect 2** (`speech_service` `NameError`)~~ — **closed by deleting the endpoint, not fixing it.** The row said "defect 2 blocks speech-to-text entirely"; what had actually happened is that B8 routed around it, moving dictation on-device *because* it was broken, so the endpoint had no caller left. Restoring it meant shipping ffmpeg and Google Cloud credentials for a feature abandoned on privacy grounds. ✅ **Defect 17 closed 15 Oct — and the claim above it was wrong.** This row said real contacts *"would let `POLICE_ROUTING_ENABLED` ever be true"*. They would not: **§7.2 / ADR 0007 closed police routing on 10 Oct because there is nothing to transmit to** — no public police API, and a cognizable offence needs the applicant at the thana in person. The defect sat blocked on data for a deliverable already cancelled, and three documents repeated the stale reason because nobody re-read it after writing §7.2.

      Fixed the half that is actually read — **names and coordinates.** `thana.py` scoped to the 51 Dhaka city thanas (was all 607 rows, Sherpur included); five rows the file marks `legacy — unverified` made **nameable but not rankable** (`Turag`'s coordinate sits 1.7 km from Rampura, `Hatirjheel`'s 4.4 km from Pallabi); points over 25 km from any Dhaka station now get **no** thana instead of one 200 km away; duplicate spellings made deterministic so a signed GD cannot say `Gandaria` one run and `Gendaria` the next.

      **The declined fallback got implemented after all, without rewriting the file:** 607 rows sharing one address is already an explicit statement of not-known, so `sos_service` measures it and refuses to email **even with the flag forced true**. **Thana numbers were never invented** — the contact columns are still the owner's own test values, and nothing depends on them any more. | S05 | Defect 17 is a data-gathering task; see §7.2 on why the gate defaults off — permanently. |
| **B5** | 🟢 **DONE, 15 Oct — and two of its three items were already finished.** ~~**Defect 16**~~ — `routeService` now comes from the services barrel with `RouteRequest`/`RouteResponse`; `Location` left out on purpose, since three declarations plus a DOM global make it the worst name to render ambiguous in a barrel. ~~**The ~30 lines of stale-closure deliberation in `HomeScreen`**~~ — already removed; the file holds one three-line note explaining why `readZones` runs on focus rather than mount, which is an explanation and stays. ~~**The shake threshold** (comment said 3.5 g, code said 6.0)~~ — settled in Guardian on 11 Oct, and **better than this row asked.** The row said "pick one and justify it with a measurement"; the right answer was that neither is correct for every handset, so it became a **user setting** paired with a live accelerometer reading. *"Shipping one constant for every handset is how a panic trigger ends up either firing in a pocket or not firing when someone is being attacked."* | S07 | The shake threshold was indeed a correctness question — and the correct answer was that it is not a constant. |
| **B6** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** ~~Feature directories under `src/features/`~~ — **this half is already done, organically.** Eight feature directories exist (`alerts`, `casework`, `geofence`, `guardian`, `navigation`, `risk`, `sos`, `voice`, 39 files), built as D06, D07, D09, B6a and B8 each landed; nobody ticked the row because the work happened without anyone running the sprint. `src/components/` reduced to shared primitives — **still open, and smaller than it sounds.** 10 files, and of the 50 import sites referencing `components/`, most import `components/motion/` (the glass/blur/animation primitives, genuinely shared, would stay). The feature-specific ones are concentrated in **one file**: `screens/Map/MapScreen.tsx` imports seven of them. So the remaining work is ~**8 file moves** plus import rewrites, verifiable by `tsc` and the 427 jest tests, with one hazard — `MapComponent.tsx` and `MapComponent.web.tsx` are a **platform-resolution pair and must move together**. ⚠️ **The finding that matters more than this row: `screens/Map/MapScreen.tsx` is 2,257 lines.** It is the map tab, the zone sheet, route comparison, news pins, place search and every risk layer in one file — and it is the file that produced the routing stack-overflow fixed in commit `6b3e2f8`. **That is the actual trap, and B6 as written does not touch it**: moving marker files rearranges the small files and leaves the large one. Splitting it is **post-rehearsal work** — eight days before D10 is the wrong moment to refactor the screen a mistake would show up on stage. | S08 | The demo track adds screens fast. This is the sprint that pays for that. **On reading: the directories paid for themselves without the sprint, and the debt went somewhere this row never names.** |
| **B6a** | 🟢 **DONE and VERIFIED ON A DEVICE, 15 Oct — geofencing.** `docs/walkthroughs/GUARDIAN.md` Part 1, steps 1–5: permissions granted including *"all the time"*, the zone watch registered, the crossing detected, the notification delivered with the server-framed mobility statement, the six-hour debounce suppressing the repeat, and the history showing both the alert and the suppression. **Verified against a seeded flag** — `backend/scripts/seed_flag_here.py` writes a live flag at any coordinates, which is what made Part 1 runnable from outside Dhaka at all. What a seeded flag exercises is the whole chain the app owns: `startGeofencingAsync` → Android's `GeofencingClient` → the headless task → the local notification → the debounce. What it does **not** exercise is step 6, the outdoor walk, which the walkthrough has always marked optional: the **+250 m early-warning margin** is still unmeasured at walking pace on a real road, and **battery impact over a day of real use is still unmeasured** (S17, open box). Neither is a code question. **The row said "push notifications"; what was wanted was S17.** Background GPS with OS-level geofencing (`startGeofencingAsync`), a headless task that posts a **local** notification as the user approaches a flagged road, each zone watched at its radius + 250 m so the warning arrives while there is still a junction to turn at, a six-hour per-zone debounce, and a user-visible crossing log that records suppressed crossings too. **No Expo project, no Firebase, no FCM key** — detection is on the phone, so the phone posts the notification. Chronic flags are never geofenced (a 2 km historical average that never expires would fire every time its owner left the house). ⚠️ Still open: route-based prediction ("a road that will take you to a zone") is approximated by the 250 m ring; the real version needs the routing engine and a destination. The **server-side push dispatcher** from the first reading of this row is also built, tested and left in place with `PUSH_ENABLED=false` — real, but not the feature asked for. | S16, S17, S15 |
| **B6b** | ⛔ **WILL NOT BUILD — declined by the owner, 15 Oct.** ~~Ingestion provenance page — what we read, and what we discarded. One endpoint over `raw_documents` + `extracted_incidents`, plus the contract and its TypeScript mirror.~~ **The owner's decision, in their words: *"I don't want to show the users this information that what our app fetched and what our app rejected. I don't want to add another screen."*** It is a product judgement, not a capacity one, and it is a reasonable one: the audience for "371 read, 34 discarded, 31 of them unplaceable" is a reviewer or an operator, not somebody checking whether a road is safe tonight, and every extra screen is weight on a person in a hurry. **Nothing is lost that was being relied on** — `discarded_reason` and the `raw_documents` → `extracted_incidents` chain are still written and still queryable, so the provenance exists as a record even with no screen over it; D04's measured precision/recall came out of exactly that data without a page. If a judge asks *"what did you throw away?"*, the answer is a SQL query, not a missing feature. ⚠️ Do not re-propose this as a user screen. If the need ever returns it belongs in **B9** (operator-facing), not in the app. | S09, S14 | **Deferred from D09 on 10 Oct for capacity, then declined outright on 15 Oct on the merits.** |
| **B7** | 🟢 **DONE and VERIFIED ON A DEVICE, 14 Oct — gazetteer density.** Delivered out of sequence, immediately after S30, because S30 ended by naming the gazetteer the ceiling on the whole pipeline: every agent calls `resolve_place(allow_llm=False)`, so a place the file does not hold is an article thrown away. **1,022 entries became 6,054, and 0 roads became 3,241** — the old harvest asked OpenStreetMap for `place`, `junction`, `marketplace`, `bus_station` and `railway=station` and **never once for a `highway`**, so a correctly-extracted "সাতমসজিদ রোড" was a guaranteed discard. The pilot box was widened to `90.30,23.66,90.54,23.94`, covering both city corporations. A road is a line but the gazetteer stores a point plus a radius, so segments are chained and the radius is the **measured** half-extent; a road too long to pin honestly is **refused rather than clamped into looking precise** (`Mirpur Road`, 8 km, draws no pin by design). Held-out accuracy 93.3% → **95.6%** with **0 fabrications and 0 wrong pins**; coverage of 193 real Dhaka references 71% → **84%**, named roads 15% → **61%**; backend tests 559 → **601**. Verified by the owner on an Android handset through the map search box — that is `PlaceSearch`, which hits `/geo/resolve`; route mode's own inputs go to the Nominatim proxy and demonstrate none of this. ⚠️ **Still open: national density beyond Dhaka**, and ~21 of 193 references still resolve to nothing — mostly minor roads and spelling variants like `Begum Rokeya Sarani` vs OSM's "Sharani", which is `aliases.json` hand work no fuzzy match reaches. | S10 | Gates geographic expansion. Manual work that does not compress — started as background early, paid off in one sprint. |
| **B8** | 🟢 **DONE and VERIFIED ON A DEVICE, 11 Oct — shout-to-SOS and shake-to-SOS.** Vivo V2344 / Android 14, `docs/walkthroughs/GUARDIAN.md`. Both triggers run end to end from any screen: countdown, camera, location, email to contacts, hands never touching the phone. ✅ **Video works — defect 53 closed 2026-10-15 on a second Android phone.** Video captured, uploaded and arrived attached to the alert email, which settles what one device could not: the Vivo V2344's `VideoCapture` starvation is **Unisoc `ums9230` driver behaviour, not our capture code**. No code change; the measured Vivo finding stands unretracted, only its scope narrowed. Defect 52 remains the permanent answer rather than a workaround — on hardware that cannot record, the SOS sends location only and says so on screen, so the alert still goes out. ⚠️ **Demo on the phone that works, and keep the claim conditional** — *"location in seconds, plus video where the hardware supports it"* — because one confirmed handset in the fleet cannot record. `sos_hot_words` is read at last: phrases are matched **on the device**, and a match only counts if the **peak loudness in the preceding 2.5 s** cleared a user-calibrated threshold — so SOS fires on a shout, not on somebody saying the phrase. Both triggers then run the real SOS automatically: video, location, email to emergency contacts, no tap, with a 5-second cancel window that can be switched off. `voice_activated` is finally written to `sos_incidents`. The privacy bar is a **refusal**, not a downgrade — `requiresOnDeviceRecognition` is silently ignored on a device that cannot honour it, so the app checks `supportsOnDeviceRecognition()` and declines to listen rather than streaming the microphone to a server. `/voice/analyze`, `speech.service.ts` and `useVoiceRecorder.ts` are deleted: **zero audio upload paths remain**. ⚠️ **Voice and shake need the app open** — Android has restricted background microphone and sensor access since Android 9, and holding the mic with the app closed needs a native foreground service no Expo module provides. Zone alerts are the one that works from a pocket. ⚠️ **Still open: the trips model**, which is the half B10 depends on — `app/trips/`, the migration, `features/journey/`. **Live progress and ETA landed separately on 13 Oct** (`features/navigation/`, see the D06 addendum): the route trims as you walk it, with turn-by-turn road names, an ETA from measured GPS speed and automatic re-routing. That is the *client* half only — it is foreground-only, holds no state across launches, and **persists nothing**, so there is still no trip to detect an anomaly against. The trips model is what B10 needs and it is still unbuilt. | S18 |
| **B9** | 🟢 **DONE, 15 Oct — and it found a feature that had never worked.** Admin observability, delivered in two halves because the operator and the user want different payloads from the same measurement. **`python -m app.agents status`** prints the operator's table — per agent: state, last run age, cadence, last status, items in/out, 24-hour run and failure tallies, error text, and a called-out diagnosis for a stuck or late agent. Exits **1** on `late` or `problem` so it works as a shell health check; `never_run` and `unknown` stay 0, because the first is the normal state of a fresh database and the second is the module declining to guess. **`GET /api/v1/agents/status` + a System Status screen under Profile → Safety** is the user's half: one card per part, in plain words written from each agent's own docstring, with "Last ran 4 minutes ago · runs every 15 minutes". ⚠️ **The owner asked for the user screen; the row only said admin.** That was the right call — the app had no answer to *"is this map current"*, and a map that is empty and a map that is empty because nothing ran are the same picture. **Both halves read one function** (`app/agents/health.py :: fleet_health`), so the operator's view and the user's can never disagree about whether something is healthy; they differ only in how much they say. **The user payload deliberately omits** error text, item counts and failure tallies — an exception repr is noise to a user and a hint to anyone probing the deployment, item counts do not mean the same thing across agents, and a failure tally is alarming without being actionable. A test asserts those stay out. **Two rules the screen holds:** it never shows green over stale data (`late` reads "Running behind", and a test sweeps every cadence against a 14-hour-old success), and it says when a red card *does not* affect the user — `expiry_sweep` is the case that forced that, since its own docstring says every surface stops serving an expired row whether the sweep ran or not. **Found two live defects on its first run: defect 57** — `report_corroboration` had **38 runs and 0 successes**, so B13's `community_clusters` was empty while three documents called B13 landed (fixed the same hour) — and **defect 58**, a `risk_flags` constraint violation in `rumour_guard`'s merge whenever two commonly-owned outlets cover one event (diagnosed, left for an owner decision, fails closed). **+63 backend tests, +27 jest.** Endpoint gated behind `get_current_user`, unlike `/ingestion/status`, which is open because *"it describes public news, not a user"* — fleet health describes our deployment, which is a different thing. | S21 | Once eight agents run on schedules, you cannot operate them without this. **Confirmed the hard way: the data had been written since D01 and nothing read it back, so an agent that had never once succeeded looked exactly like one that worked.** |
| **B10** | ⏭️ **SKIPPED by the owner, 15 Oct — and skipped because somebody else is already building it, not for capacity.** **Journey Guardian** — anomaly detection, then graded escalation. 🔭 **Owned on `origin/feature/journey-guardian`, and well past a sketch.** That branch carries **`JOURNEY_GUARDIAN.md`, 391 lines** — "the case for it, and seven phases", **JG1–JG7** — and it reasons through the parts that are actually hard, including why the outer ring summons **witnesses and never a crowd**: গণপিটুনি is named as documented, recurring and lethal, alongside the facts that the attacker may be a user and that a pin cannot be recalled once forty phones hold it. **The schema for the first four phases is already live.** `public.journeys` has **23 columns and 37 rows** as of 15 Oct afternoon (7 that morning), including `deadline_at`, `last_heartbeat_at`, `escalation_state`, `check_in_sent_at`, `answered_at`, `unanswered_at`, `leash_seconds` — that is JG1–JG4's state machine, **not** the trips model this row was waiting for. Ledger rows: `20261014150000 journeys`, `20261015120000 journey_deadline`, `20261015140000 journey_leash`. **Do not build this in parallel.** Two people writing one escalation path against one shared database, on the feature S22 calls *"the most safety-sensitive component in the system"*, is worse than waiting. ⚠️ **Owner action, and it is time-sensitive: none of those three migrations is committed anywhere — not even on that branch**, whose diff adds the design document and navigation fixes and no SQL. So a fresh checkout cannot reproduce the schema, and **`migrate.py up` already counts those versions as applied and will skip them for ever**, which means committing them later under the same timestamps does nothing. That is precisely the trap ADR 0004 records. Reconstructing them from the live schema by hand would produce files that silently differ from what was applied, so this is **a message to Nakib, not a task for whoever reads this row.** | S22, S23 | Deferred by the concept document itself. **Its two-week self-trial should start as a background activity as soon as B8's TRIPS half lands** — no sprint can contain it. ⚠️ B8 is only half done as of 10 Oct: hot words shipped, the trips model did not, and the trips model is the part this depends on. Do not read B8's 🟡 as a green light — and do not read 13 Oct's live navigation as one either. It gives the *display* of a journey in progress (position on the route, distance left, ETA) and stores none of it, so there is no history for an anomaly detector to call anomalous. |
| **B11** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Chronic Risk Agent — newspaper archive mining at scale. **Three blockers, measured 15 Oct, so the next attempt does not rediscover them:** (1) 💰 **No paid LLM account exists.** The six configured keys are **free-tier, per-feature** Gemini/Groq ones (`GEMINI_KEY_EXTRACT_ONE`, `GEMINI_KEY_CRIME_ONE`, `GEMINI_KEY_GEO_ONE`, `GEMINI_KEY_GD_ONE`, `GROQ_KEY_GEO_ONE`, `GROQ_KEY_GD_ONE`); **`ANTHROPIC_API_KEY` is empty** while `LLM_MODEL_BULK` is set to `claude-sonnet-5-5`, so the bulk model is declared and unusable. (2) ⚙️ **S24 specifies the Batch API for the 50% discount and there is no batch code in `app/llm/` at all** — that is a new client path, not a flag. (3) 📉 **The archive it would mine does not exist yet:** `raw_documents` **452**, `extracted_incidents` **63**, roughly eight days of live ingestion, because `live_risk` is deliberately sized for the free tier (`MAX_EXTRACTIONS_PER_RUN = 12`, `LOOKBACK = 12h`). A *repeat* blackspot needs many incidents at one place over months; clustering 63 incidents across all of Dhaka yields noise or nothing. 💡 **One nearly free thing that is NOT this row and would unblock it:** **fetching** archives costs only politeness and disk, and extraction is already a separately deferred step — `raw_documents.extracted_at is null` is the retry queue — so a **fetch-only backfill** could accumulate months of archive now and leave B11 as weeks of work rather than weeks plus a wait. Scope it as a background activity if wanted. ⚠️ **What exists today is not an undisclosed shortcut.** `app/scoring/chronic.py`'s own docstring says it: *"The real implementation is newspaper archive mining at scale (B11). That is weeks of work. This is an afternoon… When B11 lands it replaces this, and the 90-day half-life is the same either way so the layer does not change character."* Live today: **16 chronic flags**, one per metropolitan police unit, **20 km radius**, severity 4.3–58.9 — a baseline, labelled as a baseline, with the judge-facing wording already written. B11 must **reconcile** with it rather than stack on it; `chronic.py` solved that once and recorded the rule — `Dhaka Range` contains DMP at a *higher* score, so *"the most specific unit covering a point wins, and the aggregate is not a second opinion."* | S24 | The chronic *layer* already exists from D02's police-statistics model; this is what makes it real. **And on reading, "makes it real" is gated on a paid account and a months-deep archive, neither of which exists.** |
| **B11a** | 🟡 **STARTED 15 Oct — the official-feeds third is done, and the survey behind it is the deliverable.** `app/ingestion/sources/dmp_news.py` reads the **Dhaka Metropolitan Police's own outlet** (dmpnews.org) — WordPress, so an RSS feed with the article body in `content:encoded`, per-category feeds, and a 37-page sitemap. It is the **tenth source and the first that is not a newspaper**, and it reads the crime category, not traffic: nine of ten traffic items are the daily enforcement counter (*"2,799 cases in 24 hours"*), a statistic that would spend a slot of `MAX_EXTRACTIONS_PER_RUN` to be rejected. ⚠️ **The other three institutional bodies publish nothing usable, which is itself the finding** — Fire Service: firefighter joining notices and tenders, no incident feed; DNCC: Durga Puja cheque distribution, an e-trolley tender, officer postings; DSCC: meeting notices, municipal tax deadlines, WASA bill verification. All three run the same national-portal CMS, no RSS or API, notice boards administrative by design. **The institutional tier is largely not machine-readable in Bangladesh** — the honest answer if a judge asks why this row has one entry rather than four. Still open: RSS beyond DMP, Telegram, and the social-media half. | Concept doc §§ *Read*, *Live Risk Agent*, *Data sources*; S09, S14 | Two decisions worth carrying: **DMP is registered authoritative, which grants full weight and NOT `confirmed`** (`policy/independence.py` — the database CHECK requires two sources, and faking the count would be false data); and **a police unit is not a place**, because a Dhaka thana is also a neighbourhood, so a thana-wide sweep would otherwise be pinned as one crime. |
| **B11a — original row, kept for the remaining two thirds** | ⏭️ **SKIPPED by the owner, 15 Oct — and the measurement behind that is the useful part of this row now.** 📊 **The pipeline is conversion-limited, not supply-limited.** `live_risk` over 24 h: **59 runs, avg 4.34 documents in, avg 0.19 flags out, 11 flags total.** About **4% of what it already reads becomes a warning** — the rest is lost to the relevance filter (measured precision **0.43**), the gazetteer's 84% Dhaka coverage, and extraction correctly rejecting non-incidents. **Adding sources pushes on the wrong end:** it raises documents fetched, which is cost and competes for `MAX_EXTRACTIONS_PER_RUN = 12` slots, without moving the 4%. What would multiply output is conversion — which is **D04**'s filter and **B7**'s gazetteer, both already named and both already worked on. 🔎 **And there is direct evidence of what one more feed of this kind contributes.** Documents fetched in 7 days: `ittefaq` 98, `jugantor` 74, `channel24` 72, `samakal` 62, `bangla_tribune` 57, `prothom_alo` 54, `ekattor_tv` 15, `dhaka_tribune` 14, `independent_tv` 12, **`dmp_news` 2**. The institutional source this row delivered on 15 Oct produced **two documents in a week** — no criticism of that work, whose deliverable was the survey, but it is the best estimate available for an eleventh and twelfth feed: a trickle. 🔐 **Telegram needs credentials this project does not have** — reading arbitrary public channels is MTProto with an app ID registered to a phone number, not a bot token — plus research to find Dhaka channels that actually carry incident reports. **Still open, unchanged:** **Widen the Live Risk Agent's sources beyond newspapers — the concept document's `social media` and `early signal` half.** Candidate categories, in the order worth trying: public **RSS/Atom** feeds; public **Telegram** channels (a real API, no ToS problem); ~~**official feeds** — DMP traffic, Fire Service, City Corporation~~ *(done 15 Oct, see above)*; and **user reports**, which the concept document names in the same breath as social media and which S29/B13 already covers. Facebook and Instagram page scraping is **last**, not first — see *Why here*. Each new source is one file under `app/ingestion/sources/` plus one line in `SOURCES`. ⚠️ **Two constraints that are not optional:** social and user-generated content is lower-reliability than an edited article, so it must feed the **Rumour Guard tiering (D05)** and must never on its own produce a `confirmed` flag — D01's invariant test already forbids it and would catch an attempt; and scraping public posts about named individuals is a **different privacy surface** from quoting a newspaper headline, so it is governed by concept document §9 and the B14 retention registry, not waved through on "it was public". | Concept doc §§ *Read*, *Live Risk Agent*, *Data sources*; S09, S14 | **Deferred, not dropped — and it was never built.** The concept document promises social media in five places, including the Live Risk Agent's own definition (*"monitors news sites **and public social media pages***"). Both plans narrowed it to three newspaper sites, and `DEMO_PLAN.md` §D04's first checkbox took the concept document's own *mitigation* for social-media access restrictions — the source-agnostic interface — **as the deliverable instead of the thing it was mitigating**. That reading is defensible and it is also how a commitment becomes an abstraction. It sits here rather than earlier because the blocker is **access, not effort**: Facebook and Instagram public-page scraping breaks their terms and is brittle, and X's API is paid — which is precisely why the concept document wrote that risk row. The cheap wins (RSS, Telegram, official feeds) are worth pulling forward the moment anyone has a free afternoon. **Until it lands, do not say the system reads social media.** The honest and demonstrable claim is that ingestion is source-agnostic and a new source is one file. |
| **B12** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** ~~Legacy surface retirement~~ **and the ৳/day cost model.** ✅ **The legacy-retirement half is already done, incidentally, and this row is wrong about it.** S25 asks to *"compare `LegacyRegionalSurface` against chronic flags"* and *"retire or subsume the legacy surface"* — **there is no legacy surface left.** No `LegacyRegionalSurface` anywhere in the tree, and `route_service._get_regional_risk()` — which took the `max` across overlapping police units, so every Dhaka route scored **100** from the `Dhaka Range` row instead of **58.9** from the city row — **was deleted by D06.** `app/scoring/chronic.py` states it in its own docstring: *"D06 deletes that method; this is the replacement."* So the comparison box is **moot**, not pending: you cannot compare against something removed, and the justification for removing it is already written in the module that replaced it. ⚙️ **The cost half is real and unstarted, and smaller than it looks.** **Nothing measures token usage anywhere** — `app/llm/client.py` passes `max_tokens` as a *request* parameter and never reads the response's usage. But there is exactly **one** site where a response arrives (`complete_with_engine`, the `client.chat.completions.parse` call), so instrumentation is one insertion rather than a sweep. The plumbing is the design question: `complete_with_engine` has many callers, so threading usage out through every signature would be invasive — a **context-local tally** that `registry.run_agent` reads at the end of a run and merges into `AgentResult.metrics` changes no caller signature, and `metrics` is already persisted to `agent_runs` and **already surfaced by B9**. ⚠️ **The honesty caveat for whoever builds it:** every configured key is **free-tier**, so the invoice today is genuinely **৳0**. A cost model therefore reports *measured tokens × published list price*, with a dated USD→BDT rate — an estimate built on real usage, which is far better than a guess and **is not a bill**. Label it that way everywhere it appears. | S25 | Needs a full agent fleet to measure. **The fleet now exists and B9 made its metrics readable, so the blocker named here has lifted — what is missing is token instrumentation, not agents.** |
| **B13** | ~~Crowd verification — asynchronous, rate-limited~~ | S29 | **Landed, in the form this row asked for: asynchronous and rate-limited.** Corroboration over *user reports* rather than confirmation of news flags — an hourly agent (`report_corroboration`) clusters independent reports by family, 200 m and a 14-day window, and publishes a count to `community_clusters`. Two reporters is `provisional` at weight 0.3; three is `corroborated` at 0.6; there is **no community-only route to 1.0**, because that number means independent editors agreed. Deliberately **not** `risk_flags`: a flag is a mobility claim and `framing.py` bans the vocabulary a report cluster needs — see Defect 54 in `IMPLEMENTATION_PLAN.md`. The abuse surface this row warns about is handled as far as it honestly can be (distinct accounts, one report per account per cluster, an account-age gate measured against the incident) and the three remaining tiers are listed under S29 with the reason each is absent. The synchronous half — asking a nearby user to confirm a flag — is still open, and is still the part not to rush. |
| **B14** | 🟡 **DECLARED and TESTED, 15 Oct — but nothing has been purged, deliberately.** `app/privacy/retention.py` classifies **all 21 tables**: 6 with a delete window, 15 `KEEP` *with an argument*, because "indefinite on purpose" and "nobody got to it" must be distinguishable. **The load-bearing test is the tripwire, not the windows** — `test_every_table_in_the_database_is_classified` reads the live schema and fails on anything unclassified, which is how **`journeys`** surfaced holding per-user origin and destination (precisely what §9 names) in a table this repo has no code for. Expiry and deletion stay separate and a test enforces it: `expiry_sweep` marks rows `expired` and keeps them, *"because an expired row is the evidence that the surface retires things on its own."* The purge path is **proved, not assumed** — a year-old row is planted, counted, deleted by the script's own predicate, confirmed gone, then rolled back and re-checked on a fresh connection. ⚠️ **4 of 6 windows are `PROPOSED`** and `scripts/purge_expired.py` refuses them without `--force`; a test keeps that set non-empty so nobody quiets the script by flipping a basis. ⚠️ **Not scheduled, by decision** — a cron job deleting user data on a window nobody agreed to is the failure this module prevents. Still open: sign-off; the Storage-video half of `sos_incidents`; account deletion, which `users`/`profiles`/`gd_profiles` all defer to. | S30 | The concept document commits to data minimisation. **It is now testable and the test is honest about what it cannot yet prove**: every window is longer than the project is old, so "nothing is overdue" passes by arithmetic — which is why the deletion itself is proved separately. |
| **B15** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Agent resilience and chaos testing. ✅ **The property this row wants is already structurally enforced, and 15 Oct demonstrated it in production by accident.** `registry.run_agent` wraps every agent in a `try/except` that records a `failed` run and moves on, so one agent cannot take the fleet down by construction. The evidence, from B9's own output: **`report_corroboration` failed 38 consecutive times over several days while the other four agents ran normally** (defect 57), and **`live_risk` reported `partial` with two LLM extraction failures and a database constraint violation in one run and still published flags** (defect 58). The LLM chain already falls through its tiers and raises `LLMUnavailable` only after exhausting them, which is the "kill the LLM" case handled in code. 🎯 **So B15 would not discover whether this works — it would stop it regressing.** Inverse of defect 56: that was an unexercised path nobody tested, this is a heavily exercised path nobody tested. **Three bounded in-process tests would do it, no Docker chaos required:** (1) register a deliberately-exploding agent and assert the others still complete, since `run_agent` is the single path every agent runs through; (2) point the LLM chain at nothing and assert the agent reports `failed` rather than hanging the worker; (3) **the source-abstraction proof** — drop an entry from `SOURCES` and confirm the pipeline degrades rather than breaks. ⚠️ **The third has value beyond the test:** *"remove a source and the system degrades rather than breaks"* is the demonstrable form of a claim already made on stage — ingestion is source-agnostic, a new source is one file — and that claim currently rests on the code reading that way rather than on a proof. See also B11a, which is where "do not say the system reads social media" is recorded. | S31 | Eight agents, each able to fail without breaking the others — the concept document's §5 claim, verified. **Verified in production by accident on 15 Oct; still not asserted by any test.** |
| **B16** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Observability and cost controls, success metrics live. ⚠️ **S32's first bullet is wrong: Sentry is NOT "already in the stack, unused".** There is no `sentry-sdk` in any requirements file, no `sentry` reference in `backend/app` or `frontend/src`, and nothing in `package.json`. What exists is **one settings field**, `SENTRY_DSN: str = ""`, under a `# Monitoring` comment. So this is adding an error-reporting service from scratch, not wiring up something present — **the same "declared reads like built" pattern this sweep keeps finding** (`netinfo` installed and unused before B20's reading, `JWT_ALGORITHM` declared and unread before defect 56, the geofence permissions declared before B6a). 🔒 **And adding Sentry is a privacy decision, not plumbing:** it ships stack traces and whatever context is attached to a third party, in an app governed by concept doc §9 and the B14 retention registry, by an owner who already declined to show users what ingestion discarded. It also needs an account and DSN only the owner can create. 🔁 **Its cost-controls bullet duplicates B12** — per-agent budget caps, cache-hit monitoring, token accounting per run are the same work written into two sprints. Do not build it twice; see B12 for the one-insertion-point finding. 📊 **The §10 metrics split three ways:** *measurable today* — **time-to-alert** (`agent_runs` was built for it; its migration says *"it is also where the demo's 'time from incident to alert' number (D10 Q&A) comes from"*) and **GD completions** (`gd_drafts` exists); *measured once, not instrumented* — **flag precision**, hand-labelled at **0.43** in D04; *blocked on B10* — **false check-in rate**, a Journey Guardian number on `origin/feature/journey-guardian`; *needs client telemetry that does not exist* — **alternative-route acceptance**, and recording which routes users accept is behavioural tracking, so it is another §9 question before it is a feature. | S32 | The concept document §10 metrics, instrumented. **Two of the five are measurable today; one is blocked on a teammate and one needs a privacy decision.** |
| **B17** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Load testing — the ceiling, with numbers. 📏 **Baseline measured 15 Oct, and it is what settles this row:** `auth.users` **3**, `push_devices` **1**, `crime_reports` **8**, `risk_flags` **228** (**32** currently live). S33 asks for *"pilot-zone volume and 10×"* — **ten times three users is thirty**, which a FastAPI container will not notice. There is no measured volume to extrapolate from, so a load test would have to **invent** its target and synthesise the traffic. **No load tooling exists** either: no locust, k6, wrk or artillery anywhere in requirements or scripts. ⚠️ **And the likely ceilings are not in this codebase.** At any realistic Dhaka scale the first three bottlenecks would almost certainly be **Supabase's plan limits**, the **free-tier LLM quotas** (the six per-feature keys B11 is blocked on), and OSRM's single container — account and budget decisions, not code to patch. So S33's *"identify and fix the first three bottlenecks"* would mostly produce an invoice. ✅ **The one genuinely code-side scaling question is measurable today and belongs to B19:** S35 asks about *"map with hundreds of flags"* and the map already holds **228**, so that is a performance budget to measure now, under B19 rather than here. | S33 | **Real work before a pilot; meaningless at three users.** |
| **B18** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Offline capability and battery. ⚠️ **The misleading state this row would fix, stated plainly: with no data connection the map draws nothing and says nothing, which looks exactly like "no warnings near you."** `risk.service.ts` does not catch — `apiService.get` throws — and MapScreen's secondary layers `console.warn` their failures silently. 🔁 **And the device already holds the answer it refuses to show.** B6a's `features/geofence/storage.ts` caches the zone table to AsyncStorage so a background alert needs no network, and its docstring already contains both the pattern and the endorsement: *"Writing the text ahead of time means an alert needs no network, no token and no server. The cost is staleness: the statement is as fresh as the last time the app was open, which is stated in the UI and is the right trade for a warning that has to arrive."* So **offline today, a user walking past a flagged road still gets the notification, but sees a blank map if they open the app.** `@react-native-community/netinfo` is installed and referenced by **no file under `src/`** (found while sizing B20), so offline *detection* is paid for and unwired. 📐 **The bounded version, if this is picked up:** wire `netinfo`, cache the last successful `/risk/flags` payload with the geofence store's pattern, fall back to it on failure, and show an honest banner naming the age — turning a blank map into a stale-but-labelled one, which is the same discipline B9 established. 🚫 **Three things to refuse deliberately, with reasons:** **offline map tiles** means swapping the map library inside `MapScreen.tsx`, 2,257 lines and the source of one stack-overflow crash already; **queued SOS must not be built as a queue** — an SOS that queues is an SOS that *did not send*, and presenting it as sent would be the worst lie this app could tell, so the honest offline SOS is **B20's device-side SMS** and nothing else; and the **battery audit** is a day-long measurement on a real handset, already open under B6a, which is an owner action and not code. Queued *reports* are optional and need duplicate-submission care. | S34 | **The one skipped row with a live user-facing safety consequence, so it is the first to reconsider after D10.** |
| **B19** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Performance and accessibility budgets. 🔴 **Light mode fails WCAG AA, computed from `theme/palette.ts` on 15 Oct — this is measured, not asserted.** Against `bg #F6F9FC`: **`textFaint` `#94A3B8` = 2.43 (FAIL**, AA body text needs 4.5**)**, **`brand` `#0EA5E9` = 2.62 (FAIL)**, `warn` 3.02, `ok` 3.57, `info` 3.88 (all three large-text-only). `text` 16.90 and `textSoft` 7.17 pass. **Dark mode passes throughout**, worst case `textFaint` 4.14. The two failures are the worst possible two: `textFaint` carries the small secondary text where legibility matters most, and `brand` is the primary interactive accent. ⚠️ **B9's System Status screen uses `textFaint` for card metadata like every other screen** — left consistent with the app rather than deviating on one screen, so fixing the token fixes it everywhere at once. 🦯 **Screen reader support is largely absent, and worst where it matters:** **283 touchables** across the app against **18 files** carrying any `accessibilityLabel`; **`accessibilityHint` in 0 files**, `maxFontSizeMultiplier` in 0, `allowFontScaling` in 3. Zero labels in `GdDraftScreen` (33 touchables), `AddReportScreen` (25), **`GuardianScreen` (19 — where SOS is armed and calibrated)**, `EmergencyContactsScreen` (13), `SOSHotWordsScreen` (11). **So a blind user cannot arm SOS, add an emergency contact, or file a General Diary** — which is precisely the premise failure S35 names: *"A safety app that excludes users with disabilities fails its own premise."* 📐 **Scoped version for whoever picks this up:** labelling all 283 is **B20-sized** work across every screen, so do it in three parts — (1) darken `textFaint` and `brand` in the light palette plus a **test computing WCAG ratios from both palettes**, which fits `theme.ui.test.ts`'s existing scanning pattern and makes the fix permanent; (2) label the **safety-critical path only** — Guardian, the SOS flow, emergency contacts; (3) a test that fails on an unlabelled touchable **in those files**, so the rest can be done incrementally without the fixed ones regressing. Performance budgets need device measurement (the map already holds **228** flags, so S35's "hundreds" is reached) and are an owner action. | S35 | **Strongest remaining case of the skipped rows: a measured defect, a safety argument, and a bounded fix — the contrast half costs almost nothing.** |
| **B20** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Full `bn` localisation and SMS fallback for SOS. **Sized before asking, so the next attempt starts from facts:** (1) **no i18n framework exists at all** — not `i18n-js`, not `react-i18next`, not `expo-localization`. The only Bangla in the repo is the GD document text and the voice hot words, which are content, not interface. So this starts from zero: ~**400–500 user-facing strings** across **48 `.tsx` files**, including **101 `Alert.alert` calls**, each typically a title plus a message. (2) ⚠️ **A backend SMS gateway cannot serve the case SMS fallback exists for.** Twilio or SSL Wireless live on the internet; a phone with no internet cannot reach them. **Only device-side SMS works offline** — that is structural, not a preference. (3) The Play Store consequence that follows: silent sending needs Android's `SEND_SMS`, which **Google Play restricts to default-SMS-handler apps**, and "safety app" is not on their permitted-use list — a real rejection risk for **B21**. `expo-sms`'s prefilled composer works fully offline with **no permission**, but costs **one tap**, which degrades B8's verified *"hands never touching the phone"* promise in the offline case only. (4) `@react-native-community/netinfo@12.0.1` **is already a dependency and no file under `src/` references it** — so offline *detection* is paid for and unwired, the same pattern as the geofence permissions before B6a. `expo-sms` is not installed and is an Expo module, so it needs a dev-build rebuild. (5) **Do not let an agent write the `bn` strings and ship them.** Formal legal Bangla in a safety app is not validatable by eye, which this document already says elsewhere, and a mistranslated SOS screen is worse than an English one. | S36 | A Bangla-first product with an English-only UI is a gap worth closing before a pilot. **Largest row in the backlog, and its two halves are unrelated work** — the SMS half is bounded and safety-critical, the Bangla half is large and needs a native speaker's review. |
| **B21** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Store readiness — signed builds, both platforms. 💳 **Needs accounts nobody has bought:** Google Play developer ($25 one-time), Apple Developer ($99/yr), signing keystores, listing content and privacy declarations. None of it is code. 🛑 **HARD BLOCKER ON FIRST SUBMISSION, found 15 Oct — read this before publishing anything.** The app identifier is **`com.Meridian.app`, with a capital M**, consistently in `app.json` (`bundleIdentifier` *and* `package`), `android/app/build.gradle` (`namespace` *and* `applicationId`) and the Kotlin `package` declaration — **while the source directory is lowercase `android/app/src/main/java/com/meridian/app/`.** Two consequences: (1) **an Android `applicationId` can never be changed after the first Play publish** — a different one is a different app, with a new listing, zero installs and no reviews carried over — and the conventional form is all-lowercase, so the capital reads like an artefact of Expo deriving it from `"name": "Meridian"` rather than a decision; (2) **the declared package and its directory disagree in case**, which builds fine on Windows (case-insensitive) and is a latent hazard on Linux CI or a case-sensitive macOS volume. ⚠️ **Deliberately NOT fixed on 15 Oct, and the reason matters:** changing it needs another `expo prebuild --clean` regeneration (one is already uncommitted), and a new package makes the build on the owner's handset a **separate install** requiring a fresh dev build — which would mean re-verifying SOS, geofencing and video eight days before the D10 rehearsal, on a phone where all three are already confirmed working. **Cheap whenever it is done; irreversible if it is missed.** 🍎 **iOS has never been renamed at all** — `frontend/ios/NirapodPoint/` and `NirapodPoint.xcodeproj` are still present, because nothing has ever built the iOS target. Android *was* regenerated by `expo prebuild --clean`, which is why its Java package moved from `com/nirapodpoint/` to `com/meridian/`. 📵 **Also relevant from B20's reading:** a silent-SMS implementation would need Android's `SEND_SMS`, which **Google Play restricts to default-SMS-handler apps** — a rejection risk here. Moot while B20 is skipped; live again the moment it is picked up. | S37 | ~~Also where the **NirapodPoint → Meridian rename** must finally complete: `frontend/ios/NirapodPoint.xcodeproj` and `com.nirapodpoint.app` are still the native identifiers.~~ **Updated 15 Oct: Android is renamed (to a capital-M identifier that needs fixing first); iOS is not.** |
| **B22** | ⏭️ **SKIPPED by the owner, 15 Oct — offered for consent, declined, and left in the backlog unchanged.** Pilot preparation, pilot launch, operate and expand. **Not a sprint; the phase after launch.** It needs a **published app** (B21, which needs paid developer accounts), **20–50 pilot users** against the current **3**, and an **on-call rotation between two people** for a service with no users on it yet. S40+'s expansion is explicitly gated on **gazetteer density, not engineering capacity** — B7's open national remainder — and its institutional engagement is gated on proven precision, because *"a bad blackspot report to an authority is worse than none"* (currently 0.43). ✅ **One box is already part-written, by accident.** S38's first item is an **operational runbook** — *"agent failure, bad flag, LLM outage, cost spike, data incident. Who does what, with what command."* **B9 wrote the agent-failure entry on 15 Oct**: `docs/RUNNING.md` §8 carries the command, how to read every column, and the three failure signatures with the action for each — `FAIL` with error text, **`LATE` with a healthy last status (the agent is not failing, it is not being asked — check beat)**, and `STUCK` (nothing will retry it). That is one of five entries, written because the tool needed documenting rather than because the runbook was planned. ⚠️ **The remaining four are worth writing against a real incident history, not from reasoning** — a runbook is written *for* an on-call rotation, and one written before there is a service to be on call for is a document nobody has tested. | S38–S40+ | The original plan's Phase 7, unchanged. |

**B0 is not optional and is not last.** It is listed first because it is outstanding owner action on
a live security incident, and because deferring it has already cost more than doing it would have.

---

# 7. Open decisions

One left. The first is closed.

**7.1 — The reasoning layer for image analysis. ✅ RESOLVED 2026-10-09 —
[ADR 0006](docs/adr/0006-d07-vision-pipeline.md), accepted.**

**Cues, not categories.** A vision-language model reports which fine-grained physical cues are
visible; **our code** maps cues to a candidate category; **the reporter confirms**, so the filed
category is always human. Three tiers behind one chain, all measured on 2026-10-09:
`gemini:gemini-3.5-flash-lite` (**≈2.0s**) → `replay:vision_replay.json` (deterministic, offline) →
`ollama:qwen3-vl:4b-instruct-q4_K_M` (**≈8–9s** on an unseen photo, offline, no safety filter).

> **The earlier recommendation here was "local detection plus Claude vision". It was wrong on both
> halves**, and the reasons are worth keeping because they are the argument to a judge.
>
> *Claude vision* — **there is no Anthropic key.** The option was never available.
>
> *Local detection as the base* — the vocabulary gap is **not closeable by adding a reasoning layer
> on top.** 11 of the engine's 21 object signals are not COCO classes, so YOLOv9c can never emit
> them; feeding its detections to any model forwards a vocabulary that is already missing the
> evidence. The fix was to stop asking a detector to name crimes at all.
>
> It also mistook the real limit. **A photo cannot establish a crime** — not intent, not consent, not
> who started it, not whether it is a film shoot. The inherited design decided anyway and hid it
> behind arithmetic. Replacing the arithmetic with a better model would have kept the error.
>
> And the surprise: a **frozen** VLM is state of the art. ASK-HINT (WACV 2026) trains nothing and
> beats the best fine-tuned method on UCF-Crime, with **over 20 AUC points** coming from prompt
> design alone. "Use a VLM and prompt it well" is the frontier, not the shortcut.

**7.2 — Police routing. ✅ CLOSED 2026-10-10 by ADR 0007.**

`POLICE_ROUTING_ENABLED` **stays `false`**, and the answer to "why" is not a shortage of time — it
is that **there is nothing to transmit to.** Bangladesh Police has no public API, no developer
portal and no partner process; the only API that exists anywhere is the internal one between Online
GD and CDMS++. And a cognizable offence cannot be closed online in any case: the applicant must
appear at the thana with a printed copy.

So **routing means naming the right thana on the document**, not sending anything. The thana name
is shown; `police_stations.csv`'s `email` and `phone` columns are **never displayed** — 607 rows
carry one address and one number. The coordinates are real and are what the
lookup uses. If a real contact list is ever obtained this becomes a data change, not a code change.

> ✅ **Strengthened 2026-10-15 by defect 17, which this section had quietly already settled.**
> Defect 17 was still open and marked *"blocked on data — the owner is sourcing real DMP
> contacts"*, for a deliverable **this decision had cancelled five days earlier**: real contacts
> would not give the police anywhere to receive an email. Nobody re-read the defect after writing
> §7.2. Closed on that basis.
>
> Three things changed, none of them about contacts. `thana.py` is **scoped to Dhaka city** (the
> 51 `district == "Dhaka"` rows, verified to be exactly DMP and no upazilas) instead of all 607.
> Five rows the file marks `legacy — unverified` are now **nameable but not rankable** — `Turag`'s
> coordinate sits 1.7 km from Rampura and `Hatirjheel`'s 4.4 km from Pallabi, checked against the
> file's own trusted rows. And a point more than **25 km** from any Dhaka station now gets *no*
> thana rather than a confident one — Chattogram is 200.9 km from the nearest DMP station and used
> to be answered.
>
> The sentence above — *"a data change, not a code change"* — is now enforced rather than
> promised: `sos_service` measures whether the contact column is per-station and **refuses to
> email even with `POLICE_ROUTING_ENABLED` forced true**. Real contacts would pass that check on
> their own.

> ⚠️ **PARTLY REVERSED 2026-10-15 by the owner. `POLICE_ROUTING_ENABLED=true` now.** This
> section, and the addendum above it, over-reached — and the refusal the addendum is so pleased
> with was the over-reach made mechanical.
>
> **What stands:** everything about *filing*. There is no police API, no partner process, and a
> cognizable offence cannot be closed online — the applicant appears at the thana with a printed
> copy, which is why `thana.py` names the station on the GD. That reasoning is untouched.
>
> **What was wrong:** §7.2 concluded from "we cannot *file* with the police" that we must not
> *tell* them anything, and the two are not the same act. An email to a thana inbox during an
> emergency is a notification. It needs no API and no partner process, and the owner asked for
> it — the single shared address in the CSV was them wiring up a destination they could watch.
> The code then refused *that*, which made the data owner unable to test their own data.
>
> **What runs now.** An SOS adds **one** address: the nearest Dhaka city thana to the caller's
> live coordinates, chosen by the same `thana.nearest_thana` that prints the station on the GD —
> so the station told and the station named cannot disagree. One station, not a 5 km radius,
> because one incident has one officer-in-charge and six thanas each assuming another is
> responding is worse than one being told. Outside Dhaka city: no station, silently and by
> design. `POLICE_ROUTING_ENABLED` is the only gate, and the code default stays `false`.
>
> **The real hazard was never placeholder data, it was defect 31's:** routing unconditionally on
> while every row held a *stranger's* address (`noorlabib@iut-dhaka.edu`), so every SOS test
> emailed an uninvolved third party. The column now holds the owner's own address, so the only
> inbox reachable is theirs. `_check_contacts_are_per_station` still measures the repetition and
> now **logs it on every send** instead of refusing. Replace the column with real per-thana
> addresses before anyone outside the team relies on this — still a data change, not a code one.

Research: `docs/reference/gd-formats.md`. Decision: `docs/adr/0007-d08-casework-gd.md`,
**partly superseded on police routing** — see that file's Decision 3.

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
| **Bangla output is subtly wrong, or renders as boxes.** | Formal legal Bangla is not validatable by eye the night before, and PDF base fonts have no Bengali glyphs. **ADR 0007 made this worse:** one narrative now serves both the printed form and the online app, so if the Bangla is wrong there is nothing else carrying the draft. | Native-speaker sign-off is a D08 *gate*, and now a load-bearing one. The font is an explicit D08 task. **Arrange the reviewer in §9, before the 20th.** Model chosen by measurement, not reputation — ADR 0007: `gemini-3.5-flash-lite` wrote correct place names and Bangla numerals 12/12; `gpt-oss-120b` mangled Motijheel and Kakrail and left dates in Latin script. |
| **D07 overruns.** | §7.1 is taken, and most of the sprint is deletion — but **the evidence photo is the first storage write in the codebase** (no bucket, no image column, no precedent), and **neither model has been shown a photo that should flag.** Those are the two unestimated pieces. | Three tiers, so no single failure kills beat 6 (ADR 0006's failure matrix). The eval set is §9.3, started now and off the baton. If D07 slips, cut to **"describe and persist"** — drop the proposed category, keep the description and the stored photo. The honest version is still showable. |
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
3. **The eval set — D07.** 30–40 images. Currently 2, **and both are benign** — so today's numbers
   measure abstention and nothing about detection. **This is now the single hardest D07 gate**, and
   the only thing that will say whether either model recognises a real confrontation. Extract frames
   from UCF-Crime or SCVD **at full resolution** — the convenient pre-extracted Kaggle frames are
   64×64 and useless to a VLM — and record the licence: **CC BY-NC-SA is non-commercial**, fine for a
   hackathon eval set with attribution, not if Meridian ships.
4. **Line up a native Bangla speaker for D08**, for the 20th or 21st. It is a gate on that sprint and
   it depends on someone else's calendar.

Items 1–3 are data files only. Item 4 is a conversation. None of them touch code.
