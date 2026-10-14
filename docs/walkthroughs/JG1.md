# JG1 — the journey that survives: start one, kill the app, find it waiting

> ## ⚠️ NOT YET SIGNED OFF ON A DEVICE
>
> Written with the work, in the same commit, as the rules require — but step 0
> below needs a database change that only the owner can make, so nobody has run
> this on a phone yet. Fill in the **Ran on** line and delete this box once it
> has passed. If a step does not work, it moves to **Rough edges**; it does not
> get softened.

**Ran on:** _(not yet)_ · **By:** _(not yet)_ · **Date:** _(not yet)_ · **Takes:** 7 minutes

## What this proves

That a journey is a thing on the server and not a thing on the screen. You press `Start`, the app
writes a row — who, from where, to where, which route, when, and when it was expected to end — and
*then* begins navigating. Force-stop the app from Android's own settings, which is the hardest kill
a phone can give you, reopen it, and the journey is offered back.

This is the first of the seven phases in [`../../JOURNEY_GUARDIAN.md`](../../JOURNEY_GUARDIAN.md)
and it is deliberately the dullest. **Nothing watches anything.** There is no deadline, no check-in
notification and no escalation; a judge watching this sees survival, not safety. The reason to build
it first is that every later phase hangs off this row: JG2 puts a clock on it, JG3 gives it an
audience.

## Preconditions

- [ ] **Step 0 has been done** (below). Without it there is no `journeys` table and every `Start`
      shows "Journey not recorded".
- [ ] `.\scripts\run.ps1` is up; `/health` returns 200
- [ ] The phone and the laptop are on the same network, and `EXPO_PUBLIC_API_BASE_URL` points at the
      laptop's LAN IP — not `localhost`
- [ ] Signed in on the phone (any account; a journey belongs to whoever is signed in)
- [ ] Location permission granted to the app, and GPS on

## Step 0 — apply the migration (once, by the owner)

Paste **[`../../backend/migrations/supabase/JG1_APPLY_IN_SUPABASE.sql`](../../backend/migrations/supabase/JG1_APPLY_IN_SUPABASE.sql)**
into the Supabase SQL Editor and run it in one go.

Expect one of two outcomes:

* **It succeeds.** `migrate.py status` will now list `20261014150000__journeys` as applied.
* **It stops with** `public.journeys exists but was not created by this migration`. That is the guard
  doing its job: a `journeys` table is already there and it has none of the constraints. Run
  `drop table public.journeys;` and paste the file again. Nothing is lost — such a table has never
  held a journey, because the endpoint that writes them did not exist before it.

`migrate.py up` will refuse, and not because of this migration: the ledger carries a row for version
`20261014120000` with no file on disk to explain it. See **Rough edges**.

## Steps

| # | Do this | You should see |
|---|---|---|
| 1 | Open the app. Let the splash clear. | The map, centred on Dhaka. **No** journey card under the search box. |
| 2 | Tap the route button (the one that brings up "Start location / Where to"). | The planner card, with your location filled in. |
| 3 | Type a destination — `Mirpur 10` — and pick the suggestion. | Up to three routes drawn on the map, and the comparison card at the bottom with safety scores. |
| 4 | Note the chosen route's **minutes** and its **safety score**. Write them down. | Something like `18 min · 64/100`. |
| 5 | Press **Start**. | The planner card disappears. The navigation banner appears at the bottom with an instruction. The camera follows you. |
| 6 | Pull down Android's notification shade, go to **Settings → Apps → Meridian → Force stop**, and confirm. | The app dies. Not "back out of it" — **Force stop**. Backgrounding it proves nothing; this phase is about the process being killed. |
| 7 | Open the app again from the launcher. Let it settle for two or three seconds. | The map, and **under the search box a card reading "Journey in progress" with `18 min to Mirpur 10 · started 9:14 pm`** — the same minutes you wrote down in step 4, and the clock time you pressed Start. Two buttons: **End** and **Resume**. |
| 8 | Check that the two round buttons on the right (locate, report) have moved **down** below the card, and that none of them is covered. | A clean stack: search box, journey card, buttons. |
| 9 | Press **Resume**. | Route mode comes back. The destination field reads `Mirpur 10`. The route is drawn again — **re-routed from where you are standing now**, so if you walked during steps 6–7 it starts at your feet, not where you began. The comparison card is back. |
| 10 | Press **Start** on the comparison card. | Following resumes. |
| 11 | Open the app's journey list in Supabase (`select state, destination_label, started_at from journeys order by started_at desc limit 5;`). | **One** row for this trip, in state `active`, with the `started_at` from step 7 — **not** a second row and not a refreshed timestamp. This is the whole point of step 9: resuming does not restart. |
| 12 | Press the **✕** on the navigation banner. | Following stops. The planner card comes back. |
| 13 | Back out of route mode (the **✕** on the planner card), then re-run the Supabase query from step 11. | The row now reads `cancelled`, with an `ended_at`. No journey card on the map. |
| 14 | Start a fresh journey to somewhere close you can actually reach — across a car park is enough — and walk to it. | When you get within about 40 m of the pin, the banner says you have arrived. |
| 15 | Re-run the Supabase query. | That row reads **`arrived`**, not `cancelled`. The distinction matters more than anything else on this page: JG2 and JG3 exist to tell "got there" apart from "stopped telling us". |
| 16 | Turn **aeroplane mode on**, start a journey, and press Start. | A dialog in **the app's own material** — glass pane, Inter, the amber warning badge, a single *Continue anyway* — reading *"Journey not recorded … Directions will still work, but this journey will not be here if the app restarts."* Not Android's grey box. Then the route is followed anyway. |
| 17 | While you are there, press **Start** a second time, still offline. | The same dialog again. A failure that says nothing the second time is worse than one that says nothing the first. |

## Rough edges

* **`migrate.py up` is blocked by a ledger row nobody can account for.** `public.schema_migrations`
  has a row for version `20261014120000`, applied 2026-10-14 08:19 UTC, with no file in the
  repository on any branch and nothing in git history that ever added one. `up` refuses to run while
  any applied migration has changed or vanished, so it refuses for *all* migrations, not just this
  one. Hence step 0 being a paste. **Whoever ran that needs to say what it was** — until then,
  deleting the row would be destroying the only evidence of it.
* **Two taps to resume, not one.** `Resume` restores route mode and the route and then stops at the
  comparison card; you press `Start` again. That is on purpose for two reasons. A fresh route is a
  fresh set of candidates and which one to take is a question worth seeing the answer to. And the
  navigator's `start` closes over the route in the render it was created in, so calling it in the
  same tick as the new route arriving would quietly follow the *old* path — a bug that looks exactly
  like Resume doing nothing. One honest extra tap beat it.
* **The minutes on the journey card do not count down.** `18 min to Mirpur 10` is what the route
  promised when you pressed Start, not time remaining, and it still says 18 an hour later. There is
  no clock in JG1 at all. JG2 is the phase that puts one there, and until then a countdown would be
  a number nothing is maintaining.
* **Arrival needs the navigator running.** The `arrived` state is set when the follower sees you
  within 40 m of the final point. Force-stop the app on the last hundred metres and the journey
  stays `active` until something closes it — there is no server-side geofence on the destination,
  because that is JG2's territory.
* **A stale `active` row is cleared by the next `Start`, not by a sweep.** Starting a journey cancels
  any journey still open. That is why the Start button never jams, and it is also why a journey
  abandoned without pressing anything sits in the table as `active` until the next trip. Nothing
  reads it in the meantime.
* **One journey per person, enforced by the database.** `idx_journeys_one_active_per_user`. If it
  ever does fire, the `Start` button will fail with an insert error rather than quietly producing two
  live journeys — which, from JG3 onward, would mean two guardians watching one person.
* **Only this dialog is the app's own.** `components/Dialog.tsx` replaces
  `Alert.alert` for the one message JG1 adds. The rest of the map screen's alerts —
  "Location unavailable", "No Routes", "Cannot follow this route" — are still the
  operating system's box, and they pre-date this phase. They look wrong next to this
  one; converting them is a change to code JG1 does not own.
* **No position log, no polyline.** The row holds the destination and the clock, not the line you
  walked. Both absences are deliberate and both are written down in the migration's header. JG5 is
  the phase that wants history.

## Fallback if it fails live

* **Step 0 never ran / no `journeys` table.** Every `Start` shows the "Journey not recorded" dialog
  and navigation works exactly as it did before JG1. Demo the routing and skip this page. Nothing
  else in the app depends on journeys.
* **The resume card does not appear after a force-stop.** First check `/health` from the phone's
  browser — a laptop IP that changed is the usual cause, and a release APK bakes
  `EXPO_PUBLIC_API_BASE_URL` in at build time. Then run the step-11 query: if the row is there and
  `active`, it is a client problem; if it is not there, step 0 or the network is.
* **Resume routes to the wrong place.** Press **End** and start again by hand. The destination label
  on the card is the ground truth for what to type.

## Numbers

| | |
|---|---|
| New backend routes | 4 (`POST /journeys`, `GET /journeys/active`, `POST /journeys/{id}/arrive`, `POST /journeys/{id}/cancel`) |
| New table | 1 — `public.journeys`, 16 columns, 8 CHECK constraints, 1 partial unique index |
| States | 3 (`active`, `arrived`, `cancelled`); 2 transitions |
| Position rows written per journey | 0 |
| Polyline coordinates stored per journey | 0 |
| Launch cost | one `GET /journeys/active`, once per cold start |
| Backend invariant tests added | 20 (`tests/invariants/test_journey_states.py`) |
| Frontend tests added | 17 (`src/features/journey/resume.test.ts`) |
