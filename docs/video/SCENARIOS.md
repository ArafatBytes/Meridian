# Video scenarios

Six segments, ~3:20. One person, two evenings. Every number here was read off the running system,
not invented — re-check with `verify_video_scenario.py` before each session.

**The through-line:** Nadia commutes home across Dhaka. The app reads the city, she picks a route,
she tells one person, she gets home. A second evening goes worse.

**On-screen text, not narration.** Labels are written in the margin of each segment. No voiceover —
it fights the pace at this length and dodges the Bangla/English question.

---

## Budget

| | Segment | Length | Running |
|---|---|---|---|
| — | Open | 0:10 | 0:10 |
| 1 | News ingestion → flags on the map | 0:25 | 0:35 |
| 2 | Tap a flag → the incident and its source | 0:20 | 0:55 |
| 3 | Routing → the safe route among options | 0:30 | 1:25 |
| 4 | Journey Guardian → the whole ladder | 0:45 | 2:10 |
| 5 | SOS → three triggers, video, email | 0:25 | 2:35 |
| 6 | Crime photo → detection → Bangla GD | 0:35 | 3:10 |
| — | Close | 0:10 | 3:20 |

Segment 4 is the longest on purpose — it is the only feature with four states, and it is the one
nobody else has.

---

## Open · 0:10

Phone in frame, clean background. App closed.

Open the app. Map settles on Dhaka, covered in flags.

> **MERIDIAN**
> Safety navigation for Dhaka

No problem statement. The map is the problem statement.

---

## Segment 1 · The city reads itself · 0:25

**Situation.** It is evening. Before Nadia goes anywhere, the app has already read today's news.

### Start state
- [ ] `live_risk` has run — at least one `live-%` flag on the map
- [ ] `video_scenario.json` seeded, so the map is populated but not saturated
- [ ] Map tab, Dhaka at city zoom

### Shots
1. The map, full of flags. Hold 2 s.
2. Tap the risk badge, bottom-left: `N risk flags · news 4 min ago`.
3. The **What we read** screen. Scroll the **Today** list slowly — Bangla headlines, outlet names,
   times, and the flag each article produced.
4. Back to the map.

### On-screen text
> Ten newsrooms, read every fifteen minutes
> **213 articles today → 3 road incidents**
> Prothom Alo · Jugantor · Samakal · Ittefaq · Channel 24 · Ekattor · DMP

### Editor
The headline-scroll is the shot. Speed it to ~2× so it reads as volume rather than a list. The
213 → 3 number is the point: this is a filter, not a feed.

---

## Segment 2 · Says who? · 0:20

**Situation.** One of those flags is on her way home. She wants to know who said so.

### Start state
- [ ] Know which `live-%` flag you are tapping **before you roll** — `verify_video_scenario.py`
      prints the live ones
- [ ] On 17 Oct these were live: Prothom Alo → *Delay likely near Mohammadpur Beribadh Connecting
      Road*; Jugantor → *Delay likely near Bangla Motor*; Samakal → *Road blocked near Azampur*

### Shots
1. Tap the flag. The sheet rises: **"Delay likely near Mohammadpur Beribadh Connecting Road."**
2. Hold on the badges: `Confirmed · 1 source`, severity.
3. Scroll to the source strip — the **Bangla headline**, the outlet, the time.
4. **Tap the source. The real article opens in the browser.** Hold 2 s.
5. Back. Point at **Severity when observed** vs **Severity now**, then **Leaves the map in**.

### On-screen text
> It says what it means for the road — not "clash", not "crime"
> **Confirmed by Prothom Alo**
> Tap the source. Read the article.
> It fades as it ages, and removes itself

### Editor
Shot 4 is the single most persuasive two seconds in the video — a real newspaper, opened from the
app. Do not cut it for time.

---

## Segment 3 · Fastest isn't safest · 0:30

**Situation.** Motijheel to Kalabagan. Four ways to go.

### Start state
- [ ] `verify_video_scenario.py` prints **PASS** for `Motijheel → Kalabagan`
- [ ] If it fails, film `Gulshan 2 → Rampura` instead — same shots, different numbers
- [ ] Route mode open, start **Motijheel**, destination **Kalabagan**

### Shots
1. Enter route mode, set the two ends, calculate. Four routes draw.
2. Hold on the map — the lines are **different colours**.
3. **Recommended** tab: `100/100 · 24 min · 0 flags`, and the sentence
   *"Nothing flagged along this route. 5 minutes longer, avoids 10 flagged corridors."*
4. Tap the **last** option: `29/100 · 19 min · 8 flags`. The circle styles swap — faint becomes
   solid.
5. Scroll its flag list: Shahbagh intersection, Gulistan Zero Point, Science Lab, Elephant Road…
6. Tap back to **Recommended**. Hold on the sentence.

### On-screen text
> Four routes. One is clean.
> **24 min · nothing flagged**
> The fastest route — 19 min — passes **8** flagged places
> Five minutes is the price, and it says so

### Editor
Cut between shots 3 and 4 hard, twice if you like — the swap of solid/faint circles is the whole
argument and it reads instantly. Do not speed this segment up; the numbers need to be legible.

---

## Segment 4 · Nobody knows where I am · 0:45

**Situation.** She sets off, tells her sister, and then stops answering. Thirteen real minutes of
ladder, cut to forty-five seconds.

### Start state
- [ ] `CHECK_IN_WINDOW` is **1 minute** on this branch — ladder runs in ~4 min
- [ ] One emergency contact with a reachable inbox (3 exist, all with email)
- [ ] Inbox open on a laptop **in the same frame or as a cutaway**
- [ ] Mock location set up and following the route — no mock filtering exists, so fixes are accepted
- [ ] Push permission granted

### Shots
1. On the route card, tap the **2 min** deadline chip. The *Check in by* line jumps.
2. Under **If you go quiet, tell**, tap the contact. Hold on the line that appears:
   *"They get an email when you set off, when you arrive, and if you stop answering check-ins."*
3. **Start.** Navigation begins; the dot moves along the route (mock location).
4. Cutaway: the inbox. **Slate-grey** email — *"Nadia has started a journey"*. Scroll it: **no
   location anywhere.**
5. The dot stops moving. Hold.
6. The **journey card** changes its own title to **"Are you there yet?"** and grows an **I'm fine**
   button. Do not tap it.
7. Second nudge. Card reads **"Asked twice, still no answer."** and *"If this stays unanswered,
   `<name>` will be emailed."*
8. Cutaway: the **red** email — *"Nadia has not arrived and is not answering"*. Hold on the last
   line: **"You are the only person who has been told."**
9. Tap **I'm fine**. Red clears, back to *"On your way."*
10. The dot reaches the destination. Navigation ends by itself.
11. Cutaway: the **green** email — *"Nadia arrived safely"*.

### On-screen text
> Tell one person. Once.
> **Nothing shared while everything is fine** — no location in this email
> No answer → it asks
> Still no answer → **her sister is told where she was last**
> Nobody else. Ever.
> Arrived → one more email, and it's over

### Editor
- Film the **journey card**, not the lock-screen notification. `JG2.md` records the push banner as
  usually not drawn; the card is reliable and changing its own title is the better shot anyway.
- Speed the dot's travel to 4–8×. Title-card the waits: *4 minutes later*.
- Shots 8 and 9 back to back are the emotional beat — hold 8 longer than feels comfortable.

---

## Segment 5 · Something's wrong, right now · 0:25

**Situation.** A different evening. She is not going to type anything.

### Start state
- [ ] **Replace the hot words.** Both stored phrases are currently `Hello` — it will false-fire and
      it sounds like nothing. Profile → SOS hot words → delete both, add one distinctive phrase and
      practise saying it
- [ ] 3 emergency contacts with email are already registered
- [ ] Inbox open as a cutaway

### Shots
1. **Shake the phone.** The SOS flow starts.
2. The 10-second clip records — show the counter.
3. **"Uploading Evidence…"** → **"Alerting your contacts…"**
4. Cutaway: the SOS email. Her name, the location, the clip attached.
5. Quick cut: Home tab, press and hold the **SOS button**. Then Profile → SOS hot words, showing the
   phrase. Three triggers, three seconds.

### On-screen text
> Shake it. Say the phrase. Or press it.
> **10 seconds of video, then your contacts**
> Name · location · the clip
> 19 incidents on record — every one leaves a trail

### Editor
Speed the 10-second recording to ~3×, but keep the counter legible so it reads as real. Shot 5 is a
rapid three-way cut; don't linger.

---

## Segment 6 · Nobody will ever know · 0:35

**Situation.** She witnesses something. Reporting it officially means a Bangla General Diary at a
police station.

### Start state
- [ ] A staged photo ready that reliably produces a category with a *"Because …"* reason.
      Existing `assault` reports with photo + vision analysis are the proven path
- [ ] A report whose location resolves to a **verified** thana. The existing Agargaon report
      resolves to **Sher-e-Bangla Nagar Police Station** — verified, not one of the five legacy ones
- [ ] Internet up (cloud vision is ~3 s; the on-device path is ~9 s)

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
> Photograph it. The app reads the photo.
> **It describes what it sees — it does not accuse anyone**
> General Diary, drafted in Bangla, in the register's own form
> Nearest police station, worked out
> **You must read it to the end before you can approve it**
> Print it, or paste it into the police's own app

### Editor
Shot 7 is the beat of the segment. Film it slowly and do not speed it up — the disabled button
becoming enabled *because she scrolled* is the entire ethical argument, in two seconds.

---

## Close · 0:10

Back to the map, her report now a marker on it.

> One report changes nobody's route.
> It takes several, independently, before anything is published.
>
> **Meridian** — she still decides. She just isn't deciding blind.

---

## Pre-flight, both sessions

```
python backend/scripts/seed_risk_flags.py --fixture data/fixtures/video_scenario.json
python backend/scripts/verify_video_scenario.py
```

Then by hand:

- [ ] Hot words replaced (segment 5) — once, not per session
- [ ] Inbox open on a laptop, first email already marked *Not spam*
- [ ] Mock location app ready with the Motijheel → Kalabagan track
- [ ] Phone on Do Not Disturb except Meridian
- [ ] One `live-%` flag confirmed present, and you know which one you are tapping
