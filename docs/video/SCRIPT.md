# Meridian — the video

A shot-by-shot script for a *how to use it* video shaped like a problem, not a feature tour.

Twelve chapters, one evening, one person. Each chapter opens with the friction **shown** rather than
stated, then the taps, then what changed. Nothing is narrated that the screen does not do.

Target length **14–18 minutes**. Chapter lengths deliberately differ; uniform chapters are what make
a video feel like a template.

---

## Decide these before you record

| | |
|---|---|
| **Language** | The script below is English. Chapter 3 is *about* Bangla, and the headlines on screen in chapters 1, 2 and 10 are Bangla, so a fully English video argues against itself. Bangla narration with English subtitles reads strongest for a Bangladeshi audience; English narration with Bangla subtitles reads strongest for judges and funders. Pick one and keep it. |
| **The person** | Give her a name and say it once, in the cold open. "A commuter" is nobody; a name is somebody. |
| **Register** | **Phone in hand**, filmed, for chapters 5, 6, 7. **Clean screen capture** for 1, 2, 3, 4, 8, 9, 10, 11. Mixing the two on purpose reads as craft; at random it reads as sloppy. |
| **The inbox** | On a laptop, on screen, beside the phone. Chapters 5, 6 and 7 are worthless without it visible. |

---

## Get the data right first

This is the part that decides whether the video shows a live product or a fixture. **Do it the
morning you record.**

- [ ] **Backend up, minute sweep alive.** Every email in chapters 5–7 comes from it, and ingestion
      runs on it.
- [ ] **Let `live_risk` run** (every 15 min). Confirm you have live news flags:
      `event_key like 'live-%'`. They carry real headlines and real URLs, and **they expire in
      8–12 hours** — so chapters 1, 2 and 10 must be shot the same day.
- [ ] **Re-run the seeder** — `scripts/seed_risk_flags.py`. The scheduled flags are offset from
      *now*, so this is what puts a genuine **tomorrow** on the map. Without it chapter 10 has
      nothing to show: the seeded announcements from 11 Oct have passed, and `scheduled_risk`
      currently publishes none of its own.
- [ ] **Note down your three live flags' places** before you start filming, so you are not hunting
      for them on camera. On 16 Oct they were:

      | Outlet | On the map as |
      |---|---|
      | Prothom Alo | `Delay likely near Mohammadpur Beribadh Connecting Road.` |
      | Jugantor | `Delay likely near Bangla Motor.` |
      | Samakal | `Road blocked near Azampur.` |

- [ ] App installed from the current branch — `.\scripts\run.ps1`. A Metro reload is not enough if
      native config changed.
- [ ] Push permission **granted** when the app asked.
- [ ] One emergency contact whose inbox **you can open**. Profile → Emergency contacts.
- [ ] Send one mail to that address the day before and mark it *Not spam*. Placement belongs to the
      recipient's mailbox, not to the code, and it happens once per new address.
- [ ] One crime report already on the map, with a photo, for chapter 9 to open.
- [ ] Phone on Do Not Disturb except Meridian, so no WhatsApp banner lands mid-take.

### Three shots that need staging

Not weaknesses — just facts about what the camera can capture.

| Shot | Why | What to do |
|---|---|---|
| Journey **arrival** (ch. 5) | Needs a real GPS fix, accurate to 100 m and within 40 m of the pin. There is deliberately no button that asserts arrival. | Film that one shot outdoors |
| A proximity alert arriving on its own (ch. 11) | Alerts fire inside 500 m of a flag. Nothing is that close to your desk. | Seed a flag near you first, or film `Send me a test alert` |
| The escalation email (ch. 7) | Real ladder: deadline → buzz → 5 min → buzz → 5 min → email | Start chapter 5 **before** you film 8 and 9, and it lands on its own |

---

## Running order

| # | Chapter | Register | ≈ |
|---|---|---|---|
| — | Cold open | Filmed, no screen | 0:30 |
| 1 | "I don't know what's on that road" | Capture | 1:30 |
| 2 | "Says who?" | Capture | 2:00 |
| 3 | "I don't know the English name of my own junction" | Capture | 1:15 |
| 4 | "Fastest isn't safest" | Capture | 2:00 |
| 5 | "Nobody knows where I am" | Filmed | 2:00 |
| 6 | "Something's wrong, right now" | Filmed | 1:30 |
| 7 | "I didn't arrive" | Filmed | 1:30 |
| 8 | "I saw something and nobody will ever know" | Capture | 2:00 |
| 9 | "Filing a GD takes a day I don't have" | Capture | 2:30 |
| 10 | "The procession is tomorrow" | Capture | 1:30 |
| 11 | "How do I know it's even working?" | Capture | 1:00 |
| — | Close | Capture | 0:45 |

**Chapter 5 starts a 13-minute clock.** Shoot it before 8 and 9 so the escalation runs while you
film them, and chapter 7 is a genuine interruption.

---

## Cold open · 0:30

No app. No logo. No narration for the first six seconds.

| Shot | On screen | Narration |
|---|---|---|
| 1 | A junction at night. Two roads leaving it. Her, standing, phone in hand, not using it. | *(silence)* |
| 2 | Hold. | "This is Nadia. She has two ways home." |
| 3 | Hold. | "One of them was blocked twenty minutes ago. A newspaper reported it. She has no way to know that." |
| 4 | Cut to black. Title. | "Everything you are about to see was already public." |

Do not explain the market. Do not say "in Bangladesh, millions of people…". The scene is the problem.

---

## Chapter 1 · "I don't know what's on that road" · 1:30

**The problem** — every navigation app answers *fastest*. None answers *is this safe right now*.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Open the app. **Map** tab. Let it settle. | Dhaka, covered in coloured markers. | "This is Dhaka tonight." |
| 2 | Hold on the badge, bottom-left. | `N risk flags · news 4 min ago` | "Four minutes ago, Meridian finished reading the news." |
| 3 | Hold. | — | "Ten newsrooms. Prothom Alo, Jugantor, Samakal, Ittefaq, Channel 24, Ekattor, and the Dhaka Metropolitan Police. Two hundred and thirteen articles in the last day." |
| 4 | Hold. | — | "Three of them were about a road. Those three are on her map." |
| 5 | Slow pinch out, Jatrabari to Uttara. | Markers clustered along Mirpur Road, Airport Road, Progoti Sarani. | "They follow the main roads, because that is where this happens." |
| 6 | Hold on four markers of different colours. | Deep red, orange, yellow, grey-blue. Circles of visibly different sizes. | "Colour is how bad. The circle is how far it reaches — a blocked road reaches further than a crash." |
| 7 | Point at a hollow dashed marker beside a solid one. | One filled with a number, one hollow with a `?`. | "And a solid pin is something a newsroom published. A hollow one is something a neighbour told us. You can tell them apart without tapping anything." |

**Shot 4 is the chapter.** Two hundred and thirteen articles in, three flags out — that ratio *is*
the product. Say it as a strength, because it is one: a feed of 213 headlines helps nobody.

---

## Chapter 2 · "Says who?" · 2:00

**The problem** — the first thing anyone says about a safety map is *"so it's just rumours?"*
Protect this chapter if you cut anything. Tap one of **your real live flags**, not a seeded one.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Tap the Mohammadpur marker. | A sheet rises. Title: **"Delay likely near Mohammadpur Beribadh Connecting Road."** | "Tap it, and it tells her what it means for the road." |
| 2 | Hold on the title. | — | "Not 'clash'. Not 'crime'. What it means for getting through. That translation is deliberate — she needs to decide a turn, not read a crime report." |
| 3 | Hold on the badges. | `Confirmed · 1 source` and a severity badge | "Confirmed." |
| 4 | Scroll to the source strip. **Hold on it.** | The Bangla headline from **prothomalo.com**, with the time. | "Because Prothom Alo reported it. One of the ten newsrooms we read and checked by hand — and a national newsroom does not invent a blocked road." |
| 5 | Tap the source. | The real article opens in the browser. | "She can go and read it." |
| 6 | Back. Point at two rows. | **Severity when observed** and **Severity now**, the second smaller | "It was worse an hour ago. It is getting better, and the map knows the difference." |
| 7 | Point at the next row. | **Leaves the map in** `2h 14m` | "And it will take itself off the map. Nobody has to remember to delete it." |
| 8 | Close the sheet. Pan to Banani and Gulshan 2. | **No markers.** | "There was an accident here this morning and a fire here yesterday. They are gone, and nobody deleted them." |
| 9 | Hold. | — | "No stale red zones. That is the difference between a map and a list that grows forever." |

**Two lines do the work here:** *"Prothom Alo reported it"* and *"it will take itself off the map."*
Slow down on both.

---

## Chapter 3 · "I don't know the English name of my own junction" · 1:15

**The problem** — she says *গোলচত্বর*. Every other app wants *Circle*.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Tap the search box at the top. | Placeholder already reads `Mirpur 10 golchattar`. | "She types it the way she says it." |
| 2 | Type `Mirpur 10 golchattar`. Search. | Flies north-west, zooms in, dark-green pin. Below: **Mirpur-10 Circle**, green chip **"From our Dhaka gazetteer"**. | "Mirpur-10 Circle. Found." |
| 3 | Clear. Type `মিরপুর ১০ গোলচত্বর`. | **Same place. Same green chip.** | "The same place in Bangla. One list, either script." |
| 4 | Clear. Type `Mirpur 10 Cirlce` — leave the typo. | Still **Mirpur-10 Circle**. | "And it forgives a typo." |
| 5 | Clear. Type `Hatirjheel`. | Flies there with a **blue** pin and **"Inferred by AI"**. | "When it is not on the list, it asks a model — and tells her that is what happened." |
| 6 | Clear. Type `Sector 11`. | **No pin.** *"Could not find "Sector 11". We will not guess a location."* | "Now the one worth watching. There is a Sector 11 in Uttara and a Sector 11 in Bashundhara, ten kilometres apart." |
| 7 | Hold on the refusal. | — | "So it refuses. Confidently sending her to the wrong side of Dhaka is the one thing a safety app must never do." |
| 8 | Clear. Type `Sector 10`. | **Resolves.** Green chip. | "Sector 10 is unambiguous. It answers straight away." |

**Shots 6–8 together are the chapter.** The refusal only reads as strength because shot 8 proves it
is not a gap.

---

## Chapter 4 · "Fastest isn't safest" · 2:00

**The problem** — she has two routes and no basis for choosing.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Tap the **navigate** button. | Search box replaced by **Plan a route**. | "Where she is. Where she's going." |
| 2 | Start **Dhanmondi**, destination **Gulshan**. Calculate. | **Two** routes. Card with **Recommended** / **Option 2**. | — |
| 3 | Hold on the two lines, not the card. | One green-ish, one amber. | "The colour isn't first and second. It's how safe each one is." |
| 4 | Hold on the Recommended numbers. | `71/100` · `9 min` · `7.0 km` · `3 flags` | "Seventy-one out of a hundred. Nine minutes. Three flagged places on the way." |
| 5 | Hold on the sentence under them. | *"Passes Delay likely near Badda, reported repeatedly over time (three sources); and 2 other flagged locations. Fastest, and avoids 4 flagged corridors."* | "And it says why, in a sentence — so she isn't left interpreting a score." |
| 6 | Hold on the circles. | Solid on this route; **dashed and faint** on the other. | "Solid is what this route passes. Faint is what the other one passes. The comparison is drawn." |
| 7 | Tap **Option 2**. | Card switches, line thickens, **circle styles swap**. *"…and 4 other flagged locations. 2 minutes longer."* | "Two minutes longer, and five flagged places instead of three." |
| 8 | Hold on that sentence. | — | "Notice what it doesn't say. It doesn't claim to avoid anything, because it doesn't. It has nothing to sell her." |
| 9 | Scroll the flag list. | `3 sources`, `unconfirmed`, **`historical pattern`**. | "A blockade tonight and a two-year pattern are different claims, and they don't look the same." |
| 10 | Tap **Walking**. | Re-requests on one tap. `88 min`, label **`walking estimate`**. | "Walking, driving — and it labels which numbers are estimates." |

**Shot 8 is the one people remember.** A product that declines to oversell its own second option is
the one people trust with the first.

---

## Chapter 5 · "Nobody knows where I am" · 2:00 · **starts the 13-minute clock**

Filmed, phone in hand. **Shoot this before chapters 8 and 9.**

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | In route mode, pick a destination. | A route with a safety score. | "She's going home." |
| 2 | Hold on the deadline line. | **Check in by 1:12 PM** | "The app works out when she should be there." |
| 3 | Under **If you go quiet, tell**, tap one contact. | The chip goes solid. A line appears. | — |
| 4 | **Hold on that line and read it aloud.** | *"They get an email when you set off, when you arrive, and if you stop answering check-ins."* | "It tells her exactly what her sister will be told — before she chooses, not after." |
| 5 | Press **Start**. | Turn banner replaces the card. | — |
| 6 | Cut to the inbox. Within a minute. | A **slate-grey** email: **`Nadia has started a journey`**. | "Her sister gets this. Where she's going, when she's due." |
| 7 | **Scroll the whole email on screen.** | — | "And no location anywhere in it. While everything is fine, her sister learns nothing about where she is." |
| 8 | Back to the phone. Kill the app — swipe it out of recents. | — | "Now watch this." |
| 9 | Reopen. **Map** tab. | The **journey card** is still there: *"Journey in progress"*, `n min to <place> · check in by 1:12 PM`, **`Telling <name>`**. | "The journey isn't in the app. It's on the server. Her battery dying doesn't end it." |
| 10 | *(Outdoor shot)* Arrive within 40 m of the pin. | Navigation ends by itself. Card disappears. | — |
| 11 | Cut to the inbox. | A **green** email: **`Nadia arrived safely`**. | "That subject line is the whole product. Her sister never has to open it." |

---

## Chapter 6 · "Something's wrong, right now" · 1:30

Filmed. Different take, different light if you can — this is not the same moment as chapter 5.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | **Home** tab. Hold on the SOS button. | — | "This is for the other kind of evening." |
| 2 | Press and hold. Confirm. | 10-second clip → **"Uploading Evidence…"** → **"Alerting your contacts…"** | "Ten seconds of video, then her contacts. Seconds, not minutes." |
| 3 | While it runs, switch to **Map**. | **The map still loads.** | "And the app keeps working while it does it." |
| 4 | Cut to the inbox. | The SOS email, with location and the clip. | "This time they get exactly where she is — because this time that is the point." |
| 5 | **Profile → SOS hot words**. | The phrase list. Add one. | "She doesn't always have a hand free. So there's a phrase she can say." |
| 6 | Hold. | — | "And a shake, if she can't speak either." |
| 7 | Open the SOS record from Profile. | The incident with its evidence. | "And every one leaves a record. That matters in chapter nine." |

**Contrast worth naming out loud:** chapter 5's emails carry no location, this one does — and the
difference is whether she asked for help.

---

## Chapter 7 · "I didn't arrive" · 1:30

The payoff of chapter 5 and the peak of the video. Let it breathe.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Title card. | *13 minutes later* | "Back to the first evening. She never arrived." |
| 2 | Phone on a table, screen up. It buzzes. | **"Are you there yet?"** / *"Tap to let Meridian know you're fine."* | "It asks her." |
| 3 | Nobody touches it. Hold. | — | *(silence — let it sit)* |
| 4 | Open the app. Hold on the card **before** tapping. | Title is now **"Are you there yet?"**, with its own **I'm fine** button. | "It can be answered from here too. A safety question with one way to answer it is one failed notification away from being unanswerable." |
| 5 | Second buzz, five minutes on. Still ignored. | — | "It asks again." |
| 6 | Tap the card. | **"Asked twice, still no answer."** *"If this stays unanswered, `<name>` will be emailed."* | "And it says, out loud, what is about to happen next." |
| 7 | Cut to the inbox. | The **red** email: **`Nadia has not arrived and is not answering`**. | "Her sister. Thirteen minutes after she should have been home." |
| 8 | Scroll it. Hold on the location sentence. | *"The last place their phone reported from was …"* — or *"They started from … that is the start of the journey, not a sighting"* | "And it is precise about what it knows. If it only knows where she set off from, it says so — sending someone to the wrong end of a route is worse than sending them nothing." |
| 9 | Hold on the last line. | **"You are the only person who has been told."** | "One person. The one she chose." |
| 10 | Back to the phone. Tap the card → **I'm fine**. | Red clears. Back to *"On your way."* Timeline keeps every rung, plus `You said you were fine`. | "She was fine. Her phone was in her bag." |
| 11 | Hold. | — | "And it stops there. No second email, no contact list, no 999. Widening the circle is her sister's call — she's the one who knows whether Nadia is usually late." |

**Shot 11 is the chapter.** Most safety apps escalate until someone calls the police. Say plainly
that this one chooses one person and stops.

---

## Chapter 8 · "I saw something and nobody will ever know" · 2:00

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | **Reports → + → Add Report**. | The report form. | "A week later, she sees something." |
| 2 | Add a photo. Don't type anything first. | Analysis starts on its own. ~3 s. Badge reads **live**. | "She adds a photo. Three seconds." |
| 3 | Hold on the sentence. | A description of what is visible. | "It describes what it can see — and stops there. It doesn't name a crime and it doesn't guess what anyone intended." |
| 4 | Scroll the seven cues. | All seven, **including the ones reading `no`**. | "All seven things it looked for, including the ones it didn't find. Showing only the hits would make 'not sure' look like a crash." |
| 5 | **New report, benign photo** — an empty street, a desk. | **"No category suggested."** Category stays empty. | "And here's the behaviour the whole thing was built for. Nothing here — so it says nothing." |
| 6 | Hold. | — | "It would be easy to make it always have an answer. That's the version that gets somebody accused of something they didn't do." |
| 7 | New report: type a description **first**, then add the photo. | Typed text **not overwritten**. Card adds *"Matches what you wrote"*. | "Her words stay her words. The photo agrees, or it doesn't." |
| 8 | Submit. Open it from the list. | Evidence photo, the sentence, the engine under it. | "Filed, with the evidence attached." |
| 9 | Turn the laptop's internet off. Analyse a new photo. | Badge changes to **on this device**, ~9 s. | "And with no internet at all, it still reads it — on the device, a little slower." |

**Shots 5 and 6 are the chapter.** Use a genuinely empty photo and resist picking something
ambiguous.

---

## Chapter 9 · "Filing a GD takes a day I don't have" · 2:30

The longest chapter, and the one nobody else has.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | Open the report. Find the General Diary section. | — | "In Bangladesh, making this official means a General Diary. In Bangla, at a police station, in a form most people have never filled in." |
| 2 | Tap **Generate GD**. ~2 s. | A Bangla narrative beginning `বিনীত নিবেদন এই যে,`. | "Two seconds." |
| 3 | Hold on the narrative. | — | "In the register's own language, and the register's own form." |
| 4 | Scroll to the English line under it. | One sentence saying what the narrative claims. | "And one English sentence saying what it claims — so somebody who doesn't read Bangla can still check it." |
| 5 | Hold on the top card. | Names the police station nearest to where it happened. | "It works out the thana." |
| 6 | Tap **Change**, search, pick another, change it back. | Saves both times. | "And lets her overrule it. Forty-six of Dhaka's fifty-one stations have verified coordinates — but thana boundaries are polygons drawn by people, so the choice stays hers." |
| 7 | Hold on the missing-details card. | What the duty officer will still ask for. | "It even tells her what she'll be asked that her report didn't cover." |
| 8 | Tap **Edit**, change a word, **Save**. | Narrative updates. **Approve goes back to disabled.** | "She changes a word, and the approval resets. What she read a moment ago was a different document." |
| 9 | **Without scrolling**, tap approve. | Reads **"Scroll to the end to approve"**. Nothing happens. | "Now the part that matters most." |
| 10 | Scroll to the bottom. | Becomes **"I have read this — approve"**. | "She has to reach the end before she can approve it." |
| 11 | Tap it. | Card turns green: **Approved — ready to file**. | — |
| 12 | Hold. | — | "And that's not a greyed-out button. The server only accepts approval for the exact text it issued, and the database refuses an approved record that was never approved. Three layers, one rule: a person read this." |
| 13 | Tap **Print the form**. | Android print preview. **Bangla renders as Bangla**, conjuncts correct. | "Two ways out. Print the DMP form and walk in with it —" |
| 14 | Back. Tap **Copy**. | Narrative on the clipboard. | "— or paste the narrative straight into the police's own app." |
| 15 | Hold on the channels card. | For harassment: 999, 109, PCSW. Tapping one opens the dialler. | "And the right number for this kind of report, already dialled." |
| 16 | Scroll the whole screen slowly. | **No "submit to police" button anywhere.** | "What there's no button for is filing it. A General Diary is a statement by a person. We draft; a person files." |

**Shot 16 is the line of the video.** Do not rush it.

---

## Chapter 10 · "The procession is tomorrow" · 1:30

Needs the seeder re-run that morning — see *Get the data right first*.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | **Map**. Hold on the time control. | `Live · N flags` | "Everything so far was tonight." |
| 2 | Tap **Tomorrow**. | Label becomes a weekday and clock time, then **`N flags, 3 scheduled`**. Three **rounded squares** appear — Shahbagh, Paltan, Mirpur Road. | "This is tomorrow." |
| 3 | Hold on the squares. | Squares, while everything else stays round. | "Three things that haven't happened yet — and drawn differently, so she can't mistake one for the other." |
| 4 | Tap the Shahbagh square. | Two badges: `Confirmed · 2 sources` **and** a blue **`Scheduled`**. First row **`Scheduled for`** with a window. Next row **`Announced`**, not Observed. | "Announced, not observed. Nobody watched a procession that hasn't happened." |
| 5 | Tap the Paltan square. | **`Unconfirmed · 1 source`** *and* `Scheduled`. | "When it happens, and whether it's confirmed, are two different questions. The map answers both at once." |
| 6 | Tap **Now**. | The three squares **disappear**. | "And none of it is on tonight's map. A procession at full severity tonight would bend tonight's routes around a road that's completely clear." |
| 7 | Tap the risk badge, bottom-left. | A screen titled **What we read**. Tabs **Today** and **Tomorrow**. | "And if she wants to see the reading itself —" |
| 8 | Scroll **Today**. | Article cards: outlet, Bangla headline, time, and the flag each one produced. | "— every article, who published it, and what it became." |
| 9 | **Tomorrow** tab. | The Shahbagh procession appears **twice, once per outlet**. | "And here's why that one said two sources. Two newsrooms, shown rather than claimed." |

---

## Chapter 11 · "How do I know it's even working?" · 1:00

Short, and it buys more trust than any feature.

| Shot | Do this | On screen | Narration |
|---|---|---|---|
| 1 | **Profile → Alerts**. | **What to alert me about** — three switches. | "She chooses what's worth a buzz." |
| 2 | Hold on the severity steps. | Everything / Moderate and above / Serious only / Severe only. | "Four steps, not a slider. Nobody knows what forty-three out of a hundred means for how often their phone goes off." |
| 3 | Hold on **Quiet hours**. | 22:00–07:00 Dhaka. *"Emergency SOS is never silenced."* | "Quiet at night — except the one thing that should never be quiet." |
| 4 | Hold on the cap line. | *"At most N alerts per hour, whatever happens. You can ask for fewer, never more."* | "And a ceiling she can't raise. That's a promise, not a setting." |
| 5 | Tap **Send me a test alert**. | The notification arrives. | "She can check it works, herself, right now." |
| 6 | Scroll to the diagnosis and **Recent alerts**. | The delivery diagnosis; the alert history. | "And if one never came, this says why. An alert held back by the hourly cap and one that was never sent look identical from a lock screen — so the app tells her which it was." |
| 7 | **Profile → System status**. | Agent entries and their last runs. | "Everything reading the city, and when each one last ran. Nothing here is hidden from her." |

---

## Close · 0:45

| Shot | On screen | Narration |
|---|---|---|
| 1 | Her report from chapter 8, on the reports list. | "One last thing, and it's what we get asked about most." |
| 2 | The **Map**. Her report is a marker. **It is not a risk flag.** No route bends around it. | "Her report is on the map. It does not change anybody's route." |
| 3 | Hold. | "One person reporting a corner becomes nothing. It takes several strangers, independently, same corner, same few hours — and even then what gets published is a count and how recent it is. Not a claim." |
| 4 | Back to the junction from the cold open. Two roads. | "Because the moment one report can redirect a stranger, this stops being something you can trust." |
| 5 | Hold on her choosing a road, phone in hand. | "She still decides. She just isn't deciding blind." |
| 6 | Cut to black. | *(silence)* |

---

## If something fails mid-shoot

| It failed | Do this |
|---|---|
| Check-in never buzzes (ch. 7) | Film the **journey card** answering instead — it has its own **I'm fine** button, and that redundancy *is* the point |
| First email in spam | Mark *Not spam*, re-shoot. Once per address |
| Journey never arrives (ch. 5) | You were indoors. Press **End** — closes it as cancelled, sends nothing — and re-shoot outside |
| No live news flag on the map | `live_risk` runs every 15 min; give it one cycle. Chapters 1 and 2 need at least one |
| `Tomorrow` shows nothing | Re-run `scripts/seed_risk_flags.py` — the scheduled windows are offset from *now* |
| Risk badge reads `Risk layer unavailable` | The phone can't reach the backend. `EXPO_PUBLIC_API_BASE_URL` must be the LAN IP, not localhost |
| Vision analysis is slow (ch. 8) | That's the on-device path, ~9 s, badge reads **on this device**. Narrate it — nine silent seconds reads as a crash |
| GD draft comes back empty | Re-tap **Generate GD**. If it fails twice, film an already-generated draft |

---

## The three sentences, if it has to be cut to one minute

1. **Ten newsrooms, two hundred articles a day, three flags on your map** — each one naming the
   paper that reported it, and each one taking itself off the map when it stops mattering.
2. **It tells one person you chose, once** — and if you stop answering, it tells that same person
   where you were last. Nobody else. Ever.
3. **It drafts the General Diary in Bangla; a person files it.** There is no button that submits to
   the police, and there never will be.
