# Video shoot — build plan

Branch `feature/test-v`. Tampering is expected here; nothing on this branch needs reverting.

**Two sessions, same scenarios:**

| | When | What it is |
|---|---|---|
| **Shoot** | Tomorrow, daytime | Short snippets per segment, stitched and sped up later |
| **Judge demo** | 21:00–21:25 | Same scenarios, improvised narration off the base script |

So every scenario must be **re-creatable with one command at any hour**, not seeded once. The
existing seeder already works this way — offsets are relative to `now`, and it clears its own
`seed-` rows before inserting — so the rule for everything built here is: *no absolute timestamps,
ever.*

---

## The six segments

| # | Segment | Needs seeding? | Hardest part |
|---|---|---|---|
| 1 | News ingestion → flags on the map | **No** — real live flags | Verifying one exists at showtime |
| 2 | Tap a flag → incident detail + source | **No** — same flag | Picking one with a working source URL |
| 3 | Routing → safest route among options | **Yes** | Flags must land on the alternatives and *not* on the recommended route |
| 4 | Journey Guardian → guardian, nudges, escalation, arrival | Config + mock GPS | Compressing a 13-minute ladder |
| 5 | SOS → shake / phrase / button → video → email | **No** | Hot words need the native build |
| 6 | Crime photo → detection → Bangla GD → exits | **No** | A photo that reliably produces a category |

---

## Tasks

Status: ☐ not started · ◐ in progress · ☑ done

### ☑ T1 · Write the scenario set
**[`SCENARIOS.md`](SCENARIOS.md)** — six segments, ~3:20, with a time budget, a start-state
checklist per segment, the shots, the on-screen text and an editor note. Every number in it was
read off the running system. `SCRIPT.md` is marked as the long-form version for the 21:00 demo.

### ☑ T2 · Find the routing pair
Swept 120+ pairs against the live surface. **Chosen: `Motijheel → Kalabagan`**, backup
`Gulshan 2 → Rampura`. Numbers in *Settled* below.

What the sweep established, and it changed the plan: **the full 215-flag fixture cannot produce a
clean route.** With 204 flags live, every central-Dhaka route passes 4–23 of them, and the best
contrast available was 5 flags against 11 — which on camera reads as "both are bad". Routing counts
a flag when the route passes within `ROUTE_CORRIDOR_RADIUS_M` (150 m) of its **centre**, so wide
chronic flags do not poison every route; density does.

### ☑ T3 · Build the routing scenario into the fixture
Not new entries — a **curated subset**. `data/fixtures/video_scenario.json` is `risk_flags.json`
minus the 14 flags within 155 m of the recommended route for the three candidate pairs. 193 flags,
so the map still looks alive, but those three corridors start clean.
`seed_risk_flags.py` gained a **`--fixture PATH`** argument to load it.

### ☑ T4 · Verify the routing contrast ⭐
Passes for two of the three pairs. `backend/scripts/verify_video_scenario.py` is the check, and it
is a **pre-flight item for both sessions** — see *Settled*.

The third pair fails, and the reason is the whole point of the script: *"Delay likely near Bangla
Motor"* is a **real** live flag from today's Jugantor report, sitting on that corridor. The fixture
cannot remove agent-produced flags, so a real article can break a cleared corridor at any time. The
script names the offending flag and tells you which pair to film instead.

### ◐ T5 · Journey Guardian filming setup
- ☑ `CHECK_IN_WINDOW` shortened 5 min → **1 min** in `app/journeys/deadline.py`, marked
  **do not merge**. Whole ladder now runs in ~4 minutes instead of ~13. 18 deadline/journey tests
  still pass.
- ☐ Mock-location route (no mock filtering exists in the app, so fixes are accepted as real)
- ☐ Confirm arrival fires indoors: `ARRIVAL_M = 30`
**Done when** a full ladder runs in under 5 minutes, indoors, ending in the red email, and a second
run arrives and sends the green email.

### ◐ T6 · SOS setup
- ☑ **3 emergency contacts, all with an email address.** Nothing to add.
- ☑ 19 SOS incidents already on record, so the history screen is populated.
- ☐ **Replace the hot words.** Both stored phrases are `Hello` — duplicated, and the worst possible
  demo phrase: it will false-fire on ordinary speech and it sounds like nothing on camera. Profile →
  SOS hot words, delete both, add one distinctive phrase. **A phone job, 30 seconds.**
- ☐ Confirm shake and phrase fire on the build being filmed. This is the one feature on the list
  with no signed-off finale walkthrough behind it.

### ◐ T7 · Crime + GD setup
- ☑ **The path is proven in data.** Several `assault` reports exist with both an
  `evidence_photo_path` and a stored `vision_analysis`, so detection has worked repeatedly on this
  account.
- ☑ **The thana resolves to a verified station.** The Agargaon report produces
  **Sher-e-Bangla Nagar Police Station**, which is *not* one of the five carrying
  `legacy — unverified` coordinates. 6 drafts exist, 4 already `ready_to_file`.
- ☑ `gd_number` has never been set on any draft, so the final "record the GD number" step is still
  fresh and can be filmed as a first.
- ☐ Choose and stage the photo on the phone. Needs a category with a *"Because …"* reason — the
  categories the model has actually produced here are `assault`, `vandalism`, `theft`,
  `harassment`, `other`.

### ☑ T8 · One-command stage setup
**`backend/scripts/stage_video.py`.** Seeds the video surface, lists today's live news flags so you
know which one segment 2 taps, verifies the routing contrast, prints the manual steps, and exits
non-zero if anything is missing. Ends on **READY TO FILM** or **NOT READY**.

```
backendenv\Scripts\python.exe backend\scripts\stage_video.py
```

### ☑ T9 · The base script
Covered by [`SCENARIOS.md`](SCENARIOS.md) — see T1.

### ☑ T10 · Put real news back on the map ⭐
**The problem found on 17 Oct: there are zero live news flags.** Not a broken agent —
`live_risk` is running every 5 minutes, reading 198 articles a day from all ten publishers,
and marking ~52 relevant per run. It published nothing because *today's road news is all
outside Dhaka* (Rajbari, Sitakunda, Bandarban, Jhalokathi), so nothing resolves to a Dhaka
location. The last real flag was observed **16 Oct 06:45 UTC** and has long since expired.

Consequence if left alone: segments 1 and 2 have nothing real to show, and the
*"N real of M"* counter on **What we read** reads **0**. That is the single worst number
that could be on screen in a video about reading the news.

The fix is the mechanism D04 already built for the offline demo: **`live_replay.json`**.
It stores captured news flags as *relative offsets*, so the seeder re-lays them against the
current clock — which is exactly the two-sessions-one-scenario property everything else here
relies on. Real URLs, real Bangla headlines, real publishers, statement re-derived by
`framing.py` at load. Only the clock moves.

Captured from genuinely real flags published on 15–16 Oct, five publishers, five places:

| Statement | Publisher | Kind |
|---|---|---|
| Road blocked near Azampur | Samakal | blockade |
| Road blocked near Raj Laxmi | Dhaka Tribune | blockade |
| Delay likely near Mohammadpur Beribadh Connecting Road | Prothom Alo | clash |
| Delay likely near Bangla Motor | Jugantor | other |
| Delay likely near Tongi Junction | Ittefaq | fire |

**Done.** `scripts/capture_video_news.py` captures by event key, ignoring expiry, and
re-anchors each flag to a chosen recent offset; `seed_risk_flags.py --replay` lays them down;
`stage_video.py` passes `--replay` and marks each real flag *published here* or *replayed*.
All five come out **confirmed on one vetted source**, because the script asks `is_confirmable`
rather than letting `_row_from_entry` default them to `unconfirmed` — the same staleness as
T11, found the same day. `export_replay`'s hard-coded `source_count: 1` is also not copied;
it would fail `check_rows` for any merged flag.

### ☑ T11 · Stop the map reading as a field of question marks
77 of the 134 served flags are `unconfirmed`, and D05 renders every one as a hollow,
dashed circle with a **`?`** in it. That is correct product behaviour and completely wrong
for a thirty-second map shot — the first impression is a city full of rumours.

Cause: `app/scoring/fixture.py` defaults `status` to `unconfirmed`, and **116 of the 193
fixture entries never state a status.** Nothing decided they were unconfirmed; they simply
did not say.

Fix in the fixture, not the renderer: state `confirmed` with two independent sample
publishers on the bulk, and **leave a deliberate minority unconfirmed** so the distinction
is still on screen and still demonstrable — it is a selling point, not a blemish, and a map
with none of them would be a map that cannot tell the difference.

**Done.** Every newsroom-sourced entry now states `confirmed`, with `source_count` 2 where it was 1 so
confirmation also holds through the independent-publisher branch — no policy change, no
invariant loosened. Served flags went from **77 unconfirmed of 134** to **6 of 45** (see T13 for the trim), and
the six that remain are correct: five chronic rows (`bd_police_statistics` is a dataset, never
put through the publisher survey) and `seed-mugda-utility` (a Titas notice is not a newsroom).
The deliberately-expired rows are left untouched.

This turned up a **third** stale assertion of the same family:
`tests/invariants/test_surfaces_agree.py` restated the schema CHECK as `source_count >= 2`
for a confirmed flag. The CHECK was renamed and relaxed to `>= 1` by `e7c4fa3` on 2026-10-16;
the assertion was not updated and passed only while nothing confirmed-on-one-source was ever
served. The first real Prothom Alo flag broke it. Fixed here. **Needed on `develop` too, with
the invariant-test fix already recorded below.**

### ☑ T12 · Nothing on screen should say `sample_`
`RiskFlagSheet.tsx` carries its **own** `outletName` with a three-entry table and a raw-id
fallback, deliberately: *"An id not listed here — including every fixture `sample_*` id — is
shown raw, so the fixture stays visibly a fixture."* Good call in development; it means the
flag sheet renders the publisher as **`sample_jugantor`** on camera.

`features/risk/news.ts` already exports the `outletName` that strips the prefix and maps
nine publishers to the names people know. Two implementations of one function, disagreeing.
Point the sheet at the shared one.

**What this does not fix, and the shoot has to work around:** the 116 default entries also
get auto-generated source titles reading literally **`Sample report — Mirpur 10 golchattar`**,
because `_generated_sources` refuses to invent 230 plausible headlines — *"the point of the
`sample_` marking is that nobody, including us at midnight on the 23rd, can mistake it for
one."* That judgement is right and is not being undone for a video. So: **tap only the real
replayed flags**, which is what SCENARIOS.md segment 2 already says.


---

## Settled

### Segment 3 · the routing scenario

**Film `Rampura → Gulshan 2`.** Backup: `Gulshan 2 → Rampura`, same shots, weaker contrast.

| Route | Flags | Safety | Time | What it says |
|---|---|---|---|---|
| **Recommended** | **0** | **100/100** | 20 min | *"Nothing flagged along this route. Fastest, and avoids 5 flagged corridors."* |
| Worst of 3 | **5** | **25/100** | 22 min | Merul Badda blocked · Uttar Badda standing water · Middle Badda lane closed · +2 |

Stable across four consecutive runs on 17 Oct. **Re-check anyway** — this is the one number
here that has already moved once without anyone touching the code.

#### Two constraints that decided this, both found by measurement

**1. The surface was saturated at 189 flags.** Swept all 306 ordered pairs of eighteen Dhaka
landmarks: only two produced a route the app could recommend with nothing on it, and every
pair with a wider flag spread — up to nine — carried **four to seven flags on the
recommendation as well**, which on camera reads "both routes are bad". That is the claim this
segment exists to refute. The fixture is now **35 entries** (45 served, with the chronic layer
and the five replayed news flags), chosen to keep every flag on this corridor's alternative
and spread the rest by farthest-point sampling.

**2. Most Dhaka pairs cannot show this contrast at all, structurally.** OSRM returns a single
road for most of them; the second "route" on the card is a detour `route_service.py` builds
itself, and it only builds one *when the recommended route passes a flag worth avoiding*. So
on those pairs a clean recommendation and a flagged alternative are mutually exclusive — clear
the primary and the alternative vanishes. `Azimpur → Badda` looked like the best pair in the
world on paper (0 vs 14 after deleting six flags) and collapsed to **one route** the moment
its corridor was cleared. The contrast is only filmable where OSRM genuinely offers two
distinct roads, and this corridor is one of the few that does.

#### What the earlier pairs were, and why they are gone

`Motijheel → Kalabagan` was settled on 16 Oct against four OSRM routes, the worst carrying
eight flags — 19 minutes and eight flagged places against 24 and nothing. OSRM now returns
three routes for it and the nineteen-minute one through Shahbagh and Gulistan is not among
them. Nothing here changed; the geometry on offer did.

So the story changed with the pair, twice, and the current one is the strongest of the three:
not "safety costs five minutes" but **100 against 25 for two minutes** — the two routes cost
nearly the same and one of them is blocked at Merul Badda.

### The one command both sessions run

```
backendenv\Scripts\python.exe backend\scripts\stage_video.py
```

One command. It seeds the scenario fresh against the current clock *including the replayed
real news*, lists the real flags so you know which one segment 2 taps, verifies the routing
contrast and names the pair to film, then prints what still needs a phone. It ends on
**READY TO FILM** or **NOT READY** with a non-zero exit. **Run it at 09:00 and again at
20:55.**

Two things it cannot do for you, both one-offs rather than per-session:

```
backendenv\Scripts\python.exe backend\scripts\capture_video_news.py   # if no real flag is live
backendenv\Scripts\python.exe backend\scripts\export_route_track.py   # the mock-location GPX
```

**The venv's Python, not a bare `python`** -- that is the base conda environment here and it
has no `asyncpg`. Both database scripts now check first and print the right command rather
than failing as though a dependency were missing.

### Three defects this turned up, which are not ours to leave

All three are the **same defect in three places**: `e7c4fa3` changed `confirmed` to mean *"a
vetted newsroom published it, or two independent publishers agreed"* on 2026-10-16, and three
things that restate that rule were not updated with it. Each passed only while the surface
happened to contain nothing confirmed on a single source, and each broke the moment real
ingestion wrote one. **All three fixes are needed on `develop`.**

1. `tests/invariants/test_confirmation_requires_a_vetted_source.py` asserted two independent
   publishers per confirmed row. Fixed to use `is_confirmable`.
2. `tests/invariants/test_surfaces_agree.py` restated the schema CHECK as
   `source_count >= 2`. The constraint is `risk_flags_confirmed_cites_a_source` and reads
   `>= 1`; it was renamed and relaxed by the same commit. Fixed, with the old name recorded
   in the comment so the next reader can see what happened.
3. `app/scoring/fixture.py` still defaults `status` to `unconfirmed`, so **130 of 193**
   newsroom-sourced fixture entries were drawn as hollow question marks — not because anyone
   decided they were rumours, but because they did not say. Worked around in
   `video_scenario.json` for this branch rather than changed in the loader, because the
   default also governs `risk_flags.json` and that is a `develop` decision. **The honest fix
   on `develop` is to default newsroom-sourced entries to `confirmed`.**

`app/scoring/chronic.py` carries the same stale reasoning in a docstring — *"one source cannot
produce a confirmed flag. That rule has no exception for official data"* — but its conclusion
is still right for a different reason: `bd_police_statistics` is not in `VETTED_PUBLISHERS`
and never went through the publisher survey. The comment should be corrected; the behaviour
should not.

---

## Order of work

T1 → **T2 → T3 → T4** (the routing loop, the real work) → T5 → T6 → T7 → T8 → T9.

Then, found on 17 Oct against the running system: **T10 → T11 → T12**. T10 is the one that
changes what a viewer sees most, and T11 the one that changes the first two seconds.

T5–T7 are independent of each other and of the routing loop.

---

## Constraints that do not move

- **No absolute timestamps** in anything seeded. Both sessions run the same command.
- **Flag text comes from `app.policy.framing`**, never typed into the fixture. The seeder enforces
  this; do not work around it.
- **`expires_at` is derived by the database** from `observed_at`, `severity_0`, `half_life_hours`.
  Never written directly.
- Seeded rows use the `seed-` prefix so the seeder can clear them. Agent-produced flags
  (`live-%`) are never touched.
- Segment 1 and 2 use **real** ingested flags. They are the most persuasive thing in the video and
  there is no reason to fake them.

## Known hazards

| | |
|---|---|
| Live flags expire in **8–12 h** | Segment 1/2 needs `live_risk` to have run. It runs every 15 min, so check at 20:50 rather than assuming |
| Severity has an **hour-of-day profile** | A flag's `severity_now` differs between 10:00 and 21:00. T4 must verify the routing contrast at both |
| Push notifications are unreliable | `JG2.md` records the lock-screen notification as usually not drawn. Film the **journey card**, which changes its own title and grows an **I'm fine** button |
| `SERVE_THRESHOLD = 5.0` | A flag whose severity decays below this stops being served. Half-lives must be long enough to survive to 21:25 |

### ☑ T13 · Cut the surface to a size routing can work with
189 flags on the map is too many, and the harm is measured rather than aesthetic: it makes
segment 3 unfilmable. See *Settled → Segment 3* for the sweep and the two constraints.

Trimmed to **35 fixture entries → 45 served** (35 + 5 chronic + 5 replayed news). Selection is
deterministic: keep everything on the filmed corridor's alternative, drop anything on its
recommendation, then fill by farthest-point sampling so the map stays evenly covered instead
of clustering, with a small tie-break towards entries whose sources were hand-written — those
read like reporting if anyone taps them, where a generated one says `Sample report — <place>`.

Three secondary gains: 45 pins are individually legible at city zoom where 189 are a wash; the
real replayed flags are now findable among them, which segment 2 needs; and 189 concurrent
road incidents was never credible against our own pipeline's 3–5 a day.

### ☑ T14 · Location search offered Rampura, India
`app/geo/nominatim.py::search` sent `q`, `limit` and `addressdetails` and nothing else, so a
forward geocode was a **world** query. Typing *Rampura* in the route box ranked **Rampura,
India** first, because it is the more prominent place and nothing said to prefer Bangladesh.
The same fault is already recorded in `features/search/suggest.ts`, which found *Seoul* in the
destination field.

Not cosmetic: the destination feeds `/routes/calculate`, which scores a path against the Dhaka
risk surface. A destination in another country returns a route with no flags on it for entirely
the wrong reason.

Fixed with `countrycodes=bd` plus a greater-Dhaka `viewbox` used **unbounded** — a preference,
not a filter, so Chattogram and Cox's Bazar still resolve. The cache key carries the bias
(`search:bd:`) so entries written before the change are not served back for the rest of
`NOMINATIM_CACHE_TTL_SECONDS`. *Rampura* now returns Rampura, Dhaka first.
