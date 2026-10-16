# JG2 — the deadline: set it, miss it, answer it in one tap

> ## ✅ SIGNED OFF — 15 Oct 2026, with step 9 recorded as failing
>
> Five runs on a real phone. Between them they confirmed **steps 1–10** directly
> — the chips, the arithmetic, `leash_seconds = 120`, a deadline at exactly
> `started_at + 2 min`, a heartbeat that moves it by two minutes rather than
> twelve, the sweep asking on time, a notification that names no place and no
> time, `check_in_sent`, and an answer recorded against the trip with the
> deadline moved out. Remote push is live end to end — Expo `ok` and an FCM
> delivery receipt of `ok`. **Steps 11–19 are signed off by the owner** rather
> than transcribed run by run.
>
> **Step 9 does not pass and is not expected to.** The lock-screen `I'm fine`
> button is usually not drawn at all, for a reason outside this codebase — two
> different renderers draw this notification and only one knows about Expo
> categories. It stays in the steps as a failing step, with the measurement under
> **Rough edges**, because softening it would hide the one part of this phase that
> does not work. The answer is given on the journey card instead (step 16), which
> goes through the same endpoint and is measured: asked `12:00:04`, answered
> `12:00:34`.
>
> Every run found something. Three were real bugs, all fixed and all under
> **Rough edges**: the heartbeat eating the chosen leash, the answer eating it
> too, and answering twice being reported as failing once. Two were not bugs and
> are written up there as well, because both look exactly like one from the
> phone: a collapsed notification hides its button, and a phone on silent does
> not buzz whatever the channel says.

**Ran on:** Android (Pixel 7 Pro) · **By:** nakib · **Date:** 2026-10-15 ·
**Steps 1–10:** confirmed on device · **Steps 11–19:** owner-signed ·
**Step 9:** fails, see **Rough edges** · **Takes:** 13 minutes

## What this proves

That the clock is on the server. You set a time, the phone goes in your pocket, and the thing that
notices you are late is a sweep running in a container — not a timer in the app, which is why it
still works when the app has been force-stopped and why it would still work if the phone were in a
river.

And that answering costs one tap from a lock screen, with the app never coming to the front.

**Nobody else is told anything.** There is no guardian, no contact, no message leaving the account.
A judge watching this sees a system that notices and asks; the second person is JG3.

## Preconditions

- [ ] **Step 0 has been done** (below)
- [ ] `.\scripts\run.ps1` is up, including the **worker** container — `docker compose ps` must show
      `meridian-worker` running. Without it nothing sweeps and no check-in ever arrives
- [ ] **The worker has been restarted since `journey_watch.py` was written** — `docker compose
      restart worker`. Celery beat builds its schedule once, at startup, from the agents it can
      import, so a worker that was already running when the agent landed has no entry for it and
      sweeps nothing, for ever, with no error anywhere. This is what happened on the first run of
      this page. Confirm with `docker compose exec worker python -c "from app.agents.registry import
      beat_schedule; print(sorted(beat_schedule()))"` and look for `journey_watch`, or watch for
      `Sending due task journey_watch` in `docker compose logs -f worker`
- [ ] `/health` returns 200 from the phone's browser, at the laptop's LAN IP
- [ ] Signed in on the phone, location permission granted, GPS on
- [ ] **Notification permission granted**, and this is a **development or release build, not Expo
      Go** — Expo Go on Android cannot receive remote push at all (SDK 53 removed it). Check
      `Profile → Alerts`, which reports all four prerequisites
- [ ] **`docs/walkthroughs/B6a.md` Part 2 is done.** This is the one that stopped the second run of
      this page, and it is account setup rather than code: an EAS project id in
      `frontend/app.json` (`extra.eas.projectId` — it ships **empty**), FCM credentials uploaded to
      that project, and `PUSH_ENABLED=true` in `backend/.env` (it ships **false**, deliberately).
      Until all three are true, `push_devices` stays empty, the sweep reports
      `no_device: 1, sent: 0`, and **no notification can arrive** — steps 6, 7, 9 and **13** are not
      runnable. Everything else on this page is, because the journey card answers the same question
      through the same endpoint. Check with:
      `select count(*) from push_devices where disabled_at is null;` — zero means stop here and do
      B6a Part 2 first
- [ ] **The phone is NOT on silent.** Android's silent ringer mode suppresses sound *and* vibration
      no matter how the channel is configured, and "you feel a buzz" is the whole claim of this
      phase. Check with `adb shell settings get global mode_ringer` -- **2** is normal, 1 is vibrate,
      **0 is silent and this page cannot pass**. Also check Do Not Disturb is off
      (`adb shell settings get global zen_mode`, 0 = off): the `journey_check_in` channel has
      `bypassDnd=false`, because raising it needs notification-policy access the app does not ask
      for. This cost the fourth run of this page
- [ ] **The app is exempt from battery optimisation.** Without it Android freezes the app process
      and the check-in is not delivered until something wakes the phone -- which makes the buzz look
      like a consequence of picking the phone up, because it is. Set it with
      `adb shell dumpsys deviceidle whitelist +com.Meridian.app`, or on the phone:
      `Settings -> Apps -> Meridian -> Battery -> Unrestricted`. Confirm with
      `adb shell dumpsys deviceidle whitelist | Select-String meridian`. **Step 13 cannot pass
      without this.** See **Rough edges**
- [ ] JG1 passes. This phase is built on its row

## Step 0 — apply the migration

```
cd backend
python scripts/migrate.py status      # 12 applied, 2 pending
python scripts/migrate.py up
```

Two migrations: `20261015120000__journey_deadline` and `20261015140000__journey_leash`. The second
is a bug fix for the first, found on the first device run — see **Rough edges**.

**Unlike JG1, this is not a paste.** JG1's step 0 had to be run by hand in the Supabase SQL editor
because the ledger carried a row for a migration with no file in the branch, and the runner refuses
to apply anything while any applied migration has changed or vanished. Merging `develop` brought that
file in — it was `20261014120000__news_crime_incidents` — so `up` works again.

## Steps

| # | Do this | You should see |
|---|---|---|
| 1 | Open the app, tap the route button, and route to somewhere a few minutes away. | Routes drawn, and **under the Driving/Walking row a new line: `Check in by 2:28 PM`** with four chips — `Route ETA`, `1 hr`, `30 min`, `2 min`. `Route ETA` is selected. |
| 2 | Check the arithmetic: the time shown should be **now + the chosen route's minutes + 10**. | If the route says 18 min and it is 2:00, the line reads `2:28 PM`. The 10 is the grace period. |
| 3 | Tap `30 min`, then `1 hr`, then `2 min`. | The time changes on every tap, immediately. `2 min` reads two minutes from now. |
| 4 | **Leave `2 min` selected** and press **Start**. Without this tap the rest of the page does not hold — the default is the route ETA plus ten minutes, so a 3-minute route would give you `+13` and a wait too long to sit through. | Navigation begins exactly as it did in JG1. |
| 5 | In Supabase: `select deadline_at, escalation_state, leash_seconds, last_heartbeat_at from journeys order by started_at desc limit 1;` | `deadline_at` is **two minutes after `started_at`**, `leash_seconds` is **120**, `escalation_state` is `normal`, `last_heartbeat_at` is null. |
| 5b | Wait one minute, still following, and re-run it. | `last_heartbeat_at` is set and `deadline_at` has moved — but by **about two minutes from the heartbeat, not twelve**. That is `leash_seconds` doing its job; see **Rough edges**. |
| 6 | **Screen off, phone down, and wait.** Do not open anything, and **do not tap the route button again** -- leaving route mode calls `journey.cancel()` and ends the journey, so the deadline then passes on a `cancelled` row that the sweep correctly ignores. Stay in navigation. | Within about three minutes — two for the deadline, up to one for the sweep — the phone **buzzes** with *"Are you there yet?"* and a single **I'm fine** button. |
| 7 | Read the notification **without unlocking**, and **expand it** (swipe down on it) to see the button. | It says nothing about where you are going, when you were due, or how far you have left. That is deliberate — see the note under the table. |
| 8 | Re-run the query from step 5. | `escalation_state` is now `check_in_sent` and `check_in_sent_at` is set. |
| 9 | Press **I'm fine** on the lock screen. **Do not unlock the phone.** **This step does not pass** -- the button is usually absent, for a reason that is not fixable from this codebase. Read **Rough edges**, then go to step 16. | The notification disappears. **The app does not open.** |
| 10 | Re-run the query, adding `answered_at`. | Back to `normal`, `answered_at` set, and **`deadline_at` has moved to about two minutes from now** — your leash, not the 15-minute extension. With `Route ETA`, `30 min` or `1 hr` selected it would be the full 15. See **Rough edges**. |
| 11 | Now unlock and watch the app for two minutes while following. | Re-run the query: `last_heartbeat_at` updates about once a minute, and `deadline_at` slides forward with it. This is the phone talking. |
| 12 | **Force-stop the app** from Android settings, mid-journey, and leave the phone alone. | The deadline stops moving — the last `last_heartbeat_at` is the last one before the kill. Silence buys nothing. |
| 13 | Wait for the deadline to pass with the app still force-stopped. | The check-in still arrives. **This is the step that matters most on this page:** the clock was never in the app. |
| 14 | Ignore it for six minutes. | Nothing further buzzes about *this* question. Nobody is messaged. (With a `2 min` leash a *new* question follows, which is the leash working — pick `Route ETA` for this step if that is confusing.) |
| 15 | Re-run the query with `unanswered_at`. | It is set, about five minutes after `check_in_sent_at`. That is the recorded non-response, and in JG3 it is what starts an escalation. Nothing acts on it today. |
| 16 | Open the app. | The journey card reads **"Are you there yet?"** with one **I'm fine** button, in place of End/Resume. Tap it. |
| 17 | Re-run the query. | `normal`, a fresh `answered_at`, `unanswered_at` back to null, deadline moved out. |
| 18 | Start a new journey with `Route ETA`, then back out of route mode entirely and start another. | The second journey's deadline uses the route ETA again — a `2 min` leash chosen for one trip is not inherited by the next. |
| 19 | Walk to the destination and arrive. | The journey closes as `arrived`, and no further check-in ever comes. |

**On step 7.** The notification deliberately names no place and no time. A lock screen is visible to
whoever is standing next to you, and JOURNEY_GUARDIAN.md §5 is about the case where that person is
the problem — a notification naming her destination tells him where she is going, and one naming her
deadline tells him how long he has. `test_the_check_in_names_no_place_and_no_time` asserts it.

## Rough edges

* **The lock-screen button is the least reliable part of this phase.** It posts the answer from a JS
  context Android wakes for the purpose, with no screen and no app in the foreground. On some
  handsets and some battery-saver settings that context is killed before the request completes, and
  the answer is simply lost — the journey stays at `check_in_sent` and the sweep records a
  non-response the person did not make. There is no error anywhere; the notification disappears
  either way. The journey card in the app answers the same question through the same endpoint, and
  step 16 is there to prove it. **If step 9 fails on your handset, say so here rather than softening
  this.**
* **Answering twice used to look like failing once, in the worst possible words.** Found on the
  fourth device run. There are two ways to answer and they race: tapping the notification wakes the
  app and `answerFromNotification` posts the answer, and the card then renders from state that
  predates that round trip -- still offering **I'm fine** for a question the server has already
  closed. Pressing it posted a second answer, the endpoint correctly refused it with a 409 because
  `escalation_state` was no longer `check_in_sent`, and the screen reported *"Journey not recorded
  ... this journey will not be here if the app restarts"*. The real row said
  `answered_at = 12:00:34`, thirty seconds earlier. Two bugs in one: `checkIn` treated every failure
  as an unanswered question, and the dialog appended copy written for a failed journey *start* to a
  check-in failure. It now asks the server whether a question is still outstanding -- the only thing
  that actually distinguishes the two -- and each failure carries its own title and body. Four tests
  fail if either half is reverted.
* **The lock-screen button is usually not there at all, and that is not fixable from here.** Two
  different pieces of software draw this notification, and only one of them knows about the button:

  | Drawn by | `dumpsys` tag | actions |
  |---|---|---|
  | `expo-notifications`, in the app process | `0:1792065930503527%d2037…` (the FCM message id) | **`actions=1`** |
  | Android's own FCM renderer | `FCM-Notification:12703374` | **none** |

  Expo's relay sends the title and body as an FCM *notification* payload. When Android renders that
  itself — which it did on every observed run after the first — the Expo notification *category* is
  never consulted, so the `I'm fine` button does not exist on that notification. Nothing reports it.
  It is not a collapsed-versus-expanded problem and it is not a registration problem:
  `registerCheckInCategory` runs, the category is correct, and `actions=1` on the one Expo-drawn
  record proves it.

  Which renderer gets the message is not something the sender chooses. Forcing the Expo path means
  sending **data-only** messages, which means talking to FCM directly rather than through Expo's
  relay. `alerts/expo.py::PushTransport` is the seam for exactly that and the file already says so —
  so it is a contained change rather than a rewrite, but it is a new credential, a new transport and
  a rebuild, and it was judged not worth the risk eight days before the finale.

  **So step 9 fails, and steps 7 and 13 are about reading the notification rather than answering
  from it.** The answer is given on the journey card — step 16 — which goes through the same
  endpoint and is measured: asked `12:00:04`, answered `12:00:34`. The card was built as the other
  half of this feature precisely because the notification is the half most likely to be missing, and
  it is now the primary path rather than the fallback.

  An earlier version of this page said `actions=1` meant the button was attached and the reader had
  simply not expanded the notification. That was written from the single Expo-drawn record, before
  the FCM-drawn ones were seen, and it was wrong.

* **A pressed button whose answer is thrown away.** Separate from the above, and found in the same
  session: `addNotificationResponseReceivedListener` only fires while the JS runtime is alive, so a
  lock-screen action pressed against a frozen or killed app was delivered to Android, dismissed the
  notification, and was then held by `expo-notifications` as the *last* response — which nothing in
  this app ever read. The answer was discarded silently and the person had to open the app and
  answer a second time. `notification.service.ts` now reads
  `getLastNotificationResponseAsync()` at startup and queues taps that arrive before a handler is
  installed, with a `notificationId:actionIdentifier` dedupe so the cold-start read and the live
  listener cannot both answer the same check-in. It matters on any handset where the button *is*
  drawn, and it was a real bug regardless of which renderer wins.
* **The notification arrives when you wake the phone, which makes it look like the phone is causing
  it.** It is. Found on the fifth device run: the deadline passed, nothing happened, and the buzz
  came the instant the screen was tapped — every time, which reads like the app polling on wake
  rather than a server pushing. The log says what it actually is:

  ```
  18:51:15  D/ActivityManager: freezing 13857 com.Meridian.app
  ```

  Android's Cached App Freezer suspends the process, and `expo-notifications` composes the
  notification **inside the app process** rather than letting the system tray draw it — so a frozen
  app means a message that sits with FCM until something thaws it. Waking the screen thaws it. The
  app's App Standby bucket was `10` (active) and the FCM priority was already `high`; neither is the
  lever. The lever is the battery-optimization exemption, and the app does not have it.

  Proven rather than assumed. With the app whitelisted and the screen off and the device reporting
  `mWakefulness=Dreaming` throughout, a push posted in **5 seconds**. Without it, never, until the
  screen came on.

  **This defeats step 13, which is the claim this phase exists to make.** A deadline that only fires
  when you happen to pick the phone up is not a server-side clock in any sense a person would care
  about. The exemption is a device setting today (see the preconditions); doing it inside the app
  needs `expo-intent-launcher`, the `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` permission and somewhere
  in `Profile → Alerts` to ask from — a new dependency and a new permission, so it is a decision
  rather than a fix, and it is not in JG2.
* **A phone on silent does not buzz, and that silences the safety question.** The channel is
  correctly HIGH with `vibrationEnabled=true` and a `[0, 400, 200, 400]` pattern, and Android's
  silent ringer mode overrides all of it. Lots of people carry a phone on silent permanently, and
  for them this phase delivers a notification they will see whenever they next look -- which is not
  the promise *"you feel a buzz, you tap once, you carry on"*. `bypassDnd` would need
  notification-policy access the app does not request, and asking for it to make a check-in louder
  than the user's own silent switch is a decision for JG4 and the trial, not a quiet default. Worth
  saying out loud because it is a limit of the design rather than a bug in it.
* **A chosen leash used to be eaten by the first heartbeat, and that is what `leash_seconds` is
  for.** On the first device run of this phase somebody started a 3-minute walk, chose `2 min`, and
  watched the row go `19:45:53 started, deadline 19:47:53` — correct — and then `19:47:31 heartbeat,
  deadline 19:57:31`. The heartbeat proposed `now + remaining + 10 minutes of grace` and `greatest()`
  took it because it was later, so sixty seconds after asking to be checked on in two minutes they
  had been given twelve, silently, and the check-in never came. `20261015140000__journey_leash.sql`
  stores the choice and caps the proposal with it. Four tests fail if the cap is removed.
* **And then the *answer* was eating it too, one path over.** Found on the second device run, on the
  row that was meant to confirm the first fix: `leash_seconds = 120`, answered at `10:59:22`,
  `deadline_at = 11:14:22`. Fifteen minutes handed to somebody who had asked to be checked on every
  two — for tapping the button they were asked to tap. Two things move a deadline, the first fix
  capped one of them, and `ANSWER_EXTENSION` is a guess while a leash is something the person said
  out loud. `_CHECK_IN` now carries the same `coalesce` as `_HEARTBEAT`. It changes nothing for
  `Route ETA`, `30 min` or `1 hr`, all of which are longer than fifteen minutes or have no leash at
  all; only `2 min` was affected. No migration — the column was already there.
* **Answering a short leash means being asked again shortly.** That is the leash, not a defect: `2
  min` means "ask me every two minutes" and it keeps its word after an answer as well as after a
  heartbeat. It makes the chip noisy by design, and it is the reason step 14 says to use `Route ETA`
  if the repetition gets in the way of what that step is checking.
* **A stationary phone can still buy extensions, up to six hours.** A heartbeat extends the deadline
  because the phone reported, not because it moved — which is the design (`a phone in a jam talks`),
  and the cost is that a phone sitting in a bag with the app open and a route loaded reports a steady
  "about twenty minutes left" and slides its deadline forward one minute at a time. `MAX_DEADLINE`
  caps it at six hours from the start. Detecting the difference needs the signals JG5 collects —
  speed, screen contact, battery — and guessing at them now would produce check-ins that fire in
  traffic jams, which is the false alarm the whole design is built to avoid.
* **Up to a minute late, always.** The sweep runs every minute, so a deadline at 10:40:10 is noticed
  at 10:41:00. The grace period in front of it is ten minutes, so this is noise — but it is why
  `MIN_DEADLINE` is two minutes and not thirty seconds.
* **The deadline on the card does not count down.** It is an instant — "check in by 2:28 PM" — not
  "12 min left". An instant stays true while nobody is looking at it; a duration does not, and
  nothing in this app is maintaining one.
* **One question at a time, and it repeats.** Answering returns the journey to `normal` and buys 15
  minutes. A journey that runs long is asked again, and again. There is no cap on how many times —
  which is correct for a safety feature and is also the thing most likely to annoy somebody in week
  one. The trial JG4 depends on is what should set a limit, not a guess today.
* **Grace, window and extension are guesses.** 10 minutes, 5 minutes, 15 minutes. They are all in
  `backend/app/journeys/deadline.py` and nowhere else, and JG4 is a change to that file.
* **Nothing is told to anybody.** `unanswered_at` is written and read by nothing. That is the whole
  scope line of this phase, and `test_the_non_response_branch_sends_nothing` fails if it moves.

* **The deadline passed and nothing happened, and the sweep says `due: 0`.** Check `state` before
  suspecting the sweep:

  ```sql
  select state, ended_at, deadline_at, deadline_at - ended_at as gap
    from journeys order by started_at desc limit 1;
  ```

  `state = 'cancelled'` with `ended_at` *before* `deadline_at` means the journey was ended before it
  was ever late, and `due: 0` is the right answer. This cost the third run of this page: the journey
  was cancelled at `11:51:28` with a deadline of `11:52:58`, and leaving route mode is what did it --
  `toggleRouteMode` ends the journey on the way out, deliberately, because it throws away the route
  the journey is about. The sweep only ever looks at `state = 'active'`.

## Fallback if it fails live

* **No notification ever arrives.** Three different causes, all of which look identical from the
  phone — nothing happens, nothing errors — and each of the first two has already cost a run of this
  page. Read the sweep's own metrics and they tell them apart in one query:

  ```sql
  select started_at, metrics from agent_runs
   where agent = 'journey_watch' and (metrics->>'due')::float > 0
   order by started_at desc limit 5;
  ```

  * **No rows at all, ever** (`select count(*) from agent_runs where agent = 'journey_watch'` is 0)
    — beat has never scheduled the agent. The worker is down, or was already running when
    `journey_watch.py` landed. `docker compose restart worker`. *This was the first run's failure.*
  * **`due: 1, sent: 0, no_device: 1`** — the sweep asked, correctly, and found no phone to ask.
    `push_devices` is empty. That is **B6a Part 2 not done**, not a bug in this phase: an empty
    `extra.eas.projectId` means the app never requests a token, and `PUSH_ENABLED=false` means the
    backend would not deliver one if it had it. *This was the second run's failure*, and it is why
    it is now a precondition. The journey card still answers the same question — step 16 — so the
    rest of the page runs.
  * **`due: 1, sent: 0, failed: 1`** — it tried and Expo refused. Now `Profile → Alerts` and the
    `last_rejection` table in B6a's troubleshooting section are the right places to look.
* **The notification only arrives when you wake the phone.** Battery optimisation; the app process
  is frozen. `adb logcat -d | Select-String "freezing.*Meridian"` shows it. Whitelist it -- see the
  preconditions -- and it posts within about five seconds with the screen off.
* **The notification arrives with no buttons.** The app's notification category id disagrees with the
  backend's, or the build predates `registerCheckInCategory`. Demo step 16 instead — the card answers
  the same question.
* **The deadline never moves while walking.** The heartbeat is failing silently, by design. Check
  `last_heartbeat_at`. If it is null, the app is not reaching the server; if it is updating and
  `deadline_at` is not, the journey is already at `check_in_sent`, where heartbeats deliberately stop
  moving it.
* **Everything is too slow to demo.** Use the `2 min` chip and say what it is: a short leash, which is
  a real feature arriving early rather than a test hook.

## Numbers

| | |
|---|---|
| New backend routes | 2 (`POST /journeys/{id}/heartbeat`, `POST /journeys/{id}/check-in`) |
| New columns | 7 on `public.journeys`; 6 new CHECK constraints; 1 partial index |
| Escalation states | 2 (`normal`, `check_in_sent`); 2 edges, and it is a cycle |
| New agents | 1 — `journey_watch`, every minute |
| Things that can move a deadline | 2 — a heartbeat and an answer, **both** capped by the leash |
| Positions stored per journey | 0 |
| People told when you do not answer | 0 (JG3) |
| Backend tests added | 50 (`tests/invariants/test_journey_deadline.py`) |
| Frontend tests added | 23 (`src/features/journey/deadline.test.ts`) |
| Heartbeat interval | 60 s, matching the sweep that reads it |
| Grace / answer window / extension | 10 min / 5 min / 15 min — all guesses, all in one file |
