# Running and testing Meridian

One command starts everything. This page covers that command, what it does, how
to verify the result, and the handful of failures that are worth recognising on
sight.

---

## 1. The one command

**Windows**

```powershell
.\scripts\run.ps1
```

**macOS / Linux**

```bash
./scripts/run.sh
```

That is the whole thing. It:

1. **Preflights** — Docker running, both `.env` files present and carrying the
   keys the app cannot start without, `DATABASE_URL` using the `+asyncpg`
   driver. Each failure stops with a specific message rather than a stack trace
   from three layers down.
2. **Detects your LAN IP** and exports `EXPO_PUBLIC_API_BASE_URL` from it. This
   is the step that used to break silently: `API_BASE_URL` was hardcoded to
   `192.168.0.103`, which was correct on exactly one machine.
3. **Starts the containers** — `api` and `redis` — building the image if needed.
4. **Waits for `/health`**, and if the container dies instead, prints the last
   40 log lines rather than spinning for two minutes.
5. **Runs `npm install`** if `node_modules` is absent, then starts Expo with
   `--clear`.

### Options

| | |
|---|---|
| `-BackendOnly` / `--backend-only` | Containers only; start Expo yourself |
| `-Rebuild` / `--rebuild` | Force an image rebuild (after changing `requirements.txt` or the Dockerfile) |
| `-NoOsrm` / `--no-osrm` | Skip the local routing engine (see §6) |
| `-Osrm` / `--osrm` | Start it even when its graph looks unbuilt |
| `-Down` / `--down` | Stop everything |
| `-Logs` / `--logs` | Tail the backend log |

**The local routing engine starts automatically** when its graph is present in
`osrm-data/` — there is no flag to remember. If it is not there, the run prints a
warning and routing falls back to the public demo server, which is slower,
rate-limited, and cannot produce detour alternatives at all. §6 builds the graph.

Either way the run states which engine answered, after the API comes up:

```
    [ok] routing        local engine (osrm-data\bangladesh-latest)
    [!]  routing        public demo server (router.project-osrm.org)
```

That line exists because the fallback is otherwise invisible until a route card
says *"Routed by a public demo server"*, and by then it has usually been running
that way for days.

**First run takes 5–12 minutes**, almost entirely torch and its dependencies.
After that the layer is cached and startup is seconds. Ctrl+C stops Expo; the
containers keep running until you pass `-Down`.

---

## 2. What is running, and what is not

```
┌─ docker compose ──────────────────┐
│  api    FastAPI + YOLOv9/MediaPipe/CLIP   :8000  │
│  redis  cache / future Celery broker      :6379  │
└───────────────────────────────────┘
         │                      │
         ↓                      ↓
   Supabase (hosted)      Expo / Metro :8081
   Postgres + Auth        runs on the HOST
   + Storage
```

**Deliberately absent, and why — all three would mislead you rather than help:**

- **No Postgres container.** Your database is Supabase. A local Postgres would
  be a second, divergent source of truth, and `SCHEMA.sql` targets Supabase's
  `auth.users` and `storage` schemas, which a bare `postgres` image does not
  have.
- **No Celery worker or beat.** `app/core/celery_app.py` schedules two tasks
  whose modules do not exist, and there are no `@task` definitions anywhere, so
  beat crashes on boot. It arrives in **S04** with the agent registry.
- **Expo is not containerised by default.** There is a `mobile` profile if you
  want it, but running Metro on the host is better on Windows and macOS for
  three reasons: inotify does not propagate reliably across Docker Desktop bind
  mounts, so hot reload degrades silently; your phone must reach Metro
  directly, so the container has to advertise the host's IP; and native builds
  need the host SDKs regardless. `run.ps1` gives you one command without any of
  that.

---

## 3. Verify the backend

```bash
./scripts/test.sh          # ~15 seconds
./scripts/test.sh --ai     # also runs an image through the vision stack
```

Five phases, each probing something the app itself cannot tell you about:

| Phase | What it proves |
|---|---|
| 1 · Backend is up | `/health`, `/`, and that the OpenAPI schema builds — a malformed route breaks that before anything else |
| 2 · Supabase schema | All four app tables exist and RLS blocks anonymous reads; the `avatars` bucket exists and is public |
| 3 · Backend ↔ database | `POST /routes/calculate` queries `crime_reports` through SQLAlchemy. **This is the strongest single check**: it only passes if `DATABASE_URL`, the asyncpg driver and the uuid column types are all correct |
| 4 · Auth wiring | An unauthenticated and a bogus-token SOS are both rejected. A 200 here would mean anyone can trigger someone else's emergency alert |
| 5 · AI vision | YOLOv9c loads; with `--ai`, a probe image runs the full pipeline |

Phase 2 reporting *"table exists, RLS blocks anonymous reads"* is the **correct**
result, not a warning — it means the table is there and protected.

Also useful by hand:

- **API docs** → <http://localhost:8000/api/docs> — every endpoint, executable
  in the browser
- **Health** → <http://localhost:8000/health>

---

## 4. Verify the app

> **Status: all five steps below have been walked successfully** on a real
> device against live Supabase (2026-10-07). If one fails for you, it is your
> environment, not the code — the symptom tables are there to tell you which.

Scan the QR code with **Expo Go**. These steps are ordered because each depends
on the one before it — when something breaks, the last step that worked tells
you where to look.

> **Expo Go must be up to date.** This project is on **Expo SDK 57**, and Expo
> Go only ever supports the newest SDK. *"Project is incompatible with this
> version of Expo Go"* means your Expo Go is older than the project — update it
> from the store. (It is also why the project could not stay on SDK 54.)

### 4.1 Register → proves Supabase Auth + `profiles` + RLS

Register with a real email and a password of 8+ characters.

✅ You land on the Home screen.
✅ A row appears in Supabase → Table Editor → `profiles`.

Then, optionally, **Profile → Edit Profile → change the picture**. It proves the
`avatars` storage bucket and its per-user folder policy.

✅ `profiles.avatar_url` is populated.

> **"mime type image/jpg is not supported"** means something built the content
> type by string-concatenating the file extension. `image/jpg` is not a real
> type; it is `image/jpeg`. Use `uploadAvatar()` in `lib/supabase-storage.ts`,
> which maps extensions properly (defect 34, fixed).

> **Users appear under Authentication → Users but not in the `users` table** —
> that is expected. `auth.users` is the identity table and `public.profiles` is
> the profile table. `public.users` is transitional and is deleted by ADR 0003.

> **"Registration failed"** with nothing else means **email confirmation is
> still on**. `auth.service.ts` requires a session immediately after `signUp`,
> and with confirmation enabled the session is null. Turn it off:
> Authentication → Sign In / Providers → Email.

### 4.2 Submit a crime report → proves `crime_reports` + the AI pipeline

Reports tab → **+** → add a photo. The AI analyses it and auto-fills the
category, title and description. Pick a location, submit.

✅ The report appears in the Reports list and as a marker on the Map tab.
✅ A row appears in `crime_reports`.

> The **first** analysis downloads ~700 MB of model weights and can take several
> minutes. Subsequent ones take 2–5 seconds. The weights live in the
> `model_cache` volume and survive restarts.
>
> **"No Crime Detected ✅"** on an ordinary photo is correct behaviour, not a
> failure.
>
> Markers will all be the **same colour** — that is Defect 3 (`CRIME_COLORS` is
> capitalised, the database enum is lowercase), fixed in S07.

### 4.3 Add an emergency contact → proves `emergency_contacts`

Profile → Emergency Contacts → add one with a **real email address**, since
that is the only channel SOS has.

✅ A row appears in `emergency_contacts`.

### 4.4 Trigger SOS → proves the whole stack at once

Home → SOS Emergency. It records 10 seconds of video, uploads it, and the
backend emails your contacts with the video attached and a map link.

This is the one test that exercises **everything**: the Supabase JWT, the
backend's JWKS verification, `DATABASE_URL`, the `emergency_contacts` query, and
SMTP.

✅ The upload progress dialog completes.
✅ Your contact receives the email, with the video attached.

> **Nothing is recorded in the database.** The email is sent and the video is
> deleted; `sos_incidents` stays empty. That is defect 35, fixed in S05 — so
> there is no SOS history screen to check, and the only copy of the clip is in
> the recipient's inbox.

> **401 while everything else works** → token verification. Supabase signs
> access tokens with **ES256**, and the backend originally only tried a shared
> HS256 secret. `app/core/jwks.py` now fetches the project's JWKS and handles
> both (defect 33, fixed). If this still fails, check that `SUPABASE_URL` is set
> in `backend/.env` **and declared in `config.py`** — `extra = "ignore"` means
> an undeclared variable is dropped in silence.
>
> **"No email recipients found"** → the contact has no email address.
> `POLICE_ROUTING_ENABLED` is off by default and intentionally so: every row in
> `police_stations.csv` carries the same placeholder address, so turning it on
> emails an uninvolved stranger on every SOS.
>
> **Reports success but no email arrives** → `SMTP_*` is unset or wrong. For
> Gmail you need an App Password, not your account password. Check
> `./scripts/run.ps1 -Logs`.

---

## 5. Failures worth recognising on sight

| Symptom | Cause | Fix |
|---|---|---|
| `libGL.so.1: cannot open shared object file` | cv2/mediapipe need system GL libs | `run.ps1 -Rebuild` (the Dockerfile installs them) |
| `prepared statement "__asyncpg_stmt_x__" does not exist`, intermittent | `DATABASE_URL` on port **6543** — PgBouncer in transaction mode | Use port **5432** (session pooler) |
| `operator does not exist: uuid = character varying` | ORM out of sync with the schema's uuid columns | `app/models/columns.py` should supply `UUIDStr` to every id — see S01 |
| Container exits immediately | pydantic rejected `backend/.env` | `run.ps1 -Logs` — the error names the field |
| App: "Supabase is not configured" | `frontend/.env` missing or Metro cached the old values | Fill it in, restart with `npx expo start --clear` |
| App can reach Supabase but not the backend | `EXPO_PUBLIC_API_BASE_URL` points at the wrong IP | `run.ps1` sets it; if your IP changed, restart it |
| QR scans then hangs on "Downloading JavaScript bundle" | Phone and PC on different networks, or a firewall is blocking :8081 | Same Wi-Fi; allow Node through Windows Firewall |
| Metro crashes or behaves oddly | Node 24 is ahead of what Expo SDK 57 targets | Install Node 22 LTS |
| *"Project is incompatible with this version of Expo Go"* | Expo Go is older than SDK 57 | Update Expo Go from the store |
| `pose_analysis` is `null` in every AI result | `mediapipe` 1.x removed `mp.solutions`, so pose never loads | Known — defect 29, fixed in S06. Not a detection miss |

**Reading logs**

```bash
./scripts/run.ps1 -Logs            # follow the API
docker compose logs --tail=100 api # last 100 lines
docker compose ps                  # container status + health
docker compose exec api bash       # shell inside the container
```

---

## 6. The local routing engine

**Required since D06, not optional.** Routing honours `OSRM_BASE_URL` and reads the local
graph; without it the app falls back to the public OSRM demo server, which is rate-limited,
belongs to someone else, and **says so loudly on every request and on the route card**
(`engine: "public-demo"`). That fallback exists for D10's failure drills, not for daily use.

One-time setup: a few hundred MB of download plus 10–30 minutes of preprocessing.

### PowerShell (Windows)

**Not bash.** `mkdir -p` is not a PowerShell flag, `curl` is an alias for
`Invoke-WebRequest` (so `-O` is read as `-OutFile` and your URL becomes the *filename*), and
a backslash path plus a drive-letter colon makes Docker's `-v` parsing unreliable. All three
of these have actually bitten someone on this project.

```powershell
cd D:\Meridian
New-Item -ItemType Directory -Force -Path osrm-data | Out-Null
cd osrm-data

# curl.exe, not curl. -L because Geofabrik redirects to a mirror.
curl.exe -L -O https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf

# Sanity-check: hundreds of MB. A few KB means you downloaded an HTML error page,
# and osrm-extract will fail later with a confusing parse error instead of saying so.
Get-Item bangladesh-latest.osm.pbf | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}

# Forward slashes for Docker.
$data = (Get-Location).Path -replace '\\','/'

docker run -t --rm -v "${data}:/data" osrm/osrm-backend osrm-extract   -p /opt/car.lua /data/bangladesh-latest.osm.pbf
docker run -t --rm -v "${data}:/data" osrm/osrm-backend osrm-partition /data/bangladesh-latest.osrm
docker run -t --rm -v "${data}:/data" osrm/osrm-backend osrm-customize /data/bangladesh-latest.osrm

# Roughly 20 files if all three steps finished.
Get-ChildItem bangladesh-latest.osrm* | Measure-Object -Property Length -Sum |
  Select-Object Count, @{n='TotalMB';e={[math]::Round($_.Sum/1MB,1)}}
```

If `osrm-extract` dies without a clear message it is almost always memory — it is the step
that loads the whole graph. Raise the limit in Docker Desktop → Settings → Resources and
re-run just that step.

### Then start it and prove it routes

`scripts/run.ps1` starts it for you from here on — the graph being on disk is what
it checks. To bring it up on its own, or to read its logs:

```powershell
cd D:\Meridian
docker compose --profile osrm up -d osrm
# --profile is needed for logs too, or compose does not know the service exists
docker compose --profile osrm logs --tail 20 osrm   # "running and waiting for requests"

# OSRM takes lon,lat — reversed coordinates return NoSegment and look like a broken install.
curl.exe -s "http://localhost:5000/route/v1/driving/90.4074,23.7104;90.3687,23.8069?overview=false"
```

Expect `"code":"Ok"`. Then in `backend/.env`:

```
OSRM_BASE_URL=http://osrm:5000
```

`osrm`, not `localhost` — that hostname resolves on the compose network, where `api` runs.
Then `docker compose up -d --force-recreate api`, because **compose reads `.env` at create
time, not on restart**.

`osrm-data/` is gitignored; the graph is multi-gigabyte and is rebuilt from these commands.

> ### ⚠️ Two honest limits, both D06 findings
>
> **Durations are free-flow, scaled.** Measured on the Bangshal → Mirpur-10 route: OSRM
> says 12.61 km in 13.8 min — **54.8 km/h across central Dhaka**, with a median segment
> speed of 56 km/h. OSRM is not wrong; `car.lua` speeds come from `maxspeed` tags and
> road-class defaults, and **an OSM extract contains no traffic data at all**, so no rebuild
> of the graph can produce a realistic number. `ROUTE_CONGESTION_FACTOR` (0.35) scales it to
> ~19 km/h and the card labels it `in traffic (est.)`. The proper fix is
> `osrm-customize --segment-speed-file`, which needs a traffic source — Track B.
> **The factor is a calibration from one reading. Check it against a journey you know.**
>
> **Walking answers from the car graph.** OSRM will serve a `/foot/` request from whatever
> graph it has, so a walking route obeys car turn restrictions and may use a flyover. The
> duration is recomputed at 4.8 km/h — it returned 7.03 km in *9 minutes* otherwise — and
> the caveat is shown on the card. A second graph built with `foot.lua` is the fix.

---

## 7. Everything containerised (optional)

```powershell
$env:HOST_LAN_IP = "192.168.x.x"      # required — the container must advertise your IP
docker compose --profile mobile up
```

Read §2 before choosing this. The host-based default exists because this path
costs you working hot reload.

---

## 8. Day-to-day

```powershell
.\scripts\run.ps1            # start everything
.\scripts\run.ps1 -Down      # stop everything
.\scripts\run.ps1 -Rebuild   # after changing requirements.txt or the Dockerfile
./scripts/test.sh            # verify the backend
./scripts/smoke.sh           # verify every sprint's promises still hold
./scripts/check.sh           # lint, types, tests
```

Backend code changes reload automatically — `backend/app` is bind-mounted and
uvicorn watches it. Frontend changes hot-reload through Metro. Only dependency
or Dockerfile changes need `-Rebuild`.
