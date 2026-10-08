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

*Last updated: 2026-10-08 · by: Farhan Ishraq (Claude Code) · after: D04 (built; device walkthrough pending)*

| | |
|---|---|
| **Last sprint completed** | **D03 — ✅ closed.** **D04 — 🟡 built and verified on the backend; [`docs/walkthroughs/D04.md`](docs/walkthroughs/D04.md) not yet run on a device**, which is the one gate left. All 14 D04 checkboxes ticked in [DEMO_PLAN.md](DEMO_PLAN.md) |
| **NEXT SPRINT** | **Finish D04's gate**: run `docs/walkthroughs/D04.md` on the phone in Dhaka daytime, capture the replay (step O1), commit it. **Then D05 — Verification you can see** (Oct 15) → [DEMO_PLAN.md](DEMO_PLAN.md) §D05, source S15 |
| **Baton holder** | **Farhan Ishraq** |
| **Trunk** | Work branch **`ishraq-dev`** (cut from `main` @ `99922ec`). By agreement, commits go only to `ishraq-dev`; nothing is pushed to or merged into `main` from this side |
| **Build status** | 🟡 **193 backend tests passing in `tests/invariants` + `tests/test_ingestion_sources.py` (185 invariants, 64 new; 1 skipped until a replay is captured), `mypy --strict` clean on `app` (80 files), `ruff` clean on every D04 file, `tsc` clean, 45 jest, ESLint 0 errors / 106 warnings (budget 106, none added).** Pre-existing and unchanged: ~320 `ruff` findings in old code, 2 failures in `tests/test_crime_vision.py`. **Fixed in D04:** the `migrate.py` "drift" that was only line endings — `up` works again |
| **Slack** | D04 was scheduled Oct 13–14 and built Oct 8. **Spend the slack on §9** — the OSRM graph (D06) is still the long pole and still not started |
| **Phase** | 0 — Foundation & Contracts |

### 🟡 D04 BUILT — today's news reaches the map; the phone run is the last gate

**2026-10-08, Farhan Ishraq with Claude Code, on `ishraq-dev`.** Full entry in the Handoff Log. In one
paragraph: a `worker` container (Celery + beat) runs the **Live Risk Agent** every 15 minutes. It
lists three outlets' sitemaps (Ekattor TV, Independent TV, Channel 24 — chosen by checking all ten
channels in `top_10_bangladesh_news_channels.md`), filters headlines for incident vocabulary, reads the
survivors politely (robots.txt, 3 s per host, Playwright only for Channel 24), asks Gemini on the new
**EXTRACT** key for Dhaka mobility incidents, resolves places **gazetteer-only**, and writes
`unconfirmed` single-source flags with framed statements. The map's status pill (now visible,
bottom-left) shows "news N min ago" with refresh and **fetch news now**; the flag sheet shows outlet,
headline, age and a link to the article. The offline demo serves a captured replay
(`live_replay.json`) through the seeded surface.

**Verified without a device:** a real run against the live sites, Gemini and Supabase (367 listed, 4
relevant, 4 read, 0 Dhaka road events at 04:25 Dhaka time — correct); the publish path against the real
schema in a rolled-back transaction (`রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়` → *Road blocked near
Mirpur-10 Circle.*, served by `DbRiskSurface`; a fabricated place → `unresolved_location`, no flag).
**Not yet done:** the walkthrough on the phone, and the replay capture — which needs live flags, so it
needs Dhaka daytime.

### ⚠️ One decision is open and it is a one-line change

**Should the `GEO` LLM fallback exist at all?** `LLM_CHAIN_GEO` still ends in
`groq:openai/gpt-oss-120b`. Measured over the 53-case set:

| | If Gemini is unavailable |
|---|---|
| **Keep it** | 95.6% accuracy but **1 fabrication** — the discard invariant holds only while Gemini is up |
| **Drop it** | gazetteer only: **93.3%**, **0 fabrications**, and **no network at all** |

Recommendation is to **drop it** — 2.3 points is not worth a fabrication when "a wrong pin is worse
than no pin" is the invariant a judge is most likely to test, and the degraded path then needs no
network, which is the venue-failure story. Adding a second *Gemini* model does not help: same
provider, same rate limit, and `gemini-3.1-flash-lite` fabricates too. **Left open deliberately —
owner's call.** Full numbers in `docs/walkthroughs/D03.md` § *Model selection*.

### 🔑 The LLM tier runs on free endpoints, not Anthropic

**This project has no Anthropic key.** `ANTHROPIC_API_KEY` is in `.env.example` and absent from
`.env`, so `DEMO_PLAN.md` §7.1's claim that *"the key is already configured"* was wrong — that matters
because **D04, D07 and D08 all assume an LLM is available.**

**D04 update:** ingestion has its own key now, `GEMINI_KEY_EXTRACT_ONE`, from a separate Google
project (Gemini's free quota is per project, not per key), on `LLM_CHAIN_EXTRACT` (Gemini only).

What exists instead, and it works: `GEMINI_KEY_GEO_ONE` and `GROQ_KEY_GEO_ONE`. Both Gemini and Groq serve the
OpenAI Chat Completions wire format, so `app/llm/client.py` uses the `openai` SDK and reaches either
by changing a base URL. Configuration is **per feature**, not global — `LLM_CHAIN_GEO` picks the
models and `<PROVIDER>_KEY_GEO_*` the keys:

```
LLM_CHAIN_GEO=gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b
```

Keys are discovered from **every** variable named `GEMINI_KEY_*` / `GROQ_KEY_*`, so adding a second
account's key widens the daily quota with no code change. Quotas: 500 requests/day on the Gemini
model, 1,000/day on the Groq one, different providers so independent.

**§7.1's D07 recommendation ("local detection plus Claude vision") needs revisiting** — there is no
Claude key to spend. Gemini's flash-lite models are multimodal and free, which is the obvious
substitute, but that is a decision, not a fait accompli. **Still due 17 October.**

### 🗓️ PLAN RESEQUENCED — read [DEMO_PLAN.md](DEMO_PLAN.md) before IMPLEMENTATION_PLAN.md

**2026-10-07, Nakib, without Arafat's sign-off.** The finale is **24 October** — 17 days — and
`IMPLEMENTATION_PLAN.md` line 6 disclaims that deadline. Phase 0 alone would have finished four days
*after* the demo, with 0 of 8 agents built.

- **[DEMO_PLAN.md](DEMO_PLAN.md)** is now the authoritative **sequence**: ten sprints, `D01`–`D10`.
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** remains the authoritative **specification**.
  Every `D` sprint cites its source sprint there. **Nothing was deleted from it.**
- Everything not demo-critical is in `DEMO_PLAN.md` §6 as **Track B**, in order. §5 is a coverage
  table mapping all 39 original sprints, so "nothing was dropped" is checkable.
- Rationale, consequences and alternatives: **[ADR 0005](docs/adr/0005-finale-reordering.md)**.
- **Crime detection from image is in the demo** (`D07`), against plan §12. Owner's call.
- Prototype Gate relaxed to gates 1 and 4 only until 24 Oct, **plus one new mandatory gate:**
  **every `D` sprint ships `docs/walkthroughs/D<nn>.md`** — a play-script run on a real device, in
  the same commit. No walkthrough, no handoff. Format: [`docs/walkthroughs/README.md`](docs/walkthroughs/README.md).
  Rationale in `DEMO_PLAN.md` §0: work that is invisible on the device is indistinguishable from
  work that does not exist.

**Blocked decision:** the image-analysis reasoning layer must be settled by **16 October** or `D07`
cannot start. See `DEMO_PLAN.md` §7.1 — recommendation is local detection + Claude vision.

### ✅ D03 CLOSED — gate met on a real device, three days early

**2026-10-08, Nakib.** [`docs/walkthroughs/D03.md`](docs/walkthroughs/D03.md) was run end to end on an
iPhone in Expo Go and **all 14 steps passed**, including the three that matter most: the demo's own
phrase "Mirpur 10 golchattar" resolving, the same phrase in Bangla script resolving to the same place,
and three different kinds of refusal rendering as an explicit "could not find that place" rather than
a wrong pin.

**D03 was scheduled Oct 11–12 and closed Oct 8**, which with D02's two days makes **five days of
slack**. `DEMO_PLAN.md` §8 names schedule slip as the likeliest failure and states there is none.
Five days is not a licence to add scope — the OSRM graph (§9 item 2, D06 assumes it is built) has not
been started and is now the long pole.

**Shipped**

| | |
|---|---|
| Gazetteer | `backend/data/gazetteer/dhaka_central.json` — **1,022 entries** harvested from OpenStreetMap by `scripts/harvest_gazetteer.py`. `aliases.json` — **100 hand-written aliases over 22 entries** |
| Matcher | `app/geo/gazetteer.py` — exact, then token-subset, then fuzzy. Folds Bengali digits to Latin |
| LLM client | `app/llm/client.py` + `models.py` — one `openai` SDK reaching Gemini and Groq, key rotation, **per-feature** chains and key pools (`LLM_CHAIN_GEO`, `GEMINI_KEY_GEO_*`) |
| Agent | `app/geo/agent.py` — gazetteer → LLM → **discard** |
| Endpoint | `POST /api/v1/geo/resolve` |
| Frontend | `components/PlaceSearch.tsx`, `services/geo.service.ts`, `types/contracts/geo.ts`, wired into `MapScreen` |
| Eval | `scripts/eval_geocoding.py` over a 53-case held-out set, with committed baselines |

**The gazetteer did not have to be typed by hand, and that is the main finding.** §9 item 1 called it
"pure data entry… whoever is not holding the baton should be doing this" and budgeted it as the long
pole. It is not, because **OpenStreetMap's Dhaka coverage is Bangla-primary**: `name` holds the Bangla
form and `name:en` the romanisation, already paired, on 98% of features in the pilot box. Both halves
of every entry plus coordinates came for free. What could not be harvested is the **alias layer** —
`alt_name` exists on about 40 of 782 features — and that is the part worth having.

Two sources were measured and rejected first: **GeoNames** has 493 rows in the box and only **11** with
any Bengali name, all of them large obvious things (Dhaka, the airports, the university, a river) and
**four** road junctions in the whole city. The administrative datasets everyone links to
(`nuhil/bangladesh-geocode` and friends) stop at union level, where **all of Dhaka city is one row**.

**Measured numbers** — `scripts/eval_geocoding.py`, baselines committed:

| | Gazetteer only | Gazetteer + LLM |
|---|---|---|
| Accuracy on real places | **93.3%** | **100%** |
| Correct refusals on fakes | **100%** | **100%** |
| **Fabrications** | **0** | **0** |
| Median error | 6 m | 6 m |

The 93.3% column is the one that matters for the venue: it needs **no network at all** beyond the local
API. "Fabrications" — coordinates returned for a place that does not exist — is the number to quote in
Q&A, not accuracy.

**Model selection was measured twice, and the second pass overturned part of the first.** The
six-case probe gave `gemini-3.5-flash-lite` **6/6** (primary), `openai/gpt-oss-120b` 4/6,
`gemini-3.1-flash-lite` 5/6 but **rejected** for fabricating, `qwen/qwen3.8-27b` 1/6 disqualified.

Six cases was too thin to choose a fallback on. Over the **full 53-case set**, `gpt-oss-120b` alone
scores **15.6%** on real places with **2 fabrications** — 4/6 was flattering, and 25 of 45 real places
came back confidently wrong. As the system's only model (gazetteer still in front of it) it reaches
95.6% and **1 fabrication**, but that 95.6% is almost entirely the gazetteer: 42 of 53 cases never
reach a model. It invented coordinates for **"Gulshan 97 golchattar"**, a circle number that does not
exist.

**So there is an open decision, deliberately left open:** `LLM_CHAIN_GEO` still ends in
`groq:openai/gpt-oss-120b`. Keeping it means 95.6% with 1 fabrication if Gemini is down; dropping it
means gazetteer-only — **93.3% with 0 fabrications and no network at all.** Recommendation in
`docs/walkthroughs/D03.md` is to **drop it**: 2.3 points is not worth a fabrication when "a wrong pin
is worse than no pin" is the invariant a judge is most likely to test. **Owner's call.**

**Three bugs found while building, none by a pre-existing test**

1. **The matcher resolved "Sector 11" to "Sector 10"** at 0.89 confidence. One character apart, two
   places 2 km apart — the wrong-pin failure the discard invariant exists to prevent. **Numbers are
   now identity, not spelling:** digits must match exactly, letters may be misspelt. Found by typing
   it, not by a test.
2. **The gazetteer refused "Farmgate" and "Motijheel".** OSM lists each in two layers ~270 m apart,
   and the duplicate check compared names without looking at distance — so the invariant was failing
   in the direction that *costs* a real place. Same name within 1 km now merges; only genuinely
   distant collisions (Uttara's and Bashundhara's "Sector 11", 10 km) are refused. 123 entries are
   flagged ambiguous and refused on purpose.
3. **The LLM tier was overturning the gazetteer's ambiguity refusals.** The gazetteer declined
   "Sector 11" correctly, and the model then answered Uttara's with confidence — our own guard was
   bypassable by the weaker tier beneath it. **Found by the eval set, not by a test**, because it only
   shows up when you score refusals as outcomes. "We have never heard of this" and "we refuse this on
   purpose" are now different code paths, and the second does not consult the model.

**A fourth, which I caused and the code caught**

Three hand-written aliases (`গাবতলী`, `কাপ্তান বাজার`, `Nilkhet`) duplicated **other entries'** real
OSM names. The effect is quietly backwards: the query becomes ambiguous and the matcher refuses, so an
alias added to *help* a lookup silently broke it. The harvest cannot see this — it merges duplicates
before aliases are merged — so `_warn_about_alias_collisions()` now runs at load time and an invariant
test fails on it. It found all three the moment it was written.

**A fifth, found by the 53-case benchmark rather than by any test**

`gpt-oss-120b` returns `json_validate_failed` with empty output on roughly 1 in 10 calls, and
`app/llm/client.py` **raised** on it, because a 400 is normally a bad request from us. The first
benchmark run died on it. In production the same thing — Gemini rate limited, request falling through
to Groq — would have turned a map search into an HTTP **500** rather than an honest "could not find
that place". Model-side 400s (`json_validate_failed`, `tool_use_failed`) now fall through to the next
option while genuinely bad requests from us still surface, and two invariant tests pin both halves.

**Two more found only by running it on the phone — this is §0 earning its place again**

1. **The container would not start: `ModuleNotFoundError: No module named 'openai'`.** The dependency
   *was* declared correctly (`requirements.txt` includes `requirements/agents.txt`, which has it), but
   the Dockerfile keeps requirements in their own cached layer so code edits rebuild instantly, and
   `run.ps1` runs a plain `docker compose up -d`. The image therefore came up with D01's packages.
   **`.\scripts\run.ps1 -Rebuild` once** fixes it, and D03's walkthrough now says so as a
   precondition. Any sprint that adds a package needs it.
2. **Route mode had no reachable exit.** The button that leaves route mode was positioned *inside* the
   route-search card, which carries `zIndex: 10` / `elevation: 8` against the button's `4` — so it lost
   every stacking contest and could not be tapped. `toggleRouteMode` is the only exit, so a reload was
   the only escape. **This would have stranded the demo if anyone had tapped navigate on stage.** The
   close control now lives in the card's own header as a small ✕, and the floating button only
   *enters* route mode.

   Worth noting how it was fixed, because the first attempt was wrong: raising the button's z-order
   made it reachable but left a 56 px red circle sitting on top of a text field. Reachable and still
   wrong. A close control belongs on the thing it closes.

   `tsc`, ESLint and Jest were green throughout both. Z-order and reachability are not things they can
   see, and neither is a missing package inside an image.

**Deliberately NOT done**

- **`scripts/gazetteer_review.py`** (S10's add/review/audit tool). Not a D03 checkbox. Reviewing is
  editing `aliases.json`, which is small and readable. Track B.
- **Nominatim.** `GeoResolution.method` allows it; D06 owns the proxy.
- **The other ~1,000 entries are `reviewed: false`** and resolve on their own OSM names. 22 reviewed
  is the honest number, which is why `reviewed` is a field rather than an assumption. B7 extends it.
- **Cloudflare Workers AI**, although a token is in `.env`. It is a shared 10,000-neuron pool across
  every model, its Bangla-capable options are weak, and it is a third wire format for no gain.

**Gotchas for whoever is next**

1. **`data/gazetteer/dhaka_central.json` is generated. Never hand-edit it** — `harvest_gazetteer.py`
   overwrites it. Hand work goes in `aliases.json`, which is never generated. That split is the only
   thing protecting the alias layer.
2. **An entry listed in `aliases.json` counts as `reviewed: true`.** The flag cannot live in the
   generated file, because a re-harvest would erase it.
3. **Public Overpass mirrors are genuinely unreliable.** One query succeeded against a mirror and the
   same query timed out against all three twenty minutes later. The harvest caches raw answers in
   `backend/data/gazetteer/.osm-cache/` (gitignored) so a re-run resumes. **Not a demo dependency** —
   the JSON is committed.
4. **ODbL.** The gazetteer is OpenStreetMap data. Attribution is in the `_README` block and an
   invariant test fails if it is removed. If this is ever published as a dataset it goes out under
   ODbL too.
5. **A new Python dependency means the Docker image must be rebuilt: `.\scripts\run.ps1 -Rebuild`.**
   D03 added `openai` to `requirements/agents.txt`. The Dockerfile keeps requirements in their own
   cached layer so code changes rebuild instantly, and `run.ps1` runs a plain `docker compose up -d` —
   so the container came up with D01's packages and died at `import openai` with
   `ModuleNotFoundError`. The dependency was declared correctly; the image simply predated it. **This
   cost a failed start on the first attempt at D03's walkthrough.** Any sprint that adds a package
   needs `-Rebuild` once.
6. **Always start with `.\scripts\run.ps1`, never a bare `docker compose` command.** `run.ps1` also
   sets `EXPO_PUBLIC_API_BASE_URL` to the LAN IP, which is the only reason the *phone* can reach the
   API. D03's walkthrough originally said `docker compose up -d --force-recreate api`, copied from D02
   without the reason D02 needed it, and that would have left the app pointing somewhere unreachable.
7. **`.env` needs `--force-recreate`, not `restart`** — unchanged from D02, and it bites every time.
8. **Free-tier quota resets at midnight Pacific** for Gemini. Do not run a few hundred LLM queries on
   the 23rd.
9. **2 pre-existing failures in `tests/test_crime_vision.py`** (PIL cannot decode the seed fixtures).
   Not D03's, present before it, and D07 will have to deal with them.

**Prototype Gate: met.** 121 invariant tests passing (35 new), `mypy --strict` clean on `app`
(67 files), `ruff` clean on every D03 file, `tsc` clean, 45 jest tests, **0 ESLint errors** — D03's
three new frontend files lint completely clean, and `MapScreen.tsx` had 6 warnings before D03 and has
6 after, so none were added. **Walkthrough run on a real device, all 14 steps.**

*(A note on a claim in D02's handoff: it quoted "6 pre-existing ESLint warnings", which was a
changed-files-only count. Project-wide `eslint src` reports 105, all pre-existing. The narrower number
read as broader than it was.)*

---

### ✅ D02 CLOSED — gate met on a real device, two days early

**2026-10-07, Nakib.** [`docs/walkthroughs/D02.md`](docs/walkthroughs/D02.md) was run end to end on an
iPhone in Expo Go and **every step passed**, including the two that matter most: severity-now differing
from severity-when-observed, and flags disappearing as the time control moves forward and returning
when it goes back. The 212 flags are applied to the owner's live Supabase project.

**D02 was scheduled for Oct 9–10 and closed on Oct 7.** That is the first slack this plan has had —
`DEMO_PLAN.md` §8 names "the schedule slips" as the likeliest failure and says plainly there is none.
Two days is not a licence to add scope; it is the buffer D10 was supposed to be.

**Verified:** 86 invariant tests passing (36 new), `mypy --strict` clean across 60 files, `ruff` clean
on everything D02 touched, `tsc` clean, 45 jest tests, 0 ESLint errors. Decay measured on the seeded
surface: **191 flags live now, 149 at +3h, 137 at +6h, 108 at +12h, 64 at +24h, 28 at +48h, 24 at +30
days** — unattended, with no cleanup job running.

**Two bugs were found getting to the device, neither by a test.** Both are in the D02 handoff entry
below. The short version: the seeder crashed when run from the repository root because the surface
factory had been put in `app/scoring/__init__.py`, which made every import of the package require a
database URL; and `.\scripts\seed.sh` does not run in PowerShell at all — it returns silently and
changes nothing, so a stale 22-flag fixture file read as a successful regeneration. 86 tests, `mypy`
and `ruff` all passed throughout, because pytest runs with `backend/` as its working directory. The
failures needed someone to run the documented command from the documented place.

---

### ✅ D01 CLOSED — gate met on a real device

**2026-10-07, Nakib.** [`docs/walkthroughs/D01.md`](docs/walkthroughs/D01.md) was run end to end on an
iPhone in Expo Go and **every step passed**. Migrations and fixtures are applied to the owner's live
Supabase project; the SOS path was exercised against it, with a delivered email and a real
`sos_incidents` row.

**Two bugs were found by running it that nothing else would have found,** and both are fixed below:
the map was a blank white page on iOS, and one SOS froze the entire API for 2 minutes 34 seconds. Both
were invisible to `mypy`, `ruff`, 34 invariant tests and a verified database. That is the §0 rule
paying for itself in its first sprint.

**Applying the schema, for anyone rebuilding:** `psql` is not installed on this machine, so
`.\scripts\seed.sh` without `--sql` cannot apply anything — it detects that and prints the manual
steps. `.\scripts\seed.sh --sql` writes numbered files to `.seed-sql\`; paste `2-migrations.sql` then
`3-fixtures.sql` into the Supabase SQL Editor. `1-schema.sql` is the already-applied baseline and
`4-verify.sql` predates D01's tables. **Regenerate `3-fixtures.sql` rather than reusing a copy** — its
timestamps are relative, so an old file seeds a map of expired flags. `migrate.py up` connects
directly over asyncpg if you prefer that to pasting.

**What landed:**

| | |
|---|---|
| Migrations | `scripts/migrate.py` (forward-only, checksummed, with a paste-ready `sql` mode), `risk_flags` with the decay + verification CHECKs, `raw_documents`, `extracted_incidents`, `agent_runs` |
| Contracts | `app/contracts/{risk,surface,agents}.py`, mirrored in `frontend/src/types/contracts/` |
| Policy | `app/policy/framing.py` — the sole writer of `RiskFlag.mobility_statement` |
| Surface | `DbRiskSurface` behind the `RiskSurface` protocol; `GET /api/v1/risk/flags?bbox=&as_of=`. **`as_of` is functional, not a placeholder** — it filters on the derived `expires_at`, so 20 flags now becomes 16 at +6h, 10 at +12h, 4 at +48h. Severity-on-read is still D02 |
| Fixture | 22 sample Dhaka flags, structured fields only; statements derived through `framing.py` at load |
| Frontend | Map risk overlay (pins + radius circles, colour by severity), status pill, **defect 3** |
| SOS | **Defect 35** — every trigger now writes a row to `sos_incidents` |
| Tests | `tests/invariants/` — 34 tests, 2 invariants |
| Build | `requirements/{base,ai,agents,dev}.txt` — **defect 15** |

**Verified:** `mypy` clean across all 54 backend files · 34 invariant tests pass · frontend `tsc`
clean, `jest` 45/45 · both migrations and the fixture applied to a throwaway **PostGIS 16** container
from an empty database, with every CHECK constraint confirmed to reject bad data · the API booted
against that container and `GET /api/v1/risk/flags` served 20 flags, rejected four classes of bad
bbox with 422, and returned fewer flags for a future `as_of` · `sos_service._record_incident` wrote a
real row, with coordinates round-tripping un-swapped and no email addresses stored.

### 🐛 Found while testing, not while reading: PostGIS was unreachable for every ORM write

**`search_path` is now set on the engine** — `app/core/database.py`,
`connect_args={"server_settings": {"search_path": "public,extensions"}}`.

Supabase installs PostGIS into `extensions`, and **geoalchemy2 emits PostGIS functions
unqualified**: an insert into a `Geography` column renders as `ST_GeogFromText($1)` with no schema.
Without `extensions` on the path that fails with

```
function st_geogfromtext(unknown) does not exist
```

and the write is rolled back.

This has been latent since S01 and could not have been noticed, because **nothing had ever written to
a geography column**: `sos_incidents` was never populated — that *was* defect 35 — and
`user_locations` still is not. D01's first write found it immediately. It also means
`endpoints/tracking.py` would have failed the same way the moment anyone used it.

Raw SQL in `app/scoring/surface_db.py` qualifies `extensions.ST_*` explicitly and never depended on
the path. Both now work, deliberately: if a pooled connection ever comes back with a different
`search_path`, the risk surface keeps serving.

### 🐛 Found on the device: the map had never rendered on iOS

**`MAP_PROVIDER` now replaces `PROVIDER_GOOGLE`** in every screen — `src/components/MapComponent.tsx`.

All three map screens (`MapScreen`, `AddReportScreen`, `ReportDetailsScreen`) passed
`provider={PROVIDER_GOOGLE}` unconditionally. On iOS that forces the Google Maps SDK, and **Expo Go
for iOS does not ship it**. `MapView` mounted, laid out and drew nothing: a white rectangle, no error,
no warning, markers invisible on top of it.

`app.json` carried the literal string `"YOUR_GOOGLE_MAPS_API_KEY"` for both platforms. Those
placeholders are **removed** — they were never going to work and would have silently broken an Android
development build in exactly the same way, with the same absence of an error message.

The provider is now Apple Maps on iOS (no key, works in Expo Go) and Google Maps on Android. The two
platforms therefore look different, which is a visible consequence worth knowing before the 24th.
Matching them means a paid Google Maps key **and** a development build — a credentials decision, not
an engineering one, and not needed for the demo.

**This is the case for the §0 walkthrough rule in one line.** The risk surface, the endpoint, the
schema, the framing invariant and the flag count were all correct and verified — and on a phone the
map was a blank white page. A green test suite could not have told us.

### 🐛 Found on the device: one SOS froze the entire API for 2m34s

**Owner approved going outside D01 for this.** It blocked the D01 gate: walkthrough step 12 cannot
pass if beat 9 takes two and a half minutes and kills the map while it runs.

`email_service.send_sos_alert` was `async def` but called `smtplib` **synchronously**. `smtplib` is
blocking, so it did not block that request — it blocked the single event loop every request shares.
Measured on a real SOS: **2 minutes 34 seconds** between "Video attached" and "SOS alert sent", during
which `/health` timed out and `GET /risk/flags` could not be served. On stage that is the map dying
mid-demo.

Two causes, both fixed:

| | |
|---|---|
| **Blocking SMTP** | `await asyncio.to_thread(self._send_blocking, msg)`. The attachment read and base64 encode moved off the loop too — same class of bug, smaller magnitude. A 120-second socket timeout added: `smtplib` otherwise inherits the system default, which is usually none, so a stalled relay would hold the thread forever. Ruff's `ASYNC230`/`ASYNC240` findings on this file are now **gone**, with no new findings added. |
| **A 16.45 MB clip** | `SOSCameraModal` recorded 10 seconds at the iPhone's default quality. Now capped: `videoBitrate` 1.2 Mbps, `videoQuality="4:3"` (640×480 — the 16:9 options are Android-only), `codec: 'avc1'` because iOS ignores the bitrate without it, and `maxFileSize` 8 MB as a backstop if a device ignores bitrate control. ~16 MB → ~2 MB. |

**Also fixed the thing that made it look hung.** `HomeScreen`'s progress bar is simulated and
hard-capped at 98, and the label never changed, so "98% Uploading Evidence" actually meant "upload
finished, the server is talking to the SMTP relay". It now switches to **"Alerting your contacts…"**
when the bytes are gone. The bar was lying, and that is what sent us looking for a stall that was not
there.

**Before the fix, verified working end to end on the owner's real Supabase:** email delivered, row
written to `sos_incidents` (`923c3459-24f0-4246-ac33-04f3eec93cb8`, `delivered=True`, 1 recipient),
coordinates un-swapped. Defect 35 is closed. The fix is about how long it takes and what it freezes,
not about whether it works.

**Deliberately not done, so it is not rediscovered as a gap:**

- **`app/llm/client.py` → D03**, its first consumer. `anthropic` is declared as a dependency; the
  module is not written. Nothing in D01 or D02 needs an LLM.
- **ADR 0003 (drop `public.users`) → Track B (B1).** `endpoints/sos.py` creates rows in that table on
  every trigger and `endpoints/voice.py` imports the model. Dropping it in D01 would have broken SOS
  silently. `risk_flags` has no `user_id`, so nothing in the demo track depends on it.
- **No decay arithmetic in Python.** `risk_flags.expires_at` is derived by a database trigger, which
  is the only implementation. A generated column was tried first and Postgres rejects it —
  `timestamptz + interval` is STABLE, not IMMUTABLE. D02 adds severity-on-read, and when it needs the
  serve threshold in Python it mirrors the value with a comment on both sides.
- **No `RISK_SURFACE_IMPL` switch and no scoring methods on the surface.** Both were written and then
  **deleted**: a factory that can only return one class, and `score_point`/`score_path` that nothing
  calls until D06. D02 and D06 add them when there is a second implementation and a caller.
- **The SOS video is still not retained.** It is attached to the email and deleted. Retaining footage
  recorded under duress needs a bucket, a retention window and an access policy. The incident row
  records *that* a video was attached.
- **Flags do not reload on pan.** The map is driven by a controlled `region` prop; D01 fetches once
  per recentre over a ~39 km box. D04 adds pull-to-refresh.

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
| Frontend | ✅ Expo **SDK 57**, RN 0.86.3, React 19.2.3. `tsc --noEmit` clean. ESLint 106 warnings / 0 errors (budget 106; D01 added exactly one). **Maps: Apple Maps on iOS, Google on Android** via `MAP_PROVIDER` — no API key, and no blank map |
| Docker | ✅ `docker compose up` → `api` + `redis`; one command via `scripts/run.ps1` |
| AI vision | ⚠️ **Runs, but measurably limited** — see the two new blockers below |
| SOS | ✅ Verified end to end on real Supabase: email delivered, row written to `sos_incidents` (defect 35 closed). SMTP now runs off the event loop, and the evidence clip is capped at ~2 MB instead of 16 MB. The clip is still not retained after sending — deliberate, see above |
| `app/contracts/` | ✅ `risk`, `surface`, `agents`. `mypy --strict` clean. Mirrored in `frontend/src/types/contracts/` by hand; a drift check is Track B (B2) |
| `RISK_SURFACE_IMPL` | ❌ No switch yet, on purpose — there is one implementation (`DbRiskSurface`) and a factory over one class is not a seam. D02 adds `SeededRiskSurface` and the setting together |
| Risk surface | ✅ `risk_flags` + `DbRiskSurface` + `GET /api/v1/risk/flags`. 22 sample flags across Dhaka, rendered as coloured pins on `MapScreen`. **All sample data is marked `sample_`** — live ingestion is D04 |
| Python env | ✅ `backend/venv` on **3.12.10**. Note the Docker image is 3.11-slim; the venv is for local `check.sh` only. The backend **cannot start without the full ~2 GB AI stack**, because `api/v1/api.py` imports the vision endpoints eagerly — Track B (B3) |
| Agents live | **0 of 8** |
| LLM client | ⚠️ `anthropic` is declared in `requirements/agents.txt`; `app/llm/client.py` not written — **D03**, its first consumer. Env vars declared, unused |
| Migrations | ✅ `backend/scripts/migrate.py` — forward-only, sha256-checksummed, refuses to run if an applied file changed. `schema_migrations` ledger. `migrate.py sql` emits paste-ready SQL with the ledger insert included, for a database that refuses direct connections. ADR 0004 itself is Track B (B1) |
| `tests/invariants/` | ✅ 34 tests over 2 invariants: mobility framing, and one source never confirmed. The other five are Track B (B2) |
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

**D04 is built on `ishraq-dev` and verified on the backend; the device walkthrough is the one gate
left.** D01–D03 are closed. By agreement with the owner, work is committed to `ishraq-dev` only —
nothing is pushed to or merged into `main` from this side.

**1. Bring the stack up — `-Rebuild` once, because D04 added Chromium and a `worker` container:**

```powershell
.\scripts\run.ps1 -Rebuild
docker ps        # meridian-api, meridian-worker, meridian-redis
```

**2. Close D04: run [`docs/walkthroughs/D04.md`](docs/walkthroughs/D04.md) on the phone, in Dhaka
daytime.** At night the outlets publish almost nothing about Dhaka's roads and an empty map is the
correct result, not a bug. While live news flags exist, do step O1 — `python -m app.agents
export-replay` — and **commit `backend/data/fixtures/live_replay.json`**: it is the offline demo's beat
1. Re-run D01–D03 in the same session (§3: every previous walkthrough still passes). Then fill in the
walkthrough's "Ran on" line and flip the 🟡 above to ✅.

**3. Then D05 — *Verification you can see*, Oct 15.** [DEMO_PLAN.md](DEMO_PLAN.md) §D05, source S15
in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Four things D04 built that D05 should use:

1. **`extracted_incidents` is the input.** Every incident the agent read is a row, published or not,
   with its `doc_id`, `location_text`, `kind` and the flag it produced (`flag_id`). Corroboration is
   "several rows from *different* `source_id`s describing one event".
2. **Live flags have `event_key = live-<doc_id[:16]>-<n>`** — one per incident, no dedup yet. Rumour
   Guard's job is to give corroborating flags a shared `event_key`, raise `source_count`, merge
   `sources`, and only then set `confirmed`. The database's CHECK still refuses `confirmed` below two
   sources; do not weaken it.
3. **Two of the three outlets run on one CMS** (Ekattor TV, Independent TV) but are separate newsrooms.
   Syndicated identical copy is already collapsed by `raw_documents.content_hash`; the D05 independence
   check (cut-first per §1) is about ownership, not CMS.
4. **`sentence-transformers` is already in `requirements/agents.txt`** and therefore in the image.

**Two traps that have each cost a session on this project:**

- **PowerShell cannot execute a `.sh` file.** It returns silently and changes nothing, which is
  indistinguishable from success. `.\scripts\seed.sh` does *nothing*. Only `run.ps1` is native —
  for the others, call the Python directly or use Git Bash.
- **Never write a literal backslash inside a bash heredoc in this repo.** It gets collapsed before
  Python sees it, so `\\run.ps1` becomes `\run.ps1` and the `\r` turns into a carriage
  return inside your file. This has corrupted documents three times. Build paths from `chr(92)`.

**The gazetteer is done and §9 item 1 was wrong about it.** It said "pure data entry… no coding agent
can compress it". OpenStreetMap's Dhaka data is Bangla-primary, so a harvest produced 1,022 paired
entries in an afternoon. What cannot be automated is the **alias layer** — a synonym is not a spelling
— and 22 entries have one. Extending it is B7 and is not blocking.

**§9's remaining off-baton work. None of it has started, and the OSRM graph is now the critical one:**

1. **The OSRM Bangladesh graph — D06 on the 16th assumes it is built.** Multi-gigabyte download plus
   `osrm-extract` / `osrm-partition` / `osrm-customize` into `osrm-data/`. The compose service already
   exists and is waiting for the file. No code, no baton, and nothing in D03 moved it. **Start this
   first with the five days of slack.**
2. The D07 eval set — 2 images against a target of 30–40.
3. A native Bangla speaker for D08, for the 20th or 21st. It is a gate on that sprint and depends on
   someone else's calendar.

**Decision blocking D07, due 17 October — and D03 changed its shape.** `DEMO_PLAN.md` §7.1 recommends
local YOLOv9c detection plus **Claude** vision, and claims the key is already configured. **It is not:
this project has no Anthropic key.** Gemini's flash-lite models are multimodal, free, and already
working through `app/llm/client.py`, which makes them the obvious substitute — but that is a decision,
not a default, and it needs the conversation.

**Decision open from D03, one line of config:** whether to drop `groq:openai/gpt-oss-120b` from
`LLM_CHAIN_GEO`. See the ⚠️ block at the top of this file. Recommendation is to drop it.

**Outstanding owner actions on the security incident (B0), unchanged:** rotate the credentials, rewrite
history to drop the payload from `db6c42f`, untrack both `.env` files, delete the `agent/Arafat`
branch. Both `.env` files are tracked and hold live values, so **this repository must not be made
public.** See the incident block at the top of this file.


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
