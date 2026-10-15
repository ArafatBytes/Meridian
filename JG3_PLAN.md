# JG3 — someone else knows

**Written 15 Oct 2026, before any code.** The last phase of Journey Guardian before the finale on
24 Oct; `JOURNEY_GUARDIAN.md` Part 2 records why JG4–JG7 are not being built.

**Goal, in one sentence:** a second person is told you started, told you arrived, and told — with
your last known location — if you stopped answering.

---

## 1. What this is built on, concretely

Nothing here is new infrastructure. Every piece JG3 needs already exists and has been exercised:

| Piece | Where | State |
|---|---|---|
| `emergency_contacts` | `public.emergency_contacts` — `id, user_id, name, phone, email, relationship` | Live, with a screen (`EmergencyContactsScreen.tsx`) |
| Email out | `app/services/email_service.py::EmailService` | Live; SMTP configured and used by `sos_service.py` |
| The minute sweep | `app/agents/journey_watch.py` | Live, running every minute, verified |
| Escalation states | `journeys.escalation_state` + `journeys_escalation_check` | Two states: `normal`, `check_in_sent` |
| The recorded non-response | `journeys.unanswered_at` | **Written by JG2 and read by nothing.** JG3 is its first reader |
| Push to the traveller | `alerts/expo.py`, `journeys/checkin.py` | Live; delivery confirmed to a real device |

The last row is the important one. JG2 deliberately wrote `unanswered_at` and stopped, with
`test_the_non_response_branch_sends_nothing` holding the line. **JG3 is the phase that deletes that
test**, and it should be deleted rather than loosened, because its whole purpose was to mark the
scope boundary we are now crossing on purpose.

---

## 2. Decisions, and why

### 2.1 One guardian, chosen per journey, not a setting

Picked at Start from the existing contacts, stored on the journey row. Not a profile preference:
who should be told depends on the trip. The person you want told about a 2am ride home is not
necessarily the person for a Tuesday commute, and a global setting makes the common case wrong half
the time.

**A journey with no guardian is valid and stays valid.** `guardian_contact_id` is nullable, and a
null means JG2's behaviour exactly — the deadline and the check-in still work, nobody else is told.
This is not a degraded mode; it is the private mode, and it must keep working because the feature
must not become unusable for somebody with no contacts saved.

### 2.2 Email, not SMS

`JOURNEY_GUARDIAN.md` already settles this: email is what the SOS pipeline uses, it is configured,
and it costs nothing. SMS is what a guardian actually reads at 10pm, and that is a real limitation
to state on stage rather than engineer around in eight days. No new credential, no new vendor.

### 2.3 Location only once escalation begins, and it needs a schema change JG2 refused

This is the one place JG3 undoes a JG2 decision, and it should be done knowingly.

JG2 stores **no position at all**, enforced by `test_the_heartbeat_carries_no_position`, which
asserts `JourneyHeartbeat.model_fields == {"remaining_seconds"}` and that the migration mentions no
`latitude`, `longitude` or `st_makepoint`. The reasoning in that test is explicit: *"the only message
that needs a last known position is the escalation JG3 sends to somebody else, and a location
written before there is anything to read it is a privacy surface with no feature behind it."*

JG3 is that reader. So:

- The heartbeat gains **optional** `latitude` / `longitude`.
- The journey row gains `last_position` (geography) and `last_position_at`.
- One point, overwritten — **not** a position log. `JOURNEY_GUARDIAN.md` JG1 already decided this:
  *"Start with one row — the log is only needed once JG5 wants history."* JG5 is not being built, so
  a log would be a privacy surface with, again, no reader.
- `test_the_heartbeat_carries_no_position` is **replaced**, not edited, by a test asserting the
  narrower invariant that survives: the position is written by the heartbeat and read only by an
  escalation message, never by the started/arrived messages.

### 2.4 The states, and the gate on every edge

```
normal ──► check_in_sent ──► check_in_repeated ──► contacts_notified ──► full_sos
   ▲            │                   │                      │                 │
   └────────────┴───────────────────┴──────────────────────┴─────────────────┘
                        an answer returns to normal from any state
```

Five states, four forward edges, and **every forward edge requires a recorded non-response with a
timestamp** — the invariant `IMPLEMENTATION_PLAN.md` B10/S22–S23 already specifies and the thing
`JOURNEY_GUARDIAN.md` §7 promises: *"It cannot jump to panic."*

Each forward transition is gated on the *previous* state's unanswered timestamp being older than the
answer window. Concretely, the sweep moves a journey on only when
`<previous>_at <= now - CHECK_IN_WINDOW` and no answer has landed since.

Widening the machine means:

- `journeys_escalation_check` widened to the five names. A `text + CHECK` column was chosen in JG2
  precisely so this is an ordinary `ALTER` inside a transaction.
- `ESCALATION_STATES` and `ESCALATION_TRANSITIONS` in `models/journey.py` extended. The cycle back to
  `normal` from every state is deliberate and already the shape there.

### 2.5 What `full_sos` does, and does not do

It emails **every** emergency contact, with location. It does **not** call 999 and does **not** email
a thana: `JOURNEY_GUARDIAN.md` puts both in JG7, and the thana path is behind
`POLICE_ROUTING_ENABLED` for good reasons. Reaching `full_sos` on an unanswered check-in and then
emailing the police would be the single most damaging false positive this product could produce.

---

## 3. Schema

One migration, forward-only, `backend/migrations/versions/<utc>__journey_guardian.sql`, with the
`do $guard$ … raise exception` preamble the JG2 migrations use — `Base.metadata.create_all` runs on
every app start and will silently create a table from the model if the migration has not been
applied, which is how JG1 lost a day.

```
alter table public.journeys
    add column if not exists guardian_contact_id uuid references public.emergency_contacts(id),
    add column if not exists started_notice_at   timestamptz,
    add column if not exists arrived_notice_at   timestamptz,
    add column if not exists check_in_repeated_at timestamptz,
    add column if not exists contacts_notified_at timestamptz,
    add column if not exists full_sos_at          timestamptz,
    add column if not exists last_position        extensions.geography,
    add column if not exists last_position_at     timestamptz;
```

Constraints to add, each guarded by `conname` so a re-run is a no-op:

| Name | Says |
|---|---|
| `journeys_escalation_check` (**replaced**) | the five state names |
| `journeys_repeated_after_asked` | `check_in_repeated_at is null or check_in_sent_at is not null` |
| `journeys_contacts_after_repeated` | `contacts_notified_at is null or check_in_repeated_at is not null` |
| `journeys_sos_after_contacts` | `full_sos_at is null or contacts_notified_at is not null` |
| `journeys_position_paired` | `(last_position is null) = (last_position_at is null)` |
| `journeys_guardian_notice_needs_guardian` | `started_notice_at is null or guardian_contact_id is not null` |

The three ordering constraints are the escalation invariant **at the table level**, not only in the
sweep. A bug that skipped a step would be an `IntegrityError` rather than an email to somebody's
mother.

`idx_journeys_escalating on (escalation_state, check_in_sent_at) where state = 'active'` — the sweep
gains three more scans a minute and they must not table-scan.

PostGIS idiom, as everywhere else in this repo:
`extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography` to write,
`extensions.ST_Y(last_position::extensions.geometry)` to read.

---

## 4. Backend

### 4.1 `app/journeys/guardian.py` (new, pure)

The message bodies and the one decision about what each may contain. Pure, no I/O, so the privacy
rule is unit-testable:

```python
def started_message(*, traveller: str, destination: str, eta: str) -> Message
def arrived_message(*, traveller: str, at: str) -> Message
def escalation_message(*, traveller: str, destination: str, started: str,
                       last_seen: Position | None, maps_url: str | None) -> Message
```

**The invariant this file exists to make testable:** `started_message` and `arrived_message` take no
position and have no parameter that could carry one. Not "do not pass it" — *cannot* be passed. The
guardian learns where she is only if something went wrong, which is §2 of `JOURNEY_GUARDIAN.md`:
*"She gets watched over without being surveilled."*

### 4.2 Email templates

`email_service.py` today has one template and it is subject-lined `EMERGENCY: {name} needs help`.
That is correct for an SOS and wrong for *"Rina started her journey home"*. JG3 adds three
templates, calm by default, and the escalation one is the only one that looks urgent.

**Fix while here:** `send_sos_alert` sets `msg['To'] = ', '.join(to_emails)`, which shows every
contact's address to every other contact. Irrelevant for one guardian, a real leak at `full_sos`
where all contacts are mailed. Use `Bcc` with an undisclosed `To`. Small, and this is the phase that
makes it matter.

### 4.3 `journey_watch` — three more branches

The sweep grows from two branches to five, in one pass, ordered:

1. due for a check-in → `check_in_sent` *(exists)*
2. `check_in_sent` unanswered past the window → record `unanswered_at` *(exists)*
3. `unanswered_at` past the window → `check_in_repeated`, push the traveller **again**
4. `check_in_repeated_at` past the window → `contacts_notified`, email the guardian with location
5. `contacts_notified_at` past the window → `full_sos`, email every contact with location

Each branch: `limit 500`, re-check the state inside the `UPDATE`, mark **before** sending (JG2's
`_ask` does this deliberately — a crash after marking sends nothing, a crash before marking sends
twice), and one metric per branch so a run that does nothing is distinguishable from a run that
is broken.

### 4.4 Endpoints

- `POST /journeys` gains optional `guardian_contact_id`. Validated to belong to the caller — a
  contact id from another account would email a stranger.
- `POST /journeys/{id}/heartbeat` gains optional `latitude`/`longitude`.
- `GET /journeys/{id}` returns the timeline fields for the journey screen.
- Arrival (`POST /journeys/{id}/arrive`) sends the "arrived" message.

---

## 5. Frontend

- **Guardian picker** on the route card, under the deadline chips: the contacts list plus a
  **Nobody** option, default **Nobody**. Default matters — silently emailing somebody because they
  happened to be first in a list is the kind of surprise that loses trust permanently.
- **The heartbeat sends position** once the journey has a guardian. No guardian, no position — the
  privacy rule enforced at the point of collection, not only at the point of use.
- **Journey screen** (`JourneyScreen.tsx`): current state in plain words, and a timeline from the
  row's timestamps. No new table: six timestamps are the whole history.
- The journey card gains one line: *"Telling Ammu"* or nothing.

---

## 6. Scope boundaries — what JG3 does NOT do

- No 999, no thana email (JG7).
- No duress response, no second button (JG6).
- No risk-weighted or hour-weighted timing (JG4) — the windows stay the fixed guesses in
  `journeys/deadline.py`.
- No position **log** — one overwritten point.
- No SMS.
- No guardian-side app, account or acknowledgement. The guardian receives email and can do nothing
  in-app, because they may not be a user. A reply path is a feature with a product question behind it.
- No live location sharing, ever. The position in an escalation email is the last point the phone
  reported, timestamped and described as such.

---

## 7. Build order

Each step ends somewhere verifiable, so a day that runs out does not leave the tree broken.

| # | Step | Verifiable by |
|---|---|---|
| 1 | Migration + widen `ESCALATION_STATES`/`ESCALATION_TRANSITIONS` | `migrate.py status`; invariant tests on the CHECK names |
| 2 | `journeys/guardian.py` with the three messages | Pure unit tests, including that started/arrived cannot carry a position |
| 3 | Email templates + the `Bcc` fix | Send to a real inbox by hand |
| 4 | `guardian_contact_id` on start, ownership-validated | A contact id from another user is rejected |
| 5 | "Started" and "arrived" emails | Two emails to a second address |
| 6 | Heartbeat carries optional position; replace the no-position test | Row shows `last_position` |
| 7 | Sweep branches 3, 4, 5 with metrics | `agent_runs` metrics per branch |
| 8 | Journey screen + guardian picker | On a phone |
| 9 | `docs/walkthroughs/JG3.md`, **run on two phones** | The walkthrough rule |

Steps 1–7 are the feature. Step 8 is what a judge sees. Step 9 is what makes it finished — a phase
with working code and no run walkthrough is not finished.

---

## 8. Test plan

Invariant tests, in `backend/tests/invariants/test_journey_guardian.py`:

- No forward edge exists in the sweep without a gate on the previous state's timestamp.
- Every forward edge is also a table constraint — the three ordering CHECKs are present by name.
- `started_message` and `arrived_message` have no parameter that can carry a position, and the
  rendered bodies contain no coordinate pattern.
- `escalation_message` does contain one — the inverse test, because a privacy rule tested only in
  one direction passes trivially on a function that never says anything.
- A guardian id is never used without an ownership check in the same statement.
- `full_sos` does not reach the police path: the module imports nothing from the thana/999 code.
- `Bcc` is used wherever more than one address is mailed.

**Every new test is validated by reintroducing the bug and watching it fail.** This project's rule,
and it has caught two tests this week that passed against broken code.

---

## 9. Risks, and what will probably change

- **Size.** This is the largest remaining phase and bigger than JG2. If it is running long, the split
  is **steps 1–6 (the guardian knows) and steps 7+ (the escalation)**, and the first half is a
  demonstrable feature on its own: *"someone is told you started and told you arrived."* Ship that
  and stop if the days run out.
- **Email deliverability.** SMTP to an arbitrary address is where a demo dies — spam folders, rate
  limits, a provider that dislikes a new sender. Test to the actual address that will be on stage,
  early, not on 23 Oct.
- **The windows.** Three waits of five minutes each means `full_sos` is twenty minutes after a
  missed deadline. That is almost certainly too slow to demo and too fast for real life; the demo
  needs a short-leash path and real life needs JG4. State the number rather than tuning it twice.
- **The guardian has no way to say "I've got it."** Nothing closes the loop from their side. Known,
  accepted, and worth saying before a judge asks.
