# B6a — Push notifications: a flag on the map becomes a buzz in a pocket

> ## ⚠️ SUPERSEDED IN PART — read `GUARDIAN.md` first
>
> On 11 Oct the two features were **redefined by the owner**, and the new
> definitions are what the product needs:
>
> * *"push notification"* means **geofencing** — background GPS, and a
>   notification as the user approaches a risk zone. Not a server-initiated push.
> * *"hot words"* means an **always-listening shout detector** that fires SOS
>   automatically, plus **shake-to-SOS**.
>
> Both are implemented and are tested entirely from the phone in
> **[`GUARDIAN.md`](GUARDIAN.md)**, which needs no terminal at all. Use that.
>
> This file is kept because the machinery it describes is real, still present and
> still green — the server-side alert dispatcher, the rate cap, the framing
> invariants and the alert history. It is just not the feature that was asked
> for, and **`PUSH_ENABLED` stays `false`**, so none of its account setup is
> needed.


**Written for:** Arafat, running the steps on his own phone.
**Ran on:** _not yet — awaiting device verification_ · **By:** — · **Date:** — · **Takes:** ~15 min for Part 1, ~40 min for Part 2 (mostly waiting on a build)

> **Read this before anything else.**
>
> **Expo Go cannot receive push notifications on Android.** Expo removed that
> capability from Expo Go in SDK 53, and every D01–D09 walkthrough on this
> project ran on Expo Go. There is no workaround and no flag to set: a
> development build is required, and Part 2 is how you make one.
>
> That is why this walkthrough is in two parts. **Part 1 verifies everything
> except delivery, and it runs on Expo Go today** — the decision pipeline, the
> rate cap, the framing, the preferences, the ledger. **Part 2 is the last
> hop**, and it needs an Expo account, a Firebase project, and a build.
>
> Part 1 is not a consolation prize. The cap, the categories and the alert text
> are where the product commitments live; delivery is plumbing that either works
> or says why not.

## What this proves

**S16, and the half of B6a that is not geofencing.** A flag published by an
agent reaches a specific person's phone, carrying its mobility statement and its
source count — and it does so **at most three times an hour**, because alert
fatigue is a named risk in the concept document (§12) and a safety app people
have muted is worse than no safety app.

Four things worth asking about:

- **The rate cap is real and tested**, not a documented intention.
  `MAX_ALERTS_PER_USER_PER_HOUR=3`, enforced in one pure function, with 33 tests
  on it. Phase 3's exit criteria ask for "alert rate cap verified by test"; that
  line is `test_the_fourth_alert_in_an_hour_is_refused`.
- **A notification says no more about a place than the map does.** The body is
  the server-framed `mobility_statement`, forwarded verbatim, plus fixed
  boilerplate. An invariant test composes an alert for every combination the
  system can produce, deletes the statement, and asserts the remainder is
  byte-identical — so no f-string about a place can creep in.
- **Chronic flags do not interrupt.** Off by default, because a historical
  average with a 2 km radius that never expires would push "this area has a
  history" every time you left the house. That is the stale-red-zones product
  demo beat 5 exists to disclaim.
- **The alert history is user-visible.** A rate cap and a severity floor are
  invisible mechanisms that decide whether somebody is warned. Without a way to
  read the ledger back, "why didn't I get an alert?" has no answer short of a
  SQL console.

## What this does NOT do, and you should say so out loud

**It cannot warn you as you walk toward something.** The server knows where your
phone was **the last time you opened the app**, because `push_devices` holds one
overwritten point and there is no background location — that is **S17**, the
other half of B6a, and it is not built. A position older than six hours is not
used at all.

So the honest sentence is *"Meridian tells you about something near where you
last were"*, not *"Meridian warns you as you approach"*. The preferences screen
says this in those words, and the notification body itself ends with "Near where
the app last had your location." If anyone asks for the geofencing demo, that is
S17 and it is on the backlog.

---

## Preconditions

1. **The stack is up and the migration is applied.**

   ```powershell
   docker compose ps api worker
   docker compose exec api python scripts/migrate.py status
   ```

   `api` and `worker` read `Up`. `20261010180000__push_devices_and_alerts` reads
   `applied`.

   > ⚠️ `20261010120000__gd_drafts_and_profile` and
   > `20261010160000__gd_profiles_on_auth_users` will read **pending**. That is
   > pre-existing and not yours: those tables exist in the database (applied by
   > hand through the Supabase editor during D08) and only the ledger row is
   > missing. Do not run `migrate.py up` to "fix" it — that applies all pending
   > migrations. It is noted in PROGRESS.md.

2. **There are live flags to be alerted about.** The dispatcher alerts on what is
   near a device, so if the surface is empty nothing will happen and that will
   look like a bug.

   ```powershell
   docker compose exec api python -c "import asyncio;from sqlalchemy import text;from app.core.database import engine;asyncio.run((lambda: None)())" 2>$null
   curl.exe -s "http://localhost:8000/api/v1/risk/flags?bbox=90.33,23.70,90.45,23.82"
   ```

   You want at least one non-chronic flag with `severity_now` ≥ 40. If there are
   none, seed:

   ```powershell
   docker compose exec api python scripts/seed_risk_flags.py
   ```

3. **Signed in on the phone**, same Wi-Fi as the laptop, app reloaded. The
   startup path changed (`NotificationService.initialize()` was commented out and
   is now live) so a reload is not optional.

---

# Part 1 — Everything except delivery · runs on Expo Go

## Step 1 · The Alerts screen exists and tells the truth

Profile → **Alerts**.

**Expect:** the screen loads. At the top, an amber box saying **"Expo Go cannot
receive push notifications on Android. Install the development build to test
alerts."**

That box is the feature working, not failing. It is `blockingPushProblem()`
reporting the most fundamental unsatisfied prerequisite first — and it outranks
the permission prompt deliberately, because granting permission in Expo Go
changes nothing.

Below it, a blue box: **"Alerts are based on where the app last had your
location — Meridian does not track you in the background…"** and **"A position
older than 6 hours is not used."** Both numbers come from the server, not from
the TypeScript.

❌ **If the screen is blank or errors:** the API is unreachable from the phone.
Check `API_BASE_URL` in `src/constants/app.constants.ts` is your laptop's LAN IP,
not `localhost`.

## Step 2 · The categories, and the one that is off

**Expect** three switches:

| | |
|---|---|
| **Happening now** | on |
| **Expected later today** | on |
| **Historical patterns** | **off** |

Toggle **Historical patterns** on. **Expect a confirmation dialog** — "These are
long-term patterns, not events happening now… they share your hourly alert limit
with alerts about live incidents."

Cancel it. The switch stays off.

That dialog is the point of the step. The switch is honoured if you turn it on —
an earlier draft of the policy refused chronic alerts *twice*, once on the
category check and again on a dedicated gate, which made the second gate dead
code and the switch a lie. It is one gate now, and a test pins it.

## Step 3 · The cap, stated as a promise

Scroll to the green box.

**Expect:** **"At most 3 alerts per hour, whatever happens. You can ask for
fewer, never more."**

The number is `MAX_ALERTS_PER_USER_PER_HOUR` read from the server. "Never more"
is enforced by `AlertPreferences.effective_cap`, which takes the **min** of the
user's value and the system's — so a client bug writing `max_per_hour: 999`
cannot switch the cap off.

## Step 4 · Preferences round-trip

Set the severity floor to **Serious only**. Leave the screen, come back.

**Expect:** still **Serious only**.

```powershell
# What the server actually stored
docker compose exec api python -c @'
import asyncio, logging; logging.disable(logging.INFO)
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
async def main():
    async with AsyncSessionLocal() as db:
        for r in (await db.execute(text("select user_id, corridor_alerts, scheduled_alerts, chronic_alerts, min_severity, max_per_hour from public.notification_preferences"))):
            print(r)
    await engine.dispose()
asyncio.run(main())
'@
```

**Expect** one row with `min_severity = 60.0`.

## Step 5 · The device registered, and the server knows where it is

```powershell
docker compose exec api python -c @'
import asyncio, logging; logging.disable(logging.INFO)
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
async def main():
    async with AsyncSessionLocal() as db:
        for r in (await db.execute(text("""
            select platform, app_version,
                   extensions.ST_Y(last_location::extensions.geometry) lat,
                   extensions.ST_X(last_location::extensions.geometry) lon,
                   last_location_at, disabled_at,
                   left(expo_push_token, 24) token
            from public.push_devices"""))):
            print(r)
    await engine.dispose()
asyncio.run(main())
'@
```

**On Expo Go, expect zero rows.** No project id and no Expo Go push support means
no token, and `registerDevice` returns false rather than registering a row it
cannot deliver to. That is correct, and it is why Part 2 exists.

**On a development build (Part 2), expect one row** with a token starting
`ExponentPushToken[`, your coordinates, and `disabled_at` null.

## Step 6 · The dispatcher decides, with the transport stubbed

This is the step that proves the pipeline. `PUSH_ENABLED=false`, so
`default_transport` returns the null transport: the agent runs, applies every
policy gate, writes the ledger, and logs what it *would* have sent.

```powershell
docker compose exec api python -m app.agents run alert_dispatch
```

**Expect** an `AgentResult` with `items_in` = the number of located devices and
`metrics` carrying the refusal breakdown — something like:

```
status=ok items_in=1 items_out=1
metrics: devices=1 candidates=4 sent=1 failed=0
         already_sent=0 below_min_severity=2 category_muted=1 rate_capped=0 quiet_hours=0
```

`candidates=4 sent=1` with reasons for the other three is the whole design: a
sweep that sends nothing is distinguishable from a broken one, which "0 sent"
alone never is.

Then read what it composed:

```powershell
docker compose logs api --tail 40 | Select-String "would push"
```

**Expect** a line like:

```
[PUSH_ENABLED=false] would push to ExponentPushToken[...]: On your route now /
  Road blocked near Jatrabari. Confirmed by 3 independent sources.
  Near where the app last had your location.
```

The label in brackets is the reason nothing was delivered, and there are two:
`PUSH_ENABLED=false` means Part 2 is not done, `dry-run` means you passed
`--dry-run`. They used to share one label, which sent you looking for a flag you
had not passed.

Read that body carefully. It is **the server's framed statement, forwarded
verbatim**, plus two fixed clauses. No severity adjective, no "urgent", no place
name composed here, no number out of a 0–10 scale.

> ⚠️ On Expo Go there are no devices, so this reads `devices=0 candidates=0`.
> That is not a failure — it is step 5's finding restated. Come back to this step
> after Part 2, or create a device row by hand if you want to see the pipeline
> run before building:
>
> ```powershell
> docker compose exec api python -c @'
> import asyncio, logging; logging.disable(logging.INFO)
> from datetime import UTC, datetime
> from sqlalchemy import text
> from app.alerts.service import register_device
> from app.core.database import AsyncSessionLocal, engine
> async def main():
>     async with AsyncSessionLocal() as db:
>         uid = (await db.execute(text("select id from auth.users order by created_at limit 1"))).scalar()
>         await register_device(db, user_id=uid, expo_push_token="ExponentPushToken[FAKE-FOR-DRY-RUN]",
>                               platform="android", lat=23.7104, lon=90.4074, now=datetime.now(UTC))
>         print("fake device registered for", uid)
>     await engine.dispose()
> asyncio.run(main())
> '@
> ```
>
> Delete it afterwards:
> `delete from public.push_devices where expo_push_token like '%FAKE-FOR-DRY-RUN%';`

## Step 7 · The same flag never interrupts twice

Run the dispatcher again, immediately.

```powershell
docker compose exec api python -m app.agents run alert_dispatch
```

**Expect** `sent=0` and `already_sent` incremented in `metrics`.

Two things enforce this and both matter: the policy layer's `already_sent` gate,
and `UNIQUE (user_id, flag_id)` on `sent_alerts`. The first stops a sweep
deciding to send; the second stops two workers deciding at the same moment.

## Step 8 · The cap holds

Run it five more times.

```powershell
1..5 | ForEach-Object { docker compose exec api python -m app.agents run alert_dispatch }
```

Then count what the ledger holds for the last hour:

```powershell
docker compose exec api python -c @'
import asyncio, logging; logging.disable(logging.INFO)
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
async def main():
    async with AsyncSessionLocal() as db:
        for r in (await db.execute(text("""
            select user_id, count(*) n
            from public.sent_alerts
            where sent_at > now() - interval '1 hour'
            group by user_id"""))):
            print(r)
    await engine.dispose()
asyncio.run(main())
'@
```

**Expect `n` ≤ 3 for every user.** Not "roughly three" — the cap is a hard
boundary and the test for it asserts the fourth is refused.

If you want to watch it bite rather than infer it, seed more flags near the
device first; `metrics` will then show `rate_capped` climbing.

## Step 9 · The alert history explains itself

Back on the phone: Profile → **Alerts** → pull to refresh → scroll to **Recent
alerts**.

**Expect** the alerts from steps 6–8, newest first, each with a green dot
(`accepted` — the null transport reports success), the body as it was sent, and
the timestamp and category underneath.

**This is the step that makes the invisible checkable.** The body shown here is
the text stored at send time, not re-derived from the flag — the flag decays and
may later be confirmed, so re-deriving would show the alert as it would read
*today* rather than as it was sent.

## Step 10 · The test endpoint respects the cap

Tap **Send me a test alert**.

**Expect** one of two dialogs, and *both are passes*:

- **"Test alert sent"** / "Queued with Expo." — if you are under the cap and have
  a registered device.
- **"Nothing sent"** / "Rate cap reached: 3 of 3 alerts in the last hour. This is
  the cap working, not a failure." — if steps 6–8 used your allowance.

The second is the interesting one. A test endpoint exempt from the cap would be a
way to demonstrate the system while bypassing its most important rule, so it is
not exempt — and the message says so rather than reporting a bare failure.

On Expo Go with no device you will get **"No registered device."** Also correct.

## Step 11 · Quiet hours are Dhaka hours

Turn on **Silence 22:00 – 07:00**. Then ask the policy directly, at an instant
inside that window:

```powershell
docker compose exec api python -c @'
from datetime import UTC, datetime
from app.alerts.policy import AlertPreferences, dhaka_hour, in_quiet_hours
night = datetime(2026, 10, 10, 20, 0, tzinfo=UTC)   # 20:00 UTC
print("UTC hour  :", night.hour)
print("Dhaka hour:", dhaka_hour(night))
print("in 22->7  :", in_quiet_hours(dhaka_hour(night), 22, 7))
'@
```

**Expect:**

```
UTC hour  : 20
Dhaka hour: 2
in 22->7  : True
```

Six hours of difference, which is the whole night. If quiet hours were measured
on the UTC clock, somebody who silenced 22:00–07:00 would be alerted until 04:00
local — and the bug would be invisible to anyone testing during the day.

Turn quiet hours back off before Part 2, or the test alert will be suppressed.

---

# Part 2 — Real delivery · needs an account, a build, and about 40 minutes

Everything below is **account setup, not code**. It is here rather than in a
README because it is a prerequisite nobody can infer, and because three of its
four failure modes are silent.

## A. Create the Expo project

```powershell
cd D:\Meridian\frontend
npx eas-cli@latest login          # or: npx eas-cli@latest whoami
npx eas-cli@latest init
```

`init` writes `extra.eas.projectId` into `app.json`. **Check it did:**

```powershell
Select-String -Path app.json -Pattern projectId
```

Copy that id into `backend/.env`:

```
EXPO_PROJECT_ID=<the id from app.json>
```

> It has to be the **same** id on both sides. A token issued against one project
> and pushed from another is accepted by Expo and then never delivered — no
> error, nothing in any log. `GET /api/v1/notifications/config` returns both so
> you can compare them.

## B. Firebase, for Android delivery

Expo's push service hands Android notifications to FCM, so FCM has to know about
the app.

> ⚠️ **One Firebase project for the team, not one each.** Expo holds a single FCM
> V1 service-account key per Expo project, and `app.json`'s `owner` is
> `warfather0991` — so the key that sends is from **that** account's Firebase
> project. A `google-services.json` downloaded from a second Firebase project
> carries a different sender ID, and every send is then rejected per-device as
> `MismatchSenderId`. If somebody on the team has already done section B, do not
> repeat it: ask them for their `google-services.json` and skip to step 5.

1. <https://console.firebase.google.com> → **Add project** (any name).
2. Inside it: **Add app → Android**. Package name **must be exactly**
   `com.Meridian.app` — it is in `app.json` under `android.package`, and a
   mismatch here is the `MismatchSenderId` rejection.
3. Download **`google-services.json`** and put it at
   `D:\Meridian\frontend\google-services.json`.
4. Nothing to do: `app.json` already points at it, under `expo.android`:

   ```json
   "googleServicesFile": "./google-services.json"
   ```

   > This step used to say the opposite — "it is **not** already in `app.json`,
   > on purpose" — because a pointer at a file that is not there does not
   > degrade the Android build, it kills it (`ENOENT ... × Prebuild failed`). The
   > pointer was committed anyway in JG2, and since the file itself is
   > gitignored, that is exactly what happened on the second machine: a merged
   > `develop` that could not build at all.
   >
   > `frontend/app.config.js` now resolves that tension instead of this
   > instruction doing it: the pointer is kept when the file exists and dropped
   > with a loud warning when it does not. So the build works before you do
   > section B, picks FCM up the moment you finish it, and no longer depends on
   > anyone editing `app.json` by hand. `frontend/app.config.test.js` pins both
   > halves.

5. Firebase Console → ⚙ **Project settings → Service accounts → Generate new
   private key**. Save the JSON somewhere outside the repo.
6. Upload it to Expo:

   ```powershell
   npx eas-cli@latest credentials
   ```

   Choose **Android** → your profile → **Google Service Account** → **Manage your
   Google Service Account Key for Push Notifications (FCM V1)** → upload the file
   from step 5.

## C. Build and install the development build

```powershell
.\scripts\run.ps1
```

That is the whole step. `run.ps1` keeps a stamp of `sha256(app.json +
package.json)` at `frontend/android/.meridian-build-stamp`, and A and B above both
change `app.json` -- so it will report *"app.json or package.json changed since
the last build"* and run `expo prebuild` then `expo run:android` itself, in that
order. The order is the point: `expo run:android` only prebuilds when `android/`
is **missing**, so running it alone against an existing folder compiles the old
manifest and leaves you with a stamp claiming the phone matches an `app.json` it
does not. Needs the phone in USB-debugging mode; 2-6 minutes cold.

If you would rather not build locally:

```powershell
npx eas-cli@latest build --platform android --profile development
```

That produces an installable APK in the cloud, and needs an `eas.json` with a
`development` profile, which this project does not have yet.

> **`android/` is gitignored, not committed** -- `git ls-files frontend/android`
> returns nothing. An earlier version of this page said the opposite and told you
> to check `git diff --stat android/` afterwards for lost hand edits; there is
> nothing there to lose, and `run.ps1` says as much in its own comments. The two
> things in that folder that look hand-made are not: `debugOptimized/` is a build
> variant Expo's own template generates, and `.meridian-build-stamp` is written
> by `run.ps1` at the end of a build that succeeded.

## D. Switch delivery on

```powershell
# backend/.env
PUSH_ENABLED=true
```

```powershell
cd D:\Meridian
docker compose up -d --force-recreate api worker
```

`--force-recreate`, not `restart`: compose reads `.env` at create time.

## E. Verify the last hop

1. Open the development build. Allow notifications when asked.
2. Profile → **Alerts**. **Expect the amber box to be gone.**
3. Re-run **step 5** — there should now be one `push_devices` row with a real
   `ExponentPushToken[...]`.
4. Tap **Send me a test alert**.

**Expect a notification on the lock screen**, titled **"Meridian test alert"**,
filed under the **App status** channel.

5. **Now the real thing.** Put the phone down, locked. Then:

   ```powershell
   docker compose exec api python -m app.agents run alert_dispatch
   ```

   If a qualifying flag is near your last known position and you are under the
   cap, **the phone buzzes within a second or two**, on the **Road and route
   alerts** channel, with the mobility statement and the source count.

   Tap it. **Expect the app to open.**

6. **Check the channels landed.** Android Settings → Apps → Meridian →
   Notifications.

   **Expect three channels:** *Road and route alerts*, *Emergency SOS*, *App
   status*. **Expect NO "Danger Zone Alerts"** — a channel name is a user-visible
   string, and shipping one with that word in it would put the one thing concept
   document §9 forbids into the OS settings screen, where nothing in `framing.py`
   can reach it.

7. **The 60-second claim.** Phase 3's exit criteria ask for a push within 60 s of
   a flag appearing on a corridor. `alert_dispatch` runs on `* * * * *`, so with
   `worker` up you do not need to trigger it:

   ```powershell
   docker compose logs worker --tail 20 | Select-String alert_dispatch
   ```

   **Expect** a run per minute. Publish or seed a flag near your position, put the
   phone down, and time it.

---

## If nothing arrives

Four prerequisites, three of them silent. In the order to check them:

```powershell
curl.exe -s -H "Authorization: Bearer <your token>" http://localhost:8000/api/v1/notifications/config
```

| `config` says | Means | Fix |
|---|---|---|
| `push_enabled: false` | delivery is off server-side | Part 2 §D |
| `expo_project_id: null` | backend has no project id | Part 2 §A |
| `devices.active: 0` | the app never registered a token | Expo Go, denied permission, or no project id in `app.json` |
| `devices.located: 0` | registered but no position | grant location permission, reopen the app |
| `last_rejection: "MismatchSenderId"` | the FCM app is a different package | Part 2 §B step 2 |
| `last_rejection: "InvalidCredentials"` | no FCM key on the EAS project | Part 2 §B steps 5–6 |
| `last_rejection: "DeviceNotRegistered"` | token is dead; the row was disabled | reopen the app to re-register |
| all clean, still nothing | the policy refused it | `metrics` on the last `alert_dispatch` run says which gate |

The Alerts screen shows the same diagnosis in one sentence, picked by
`blockingPushProblem()`. If it says nothing is wrong and nothing arrives, the
answer is in the dispatcher's refusal counts, not in the delivery path.

## What is deliberately not here

- **Delivery receipts.** Expo's `/push/getReceipts` reports, seconds later,
  whether FCM actually accepted each message. Reading it needs a second
  scheduled pass and a `pending` ledger state. `DeviceNotRegistered` is caught
  synchronously and handled; the rest shows up as "it never arrived" and is
  diagnosed from the table above.
- **Geofence crossing.** S17. The dispatcher alerts on where a device *was*, not
  on movement.
- **SOS push to emergency contacts.** Contacts are phone numbers and email
  addresses, not app installs. SOS still goes out by email (S01).
- **iOS.** The code paths are there and iOS needs no channels, but nothing has
  been run on an iPhone and no APNs key has been uploaded. Do not claim it works.

## Sign-off

- [ ] Part 1, steps 1–11 on Expo Go
- [ ] Part 2 §A–D completed
- [ ] Part 2 §E, steps 1–7 on a development build
- [ ] Android settings shows three channels and no "Danger Zone"
- [ ] A locked phone buzzed within 60 s of a flag, unprompted

**Verified by:** —
**Date:** —
