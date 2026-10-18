# Video scenarios

Six segments, ~3:20. Shot list and on-screen text only.

**The through-line:** Nadia commutes home across Dhaka. The app reads the city, she picks a route,
she tells one person, she gets home. A second evening goes worse.

Every number here was read off the running system, not invented — re-check with
`verify_video_scenario.py` before each session.

---

## Budget

| | Segment | Length | Running |
|---|---|---|---|
| 0 | Open — login → loading → home | 0:10 | 0:10 |
| 1 | News ingestion → flags on the map | 0:25 | 0:35 |
| 2 | Tap a flag → the incident and its source | 0:20 | 0:55 |
| 3 | Routing → the clean route against the blocked one | 0:30 | 1:25 |
| 4 | Journey Guardian → the whole ladder | 0:45 | 2:10 |
| 5 | SOS → three triggers, video, email | 0:25 | 2:35 |
| 6 | Crime photo → detection → Bangla GD | 0:35 | 3:10 |
| — | Close | 0:10 | 3:20 |

---

## Segment 0 · Open · 0:10

### Shots
1. **Phone in frame, app closed.** Tap the icon. Hold half a second on the launch — the app
   icon is the first thing anyone sees of it.
2. **Login.** `Welcome back` · *Sign in to continue*, the shield mark above it. Email and
   password typed at normal speed, not hunted for. Tap **Log in**.
3. **Loading.** The signature animation — the rotating ring, the pulsing shield, four
   satellites — under **Meridian** · *Setting up your safety zone…* Hold the full beat.
4. **Home.** It settles: the **SOS** button, the Guardian status line, and the four actions —
   *Report crime* · *Plan a route* · *Live map* · *Contacts*. Hold 2 s. Do not tap anything.

### On-screen text
> **MERIDIAN**
> Safety navigation for Dhaka
> Real accounts, real sign-in — Supabase OAuth
> Every feature, one tap from home

Over shot 1, cleared before shot 3.

---

## Segment 1 · The city reads itself · 0:25

### Shots
1. The map, full of flags. Hold 2 s.
2. Tap the risk badge, bottom-left: `N risk flags · news 4 min ago`.
3. The **What we read** screen. Scroll the **Today** list slowly — Bangla headlines, outlet names,
   times, and the flag each article produced.
4. Back to the map.

### On-screen text
> Every incident across Bangladesh, on one map.
> Meridian reads the news before you ask.
> Ten newsrooms and TV channels. Every fifteen minutes.
> And every flag keeps the story it came from.


---

## Segment 2 · Says who? · 0:20

### Shots
1. Tap the flag. The sheet rises: **"Delay likely near Mohammadpur Beribadh Connecting Road."**
2. Hold on the badges: `Confirmed · 1 source`, severity.
3. Scroll to the source strip — the **Bangla headline**, the outlet, the time.
4. **Tap the source. The real article opens in the browser.** Hold 2 s then go back.
5. Step the clock forward — **+3 h**, **+6 h**. The flags fade as you tap, and the ones past
   their life drop off the map. Hold it long enough for one flag to visibly go.

### On-screen text
> AI reads each story and sets the flag — how bad it is, how long it lasts.
> It shows you who said so: the outlet, the headline, the time.
> The newspaper's own article, one tap away.
> As it ages it fades — then takes itself off the map.

---

## Segment 3 · One route is clean · 0:30

### Shots
1. Tap **Plan a route** (the map's route button). The panel opens with **Start location**
   already reading *My Location* — that is the GPS, so with the track at Rampura it is
   Rampura. The **Where to?** field takes focus by itself and the keyboard comes up.
2. Type `Gulshan` — suggestions appear from the third character. Tap
   **Gulshan 2, Gulshan, Dhaka…** (the **first suggestion**). The keyboard drops, the field
   reads `Gulshan 2`, and the route is calculated immediately. No separate Go button.
3. **Pinch out.** Nothing fits the camera to the route — selecting a suggestion zooms to the
   *destination* at ~1.7 km across, and the route is 5.5 km, so one end is off screen until
   you frame it yourself.
4. Two lines: the recommendation solid, the alternative faint. Hold 2 s.
5. The card's tabs read **Recommended 100** · **Option 2** and whatever it is tonight.
   Hold on that row — `100` is the number that matters and it does not move.
6. **Recommended**: `100/100 · 21 min · 0 flags`, and the sentence
   *"Nothing flagged along this route. 1 minute longer, avoids 4 flagged corridors."*
   Hold on **1 minute longer** — that is the whole segment in three words.
7. Tap **Option 2**: `20 min · 4 flags`, scoring in the fifties or sixties. The lines
   swap — faint becomes solid.
8. Tap **Details · 4 flags** to expand the card, and scroll the list: **Road blocked near Merul
   Badda** · Uttar Badda standing water · Badda and Progoti Sarani, both *reported repeatedly
   over time*.
9. **Hide details**, tap back to **Recommended**. Hold on the sentence.

**Do not press Start.** That is segment 4.

### On-screen text
> It ranks every route safety first, speed second.
> **100 out of 100 · nothing flagged**
> The faster road passes four flagged places.
> And it shows you the one it turned down, and why.

---

## Segment 4 · Nobody knows where I am · 0:45

### Shots
1. On the route card, tap the **2 min** deadline chip. The *Check in by* line jumps to a clock
   time two minutes out.
2. Under **If you go quiet, tell**, tap the contact. Hold on the line that appears:
   *"They get an email when you set off, when you arrive, and if you stop answering check-ins."*
3. **Start.** Navigation begins and the dot moves along the route.
4. Cutaway: the inbox. **Slate-grey** email — *"Nadia has started a journey"*. Scroll it: **no
   location anywhere.**
5. Back to the phone. The journey card counts down to the check-in. Hold.
6. The **journey card** changes its own title to **"Are you there yet?"** and grows an **I'm
   fine** button. Do not tap it.
7. Second nudge. Card reads **"Asked twice, still no answer."** and *"If this stays unanswered,
   `<name>` will be emailed."*
8. Cutaway: the **red** email — *"Nadia has not arrived and is not answering"*. Hold on the last
   line: **"You are the only person who has been told."**
9. Tap **I'm fine**. Red clears, back to *"On your way."*
10. The dot reaches Gulshan 2. Navigation ends by itself.
11. Cutaway: the **green** email — *"Nadia arrived safely"*.

Shots 4, 8 and 11 are the laptop inbox — captured separately, as they land.

### On-screen text
> Tell one person you're travelling. Just one.
> **Nothing is shared while everything is fine.**
> Go quiet, and it asks if you're okay.
> Still no answer — your guardian is told where you were last.
> Nobody else. Ever.
> You arrive, it stands down. One last email, and it's over.

---

## Segment 5 · Something's wrong, right now · 0:25

### Shots
1. **Click SOS Emergency** The SOS flow starts.
2. The 10-second clip records — show the counter.
3. **"Uploading Evidence…"** → **"Alerting your contacts…"**
4. Cutaway: the SOS email. Her name, the location, the clip attached.
5. Quick cut: Home tab, press and hold the **SOS button**. Then Profile → SOS hot words, showing
   the phrase. Three triggers, three seconds.

### On-screen text
> Three ways to call for help: shake the phone, say your word, or press.
> **It films ten seconds — then sends it, without being asked again.**
> Your contacts get your name, your location, and the clip.

---

## Segment 6 · Nobody will ever know · 0:35

### Shots
1. **Reports → + → Add Report.** Add the photo.
2. The analysis card appears, ~3 s, badge reads **live**. Hold on the sentence and the suggested
   category with its *"Because …"*.
3. Submit. Open the report.
4. Tap **Generate GD**. ~2 s. The Bangla narrative appears, beginning `বিনীত নিবেদন এই যে,`.
5. Hold on the thana card: **Sher-e-Bangla Nagar Police Station**, nearest to where it happened.
6. Hold on the English summary line under the narrative.
7. **Without scrolling**, tap approve — it reads **"Scroll to the end to approve"** and does
   nothing. Scroll to the bottom; it becomes **"I have read this — approve"**. Tap. Card turns
   green: **Approved — ready to file**.
8. Tap **Print the form** — Android print preview, Bangla rendering correctly. Back, tap **Copy**.

### On-screen text
> Reporting a crime, without the paperwork.
> Photograph it. The app reads the photo.
> **It describes what it sees — it never accuses anyone.**
> A General Diary, drafted in Bangla, in the register's own wording.
> The nearest station, worked out for you.
> **You have to read it to the end before you can approve it.**
> Print it, or paste it into the police's own app.

---

