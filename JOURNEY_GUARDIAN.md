# Journey Guardian

**Today:** Meridian can send an SOS when you press, shake, or shout. All three need you to *act*.

**Journey Guardian:** it watches the journey, so it can act when you can't.

**The foundation:** a journey that survives — start, destination, chosen route, ETA, saved on the
server. Today the app shows your progress but forgets everything the moment it closes. Everything
below needs that one piece first.

**Part 1 is the case for building it** — eight features, each as a problem and what the user gets.
**Part 2 breaks it into seven phases** that can be built and tested one at a time.

---

# Part 1 — the case

## 1. Arrival deadline

> **Problem:** Rina takes a CNG from Dhanmondi to Mirpur at 10pm. Her phone is snatched at 10:15.
> No app can detect anything — the phone is gone.

**Solution:** when she starts, the *server* holds a deadline: "confirm arrival by 10:40." Nothing on
the phone has to survive.

**Result:** at 10:45 her brother gets: *"Rina started at 9:55 toward Mirpur. She hasn't arrived and
isn't responding. Last seen near Sobhanbagh."* Someone knows within minutes instead of in the
morning.

### How the deadline gets set

**Start from the route's own ETA, pre-filled and editable.** One tap to accept. Not fully automatic,
because the router does not know she is stopping for food; not fully manual, because nobody wants to
do arithmetic at 10pm.

**It slides forward while she is moving — but only while she is reporting.** The phone already works
out a live ETA from measured GPS speed. Stuck in a jam? The phone says *"still moving, revised
10:52"* and the clock extends. **Silence never buys an extension.** That asymmetry is the whole
design: a phone in a jam talks, a phone in a ditch does not.

**The grace period scales with risk and hour.** A 2pm commute gets a generous one. An 11pm ride
through flagged corridors gets a tight one. Same idea as section 3.

**One tension worth saying out loud:** the mechanism that catches a dead phone is the same one that
misfires on bad data coverage, and Dhaka has plenty of both. The fix falls out of the escalation
chain — **the first check-in is a liveness test, not just a question.** A phone that has merely been
quiet wakes on the push and answers in one tap. Only a phone that ignores a *push* moves a step
further. A signal gap costs one buzz, not a call to her mother.

**The real numbers come from the trial, not from us.** The plan already commits to two weeks on our
own commutes with false check-ins measured, targeting under one per user per week. Any figure we pick
today is a starting value to be tuned.

## 2. A real person watching

> **Problem:** This is what people already do — "reached?" / "almost" / silence. Then you fall
> asleep and nobody follows up.

**Solution:** pick one person when you start. They get "started" and "arrived". Nothing in between —
no live dot, no tracking.

**Result:** Rina's brother gets two messages a night instead of worrying. He only learns *where* she
is if something actually goes wrong. She gets watched over without being surveilled.

## 3. The leash tightens where the risk is

> **Problem:** A detour at 2pm down a busy road is nothing. The same detour at 11pm into a corridor
> with two confirmed flags is not nothing. One setting can't cover both.

**Solution:** Meridian already scores every road. Use that score, plus the hour, to decide how
patient to be.

**Result:** Rina's afternoon commute never nags her. Her 11pm ride asks "all okay?" after 90 seconds
off-route instead of five minutes. **No other safety app can do this — they don't have a risk map.**

## 4. Signals better than "off the route"

> **Problem:** In Dhaka you go off-route constantly — blocked roads, lane changes, the driver's
> shortcut. An app that pings you every time gets switched off in a week.

**Solution:** watch for things that *aren't* normal: you were walking, now you're moving at 60 km/h.
You've been stopped 200 m down a side lane and haven't touched your screen. Your battery just hit
10%.

**Result:** the jam on Mirpur Road stays silent. Being put into a car does not. And when her battery
is about to die, her brother gets a heads-up *before* the phone goes dark — instead of just
unexplained silence.

## 5. Answer from the lock screen — or lie on purpose

> **Problem:** "Are you safe?" is useless if the dangerous person is sitting next to you watching you
> answer. And a loud notification announces that your phone is worried about you.

**Solution:** one tap from the lock screen, one quiet vibration, no app to open. And **two** buttons
that both look like "I'm fine" — one of them silently escalates instead.

**Result:** the driver took a wrong turn and is watching her. She taps the safe-looking button. He
sees her dismiss a notification. Her brother gets her location.

## 6. "Someone is following me"

> **Problem:** Walking from the bus stop, you notice footsteps behind you. You're not ready to scream
> for help — but you want someone ready if you can't.

**Solution:** one button that shortens the leash to minutes: check in, or we escalate.

**Result:** Rina presses it, keeps walking, keeps her phone in her hand. If nothing happens, she
presses it again at her gate and nobody is ever disturbed. If something does, help is already moving.

## 7. It assumes you're fine — and proves otherwise before acting

> **Problem:** The nightmare for this feature isn't missing a real emergency. It's calling her mother
> at midnight because she stopped for tea. One false alarm and she turns it off forever.

**Solution:** escalate in steps, and never skip one. Each step widens the circle by exactly one
ring:

```
quiet check-in  →  ask again  →  your guardian  →  your contacts + 999 + a thana record  →  witnesses nearby
```

Every step past the first requires a **recorded** non-response with a timestamp. It cannot jump to
panic. And every ring is consented: hers, then her people, then institutions, then strangers who
volunteered.

**Result:** 95% of the time it asks once, she taps once, and that's the end of it. The 5% is the
whole reason it exists.

## 8. The outer ring — witnesses, not a mob

> **Problem:** A person 100 m away arrives before any police car. The nearest help is almost always
> someone who is simply nearby, and right now there is no way to reach them.

**Solution, and the wording is the entire feature.** Nearby users who opted in get:

> *"Someone nearby raised an alert on Satmasjid Road in the last 10 minutes. If you saw anything,
> report it."*

Not a pin — a road. Not an identity. Not "danger". **It asks for information, not intervention.**

**Result:** three people who were on that road file what they saw. Those reports land in
`community_clusters` — the corroboration machinery already built in B13 — and become something a
responder, or a court, can actually use.

### Why not "someone is in danger, come help"

This is the version to refuse, and it is worth being able to say why on stage:

| Risk | Why it is serious here |
|---|---|
| **Mob violence** | গণপিটুনি is documented, recurring and lethal in Bangladesh. Summoning a crowd to an accusation is how the wrong person gets beaten to death. |
| **The attacker may be a user** | A precise pin would be sent to him too. |
| **It is a weapon** | A false alert summons a crowd to an address of the sender's choosing. |
| **It cannot be recalled** | Once forty phones hold the location, there is no undo. |

And the most likely real outcome is the fifth one: **nobody comes**, which makes it theatre.

So: area not pin, witnesses not rescuers, opt-in on both sides, and **only on a confirmed
emergency** — full SOS or the duress button. Never on an unanswered check-in, because an unanswered
check-in is usually a phone in a bag.

### The institutional ring, described accurately

The SOS pipeline already finds stations within 5 km and emails them, behind the
`POLICE_ROUTING_ENABLED` gate. What matters is not overselling it:

- **999 is the emergency channel.** It should be one tap on the escalation screen.
- **The thana email is a paper trail**, not a dispatch — and the Casework Agent turns it into a
  General Diary draft. That is the real institutional value, and it is a stronger claim than
  "we alerted the police".

### One honest limit

"Nearby" is approximate today. The push table holds a single overwritten point from wherever the app
was last in the foreground, so the truthful claim is *"users who were recently near that area"*.
Background location (S17) is what sharpens it.

---

## The bonus nobody expects

Shake-to-SOS and shout-to-SOS **only work with the app open today** — Android blocks background
sensors. But a journey in progress is the one time the app legitimately earns a permanent "Journey
Guardian active" notification. That may make **shake-to-SOS work with the phone in her pocket**, for
the length of the journey.

Worth testing before we promise it.

---

## Why this is the right thing to build

- It is the only feature that works when the user **can't** act — the concept document says exactly
  this.
- It is the feature a user **tells their friends about**, because it solves something they already do
  badly by hand.
- It reuses what is already built: the risk map, the SOS pipeline, background location, the
  escalation design.
- Items **1 and 2 alone** are a complete, demoable feature. Items 3–6 are what make judges lean
  forward.

---

# Part 2 — the phases

> ## Scope decision, 15 Oct 2026: this stops at JG3
>
> **JG1–JG3 ship. JG4–JG7 are not being built before the finale on 24 Oct.** The
> freeze is 23 Oct, which is eight days, and JG2 alone took five runs on a real
> phone. That is the whole reason, and two of the four dropped phases would not
> have fitted anyway:
>
> * **JG5 is blocked.** It needs continuous background location, which is S17 and
>   does not exist — `expo-location` is installed but only geofencing is wired
>   (`features/geofence/task.ts`); `startLocationUpdatesAsync` appears nowhere in
>   the codebase. Building that first is its own phase.
> * **JG7 needs an opt-in surface and a privacy review**, and it is the phase that
>   looks worst half-done: a witness request is a message to strangers.
> * **JG4 is genuinely cheap** — one pure function in `app/journeys/deadline.py`,
>   which JG2 already isolated for exactly this. It is the first thing to pick up
>   if JG3 lands early.
> * **JG6 is the most impressive thing in this document** and is worth more than
>   JG4 to a judge, but it is useless without JG3's escalation chain and the plan
>   already says it needs teaching rather than a toggle to be real.
>
> What JG1–JG3 adds up to is a complete story rather than a truncated one: the
> journey survives the app being killed, the server notices you are late and asks,
> and a second person is told when you do not answer. That is the premise of the
> feature, start to finish. Stopping here costs refinements; stopping at JG2 would
> have cost the point.
>
> Nothing below is deleted. JG4–JG7 keep their sections, marked, because the
> argument for each is still good and the order still holds.

**These are not fixed.** Each phase is a day or two of work that ends in something you can show on a
phone, and the shape of a later phase will change once an earlier one is on a device. Where a phase
turns out to be two, split it; where two collapse into one, merge them. What should not move is the
**order**, because each phase depends on the one before it, and the **rule that every phase ends with
a walkthrough that was actually run on a phone**.

| Phase | What it makes showable | Depends on | Status |
|---|---|---|---|
| **JG1** | A journey that survives the app being killed | — | Built. Walkthrough signed off 15 Oct |
| **JG2** | A deadline that pings you, and one tap to answer | JG1 | Built. Walkthrough signed off 15 Oct, **with step 9 recorded as failing** — the lock-screen tap does not work; the journey card answers instead |
| **JG3** | Someone else knows you got home | JG2 | **Code complete, unverified.** All nine steps of `JG3_PLAN.md` built, including `docs/walkthroughs/JG3.md` — but that page has **not been run on a device** and **no guardian email has reached a real inbox** |
| **JG4** | The leash tightens at night and near flagged roads | JG3 | Not before the finale. First stretch goal |
| **JG5** | Being put in a car is noticed; a jam is not | JG3 | Not before the finale. Blocked on S17 |
| **JG6** | Answering safely while being watched | JG3 | Not before the finale. Second stretch goal |
| **JG7** | Witnesses nearby, and one tap to 999 | JG3 | Not before the finale |

**JG1–JG3 are the feature.** JG4–JG7 are independent of each other and can be built in any order, or
dropped, without breaking what came before — which is what has now happened.

---

## JG1 — the journey that survives

**Goal:** start a journey, kill the app, reopen it, and the journey is still there — because it lives
on the server, not in the screen.

**What lands:**

- A trip record: who, from, to, the chosen route, when it started, the ETA, its state.
- Start and end it from the route card — the same **Start** button that exists today, now writing a
  trip before it begins following.
- The app reads an open trip back on launch and resumes following it.
- Nothing watches anything yet. No deadline, no check-in, no escalation.

**Done when:** you start a journey, force-stop the app, reopen it, and it says *"journey in progress
— 12 min to Mirpur"* rather than showing an empty map.

**Walkthrough:** `docs/walkthroughs/JG1.md`

**What might change:** whether a trip is one row or a row plus a position log. Start with one row —
the log is only needed once JG5 wants history, and a log written from day one is a privacy surface
with no feature behind it yet.

## JG2 — the deadline, and one tap to answer

**Goal:** the server expects you to arrive, and asks once when you do not.

**What lands:**

- A deadline on the trip, pre-filled from the route ETA and editable with one tap at start.
- Heartbeats from the phone while it moves, which slide the deadline forward. **Silence never
  extends it.**
- The first two states of the escalation machine: `normal → check_in_sent`, with the non-response
  recorded with a timestamp.
- The check-in arrives as a push with a **one-tap answer from the lock screen**, and the answer is
  recorded against the trip.

**Done when:** you start a journey, set the deadline two minutes out, put the phone down, get a buzz,
tap once from the lock screen, and the trip goes quiet again.

> **Partly failed, 15 Oct 2026.** Everything up to the buzz works on a real phone, and the trip does
> go quiet again. **The tap from the lock screen does not.** Android draws the notification itself
> when it arrives from FCM with a title and body, and its own renderer knows nothing about Expo
> notification categories — so the `I'm fine` button is simply absent. Proven on the device: an
> `expo-notifications`-drawn record carries `actions=1`, an FCM-drawn one (`tag=FCM-Notification:…`)
> carries none, and which of the two draws it is not ours to choose from the server.
>
> The fix is to send **data-only** — no `title` or `body`, everything in `data` — so FCM has nothing
> to render and `expo-notifications` is forced to handle it, at which point the app posts the
> notification itself with the category attached. That stays on Expo's relay and needs no new
> credential; it is a change to `compose_check_in` plus a handler in the app. It was not taken before
> the finale because the risk runs the wrong way: a data-only message to a *killed* app may display
> nothing at all, and trading a notification that reliably arrives without a button for one that may
> not arrive is the worse failure. To be attempted after JG3, with the journey card unchanged as the
> guaranteed path.
>
> The answer is given on the journey card instead, which goes through the same endpoint and is
> measured: asked `12:00:04`, answered `12:00:34`. Recorded here rather than quietly reworded,
> because `JOURNEY_GUARDIAN.md` §5 builds the duress response on a notification button, and JG6 now
> has to know that ground is not solid.

**Walkthrough:** `docs/walkthroughs/JG2.md`

**What might change:** the grace period, which is a guess until JG4 and the trial. Start generous — a
feature that cries wolf in week one never gets a week two.

## JG3 — someone else knows

**Goal:** a second person is told you started, told you arrived, and told if you did not.

**What lands:**

- Pick a guardian when starting, from the emergency contacts already in the app.
- "Started" and "arrived" messages. Nothing in between.
- The rest of the escalation machine: `check_in_repeated → contacts_notified`, every transition
  gated on a recorded non-response, no step skippable. **The ladder ends there** — see below.
- The guardian's message carries last known location **only once escalation begins.**
- A journey screen: current state, what happened and when.

**Done when:** a second phone receives "started", then "arrived" — and in a second run where you
ignore the check-ins, receives the escalation instead, with a location.

> **Met, on a device, 16 Oct 2026.** One phone and one inbox rather than two phones — the guardian
> has no app, so a second account was never needed. The "started" notice and the escalation both
> arrived in a real Gmail inbox, not in spam, and the escalation carried a location. Still to do
> before the 23rd: one send to **the address that will be on stage**, because new-sender throttling
> and spam placement are properties of the recipient, not of the code.

**Changed from the plan: there is no fourth ring.** `full_sos` — the rung that emailed every contact
the traveller had listed — was built, run, and then removed on 16 Oct after watching a real
escalation land. The reason is §8's own argument turned on this feature: the outer ring is for
**witnesses on a confirmed emergency**, and an unanswered check-in is not that. Four rungs down from
a missed tap, an employer and a neighbour would be told somebody is missing, with a map, on the
strength of a phone in a bag. Widening the circle past the one person who was *named* is a decision
for whoever reads the escalation — they have the context, and they can act in seconds. So the ladder
ends at the guardian, and the sweep no longer holds a query that can return more than one address.

`full_sos` remains a legal `escalation_state`: journeys reached it before the change and those rows
are still read, answered and rendered. Nothing climbs to it. JG7 is where a wider circle returns,
with the gate §8 asks for.

**Also landed, not in the list above:** the three notices are sent as HTML and plain text, with a
palette per message — slate for "set off", green for "arrived", and the SOS mail's red only for the
escalation, so a guardian who gets two of these a week still reacts to the third. And answering is
accepted from **every** rung of the ladder, including `full_sos`. It was not, until step 8 ran the statement against a row in each state: the
endpoint had kept JG2's single-state gate, so the sweep would push somebody a second time and then
refuse the answer, climbing on to email their contacts while they pressed the button. Three bugs of
that shape — all introduced by widening the state machine without widening what faces the phone —
are recorded in `JG3_PLAN.md` §7.

**Detailed plan:** `JG3_PLAN.md` — written 15 Oct 2026, before any code.

**Walkthrough:** `docs/walkthroughs/JG3.md`

**What might change:** the channel. Email is what the SOS pipeline already uses and is the cheapest
thing that works; SMS is what a guardian will actually read at 10pm. Email first, then measure the
complaint.

## JG4 — the risk-weighted leash

> **Not before the finale — first stretch goal.** The cheapest phase here: the derivation already has a home in `app/journeys/deadline.py`, which JG2 built as pure functions over offsets for exactly this. Pick this up if JG3 lands early.

**Goal:** the same deviation gets a different reaction at 2pm and at 11pm.

**What lands:**

- Grace and check-in timing derived from the route's own safety score and the hour.
- The derivation lives in one place and is a pure function, so it can be tested without a phone.
- The journey screen says which leash it is using, in plain words.

**Done when:** two journeys over the same road, seeded at different hours, visibly wait different
lengths before asking.

**Walkthrough:** `docs/walkthroughs/JG4.md`

**What might change:** everything about the numbers. This is the phase most likely to be rewritten
after the trial, and the pure function is what makes that cheap.

## JG5 — signals better than off-route

> **Not before the finale — blocked.** Every signal here needs continuous background location, which is S17 and is not built: only geofencing is wired (`features/geofence/task.ts`), and `startLocationUpdatesAsync` appears nowhere in the codebase. The background-location work is its own phase and has to come first.

**Goal:** notice the things that are actually unusual, and stay quiet about the things that are not.

**What lands:**

- A speed jump: walking pace to vehicle pace, unexplained by the route.
- A stop that is off the route line, with no screen activity.
- A battery warning to the guardian **before** the phone dies.
- Each signal shortens the leash rather than firing an alert on its own.

**Done when:** a seeded jam produces nothing; a seeded speed jump produces a check-in.

**Walkthrough:** `docs/walkthroughs/JG5.md`

**What might change:** which signals survive. Expect at least one of these to be dropped for firing
too often on a real commute — that is what the trial is for, and dropping one is a success, not a
failure.

## JG6 — answering safely

> **Not before the finale — second stretch goal, and the one worth most.** The duress response is the most striking thing in this document, and JG2 already reserves the ground for it: `checkin.py::CHECK_IN_ACTION_OK` documents why there is one button today and not two. It needs JG3's escalation chain to escalate into, and it needs teaching rather than a settings toggle, which is a design problem and not an afternoon.
>
> One caution from JG2's device runs: a lock-screen button cannot be relied on with this push stack at all (see `docs/walkthroughs/JG2.md`). A duress *button on a notification* may therefore not be deliverable, and this phase would have to put both responses on the journey card.

**Goal:** a check-in that can be answered honestly while somebody is watching you answer it.

**What lands:**

- Two responses that both look like "I'm fine". One is.
- The quiet one escalates without changing anything on screen.
- A "someone is following me" button that shortens the leash to minutes, on demand.
- Both are off by default and explained once, in settings.

**Done when:** pressing the duress response shows the same thing as the safe one, and the guardian
receives an escalation anyway.

**Walkthrough:** `docs/walkthroughs/JG6.md`

**What might change:** how it is taught. A safety feature nobody remembers under stress is
decoration, and the honest answer may be that this needs a one-time walkthrough inside the app rather
than a settings toggle.

## JG7 — the outer ring

> **Not before the finale.** The largest of the four, and the one that looks worst half-finished: a witness request is an unsolicited message to strangers about an emergency. It needs an opt-in surface that does not exist and a privacy review, and the radius and wording are explicitly judgement calls to be made with the notification on a real phone.

**Goal:** reach the people who are actually nearest, without summoning a crowd.

**What lands:**

- A witness request to opted-in users recently near the area: a road, not a pin; no identity; asks
  for information, not intervention.
- Fired only on a **confirmed** emergency — full SOS or the duress response. Never on an unanswered
  check-in.
- Replies land as reports, and flow into the `community_clusters` corroboration already built.
- A one-tap 999 call on the escalation screen, and the thana email described as the paper trail it
  is.

**Done when:** a confirmed emergency on one phone produces a witness notification on a second, with
no pin and no name — and a report filed from that second phone shows up as corroboration.

**Walkthrough:** `docs/walkthroughs/JG7.md`

**What might change:** the radius and the opt-in wording, both judgement calls that should be made
with the notification in front of you on a real phone rather than in a planning document.

---

## The rule for every phase

From `docs/walkthroughs/README.md`, and it applies here unchanged:

> A walkthrough is a play-script you run on a phone, as the user, with no knowledge of the code. It
> is written by the sprint owner, at the end of the sprint, in the same commit as the work, and the
> owner must have actually run it on a real device before pushing.

So a phase is finished when there is a `JG<n>.md` that someone else could follow on a phone, with an
expected result beside every step and a **Rough edges** section that is honest. A phase with working
code and no walkthrough is not finished, because work that is invisible on a device is
indistinguishable from work that does not exist.

---

*Corresponds to **B10 / S22–S23** in `IMPLEMENTATION_PLAN.md`, where the escalation chain and the
non-response invariants are already specified. The phase breakdown above is mirrored in
`DEMO_PLAN.md` §6.*
