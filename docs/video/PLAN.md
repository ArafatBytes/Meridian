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
python backend/scripts/stage_video.py
```

### ☑ T9 · The base script
Covered by [`SCENARIOS.md`](SCENARIOS.md) — see T1.

---

## Settled

### Segment 3 · the routing scenario

**Film `Motijheel → Kalabagan`.** Tap Motijheel as the start, Kalabagan as the destination.

| Route | Flags | Safety | Time | What it says |
|---|---|---|---|---|
| **Recommended** | **0** | **100/100** | 24 min | *"Nothing flagged along this route. 5 minutes longer, avoids 10 flagged corridors."* |
| Option 2 | 2 | 73/100 | 25 min | Moghbazar flyover works · **Bangla Motor — today's real Jugantor report** |
| Option 3 | 2 | 50/100 | 25 min | Moghbazar road blocked |
| Option 4 | **8** | **29/100** | **19 min** | Shahbagh intersection, Gulistan Zero Point, Science Lab, Elephant Road … |

The story this gives you is better than "the safe route is also the best": **the fastest route is
the dangerous one.** 19 minutes and 8 flagged places, against 24 minutes and nothing. Safety costs
five minutes, and the app says so in its own words rather than hiding it.

Option 2 carries a **real news flag** from today's Jugantor article, so the flag list mixes seeded
roadworks with live reporting — which is what the product actually does.

**Backup:** `Gulshan 2 → Rampura` — recommended 100/100, 23 min, 0 flags, *"Fastest, and avoids 6
flagged corridors"*; worst option 52/100, 28 min, 6 flags.

### The two commands both sessions run

```
python backend/scripts/seed_risk_flags.py --fixture data/fixtures/video_scenario.json
python backend/scripts/verify_video_scenario.py
```

The first lays the scenario down fresh against the current clock. The second says whether segment 3
is filmable and which pair to use. **Run both at 09:00 and again at 20:55.**

### A defect this turned up, which is not ours to leave

`tests/invariants/test_confirmation_requires_a_vetted_source.py` still asserted that every
`confirmed` row cites **two** independent publishers. Commit `e7c4fa3` made one vetted newsroom
sufficient, but that test's body was never updated — it passed only while no confirmed
single-source row existed, and started failing the moment live ingestion wrote one. Fixed here to
use `is_confirmable`. **The same fix is needed on `develop`.**

---

## Order of work

T1 → **T2 → T3 → T4** (the routing loop, the real work) → T5 → T6 → T7 → T8 → T9.

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
