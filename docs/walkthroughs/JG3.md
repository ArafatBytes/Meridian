# JG3 — someone else knows: told you set off, told you arrived, told if you did not

> ## ✅ RUN ON A DEVICE — 16 Oct 2026
>
> The thing this page existed to establish: **email reaches a real inbox.** Both
> the "started" notice and the escalation arrived in Gmail, in the inbox and not
> in spam, from the configured `SMTP_FROM`. The escalation landed with the
> origin fallback in it — *"They started from 23.78027, 90.37084 … that is the
> start of the journey, not a sighting"* — which is the branch a stationary
> phone actually produces, and the one no fixture had ever exercised.
>
> Two things changed **after** the run and are not what was observed:
> the three notices now ship as HTML as well as plain text, and **ring four was
> removed** (see *Rough edges*), which retires steps B10–B11 as they were run.

**Ran on:** a real Android device + Gmail · **By:** Nakib · **Date:** 16 Oct 2026 ·
**Takes:** 12 minutes for Runs A, C and D; **plus ~20 minutes of waiting** for Run B unless you
use the fast-forward in step B6 · **Needs:** one phone and one email inbox — **not** two phones,
and **not** a second account

## What this proves

That somebody else finds out. JG1 made a journey survive the app being killed; JG2 made the server
notice you were late and ask you once. This is the phase where a second person is told — when you
set off, when you arrive, and, if you stop answering, that you have stopped answering, with the last
place your phone reported from.

And that it is **off by default**. The picker starts on `Nobody`, and a journey with no guardian
sends nothing to anybody, collects no position at all, and is exactly JG2's behaviour. That default
is the part worth pointing at: a safety feature that silently emails somebody's mother the first
time they press Start is one people stop using.

A judge watching Run A sees two emails arrive while the phone sits in somebody's pocket. Run B is
the one the product is for, and it takes twenty minutes — so demo that one with the fast-forward in
step B6, or from a recording.

## Preconditions

- [ ] **JG1 and JG2 pass.** This phase is built on JG2's deadline and its sweep; if the check-in
      never arrives, nothing here escalates
- [ ] **One phone, signed in, location granted, GPS on.** It is the only device this page needs;
      the paragraph under this list says why, and what "the inbox" means below
- [ ] **Step 0 has been done** (below) — two migrations
- [ ] **An emergency contact whose email you can read.** On the phone: `Profile → Emergency
      Contacts → +`, give it a name you will recognise in a subject line, and that address — see
      **Which address to use** below. **A contact with no email cannot be a guardian**: the picker
      shows it greyed out with `· no email`, and the server refuses it with a 422
- [ ] **SMTP is configured in `backend/.env`.** Five names, and all five must be non-empty:
      `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`. The one-line check is
      under **Which address to use** below; it prints one boolean per name and no values. All five
      `True`, or this page cannot pass — with them empty the sweep reports `notices_failed` and
      nothing arrives, which looks identical to a broken agent
- [ ] **Check the spam folder before deciding nothing arrived.** These are the first messages
      this project has ever sent from `FROM_EMAIL` to that address, and a first message from a new
      sender to a Gmail address is a coin toss. *This is the single most likely way this page fails,
      and it is not a bug in the feature*
- [ ] `.\scripts\run.ps1` is up, including the **worker** — `docker compose ps` must show
      `meridian-worker` running
- [ ] **The worker has been restarted since `journey_watch.py` last changed** — `docker compose
      restart worker`. Celery beat builds its schedule once at startup; a worker that was already
      running has no entry for the agent and sweeps nothing, for ever, with no error anywhere. This
      cost JG2 a run. Confirm with `docker compose logs -f worker` and look for
      `Sending due task journey_watch`
- [ ] **A rebuilt app.** `app.json` gained `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` during JG2's fixes
      and JG3 added a screen and a route, so an old build has neither. `.\scripts\run.ps1`, then
      install the development build on the phone
- [ ] **From JG2, both still true:** the app is exempt from battery optimisation
      (`adb shell dumpsys deviceidle whitelist +com.Meridian.app`), and **the phone is not on
      silent** (`adb shell settings get global mode_ringer` must be `2`). Neither affects the
      *emails* — those come from the server — but both affect every check-in push, which is what
      you are deliberately not answering in Run B

**There is no second phone, and no second account.** The guardian has no app, no login and no
screen — `JG3_PLAN.md` §6 is explicit that JG3 gives them nothing but email — so "the guardian" is
an **address**, and reading it in a browser tab is the whole of their half. A second Meridian
account would prove nothing here, because a guardian never signs in to anything. Where the steps
below say **"the inbox"**, they mean wherever that address is read; a laptop tab is easiest, and it
has one real advantage over reading the mail on the phone itself — see the note under Run B.

### Which address to use

It changes what the run proves, so it is worth deciding before you start:

| Address | Runs today | What it tests |
|---|---|---|
| **Your own** — the one `FROM_EMAIL` sends from | Yes, immediately | The feature. Mail from an address to itself is never spam-filtered, so this proves the sweep sends and the message reads correctly, and proves **nothing** about deliverability |
| **Any second address** — another free Gmail, Outlook, anything | Yes | The same, plus first-contact filtering, which is the honest test |
| **The address that will be on stage** | Yes | The only one that answers the question that matters on the 24th |

Use the first to run the page. Use the **third at least once before the 23rd**, because a first
message from a new sender to a Gmail address is a coin toss, and that coin gets flipped live.

Whichever you pick, confirm the server can send at all before starting. This prints one boolean per
setting and none of the values:

```
cd backend
python -c "from app.core.config import settings as s; print({k: bool(getattr(s,k)) for k in ('SMTP_SERVER','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','FROM_EMAIL')})"
```

### Running this at a desk

Nothing on this page needs you to walk anywhere, which is worth stating because two steps read as
though it does.

* **Heartbeats are a timer, not a tripwire.** Sixty seconds of being in navigation is sixty seconds
  of reporting in, stationary or not.
* **Arriving** is the one thing a desk cannot do honestly, because the navigator decides it by
  reaching the end of the route. Close the journey the way the app would —
  `update journeys set state = 'arrived', ended_at = now() where journey_id = '<id>';` — and the
  sweep sends the "arrived safely" email from there. That is the branch under test; the walking is
  not.
* **A stored position** needs a fix the navigator will accept, which indoors it usually will not.
  The escalation email covers that case on its own — see the note under Run B — and the SQL there
  sets a point by hand if you want to see the other wording.

A nudge in SQL moves the clock or the state; it never skips a gate, a CHECK or a message. Everything
that decides *whether* to send, and *what* to say, is the code the unhurried run uses.

## Step 0 — apply the migrations

Two files. The first is JG3's schema; the second is a one-bug correction to it, written the same day.

```
cd backend
python scripts/migrate.py status
```

Both should read `applied`:

```
applied  20261015180000__journey_guardian
applied  20261015190000__guardian_notice_outlives_the_contact
```

**If either says `pending`, do not run `up`** — it will refuse, and for a reason that has nothing to
do with this phase. The ledger carries a row for `20261015160000`, applied by a teammate whose file
has never been pushed, and the runner stops while any applied migration has changed or vanished. So
print the SQL and paste it into the Supabase SQL editor instead:

```
python scripts/migrate.py sql --version 20261015180000
python scripts/migrate.py sql --version 20261015190000
```

**Paste the whole output of each, including the `insert into public.schema_migrations` at the
bottom.** That insert is what records the migration as applied; without it the DDL runs but
`status` keeps saying `pending`, which is exactly what happened on the first manual application of
each of these. Afterwards, confirm the correction actually took:

```sql
select count(*) from pg_constraint where conname = 'journeys_notice_needs_guardian';
```

**Zero.** A `1` means `20261015190000` did not run, and deleting any contact who has ever been a
guardian will fail — see **Rough edges**.

The query every run below uses, once:

```sql
select state, escalation_state, guardian_contact_id is not null as has_guardian,
       deadline_at, check_in_sent_at, answered_at, unanswered_at,
       check_in_repeated_at, contacts_notified_at, full_sos_at,
       started_notice_at, arrived_notice_at,
       last_position is not null as has_position, last_position_at
  from journeys order by started_at desc limit 1;
```

## Run A — told you set off, told you arrived

The happy path, and the one a judge should see. About six minutes, most of it walking.

| # | Do this | You should see |
|---|---|---|
| A1 | Route to somewhere two or three minutes away, as in JG2. | Routes drawn, the `Check in by …` row, and **under it a new row: `If you go quiet, tell nobody`** with a `Nobody` chip selected and one chip per contact. |
| A2 | Look at the contact chips without tapping. | Your contact is there by name. Any contact with no email address is **dimmed and reads `· no email`** — it cannot be picked. |
| A3 | Tap your contact's chip. | The chip highlights, the row above changes to `If you go quiet, tell <name>`, and a line appears: *"They get an email when you set off, when you arrive, and if you stop answering check-ins."* **Nothing has been sent yet** — nothing is sent until Start. |
| A4 | Leave the deadline on `Route ETA`. Press **Start**. | Navigation begins. |
| A5 | Run the query. | `has_guardian` is **true**, `escalation_state` is `normal`, `started_notice_at` is **null** — the email has not been sent yet, because the sweep sends it, not the request. |
| A6 | Wait up to a minute. Re-run the query. | `started_notice_at` is now set. |
| A7 | **Open the inbox.** | An email: subject **`<your name> has started a journey`**. It names the destination and the time you are due, says you will get one more message when they arrive, says you will be told *and only then told where they were last* if they do not — and ends *"There is nothing you need to do now."* **No location anywhere in it.** |
| A8 | Look at the journey card on the map. | A third line under the destination: **`Telling <name>`**. |
| A9 | Tap the journey card. | The **journey screen**: *"On your way."*, *"<name> will hear if you go quiet."*, the destination, `Check in by …`, `Telling <name>`, and a timeline — `Journey started`, `<name> was told you set off`. |
| A10 | Arrive. Walking or driving the route to its end is the real thing; at a desk, close it the way the app does — `update journeys set state = 'arrived', ended_at = now() where journey_id = '<id>';` — and the sweep takes it from there. | The journey closes. The card disappears (after the next `refresh`, so reopen the app if it is still showing). |
| A11 | Re-run the query. | `state` is `arrived`, `arrived_notice_at` set within a minute. |
| A12 | **The inbox again.** | A second email: **`<your name> arrived safely`**, two lines, no location. That subject line is the whole product — it is all a guardian needs to read. |

**On what these look like.** All three notices are `multipart/alternative`: a laid-out HTML half and
the plain text it was written as. The palette is the tone and is checked by a test — the "started"
notice is **slate**, "arrived safely" is **green**, and only the escalation wears the SOS mail's
**red**, so a guardian who gets two of these a week still reacts to the third. The plain half is not
a formality: a client that cannot render HTML shows markup instead of the message, and that client is
a cheap handset. Both halves carry the same sentences — the privacy tests read both, because a
layout is exactly where somebody later adds a helpful map thumbnail to a notice that must not have
one.

## Run B — you stopped answering, so they were told

The one the feature exists for. The ladder is five minutes per rung by design, so this is **about
twenty minutes end to end**; step B6 is how to compress it.

| # | Do this | You should see |
|---|---|---|
| B1 | Route somewhere, pick the same contact, and this time tap the **`2 min`** deadline chip. Press **Start**. | Navigation begins. `deadline_at` is two minutes after `started_at`. |
| B2 | **Stay in navigation for ninety seconds.** No walking: the heartbeat is a timer, not a tripwire — it fires every 60 s while following and sends whatever fix the navigator holds. | Re-run the query: `last_heartbeat_at` is set. **`has_position` may be either**, and indoors it is usually false — see the note below the table. Both are fine; the rest of the run works either way. |
| B3 | Now put the phone down, screen off, and **ignore everything**. **Read the guardian's mail somewhere other than this phone if you can** — see the warning below the table. Do not open the app, and **do not tap the route button** — leaving route mode cancels the journey and the sweep correctly ignores a cancelled row (this cost JG2 a run). | Within about three minutes the check-in arrives: *"Are you there yet?"*. **Do not answer it.** |
| B4 | Re-run the query. | `escalation_state` is `check_in_sent`, `check_in_sent_at` set. |
| B5 | Wait five more minutes. Re-run. | `unanswered_at` is set **and** `escalation_state` has moved to **`check_in_repeated`** with `check_in_repeated_at` set — the same sweep does both. The phone buzzes a **second** time. Still do not answer. |
| B6 | **The fast-forward.** Each remaining rung needs the one below it to be five minutes old. To skip the waiting, age the last stamp by hand and let the next sweep find it: <br><br>`update journeys set check_in_repeated_at = now() - interval '6 minutes' where journey_id = '<id>';` <br><br>This moves the clock, not the code: every gate, every CHECK and every message is the same one the unhurried run uses. | Within a minute, the next rung fires. |
| B7 | Wait for the next sweep. Re-run the query. | `escalation_state` is **`contacts_notified`**, `contacts_notified_at` set. |
| B8 | **The inbox.** | The email that matters: subject **`<your name> has not arrived and is not answering`**. It says Meridian asked twice, then gives a point and a Google Maps link — **either** *"The last place their phone reported from was …"* if a fix was stored, **or** *"They started from … that is the start of the journey, not a sighting"* if none was. Then *"You are the only person who has been told."* **No instruction to call the police** — see **Rough edges**. |
| B9 | Open the app and tap the journey card. | The journey screen reads **`<name> has been emailed.`** in red, *"Meridian has done everything it does automatically."*, and the timeline now has every rung on it with times. |
| B10 | Back out without answering, age `contacts_notified_at` by six minutes as in B6, and wait a few sweeps. | **Nothing happens, and that is the test.** `escalation_state` stays `contacts_notified`, no further email is sent, and `agent_runs` shows no new escalation counter. The ladder ends at the guardian — see **Rough edges**. |
| B12 | Tap the journey card, then **I'm fine**. | The screen stops being red. Re-run the query: `escalation_state` is back to `normal`, a fresh `answered_at`, and the deadline has moved out. **An answer works from every rung, including this one** — see the note below the table. |
| B13 | Check the sweep's own account of it. | `select started_at, metrics from agent_runs where agent = 'journey_watch' order by started_at desc limit 8;` — one of these runs has `started_notices: 1`, another `repeated: 1`, and another `guardians_told: 1`. One counter per ring, so a run that did nothing is distinguishable from a run that is broken. There is no `full_sos` counter: nothing climbs there any more. |

**On B2, and why nobody has to walk.** The heartbeat is a 60-second timer inside the navigator,
so a phone sitting on a desk in route-following mode reports in exactly like one being carried. What
a stationary phone usually does *not* produce is a **fix**: the navigator drops anything with
accuracy worse than 100 m (`MAX_ACCURACY_M`) before it reaches state, and indoors on a tethered
phone that is every reading, so `follow.position` stays null and the heartbeat honestly carries
nothing. Measured on the first real guardian journey: twenty minutes of heartbeats, `has_position`
false the whole way.

That is why the escalation email falls back to **where the journey started** — `origin` is on every
journey because the route was planned from it, so there is always somewhere to point, and the email
says which of the two it is holding. To see a real `last_position` instead, either run the journey
outdoors, or set one by hand (longitude first — `POINT` is `(x, y)`):

```sql
update journeys
   set last_position = extensions.ST_SetSRID(
           extensions.ST_MakePoint(90.39342, 23.75092), 4326
       )::extensions.geography,
       last_position_at = now()
 where journey_id = '<id>';
```

**On B3, and the one reason a laptop tab beats reading mail on the phone.** Opening a mail app is
harmless. **Tapping Meridian's own check-in notification is not — and not only the `I'm fine`
button.** A plain tap on the notification body counts as an answer: `isCheckInAnswer` accepts
`DEFAULT_ACTION_IDENTIFIER`, deliberately, because somebody who opens the app from a check-in has
demonstrably seen it and treating that as silence would be the feature escalating about a person who
responded. During Run B that is the trap — one absent-minded tap returns the journey to `normal` and
ends the climb.

Swiping the notification away is safe: a dismissal is not a response and nothing reads it. So if the
only inbox is on the same phone, swipe Meridian's notifications aside and read the mail from there.

**On B12.** Until this phase was wired to a screen, the check-in endpoint only accepted an answer
from `check_in_sent` — JG2's single state. Ring 2 pushes the traveller a *second* time, so the
person pressing the button hardest was the one getting a 409 while the ladder went on to email their
contacts. Found by running the statement against a row in each of the four states; three answered
nothing. If B12 ever stops working, that is the bug back.

## Run C — nobody is told, and nothing is collected

Two minutes, and it is the run that makes the feature trustworthy rather than impressive.

| # | Do this | You should see |
|---|---|---|
| C1 | Route somewhere, and **leave `Nobody` selected**. Press Start. | Navigation begins. No `Telling …` line on the card. |
| C2 | Follow for two minutes so several heartbeats go out, then run the query. | **`has_position` is false and `last_position_at` is null.** The phone is reporting that it is still going and deliberately not saying where: with nobody to show a position to, none is collected. The app drops the fix before the request exists, and the server refuses to store one anyway. |
| C3 | Tap the journey card. | *"On your way."* and **"Nobody is being told about this journey."** |
| C4 | Let the deadline pass, ignore the check-in, and let it climb (fast-forward as in B6). | The rungs still fire — the record of what was asked and ignored is kept — but **no email is sent to anybody**, and the journey screen says *"This journey has no guardian, so Meridian has not told anybody."* The sweep counts these as `nobody_to_tell`, not `notices_failed`. |
| C5 | Start another journey and watch the picker. | It is back on **`Nobody`**. A guardian chosen for one trip is never inherited by the next — an inherited deadline is a nuisance, an inherited guardian is an email somebody did not mean to send. |

## Run D — the things that should be refused

| # | Do this | You should see |
|---|---|---|
| D1 | `Profile → Emergency Contacts`, and **delete the contact you used as a guardian**. | It deletes. Until `20261015190000` it did not — see **Rough edges** — and the screen could only say "Failed to delete contact". |
| D2 | Run the query against that journey. | The journey is intact, `guardian_contact_id` is now null, and `started_notice_at` is still set: the record that a message was sent survives the person's deletion. |
| D3 | Open the journey screen for that journey, if it is still open. | **`Telling your guardian`** rather than a blank name or a name that no longer exists. |
| D4 | Add a contact with a name and **no email**, then look at the picker. | Dimmed, reads `· no email`, and cannot be tapped. |
| D5 | Start a journey against `POST /journeys` with **another account's** contact id as `guardian_contact_id` — see the note below the table for where to get one. | **404.** The contact is checked against the caller's own contacts before it is written; an unvalidated id here would have Meridian email a stranger about a journey they have nothing to do with. |

**On D5.** It needs a contact belonging to **another account**, and no new account has to be
created to get one: there are already three accounts in `auth.users`, two of them holding a contact
with an email address. Sign in as one, take the other's contact id from
`select id, user_id from emergency_contacts;`, and send that as `guardian_contact_id`.

## Rough edges

* **The ladder ends at the guardian, by decision.** There was a fourth rung, `full_sos`, that
  emailed every contact the traveller had listed. It was removed after the first real escalation
  landed in an inbox: the thing a timer should not do is widen somebody's circle. Four rungs down
  from a missed tap, an employer and a neighbour would be told that a person they know is missing,
  with a map — on the strength of a phone in a bag. Widening past the one person who was *named*
  is a decision for whoever reads the email, and they have the context to make it. The state stays
  legal in the schema because journeys reached it before this changed and those rows are still
  read and rendered; nothing climbs to it now, and `test_the_sweep_has_no_way_to_read_a_whole_contact_list`
  is what keeps that true — the sweep no longer has a query that can return more than one address.

* **Nothing on this page has run on a device, and no email has ever been sent.** Every claim above
  is proved against the real database in a rolled-back transaction, which is not the same thing.
  SMTP deliverability is untested, and it is where a demo of this dies.
* **The guardian is never told you are fine again.** If they were emailed at ring 3 and you then
  answer, they get **nothing** — no all-clear. If you go on to arrive, the "arrived safely" email
  closes the loop; if you answer and then *cancel*, the last thing they ever heard was "has not
  arrived and is not answering". That is a real gap and a product decision rather than an oversight:
  a fourth message is cheap to send and not cheap to word, and JG3's scope is three. Say it out loud
  if a judge asks, because it is the first thing a guardian would ask for.
* **Cancelling tells nobody.** Ending a journey from the card sends no email, deliberately — "she
  stopped the journey" is not news, and sending it would teach people to ignore these messages. The
  consequence is the gap above.
* **`full_sos` does not call the police, and the email says so by omission.** 999 and the thana
  record are JG7. `JOURNEY_GUARDIAN.md` is explicit that reaching full escalation from an unanswered
  check-in and *then* contacting police would be the most damaging false positive this product can
  produce — an unanswered check-in is usually a phone in a bag. The journey screen says it in as
  many words: *"Meridian only emails the people you chose. It does not call the police."*
* **Five minutes per rung, plus up to a minute of sweep.** `check_in_sent → check_in_repeated →
  contacts_notified → full_sos` is three windows of `CHECK_IN_WINDOW`, so a real run from a missed
  deadline to the last ring is about twenty minutes. The windows are guesses, they all live in
  `backend/app/journeys/deadline.py`, and making them depend on the hour and the place is JG4.
* **One rung per sweep, and that is arithmetic rather than a rule.** A sweep stamps the rung it
  fires with its own `now`, and the next rung's gate wants that stamp five minutes old — so no sweep
  can climb twice. Nothing enforces it; nothing needs to.
* **The timestamps describe the current question, not the trip.** Asking a new check-in clears the
  three ladder stamps, so a journey that escalated, was answered and is asked again shows one cycle
  on its timeline and not two. The alternative is an events table, which is a bigger feature than
  the thing it would be documenting. **The migration's own comment says the opposite** — it claims
  an answered journey keeps the timestamps — and it is wrong; the file is applied and checksummed so
  it cannot be edited, and `test_a_new_question_resets_the_escalation_record` is the correction.
* **A journey with no guardian still climbs the ladder.** It sends nothing at any rung, including
  the last, because every escalation email starts from the guardian. The first version of the
  journey screen told such a traveller that "your guardian has been emailed" when nothing had been
  sent to anybody; the sweep also counted those climbs as `notices_failed`, which would have made a
  healthy run look broken. Both fixed, both tested.
* **Deleting a guardian contact used to fail, permanently.** `20261015180000` added
  `journeys_notice_needs_guardian`, a CHECK requiring a notice timestamp to have a guardian beside
  it, while the foreign key is `on delete set null` — so deleting the contact nulled the reference,
  the CHECK rejected the row, and the `DELETE` failed with an IntegrityError on a screen that has
  nothing to do with journeys. Any contact ever used as a guardian became undeletable.
  `20261015190000__guardian_notice_outlives_the_contact.sql` drops it. Found by running the delete
  against the real table; 741 tests could not see it, because both halves were separately correct
  and each had a passing test that contradicted the other.
* **A phone that is not moving usually stores no position at all.** Measured on the first real
  guardian journey: twenty minutes, heartbeats throughout, `last_position` null the whole way. The
  navigator drops any fix with accuracy worse than 100 m before anything sees it — right for
  snapping a route to a road, and indoors or in a basement that is every fix — so the heartbeat
  honestly reports "still going" with nowhere attached. It is a coupling worth knowing: the
  **position is a by-product of the navigator's accuracy bar**, and the places where that bar fails
  (indoors, underground, a vehicle with a metal roof) overlap with the places this feature is for.
  The escalation email handles it by falling back to where the journey started, and says which it
  is holding. Loosening the bar for the journey position alone — a 300 m fix is useless for drawing
  a route and perfectly useful for "she was last in this neighbourhood" — is a small change and
  not one made eight days before the finale.
* **A place name can arrive as four lines, in two scripts.** The destination on that same journey
  was `National Museum of\nScience and Technology\nজাতীয় বিজ্ঞান ও\nপ্রযুক্তি জাদুঘর` — a POI label from a
  map tap, which broke the most important sentence in the escalation email into four. Every name
  and place now goes through `_oneline` before it is rendered, and the transport folds its own
  subject. There was a quieter failure behind the untidiness: a newline in a **display name** is
  not a header injection (Python raises rather than flattening it) but the transport would have
  caught that, reported a failed send, and the notice was **already marked sent** — so one newline
  in somebody's name would have meant their guardian was never told anything, on any journey, for
  ever.
* **One position, overwritten, and never a log.** A journey with a guardian keeps exactly one point
  — the last heartbeat's — with its timestamp. There is no history, no live sharing and no map on
  the traveller's screen, and the email describes the point as where the phone last spoke rather
  than where the person is. Everything else is JG5 and beyond.
* **No position if the phone never followed the route.** The coordinates come from a heartbeat, and
  heartbeats only run while actually navigating. Start a journey, lock the phone immediately, and the
  escalation email honestly says *"their phone has not reported a location on this journey"* — which
  reads as a failure and is the design: "we do not know where she is" is itself the most important
  fact in that email.
* **Email, not SMS.** It is what the SOS pipeline already uses and the cheapest thing that works. A
  guardian at 10pm reads SMS and may not read email. Measure the complaint first — that is the note
  in `JOURNEY_GUARDIAN.md` and it has not changed.
* **A notice older than six hours is never sent.** If the worker was down while a journey started,
  the "she set off" email for it is dropped rather than arriving at 3am about a trip that finished
  at 9pm. The backlog guard is `NOTICE_BACKLOG` in `journey_watch.py`.
* **Everything JG2's Rough edges say still applies**, in particular that the lock-screen `I'm fine`
  button is usually not drawn at all, and that a phone on silent does not buzz. Both affect the
  check-ins you are ignoring in Run B, so neither can break this page — but the answer in B12 is
  given on the journey card for exactly that reason.

## Fallback if it fails live

* **No email arrives at all.** Check the **spam folder first** — it is the most likely cause
  and it is not a bug. Then read the sweep's own metrics:

  ```sql
  select started_at, metrics from agent_runs
   where agent = 'journey_watch' order by started_at desc limit 10;
  ```

  * **`started_notices: 1`** — it was sent. The problem is delivery, not the feature. Spam, or the
    contact's address has a typo: `select name, email from emergency_contacts;`
  * **`notices_failed: 1`** — SMTP refused it. Credentials in `backend/.env`, or Gmail blocking a
    sign-in. `docker compose logs worker | Select-String -Pattern "guardian|smtp"` has the reason
  * **`nobody_to_tell: 1`** — the journey has no guardian. Either `Nobody` was selected, or the
    contact was deleted after Start
  * **No rows for `journey_watch` at all** — beat never scheduled it. `docker compose restart
    worker`. This has cost a run before
* **The escalation email has no coordinates.** The journey never sent a heartbeat with a fix: the
  phone did not actually follow the route, or the guardian was picked but the app was backgrounded
  before the first beat. `select last_position is not null, last_heartbeat_at from journeys …`. Not a
  bug — the message says so in words.
* **The ladder is stuck on one rung.** Check `answered_at`: an answer at any point resets the
  journey to `normal` and the climb stops, which is the feature. Otherwise check the rung's own
  timestamp is five minutes old, and that `state` is still `active` — a cancelled journey is ignored
  by every branch.
* **Run B is too slow for the room.** Use the step B6 fast-forward, and say what it is: the clock
  moved, not the code. Or show Run A live and Run B from a recording — but have the recording.
* **`migrate.py up` refuses.** Expected, and nothing to do with this phase. Use `sql --version` and
  paste, including the ledger insert. See step 0.

## Numbers

| | |
|---|---|
| New backend routes | 0 — `POST /journeys` and `/heartbeat` gained optional fields |
| New columns | 8 on `public.journeys` — `guardian_contact_id`, four timestamps, two notice stamps, one position |
| New constraints | 10: one foreign key and nine CHECKs. One of the nine replaces JG2's state check, and one was **dropped the same day** for breaking contact deletion. Plus 1 partial index |
| Escalation states | 5 stored (`normal`, `check_in_sent`, `check_in_repeated`, `contacts_notified`, `full_sos`), **4 reachable** — `full_sos` is historical |
| Rings that tell somebody else | 2 of 4 — and the first is at least ten minutes after the first question |
| Emails per journey, happy path | 2 (set off, arrived) |
| Emails per journey, worst case | 3 (set off, escalation to the guardian, arrived) — and never more than **one recipient** each |
| People told when you pick `Nobody` | 0, and no position is stored either |
| Positions stored per journey | 1, overwritten, and only once a guardian exists — **or none**, which indoors is the normal case |
| Points the escalation can offer | A stored fix, else where the journey started (`origin`, which every journey has), else an honest "we do not know" |
| Time from missed deadline to the guardian's email | ~11 min — up to 1 to be asked, 5 to be recorded unanswered and asked again, 5 more to the guardian |
| Time to the last ring | ~16 min from the missed deadline |
| Notice backlog guard | 6 hours |
| Sweep branches | 7, in one pass, one metric each |
| Backend tests | 72 in `tests/invariants/test_journey_guardian.py`; 743 in the suite |
| Frontend tests | 26 in `src/features/journey/escalation.test.ts`; 508 in the suite |
| Bugs this phase found in its own earlier steps | 4, all found by running something rather than reading it — see `JG3_PLAN.md` §7 |
