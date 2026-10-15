# Guardian — the app acts without being asked

**Written for:** Arafat, running every step on his own phone, in front of judges.
**Ran on:** Vivo V2344, Android 14, development build · **By:** Arafat · **Date:** 2026-10-11, Parts 2–3 · **Part 1 (zone alerts):** 2026-10-15, steps 1–5 · **Takes:** ~15 min once the build is installed

**All three features are now verified on a device.** Voice SOS and Shake SOS end to end on 11 Oct — trigger, countdown, camera, location, email to contacts. **Zone alerts verified 15 Oct, steps 1–5**, against a flag seeded with `scripts/seed_flag_here.py` at the test location: every risk flag from the pipeline is in Dhaka and the testing happened from Jashore, 142 km away, so a seeded flag was the only way to run Part 1 at all. Android's `GeofencingClient` does the detection and cannot tell a seeded row from a pipeline one, so the app's whole path ran for real. **Step 6 — the outdoor pocket walk — is still unrun**, so the +250 m early-warning margin is unmeasured at walking pace. See *Step 2*.

> **Everything in this walkthrough is done on the phone.** No terminal, no curl,
> no Docker, no SQL. The only command you run is the one that builds and installs
> the app.

## The three features

| | What it does | Works with the app closed? |
|---|---|---|
| **Risk zone alerts** | Background GPS. A notification as you approach a flagged road | ✅ **Yes** — the OS does the watching |
| **Voice SOS** | You shout a saved hot word → SOS fires automatically | ❌ No — app must be open |
| **Shake SOS** | You shake the phone hard → SOS fires automatically | ❌ No — app must be open |

An SOS means: a short video is recorded, your location is taken, and both go to
your emergency contacts. No tapping.

All three live on **one screen**: Profile → **Guardian**.

### The one limit, stated before you test anything

**Voice SOS cannot run with the app closed, and nor can Shake SOS.** That is
Android, not this code: microphone and sensor access for apps that are not in the
foreground has been restricted since Android 9, and `SpeechRecognizer` — which
every React Native speech library wraps — simply stops returning results. Holding
the microphone with the app closed needs a **foreground service** of type
`microphone`: a permanent notification plus a native service class. No Expo module
provides one, so it is a Kotlin-and-config-plugin job, not a JavaScript one.

What you get is: armed from any screen, surviving tab switches, working with the
screen on and Meridian in front. **Zone alerts are the one that works from a
pocket**, and they are the one that matters most for the demo, because the OS is
doing the watching.

If a judge asks, that is the honest answer, and it is a better answer than
pretending.

---

## Before you start

### 1. Install the development build

Voice SOS needs a native module and zone alerts need background location. Expo Go
can do neither. One build covers both:

```powershell
cd D:\Meridian\frontend
npx expo prebuild --clean
npx expo run:android
```

> `prebuild --clean` regenerates `android/`, which is committed on this project —
> check `git diff --stat android/` afterwards.

**In Expo Go the app still opens**, and Guardian explains that Voice SOS needs the
development build. That is deliberate: it used to crash the whole app at boot.

### 2. Add an emergency contact

Profile → **Emergency Contacts** → add one with a real email address you can
check.

**Without this an SOS sends to nobody** and steps 6 and 9 prove much less than
they look.

### 3. Add a hot word

Profile → **SOS Hot Words** → type `help me` → **Add Hot Word**.

Try `sos` first. **Expect it to be refused**: *"Too short — use at least 4
characters. Very short phrases are set off by ordinary speech and background
noise."* Three characters is not a safety margin — "bus", "box" and "bas" are one
phoneme apart and all plausible on a Dhaka street.

Then try adding `help me now`. **Expect:** *"\"help me\" is already in this
phrase, so it would trigger first. This one would never be used."* Worth showing:
the user's instinct is that more phrases means more coverage, and it does not.

### 4. Make sure there are flags to geofence

Open the **Map**. You need pins. If the map is empty there is nothing to build a
zone from, and step 2 will correctly report zero.

---

## Part 1 — Risk zone alerts

### Step 1 · Turn it on and grant "all the time"

Profile → **Guardian** → **Risk zone alerts** → switch on **Warn me as I
approach**.

Android will ask for location. Then it will ask again, differently.

**Expect a dialog** saying zone alerts need location access *"all the time"*, with
an **Open settings** button. Tap it → Permissions → Location → **Allow all the
time**. Come back and switch on again.

> Android 11+ does **not** offer "all the time" in an in-app dialog at all. The
> request returns denied immediately and the only route is the settings screen.
> That is why the app sends you there instead of asking twice.

### Step 2 · Read the status block

**First: are you near any flagged roads?** Every flag in this project's data is in
**Dhaka**. The app only fetches flags within about **19 km** of you, so if you are
anywhere else the honest answer is zero and the status block says so.

**If you are in Dhaka, expect:**

| | |
|---|---|
| System monitoring | **Active** |
| Location permission | **All the time** |
| Zones being watched | **a number above 0** |

**If you are not in Dhaka, expect:**

| | |
|---|---|
| System monitoring | **Idle — nothing nearby to watch** |
| Location permission | **All the time** |
| Zones being watched | **0** |

with the note *"No live risk flag within about 19 km of you… This is working
correctly."*

**Both are passes.** The second is not a failure and not a half-state: with no
qualifying flags there is no region set, and the app deliberately does **not**
hand the OS an empty one — some Android versions treat that as an error. So
nothing is being monitored, and saying "Active" would be a lie.

Only **Location permission** must be green in both cases. That is the one thing
this step actually gates.

❌ **A real failure looks like:** permission green, you are in Dhaka, the Map has
pins, and the count is still 0. Tap **Refresh zones**; if it stays 0, that is a
bug worth reporting.

### What this means for testing away from Dhaka

Geofencing needs a real flag near a real you. From outside Dhaka, steps 3–6
cannot run — there is nothing registered to cross, and **Test the nearest zone
now** reads the same empty list and will tell you so.

Three ways forward:

1. **Test in Dhaka.** Everything works with no further setup. If the demo is in
   Dhaka, this is also the only configuration that matters.
2. **Seed a flag where you are.** One command, then **Refresh zones**:

   ```powershell
   docker compose exec api python scripts/seed_flag_here.py --lat <your lat> --lon <your lon> --clear
   ```

   Get your coordinates from the Map screen, or just use your city centre — the
   flag only has to be within ~19 km for the fetch, and the geofence it creates
   is the flag's 300 m radius plus a 250 m approach ring.

   Remove it afterwards:

   ```powershell
   docker compose exec api python scripts/seed_flag_here.py --clear-only
   ```

   It writes a real flag through the real invariants — statement from
   `framing.py`, `expires_at` derived by the trigger, `unconfirmed` with one
   source. The `devhere-` key prefix keeps it separate from the `seed-` fixture
   rows, so neither cleanup touches the other.

   ⚠️ **Filing a crime report in the app does not do this.** `crime_reports` and
   `risk_flags` are different tables with no pipeline between them, deliberately:
   a single unverified report must not become a published risk claim. The Map
   draws both as pins, which makes them look interchangeable, and they are not.
   User reports feeding the risk surface is backlog **B13 / B11a**.
3. **Do Parts 2 and 3 first.** Voice SOS and Shake SOS need no flags at all and
   are the two features that need calibrating on your handset. They are
   completely testable from Jashore, or anywhere.

**Option 3 is the one to take now** — calibration is the step that must not be
done for the first time on demo day, and it does not depend on where you are.

### Step 3 · Prove the alert, indoors

Tap **Test the nearest zone now**.

**Expect a notification on your phone**, titled **"Risk zone ahead"**, with the
flag's own wording — something like *"Road blocked near Jatrabari. Confirmed by 3
independent sources. You are approaching this area."*

Read that body to the judges. Three things in it are deliberate:

- The road sentence is **the server's**, forwarded word for word. The phone never
  writes a sentence about a place — concept document §9, and there is a test that
  deletes the forwarded sentence and checks the rest is byte-identical for every
  zone.
- **No "dangerous", no "unsafe", no "avoid".** The product says what a road is
  doing, never what a place is.
- The **source count** is there, because an unconfirmed single-source report and
  three independent ones are different claims.

This runs the real path — same zones, same debounce, same notification. Only "you
moved" is simulated, because a real crossing needs you to physically walk through
a boundary several hundred metres wide.

### Step 4 · Prove the debounce

Tap **Test the nearest zone now** again, immediately.

**Expect: "Nothing sent"** — *"Suppressed: this zone already alerted in the last 6
hours. That is the debounce working."*

This is a pass, and it is the thing that stops the feature being the reason
someone turns notifications off. Android reports a crossing **every** time you
cross the boundary, and walking to a shop and back is two crossings.

### Step 5 · Read the history

Scroll to **Zone alert history**.

**Expect two entries**: the first with a green dot and "notified", the second grey
and "suppressed: test crossing — already alerted…".

Suppressed crossings are logged on purpose. "I walked past and got nothing" has
four possible causes, and without this there is no way to tell *the debounce
worked* from *it never fired*.

### Step 6 · The real thing, outdoors (optional, and the best demo)

With zone alerts on, **lock the phone, put it in your pocket, and walk toward a
flagged road** on the map.

**Expect the phone to buzz before you get there** — the zone is watched at the
flag's radius **plus 250 m**, which on foot is three or four minutes of warning,
enough to turn down a different street. That margin is the entire point: alerting
you as you enter tells you something you are about to see for yourself.

Meridian does not need to be open.

---

## Part 2 — Voice SOS

### Step 7 · Arm it and watch the meter

Guardian → **Voice SOS** → switch on **Listen for my phrase**. Grant the
microphone.

**Expect:**
- the switch turns red and the label becomes **Listening on this device**;
- the **Loudness now** bar starts moving;
- a **Heard** box appears, saying *"Say something…"*.

Say "the weather is fine today". **Expect the Heard box to fill in with what you
said**, and no trigger.

That box is how you show the recogniser works at all — accents and street noise
matter — and that the transcript stays on the phone. Nothing is uploaded.

❌ **If it switches itself off** with *"This phone cannot recognise speech without
sending audio to a server…"* — that is a **pass**, not a failure. The app refuses
rather than quietly streaming your microphone to Google. Shake SOS still works;
use that for the demo and say why.

❌ **If it says no offline language pack is installed**, tap **Install an offline
language pack**, finish Android's dialog, come back and arm again.

### Step 8 · Calibrate the shout threshold — do this before the judges arrive

This is the step that makes or breaks the demo, because **the loudness scale is
different on every phone**. It is Android's RMS value from −2 to 10, not decibels,
and the microphone, the case and your grip all move it.

1. Armed, say your hot word **at normal volume**. Watch the **peak** figure.
2. Now **shout it**. Watch the peak again.
3. Set **Shout threshold** with − / + to sit **between the two**.

**Expect, speaking normally:** *"Heard \"help me\" but not loudly enough (3.4 of
6.0). Shout to trigger SOS."*

Show a judge that message. It is the "only by shouting" requirement working: a hot
word said conversationally is somebody talking about the app, not somebody in
trouble — and this screen's whole subject is a phrase people say out loud while
setting it up.

### Step 9 · Shout it, and let the SOS go

Make sure an emergency contact is saved. Then **shout "help me"**.

**Expect, in order:**
1. listening **stops** — the microphone closes the moment a phrase matches;
2. a single countdown dialog: **"Sending SOS"** with a large number counting
   5→1, saying *You shouted "help me" (loudness 7.4)*, with **Cancel** and
   **Send now**;
3. if you do nothing, the camera opens by itself and **starts recording**;
4. the progress bar runs: *Uploading evidence* → *Alerting your contacts*;
5. your contact gets an email with the location, and the video **if this phone
   can record one** — see *Video capture* below.

Tap **Cancel** on the first run to see the window work, then do it again and let
it through.

> The five seconds are not a tap you have to make — leaving it alone sends. It
> exists because both automatic triggers are heuristics: a recogniser can mishear
> and a phone can be dropped, and every false positive tells somebody's family
> they are in danger. Turn it off in **When something triggers** once you trust
> your thresholds; the SOS then fires instantly.

### Step 10 · It works on any screen

Arm Voice SOS, then go to the **Map** tab. Shout your phrase.

**Expect the countdown to appear over the map.**

There is exactly one recogniser and one SOS controller for the whole app. Before
this they lived inside screens, which meant a shouted phrase only worked on the
screen that happened to be open — and, because the tab navigator keeps screens
alive, a single shake fired **two** SOS alerts once you had visited two tabs.

---

## Part 3 — Shake SOS

### Step 11 · Calibrate against the live reading

Guardian → **Shake SOS**.

**Expect the "Shake force now" bar to be moving already** — it reads whenever this
screen is open, armed or not, because you cannot calibrate a threshold you have to
arm first.

1. Hold the phone still. **Expect about 1.0g** — that is gravity.
2. Shake it as hard as you would in an emergency. Watch the peak.
3. Set **Shake threshold** below that peak but well above 1.0.

> The inherited code disagreed with its own comment here — 3.5g in the comment,
> 6.0g in the code — and `IMPLEMENTATION_PLAN.md` logged it for B5 asking for it
> to be settled "with a measurement". This slider plus the live reading *is* the
> measurement, taken on the phone it will run on. 6.0g is the starting point
> because that is the value that had actually been used on a device; 3.5g is
> reachable by putting a phone down firmly.

### Step 12 · Shake it

Switch on **Shake hard to call for help**, then shake.

**Expect the same countdown**, saying *The phone was shaken hard (7.2g)* — then
the camera, then the send.

Shake again immediately. **Expect nothing**: there is a 20-second cooldown,
because one violent shake is a dozen threshold crossings over about a second and
each of them would otherwise try to open the camera.

---

## What to show a judge, in order

1. **Guardian screen** — three protections, one place, each with a live meter.
2. **Shout the phrase at normal volume** → refused, with the numbers on screen.
3. **Shout it properly** → countdown → camera → email arrives. Hands never touch
   the phone.
4. **Shake it** → the same thing, a different trigger.
5. **Test the nearest zone** → the notification, and read its wording out: the
   road, the source count, and nothing about the place being dangerous.
6. **Tap it again** → suppressed, and explain why that is the feature.

If you have five minutes outdoors, swap 5 for the real thing: lock the phone, walk
toward a flagged road, and let it buzz in your pocket.

## ⚠️ Video capture — known to fail on some Android hardware

On the phone this was verified on (**Vivo V2344**, Unisoc `ums9230`), the camera
**never records**, and the SOS correctly sends **location only**:

> **Sending without video**
> The camera could not record on this phone, so your location is being sent to
> your emergency contacts without a video.

The alert still goes out. This is a deliberate degradation, not a failure — and
before it was built that way, a camera failure killed the whole SOS.

**It is the device, not the app.** Measured from `adb shell logcat`, at every
quality the API offers (`Quality.LOWEST`, `Quality.SD`, and the 1080p default):

- the recording runs its **full ten seconds**
- audio is captured throughout
- the encoder is configured correctly (`c2.unisoc.avc.encoder`, 1080×1920 @ 30fps)
- `Recorder` logs *"Cached audio data while we wait for video keyframe before
  starting muxer"* **43 times a second for the entire duration**

Not one video frame ever reaches CameraX's `VideoCapture` surface. Audio works;
video never arrives. The encoder only emits its format *after* being stopped,
because its input was starved the whole time.

The remaining lever is CameraX's `PreviewView` implementation mode — Google's
documented workaround for this class of device bug is `TEXTURE_VIEW` instead of
`SurfaceView`, and the log confirms expo-camera uses `SurfaceViewImpl`.
**expo-camera does not expose it as a prop**, so changing it means patching
native Kotlin. Not worth doing before the finale.

**Try another Android handset.** Video is expected to work on most, and that
would confirm this is one device rather than the code. Until then, the honest
claim is: *location to emergency contacts in seconds, plus a video clip where
the hardware supports it.*

### ✅ Confirmed 2026-10-15: it is the device

SOS was run on a **second Android phone** and video **captured, uploaded and
arrived attached to the alert email**. That closes defect 53: the starvation above
is **Unisoc `ums9230` driver behaviour**, upstream of this app.

Everything in this section still describes the Vivo exactly and is kept as the
record. Two things change:

- **The `TEXTURE_VIEW` native patch will not be written.** Patching expo-camera to
  work around one SoC buys one handset.
- **The location-only degradation is the permanent design**, not a stopgap for an
  open defect. It is what lets the alert go out on hardware that cannot record,
  and it is the behaviour to demonstrate deliberately rather than apologise for.

⚠️ **Keep the claim conditional and demo on the phone that works.** *"Location to
emergency contacts in seconds, plus a video clip where the hardware supports it"*
is still the accurate sentence — one confirmed handset in the fleet cannot record,
so promising video unconditionally would be promising something this project has
watched fail.

## Known limits — say these rather than be caught by them

- **Voice and shake need the app open.** Android restriction, not a bug. Zone
  alerts do not.
- **Zone alerts need Android to grant "all the time"**, which only its settings
  screen offers.
- **Geofences are dropped on reboot.** Android does that to every app. Meridian
  re-registers them next time you open it — so after restarting the phone, open
  the app once.
- **The platform watches at most 20 zones on iOS and 100 on Android.** Over the
  limit the extras are dropped *silently*, so the list is capped deliberately and
  Guardian shows the overflow count.
- **Chronic/historical flags are never geofenced.** By design — see step 2.
- **Bangla voice depends on the handset.** The matcher handles Bangla correctly;
  whether Google ships an on-device Bengali pack for your phone is the phone's
  business. Check in step 7 before promising it.
- **iOS is untested.** The code paths exist. Do not claim it works.
- **Video capture may be unavailable** — see the section above. The SOS sends
  location only, and says so.
- **A 20-second cooldown between automatic triggers.** One violent shake is a
  dozen threshold crossings in a second, so without it each would open the
  camera. If a trigger seems ignored, the Guardian screen shows
  *"Ignored — Ns left of the 20s cooldown"*.

## Sign-off

- [x] Steps 1–2 (zone alerts on; **Location permission green**, and either zones > 0 in Dhaka or "Idle — nothing nearby" elsewhere) — ✅ 15 Oct
- [x] Steps 3–5 (test alert arrives, debounce suppresses, history shows both) — **needs a flag within ~19 km**; ✅ 15 Oct against a seeded flag
- [ ] Step 6 (a real crossing in a pocket) — optional, **still unrun**; this is the only thing that measures the +250 m margin at walking pace
- [ ] Steps 7–8 (listening, meter moves, threshold calibrated)
- [ ] Step 9 (normal voice refused, shout triggers, SOS email arrives)
- [ ] Step 10 (works from the Map tab)
- [ ] Steps 11–12 (shake calibrated, triggers, cooldown holds)
- [ ] Noted the handset, the Android version, and the two thresholds you settled on

**Verified by:** Arafat
**Date:** 2026-10-11 (Parts 2–3) · 2026-10-15 (Part 1, steps 1–5, seeded flag)
**Phone / Android version:** Vivo V2344 / Android 14 (Unisoc ums9230)
**Shout threshold:** _record yours_ **Shake threshold:** _record yours_
**Video capture:** ❌ unavailable on this handset — SOS sends location only

**Second handset, 2026-10-15 — defect 53 closed.** SOS run on another Android phone:
**video captured, uploaded and delivered attached to the alert email.** Two devices is
what it took to attribute the Vivo failure to the Unisoc `ums9230` rather than to this
app. ⚠️ **The handset was not recorded here.** Fill in make / model / Android version
the next time you have it to hand — a device-compatibility claim is only as good as the
device list behind it, and right now that list is one phone that works and one that does
not.
