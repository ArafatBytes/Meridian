# ADR 0007 — D08: the General Diary, and the hand-off we do not automate

| | |
|---|---|
| **Status** | **Accepted** — 2026-10-10. Built the same day; see the addendum |
| **Date** | 2026-10-10 |
| **Decider** | Nakib (owner) |
| **Consulted** | — |
| **Decides** | `DEMO_PLAN.md` D08, and §7.2 (police routing), which it closes |
| **Affects** | D08 (Oct 20–21), D10's §7.2 checkbox, `LLM_CHAIN_GD` |
| **Research** | `docs/reference/gd-formats.md` · `docs/reference/dmp-gd-form.pdf` |

---

## Recommendation

**Generate one formal-Bangla narrative. Put it on the official DMP form as a PDF, and on the
clipboard for the police's own app. Then stop.** Meridian never files anything with the police, and
the state machine has no `filed` state to reach.

Model: **`gemini-3.5-flash-lite` primary, `groq:openai/gpt-oss-120b` fallback** — the same shape as
`LLM_CHAIN_GEO`, chosen from a measured bake-off (below), not from the model's reputation.

---

## The question D08 actually faces

The plan says "generate a Bangla General Diary". The unasked question is what happens *next*, and
the honest answer decides the architecture:

> We have no collaboration with Bangladesh Police, no API, and no way to get one in fourteen days.
> So what, exactly, does the user do with what we generate?

## What the research found

Full detail in `docs/reference/gd-formats.md`. The four facts that decide this:

**1. The written application is wide open to us.** The Police Act 1861 obliges every officer-in-
charge to keep a general diary and record complaints. No law prescribes a format for the
*application*; a 2008 Daily Star legal Q&A states it may be in any form, "including a
computer-composed one." Filing is free. DMP publishes a standard form, which we have and have
transcribed.

**2. The DMP form is a frame around one blank space.** Everything above
`আমি এই মর্মে জানাচ্ছি যে,` is identity; everything below is the closing. Two-thirds of the page is
one free-text area. **That blank middle is the entire product.**

**3. The online GD app wants the same blank space.** Confirmed from the device: under
`অন্যান্য আবেদন`, choosing `সাধারন ডায়রী করার আবেদন` gives **exactly two fields** — the type, and
one large `বিবরণ` box. The other options and the lost-document flows open long structured forms that
build a GD draft for you; those are document-replacement workflows, not incident reports, and
competing with a form the police already generate buys us nothing.

**So one narrative serves both routes.** No second template, no per-category forms.

**4. The physical step cannot be removed.** A cognizable offence cannot be closed online — the
applicant must appear at the thana with a printed copy or the complaint code. Cognizable covers
assault, robbery, theft and burglary: *every category D07's vision pipeline proposes.* Route 1 is
therefore the primary path and route 2 is the convenience, not the other way round.

Coverage is also partial. Online GD went all-types from a pilot on 15 April 2025, reaching 457
thanas across six ranges plus metropolitan units, with Khulna and Barishal following. **No source
confirms complete national coverage**, and DMP's own commissioner said in 2024 that GDs which
cannot be filed online are filed manually.

---

## Decision 1 — we draft, a person files

Three exits, in the order the user meets them:

| Exit | What it is | Who acts |
|---|---|---|
| **Print** | PDF on the DMP frame: addressed to the OC of the identified thana, identity block filled, narrative in the middle, **blank signature line** | User signs two copies, hands them to the duty officer, keeps the one he signs back |
| **Copy** | The narrative alone, on the clipboard | User opens Online GD with their own NID and OTP, picks `অন্যান্য আবেদন` → `সাধারন ডায়রী করার আবেদন`, pastes into `বিবরণ` |
| **Where else** | A card keyed off category — 999, 109, PCSW, CID Cyber | User calls |

### What we will not build, and why

- **No scripted submission to `gd.police.gov.bd`.** It would need the user's NID, their live selfie
  and their OTP. It is a government authentication system, it is covered by CSA 2023, and it breaks
  the night before when a form field moves. Bad engineering before it is anything else.
- **No `filed` state.** The state machine ends at `ready_to_file`. What we add instead is a
  **"GD number (if filed)"** field the user types back in. That closes the loop truthfully and makes
  Meridian their case record.
- **No claim of a police partnership**, anywhere in the app or the pitch.

**The demo line:** *"We don't file it for you — a legal document needs your signature. What we
remove is the blank page, the wrong thana, and the formal Bangla you don't want to write at 2 a.m."*
A principled limit survives a judge's question; an overclaim does not.

---

## Decision 2 — `LLM_CHAIN_GD=gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b`

### The bake-off

Three scenarios (assault in Banglish with no suspect identity; a snatching with an IMEI and a
model number; stalking, which invites a legal conclusion). Strict `json_schema` through
`.parse()`, `max_retries=0` — the production path. Two rounds, 2026-10-10.

| Model | Succeeded | Latency | Bangla | Notes |
|---|---|---|---|---|
| **gemini-3.5-flash-lite** | **12 / 12** | **1.84s avg** | 97–100% | Correct place names, Bangla numerals, proper formal register |
| groq gpt-oss-120b | 5 / 12 | 2.48s | 90–100% | Schema validation failures, then rate limits |
| gemini-3.5-flash | 5 / 12 | 9.57s | 85–100% | Repeated 503s; leaves place names in English |
| groq gpt-oss-20b | 1 / 3 | 1.68s | 100% | Dropped after round 1 |

**GPT-OSS-120B is not the right primary.** It is fast and its Bangla is serviceable, but it failed
Groq's own JSON validation on whole scenarios — the same silent-failure class D07 hit — and it
mangles proper nouns: `মজিদহিল` for Motijheel, `কাখরাইল` for Kakrail, and it left
`8 October 2026` and `IMEI 352099001761481` in Latin script inside an otherwise Bangla document. A
police application with a mangled place name is a worse document than no document. It stays in the
chain as a **fallback**, because it is a different provider and a degraded draft a human then edits
beats no draft at all.

`gemini-3.5-flash` is out: reasoning tokens ate the entire budget in round 1 (32 completion tokens
of 1480 total), and raising the budget to 4000 only exposed repeated 503s. Five times slower than
flash-lite for worse Bangla.

### Two defects that were ours, not the models'

Both appeared in round 1 and both went to zero in round 2 after a prompt change — recorded because
the measurement would otherwise read as a model difference:

1. **flash-lite moved the year**, writing ২০২৫ for an incident in 2026. Fixed by *"Copy every date,
   time, number and name exactly as given. Never shift a year, round a time or correct a spelling of
   a place."* **0/9 in round 2.**
2. **Both models repeated `আমি এই মর্মে জানাচ্ছি যে,`**, which the form already prints above the
   blank. Fixed by telling the model what the form prints. **0/9 in round 2.**

### The offline tier is undecided

Ollama was not running when this was measured, so the local tier is **untested for Bangla**. The
recommendation is **replay, not a local model**: a 4B model writing formal legal Bangla is a bad
bet, and unlike D07's photo analysis the GD text for a rehearsed demo report is fixed, so a replay
fixture is both honest and deterministic. **Measure before deciding** — this is the one open item.

---

## Decision 3 — §7.2 closes now: `POLICE_ROUTING_ENABLED` stays `false`

§7.2 defers the police-routing position to D10. The research decides it: **there is nothing to
transmit to.** No API, no partnership, and `backend/police_stations.csv` carries real coordinates
for 606 stations behind a single placeholder email and phone repeated on every row.

So "routing" in Meridian means **naming the right thana on the document** and telling the user which
channel to use. The thana name is shown; **the contact columns are never displayed**, because
showing a placeholder phone number beside a crime report is worse than showing none. The numbers in
the "where else" card are national ones that are real.

If a real contact list is ever obtained, this becomes a data change, not a code change.

---

## What D07 hands over, and the limit on it

A GD application is a statement by a citizen, and a false complaint is punishable. **Nothing the
vision model proposed may enter the narrative as fact.** The category the reporter confirmed may
select the template; the cue outputs may not become sentences. The evidence photo is attached as an
attachment and described as a photograph the complainant took — and since the `অন্যান্য আবেদন` path
has no attachment control, in practice it goes to the thana on paper.

This is the same rule as D07's, one step further down the pipeline: *the machine proposes, the
person states.*

---

## What this costs

| Item | Status |
|---|---|
| Narrative generation | One LLM call, one validated output model. Measured at 1.84s |
| Thana identification | Nearest-point lookup over 606 rows already in the repo |
| The DMP frame | A template with five constants and one blank |
| **GD profile screen** | **New, and not in the plan.** NID, পিতা, মাতা, permanent and present address. The form requires them, we store none of them, and they are not guessable |
| PDF with a Bengali font | Already an explicit D08 task, and still the classic trap |
| Review gate | State machine, as planned |
| Offline tier | Open — measure Ollama, or ship replay |

The GD profile is the only genuine addition. Everything else is smaller than the plan assumed,
because the two routes turned out to want the same artefact.

---

## Consequences

**Good.** One narrative, two routes. No credential handling, no government auth, no partnership
claim, no dependency on a rollout we do not control. The review gate stops being a safety feature
bolted on and becomes the actual product boundary.

**Bad.** The narrative is now the *entire* product in both routes. If the Bangla is wrong there is
nothing else carrying the draft — so the native-speaker gate is load-bearing, and the reviewer needs
arranging before the 20th, not on it. And the user still walks to a thana; we have made that walk
shorter, not removed it.

**Accepted risk.** Route 2 may not cover the demo thana, since the all-types rollout is incomplete.
Route 1 works everywhere, which is why it is primary.

---

## Addendum — 2026-10-10, built

Accepted as proposed, with three things the build changed or discovered.

### The Bengali-font trap was stepped around, not solved

The plan budgets time to embed a Bengali glyph font in a server-side PDF. We print on the device
through `expo-print`, which renders HTML with Android's own text stack — the same one already
drawing Bangla everywhere else in the app. No font to embed, no shaping library, and no PDF
dependency in the backend at all. The one assumption is a phone with Bengali fonts, which any
phone in Bangladesh has.

### The model cannot copy a 15-digit number, and prompting does not fix it

Asked to carry `352099001761481` into the narrative, Gemini produced `35209900171481`,
`35099001761481` and `3352099001761481` across five attempts — a digit dropped, dropped again, and
one added. Adding an explicit instruction not to convert identifiers to Bangla numerals changed
nothing, because the failure is copying a long digit string at all, not the script it lands in.

`app/casework/draft.py::_repair_identifiers` now substitutes the complainant's own string back in
after generation. Where the substitution would be ambiguous — several digit runs of similar length
— it does **not** guess; it adds a line to `missing_details`, which the review screen shows before
anything can be approved. Where the model simply omitted the number, nothing is said, because a
warning about a number that is not on the page is noise, and noise is how a real warning gets
ignored.

This is the same division of labour as D07, one layer down: *the model proposes language, our code
preserves facts, the person states them.*

### `police_stations.csv` was wrong, and is now half right

Thana identification assumed the coordinates were usable. They were not: Motijheel was 14.6 km from
Motijheel, Ramna 8.4 km from Ramna, and Ramna's listed point is the generic "Dhaka city" coordinate
every dataset ships. Dhaka thanas sit 2–4 km apart, so nearest-station lookup was effectively
random — a report from Dhanmondi proposed Mugda.

**34 of 51 Dhaka stations** now carry coordinates checked against OpenStreetMap, and a
`coord_source` column records which. Dhanmondi 27 now resolves to Dhanmondi at 0.67 km, Motijheel to
Motijheel at 0.25 km, Uttara to Uttara at 0.27 km.

The remaining 17 — Paltan, Lalbagh, Demra, Cantonment, Kalabagan and others — **are not mapped as
police stations in OSM or findable through Nominatim**, so no query reaches them. They keep their
original coordinates and say so. One match was refused outright: Nominatim returns *Tejgaon
Industrial Area Police Station* for "Tejgaon", and DMP lists those as two separate thanas; using one
for the other would be the same class of error this fix exists to correct.

**This does not make the thana authoritative and nothing in the UI claims it does.** Jurisdiction is
a polygon drawn by people, not a Voronoi cell around a point. The lookup proposes; the picker is
how the user corrects it; and a coordinate outside Bangladesh names no thana at all rather than the
nearest one by arithmetic.

### Still open

- **No offline tier.** Decided rather than measured: the owner ruled out the 4B model. With no
  network, drafting fails with a message and saves nothing. A replay fixture is the answer if D10
  wants beat 7 to survive a dead venue network.
- **The native-speaker gate is not met.** `scripts/eval_gd_drafts.py` writes three scenarios ×
  three drafts with a sign-off box. Nine of nine passed the automated checks on 10 October; those
  checks say nothing about whether the Bangla is *right*.
- **The device walkthrough has not been run.** Per §0, that means D08 has not ended.

---

## Addendum 2 — 2026-10-10, the 4B measured and the thana data fixed properly

### qwen3-vl:4b on this task: measured, and the answer is no

The first addendum recorded the local tier as *decided rather than measured*. It has now been
measured, on the same three scenarios, two runs each, through the same prompt.

| | cloud (`gemini-3.5-flash-lite`) | local (`qwen3-vl:4b`) |
|---|---|---|
| Latency | 1.8s | **7.2 – 13.4s** |
| Place names | কাকরাইল মোড়, মতিঝিল শাপলা চত্বর | **কাকুরির মর, মুটি জেলার শাপলা চট্টার, শাম্পা চট্টার** |
| Dates | correct every run | **`০৯ অক্টোবর ২৮` — the year destroyed** |
| Invented facts | none in 9 runs | **an address, `৫০১/৩`, that appears nowhere in the report** |
| Readability | formal, coherent | broken grammar; `লathi` with Latin letters inside a Bangla word |

One run produced a narrative that does not parse as Bangla sentences at all, and its English gloss
simply echoed the prompt's own field labels back.

**The automated checks called four of those six runs "clean".** That is the most useful thing this
measurement produced: the eval script checks numbers, script ratio and duplicated form lines, and
*none of those catch bad Bangla*. It is the clearest possible argument for why the native-speaker
sign-off is a gate and not a formality — and a warning not to read a green eval as a verdict on
language quality.

So `LLM_CHAIN_GD` stays cloud-only, now on evidence. **With no network, drafting fails with a
message and saves nothing**, which is the honest outcome: a document that looks like a police
application but reads like that one does is worse than no document, because the person signing it
cannot tell.

### A seam limit worth knowing: Ollama's grammar compiler has a `maxLength` ceiling

Running the 4B at all first required finding out why it returned
`400 — Failed to initialize samplers: failed to parse grammar` before generating a token.

Ollama compiles a strict `json_schema` into a GBNF grammar, and a large `maxLength` on a string
breaks that compiler. Measured against qwen3-vl:4b: **200, 500, 1000 and 1500 compile; 2000 and
3000 do not.** `GdDraft.narrative_bn` is 3000, which is why it failed instantly.

This is not a D07 regression — `CrimeCues.description` is 200, so the vision tier has never been
near it, and it was re-checked today and still works. It is recorded in `app/llm/models.py` beside
the field, because the person it will bite is whoever next adds a local tier to a feature whose
output is longer than a sentence.

### `police_stations.csv`: 46 of 51 Dhaka stations now verified, 43 from DMP itself

The first addendum reported 34 of 51 from OpenStreetMap, with 17 unreachable. The owner pointed at
`dmp.gov.bd/find-your-local-police/`, which turned out to carry a Google Maps embed per station.
The embed's own `pb` parameter holds only the map *centre* — often just "Dhaka" at those zoom
levels — but **fetching the embed resolves the place marker**, which is the station.

That gave **42 stations from the police's own pages**, including every one OSM lacked: Paltan,
Lalbagh, Demra, Kalabagan, Rupnagar, Shah Ali, Sher-e-Bangla Nagar, Dakshin Khan, Bangshal and both
Tejgaon thanas. Combined with OSM for three more, the file now has **46 of 51 Dhaka stations
verified**, and `coord_source` says which source each came from.

**The two sources agree, which is why this is trustworthy rather than merely newer.** Where both
have a point, 18 of 22 agree within 62 metres; Adabar differs by 14 m. Four disagree by more —
Badda 2.8 km, Ramna 1.1 km, Wari 667 m, Banani 574 m — and DMP wins those, being the police's own
publication.

Five remain unverified and say so: **Cantonment, Turag, Uttarkhan, Hatirjheel, Bhashantek**. None
has a map embed on the DMP page and none is mapped in OSM.

The effect on the lookup, which was the point:

| Test point | Before any fix | Now |
|---|---|---|
| Dhanmondi 27 | Mugda, 8 km wrong | Dhanmondi, 0.66 km |
| Motijheel | — | Motijheel, 0.24 km |
| Paltan | — | Paltan, 0.10 km |
| Mugda | — | Mugda, 0.05 km |
| Uttara Sector 4 | — | Uttara, 0.28 km |

This also makes the "find the nearest police station" feature the owner is considering viable,
which it was not this morning. **It still does not make the thana authoritative**, and nothing in
the UI says it does: jurisdiction is a polygon drawn by people, not a Voronoi cell around a point.
The lookup proposes and the picker corrects.
