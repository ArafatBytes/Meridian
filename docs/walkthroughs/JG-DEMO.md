# Journey Guardian — the whole thing, on a phone

The end-to-end demonstration of JG1 + JG2 + JG3, run the way a user runs it: **a phone and an email
inbox, and nothing else.** No SQL, no fast-forward, no `agent_runs`, no Supabase tab. Every number on
this page is the real one, so the escalation run takes about **thirteen minutes of waiting** — that
is the feature working, not the feature being slow.

The other walkthroughs (`JG1.md`, `JG2.md`, `JG3.md`) prove the machinery, and they use the database
to do it. This one proves the *product*: what somebody actually sees.

---

## Before you start

| | |
|---|---|
| **The app** | Built and installed from the current branch — `.\scripts\run.ps1`. A Metro reload is not enough if native config changed. |
| **The backend** | Running, with the minute sweep alive. Everything on this page is driven by it; nothing happens without it. |
| **Push** | Allowed when the app asked. If you denied it, the check-in cannot buzz — see *When something does not work*. |
| **One emergency contact with an email address** | Profile → emergency contacts. **The address must be one you can open**, because you are going to play both parts. The contact does **not** need the app, an account, or anything else. |
| **The inbox** | Open on a laptop, not on the phone you are demonstrating with. Switching apps on the phone mid-journey is a distraction, and the phone's own mail app will mark things read before you can show them. |
| **Outdoors, for the arrival run** | Arrival is decided by a real GPS fix within 40 m of the destination. Indoors the navigator rejects every fix as too inaccurate and the journey will simply never arrive. The escalation run works fine at a desk. |

**Pick a destination you can walk to in a few minutes** for Demo 1. A shop at the end of the road is
ideal. Tap it on the map and the app takes its name.

---

## What is on a timer

Worth knowing before you stand there wondering whether it is broken.

| | |
|---|---|
| The sweep | Runs **every minute**. Every email and every check-in comes from it, so nothing is ever instant — up to 60 seconds late is normal and correct. |
| Heartbeat | Every **60 seconds** while you are following the route. It is a timer, not a tripwire: a stationary phone reports in exactly like a moving one. |
| Between rungs | **5 minutes.** Each step of the escalation needs the one below it to have sat unanswered that long. |
| The whole ladder | Deadline → first buzz → *5 min* → second buzz → *5 min* → guardian emailed. **It stops there.** |

---

## Demo 1 — the good day

The one worth leading with. Nothing goes wrong, and the feature is still doing something.

| # | Do this | You should see |
|---|---|---|
| 1 | Open the app, go to **Map**, tap the route button. | The route card: **My Location**, **Where to?**, Driving / Walking. |
| 2 | Tap a shop or building a few minutes' walk away. | The destination fills in **with the place's name** — not "Selected Location". A route is drawn with a safety score. |
| 3 | Choose **Walking**. | The ETA changes. This matters: it is the number the deadline is built from. |
| 4 | Look at the line reading **Check in by 1:12 PM**. | That is the deadline the server will enforce, shown as a clock time rather than a countdown. Leave it on **Route ETA**. |
| 5 | Under **If you go quiet, tell**, tap your contact's name. | The chip goes solid. A line appears: *"They get an email when you set off, when you arrive, and if you stop answering check-ins."* **Say that line out loud** — it is the whole privacy promise, made before the choice rather than after. |
| 6 | Press **Start**. | Navigation begins. The route card is replaced by the turn banner. |
| 7 | **The inbox, within a minute.** | A **slate-grey** email: **`<your name> has started a journey`**. It names the destination and the time you are due, and promises one more message when you arrive. **There is no location in it anywhere.** That is the point — hold it up. |
| 8 | Walk. | The map follows you. |
| 9 | Press the home button. **Kill the app entirely** — swipe it out of the recents list. | Nothing is lost. This is JG1. |
| 10 | Reopen the app. Go to Map. | The **journey card** is still there: *"Journey in progress"*, `<n> min to <place> · check in by 1:12 PM`, and **`Telling <name>`**. The journey lives on the server, not in the app. |
| 11 | Tap the card. | The **journey screen**: *"On your way."*, *"<name> will hear if you go quiet."*, and a timeline — `Journey started`, `<name> was told you set off`, with times. |
| 12 | Press **Resume** on the card and walk the rest of the way. | Navigation picks up where it was. |
| 13 | Arrive — get within 40 m of the pin. | Navigation ends by itself. The card disappears. |
| 14 | **The inbox.** | A **green** email: **`<your name> arrived safely`**. Two lines, no location. |
| 15 | Tap the journey card if it is still showing, or just say it. | *"That subject line is the entire product. A guardian never has to open it."* |

---

## Demo 2 — you stopped answering

The run the feature exists for. Do this one sitting down; it needs no movement at all.

| # | Do this | You should see |
|---|---|---|
| 1 | Route mode. Pick any destination. | A route. |
| 2 | Tap the **2 min** deadline chip. | The *Check in by* line jumps to two minutes from now. This is the only "cheat" on this page, and it is a button in the app — not a database edit. |
| 3 | Pick your contact as the guardian again. | `Telling <name>`. |
| 4 | **Start.** Then put the phone down and leave it on the navigation screen. | Heartbeats run in the background. You do not have to move. |
| 5 | **Minute 1.** The inbox. | The **"has started a journey"** email again. |
| 6 | **Minute 2–3.** Wait. | The phone **buzzes**: **"Are you there yet?"** / *"Tap to let Meridian know you're fine."* **Ignore it.** |
| 7 | Open the app. Look at the journey card **before** tapping it. | Its title has changed from *"Journey in progress"* to **"Are you there yet?"**, and it has grown its own **I'm fine** button. The question is answerable from the glanceable card, not only from the notification. |
| 8 | Now tap the card. | The journey screen reads **"Meridian is waiting to hear from you."**, *"Tap 'I'm fine' and the clock moves on."*, with an **I'm fine** button and a new timeline row: `Meridian asked if you were okay`. **Do not tap it.** Back out. |
| 9 | **Wait five minutes.** | The phone buzzes a **second** time. Same question. Still ignore it. |
| 10 | Tap the journey card. | **"Asked twice, still no answer."** and *"If this stays unanswered, `<name>` will be emailed."* The timeline has `No answer by the deadline` and `Meridian asked again`. This is the last moment before somebody else is involved, and the screen says so. |
| 11 | **Wait five more minutes.** | |
| 12 | **The inbox.** | The **red** email: **`<your name> has not arrived and is not answering`**. It says Meridian asked twice; it gives a point and a map link; it ends **"You are the only person who has been told."** |
| 13 | Read the location sentence carefully. | It is **one of two**, and which one you get is honest: *"The last place their phone reported from was …"* if a fix was stored, or *"They started from … that is the start of the journey, not a sighting"* if none was. Indoors you will get the second. **That distinction is the thing to point at** — a start point presented as a sighting sends a searcher to the wrong end of the route. |
| 14 | Tap the journey card, then **I'm fine**. | The screen stops being red. It goes back to *"On your way."* and the deadline moves out. The timeline keeps every rung — `You said you were fine` is added, nothing is erased. |
| 15 | Say the last part. | **Nothing further happens. Ever.** No second email, no contact list, no 999. The ladder ends at the one person you named. |

**What you will not see, and should say:** the guardian's whole contact list is never mailed. Meridian
tells the person you chose, and then stops. Widening the circle is a decision for whoever reads that
email — they know whether you are usually late.

---

## Demo 3 — Nobody, and what it costs you

Thirty seconds, and it is the demo that makes the other two believable.

| # | Do this | You should see |
|---|---|---|
| 1 | Route mode, any destination. Leave the guardian on **Nobody** — the default. | The chip row shows `Nobody` selected, and the "they get an email" line is **absent**. |
| 2 | Start, then tap the journey card. | The journey screen reads *"Nobody is being told about this journey."* No `Telling …` line anywhere. |
| 3 | Say what is happening underneath. | With no guardian, **no position is stored at all** — the app does not even send one. It is not a flag that could be flipped; there is no recipient, so there is nothing to collect for. |
| 4 | Press **End** on the journey card. | The card disappears. **No "journey ended" email is sent** — ending a journey tells nobody, because "she stopped the journey" is not news and mailing it would train people to ignore these. Only *arriving* sends anything. |

---

## Demo 4 — the honest footnote

Not a step; a thing to show on the journey screen at any point.

At the bottom of that screen: **"Meridian only emails the people you chose. It does not call the
police."**

Say why it is there: an unanswered check-in is usually a phone in a bag. A product that called 999
on a missed tap would be wrong far more often than right, and the first time it was wrong it would
cost the user a relationship with the police they cannot get back. The 999 path exists — it is JG7,
and it fires on a **confirmed** emergency, not on silence.

---

## When something does not work

No SQL here either. These are the three things that actually fail.

**The check-in never buzzes.** Push is the least reliable part of this on any given handset — a
denied permission, a dead token, battery optimisation. It does not matter for the demo: **the
journey card answers too.** Open the app, tap the card, press **I'm fine**. Same endpoint, same
result. Say so — a safety question with exactly one way to answer it is one notification failure
away from being unanswerable, which is why there are two.

**The first email goes to spam.** Likely once per new recipient, and then never again. Open the
folder, mark it *Not spam*, and keep going. **Do this to the address you will use on stage, the day
before** — spam placement is a property of the recipient's mailbox, not of the code.

**The journey never arrives.** You were indoors, or not close enough to the pin. The navigator needs
a fix accurate to better than 100 m and within 40 m of the destination, and a tethered phone at a
desk produces neither. There is no in-app way to force it, by design: ending as *arrived* is the
claim the whole feature rests on, and a button that asserted it would make the claim worthless.
Press **End** on the card instead — that closes the journey as cancelled and sends nothing — then
run it again outdoors.

---

## The shape of it, in three sentences

If you have one minute rather than fifteen:

1. **You tell one person, once, when you set off** — and they are told again when you get there.
2. **If you stop answering, that same person is told where you were last** — and nobody else is,
   ever.
3. **Nothing is shared while everything is fine.** No live tracking, no location in the first two
   emails, and with no guardian chosen, no position is collected at all.
