# Deploying Meridian

**Goal: a judge anywhere in the world installs the app on their own Android phone
and it works.** Not a store listing, not a staging environment — one APK link and
one backend that stays up.

This page is a runbook. Every command here is meant to be run as written, in
order. Where a value is yours to choose it is written `LIKE_THIS`.

**Read [§0](#0-three-traps-that-will-cost-you-the-demo) before you start.** All
three are silent failures: the build succeeds, the app installs, and the feature
is simply dead on the judge's phone.

---

## What you are building

```
  Judge's Android phone
      │   installs from  https://expo.dev/accounts/.../builds/<uuid>
      ▼
  Meridian APK  ──── HTTPS ────►  Caddy :443        one VPS, Asia (India)
                                    │   meridian-backend.duckdns.org
                                    │                8 GB RAM, 100 GB disk
                                    ▼
                                  api :8000
                                    ├── worker (Celery + beat)
                                    ├── redis
                                    └── osrm  (Bangladesh graph, on disk)
                                    │
                                    ├──► Supabase        already global
                                    ├──► Gemini / Groq   already global
                                    ├──► SMTP            SOS + guardian email
                                    └──► Expo Push → FCM
```

Supabase, the model providers and Expo Push are already reachable from anywhere.
**The only thing that is not yet on the internet is your own backend**, and the
only thing the judges cannot get is the app. That is the whole job.

---

## Before you start

| You need | Notes |
|---|---|
| **Contabo Cloud VPS 4, Asia (India)** | 4 vCPU / 8 GB / 100 GB. Ordered as in [§2](#2-the-server). |
| **`meridian-backend.duckdns.org`** | Already created. Free. No registrar, no A record — see [§3](#3-hostname-and-https). |
| The Expo account that owns `app.json`'s `owner` | Currently **`warfather0991`** — Nakib's. The build must run from that account or the FCM credentials will not match. |
| `frontend/google-services.json` | Gitignored. See [§0.1](#01-google-servicesjson-will-not-reach-eas-build). |
| SMTP credentials | Without them SOS and guardian emails report success and deliver nothing. |

**Budget: $9.60/month, all in.** $6.60 for the server plus $3.00 for the India
region. The hostname is free, and Supabase, EAS, Gemini/Groq and Expo Push all
stay on free tiers you already use.

---

## §0 Three traps that will cost you the demo

### 0.1 `google-services.json` will not reach EAS Build

`.gitignore:191` ignores `frontend/google-services.json`, and it is **not tracked**:

```bash
git check-ignore -v frontend/google-services.json
# .gitignore:191   frontend/google-services.json
```

EAS Build uploads your git repository. A gitignored file is not in it. So on EAS,
`app.config.js` finds the file missing, does exactly what it was written to do —
drops the pointer and warns — and **the APK ships with no FCM**. Remote push is
dead on every judge's phone: no Journey Guardian overdue alert, no "told if you
did not arrive". Guardian zone alerts still work, because those are local
notifications, which is why nothing looks broken.

**Fix — upload the file as an EAS secret and teach the config to read it:**

```bash
cd frontend
eas secret:create --scope project --name GOOGLE_SERVICES_JSON \
  --type file --value ./google-services.json
```

Then in `frontend/app.config.js`, replace this line:

```js
const declared = android.googleServicesFile;
```

with:

```js
// On EAS Build the file arrives as an uploaded secret at an absolute path in
// GOOGLE_SERVICES_JSON, because frontend/google-services.json is gitignored and
// so is never in the repository EAS checks out. Without this the branch below
// drops the pointer and the APK ships with no FCM, silently.
const declared = process.env.GOOGLE_SERVICES_JSON ?? android.googleServicesFile;
```

and make the keep-branch explicit, so an absolute secret path is written back:

```js
if (declared && fs.existsSync(path.resolve(__dirname, declared))) {
  android.googleServicesFile = declared;
} else if (declared) {
  delete android.googleServicesFile;
  // ... existing warning, unchanged ...
}
```

`path.resolve` returns an absolute second argument unchanged, so this keeps
working locally. Re-run `npx jest app.config.test.js` afterwards — all six
should still pass.

**Verify after the build:** the build log must **not** contain
`[meridian] ./google-services.json is missing`. If it does, push is off.

### 0.2 The API URL is baked into the APK

`EXPO_PUBLIC_API_BASE_URL` is inlined at build time, not read at runtime. So the
order is fixed and cannot be reversed:

> **DuckDNS pointed at the VPS → HTTPS working → `/health` green from outside
> → then build the APK.**

Change the backend URL afterwards and every installed APK points at nothing. You
get 15 free Android builds a month; do not spend them discovering the URL was
wrong.

### 0.3 The judge's GPS is not in Dhaka

`MapScreen.tsx:250` mounts on `DEFAULT_MAP_REGION` (Dhaka) and moves to the device
location the moment it arrives. A judge in London therefore gets:

- an empty map — every risk flag is in Dhaka
- routing that fails — the OSRM graph is Bangladesh only
- an SOS whose thana lookup **correctly refuses**, because they are outside Dhaka city

Every one of those is the system behaving as designed, and the demo still shows
nothing. **This is a product gap that no deployment choice fixes.**

The cheap fix is a *"View as Dhaka"* toggle that pins the location store to
`DHAKA_COORDINATES` (`app.constants.ts:41`) instead of the device fix. The
alternative is talking each judge through Android's mock-location developer
settings, which most will not do.

**Decide this before you build the APK**, because it changes the APK.

---

## §1 Make the backend image deployable

The current image is **6.21 GB** and `docker compose build --no-cache` **will fail
today**. `backend/Dockerfile` still runs:

```dockerfile
RUN python -c "from ultralytics import YOLO; YOLO('yolov9c.pt')" ...
```

but ADR 0006 removed `ultralytics` from every requirements file — `ai.txt` now
contains no packages at all. Nothing installs it, so that line raises
`ModuleNotFoundError` and the build stops. The running container only works
because its image predates the change.

Two images, because the split is real: `app.main` imports **none** of the heavy
modules. Verified:

```bash
docker exec meridian-api python -c "
import sys, app.main
m = set(sys.modules)
print([h for h in ('torch','sentence_transformers','playwright','cv2','transformers')
       if any(k == h or k.startswith(h + '.') for k in m)] or 'NONE')"
# NONE
```

Only the worker needs weight: `sentence-transformers` in `agents/rumour_guard.py`
and `playwright` in `ingestion/fetcher.py`.

### `backend/Dockerfile.api`

```dockerfile
# =============================================================================
# Meridian API — production
# =============================================================================
# base.txt only. No torch, no playwright, no YOLO weights: app.main imports none
# of them, and ADR 0006 deleted the code that did.
# =============================================================================
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# libgl1/libglib2.0-0/libsm6/libxext6/libxrender1 are gone with cv2 and
# mediapipe. geos and proj are for shapely and pyproj; libmagic1 for
# python-magic. gcc/g++ are belt and braces for any source build.
RUN apt-get update && apt-get install --no-install-recommends -y \
        gcc g++ libpq-dev libgeos-dev libproj-dev libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt ./requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .
RUN mkdir -p logs uploads

EXPOSE 8000

# 20s, not 90s: there is no torch import to wait for any more.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### `backend/Dockerfile.worker`

```dockerfile
# =============================================================================
# Meridian worker — production
# =============================================================================
# The agents, which are the only half that needs weight: sentence-transformers for
# cross-outlet dedup, playwright for the one outlet that renders client-side.
# =============================================================================
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    HF_HOME=/cache/huggingface \
    TORCH_HOME=/cache/torch

RUN apt-get update && apt-get install --no-install-recommends -y \
        gcc g++ libpq-dev libgeos-dev libproj-dev libmagic1 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# CPU torch FIRST, from PyTorch's CPU index. sentence-transformers depends on
# torch, and left to itself pip takes the default PyPI wheel, which bundles the
# CUDA runtime -- ~2.5 GB of GPU libraries this machine cannot use. Installing
# the CPU build first means the later resolve sees it satisfied. torchvision is
# NOT installed: nothing imports it.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements/base.txt requirements/agents.txt ./requirements/
RUN pip install --no-cache-dir -r requirements/base.txt -r requirements/agents.txt

RUN playwright install --with-deps chromium

COPY . .
RUN mkdir -p logs uploads /cache

CMD ["celery", "-A", "app.core.celery_app", "worker", "-B", "--concurrency", "1", "--loglevel", "info"]
```

> Note the deleted YOLO step. If you ever reinstate it, the build breaks again.

---

## §2 The server

### What to order

**Contabo Cloud VPS 4** — 4 vCPU / 8 GB RAM / 100 GB SSD / 200 Mbit/s.

| Option | Choose | Why |
|---|---|---|
| **Term** | **1 Month — $6.60** | No setup fee on any term, so monthly costs nothing to stay flexible. 12 months saves $0.99/mo but commits $67 upfront on a project whose future depends on advancing. |
| **Region** | **Asia (India) — $3.00/mo** | Singapore (49 ms from Dhaka) was out of stock. India is 51 ms and is the shortest remaining hop to Supabase. See Appendix A. |
| **Storage** | 100 GB SSD (free) | About 25 GB gets used. |
| **Image** | **Ubuntu 24.04 LTS** (included) | Never Windows — Docker on a Windows VPS loses 1–1.5 GB to the hypervisor before a container starts. |
| **Auto Backup** | **No Data Protection** | The plan includes 1 free snapshot; take it by hand once the stack is verified (below). Nothing on this box is unique: code is in git, the OSRM graph is on your machine, all real state is in Supabase. |
| **IPv4** | **1 IP Address (free)** | A *dedicated* address. This is what makes ports 80 and 443 yours, and the entire HTTPS plan depends on it. |
| Private Networking · Object Storage · Monitoring | None | Single server; evidence photos go to Supabase Storage; `python -m app.agents status` is the monitor. |

**$9.60/month.** Provisioning is usually quick, but new accounts are sometimes
held for manual ID verification — watch your email and answer promptly. Set a
long random root password and save it now; Contabo does not email it, and losing
it means a reinstall.

### First login

```bash
# From your machine
ssh root@SERVER_IP

# Docker, from Docker's own repository
curl -fsSL https://get.docker.com | sh
docker --version && docker compose version

# Swap, so a memory spike cannot take the box down
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Firewall: SSH and the web only. Nothing else is exposed.
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

Then lock SSH to a key. This box will hold your SMTP password, your Supabase
service-role key and your LLM keys; a root password on a public IP is
brute-forced within hours.

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys          # paste your public key, save
chmod 600 ~/.ssh/authorized_keys
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

**Open a second terminal and confirm you can still log in before closing this
one.** A broken `sshd_config` with password auth already disabled means a
rescue-console trip.

Then get the code onto it. The repository is private and **must stay private**, so
use a deploy key or clone over SSH with agent forwarding:

```bash
mkdir -p /opt && cd /opt
git clone git@github.com:ArafatBytes/Meridian.git meridian
cd /opt/meridian && git checkout develop
```

---

## §3 Hostname and HTTPS

The hostname is **`meridian-backend.duckdns.org`**, on DuckDNS. There is no
registrar, no renewal and no A record to create — DuckDNS *is* the DNS, and it is
free.

### Point it at the server

> ⚠️ **A fresh DuckDNS domain points at the browser that created it** — your own
> connection in Dhaka, not the server. Nothing below works until this is changed.

1. Open <https://www.duckdns.org>
2. In the **current ip** box for `meridian-backend`, replace the address with the
   Contabo IP
3. Click **update ip**

The TTL is 60 seconds. Verify **from your laptop, not from the server**:

```bash
nslookup meridian-backend.duckdns.org
```

It must return the Contabo IP. If it still shows your home address, the update
did not take and Caddy will fail to get a certificate.

> **Keep the DuckDNS account and its token safe.** This hostname is compiled into
> every APK you hand a judge, so whoever controls that page controls where every
> installed copy of the app sends its traffic.

### Caddy

`deploy/Caddyfile`:

```
meridian-backend.duckdns.org {
	encode zstd gzip
	reverse_proxy api:8000
}
```

That is the whole TLS configuration. Caddy obtains and renews a Let's Encrypt
certificate on its own, over HTTP-01 on port 80 — which is exactly why §2
insisted on a dedicated IP. DuckDNS works normally here: `duckdns.org` is on the
Public Suffix List, so this subdomain gets its own Let's Encrypt rate-limit
budget instead of sharing one with every other DuckDNS user.

> **Do not fall back to plain HTTP.** `app.json` sets `usesCleartextTraffic: true`,
> so an HTTP backend *would* work — and would put JWTs, live location and SOS
> payloads in clear across the open internet. For a safety app that is the one
> thing a judge might reasonably call out.

---

## §4 Production environment

`backend/.env` is tracked in git, so the server already has your development one.
**Edit it on the server; do not commit the result.**

```bash
cd /opt/meridian && nano backend/.env
```

| Set | To | Why |
|---|---|---|
| `APP_ENV` | `production` | |
| `DEBUG` | `False` | |
| `RELOAD` | `False` | |
| `PUSH_ENABLED` | `true` | Otherwise the dispatcher logs what it would have sent. Journey Guardian's escalation never reaches a phone. |
| `EXPO_PROJECT_ID` | `e6d4c6f9-a422-4a63-8119-b70d26ccdc2f` | Must equal `app.json`'s `extra.eas.projectId`. A token issued against one project and pushed from another is accepted by Expo and then never delivered. |
| `OSRM_BASE_URL` | `http://osrm:5000` | The service name inside the compose network. |
| `RISK_SURFACE_IMPL` | `db` | `seeded` is the offline fallback; see [§8](#if-something-breaks-mid-demo). |
| `POLICE_ROUTING_ENABLED` | **`false`** | All 606 rows of `police_stations.csv` share one inbox (`hello3210bye@gmail.com`). With judges triggering SOS, every alert lands in that one mailbox. Defect 17. |
| `SMTP_*`, `FROM_EMAIL` | real values | SOS and guardian email. Blank means silent non-delivery. |

Leave `DATABASE_URL` alone — it already points at Supabase, with the
`+asyncpg` driver and the session pooler on **5432**, not 6543.

---

## §5 Ship the OSRM graph

You already built it, and it is already proven. Upload it rather than rebuilding:
`osrm-extract` on the 356 MB Bangladesh PBF wants ~4–6 GB of RAM and will OOM a
4 GB box.

```bash
# From your Windows machine, in the repo root (Git Bash)
rsync -avP osrm-data/ root@SERVER_IP:/opt/meridian/osrm-data/
```

1.5 GB, once. Serving it costs **560 MB of RAM** — measured, for all of Bangladesh.

<details>
<summary>Optional: cut it to greater Dhaka first, if the upload is painful</summary>

The app is Dhaka-scoped anyway — the gazetteer box is `90.30,23.66,90.54,23.94`.
A slightly wider cut keeps the approaches:

```bash
# needs osmium-tool, locally or from any osmium-tool container image
osmium extract -b 90.20,23.55,90.65,24.05 \
  osrm-data/bangladesh-latest.osm.pbf -o osrm-data/dhaka.osm.pbf

docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/dhaka.osm.pbf
docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend \
  osrm-partition /data/dhaka.osrm
docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend \
  osrm-customize /data/dhaka.osrm
```

Then point the `osrm` service at `/data/dhaka.osrm`. Smaller upload, smaller RAM,
and routing stops at the edge of the box — which is where the app stops anyway.
</details>

---

## §6 Bring it up

`docker-compose.prod.yml` — a **standalone** file, not an override. Override
merging has subtle rules for volumes and commands; a deadline is the wrong place
to meet them.

```yaml
# Meridian — production. Run with:
#   docker compose -f docker-compose.prod.yml up -d --build
#
# Differences from docker-compose.yml, all deliberate:
#   * no source bind mounts   the image carries the code; nothing live-reloads
#   * no --reload             uvicorn runs 2 workers instead
#   * no published port 8000  only Caddy is on the internet
#   * osrm is not a profile    routing is not optional in front of judges
services:
  caddy:
    image: caddy:2-alpine
    container_name: meridian-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - api

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.api
    image: meridian-api:prod
    container_name: meridian-api
    restart: unless-stopped
    env_file:
      - ./backend/.env
    environment:
      REDIS_HOST: redis
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      OSRM_BASE_URL: http://osrm:5000
      PYTHONPATH: /app
    expose:
      - "8000"
    volumes:
      - ./backend/logs:/app/logs
      - ./backend/uploads:/app/uploads
    depends_on:
      redis:
        condition: service_healthy

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    image: meridian-worker:prod
    container_name: meridian-worker
    restart: unless-stopped
    env_file:
      - ./backend/.env
    environment:
      REDIS_HOST: redis
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      OSRM_BASE_URL: http://osrm:5000
      PYTHONPATH: /app
    volumes:
      - model_cache:/cache
      - ./backend/logs:/app/logs
    depends_on:
      redis:
        condition: service_healthy
      api:
        condition: service_started
    healthcheck:
      disable: true

  redis:
    image: redis:7-alpine
    container_name: meridian-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --save 60 1
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  osrm:
    image: osrm/osrm-backend
    container_name: meridian-osrm
    restart: unless-stopped
    volumes:
      - ./osrm-data:/data
    command: osrm-routed --algorithm mld /data/bangladesh-latest.osrm

volumes:
  redis_data:
  model_cache:
  caddy_data:
  caddy_config:
```

```bash
cd /opt/meridian
docker compose -f docker-compose.prod.yml up -d --build   # first build: 10-20 min
docker compose -f docker-compose.prod.yml ps
```

### Verify from outside, not from the server

Run these from your laptop. A check that only passes on the box proves nothing
about what a judge's phone can reach.

```bash
curl -sS https://meridian-backend.duckdns.org/health
curl -sSI https://meridian-backend.duckdns.org/health | head -1    # expect HTTP/2 200
curl -sS "https://meridian-backend.duckdns.org/api/v1/risk/flags?bbox=90.30,23.66,90.54,23.94" | head -c 400
```

Then the two that prove the agents are alive:

```bash
# on the server
docker exec meridian-worker python -m app.agents status    # exits 1 if any agent is late
docker compose -f docker-compose.prod.yml logs --tail 40 worker
```

`python -m app.agents status` is the real gate. `journey_watch` and
`alert_dispatch` run every minute; if they are not running, Journey Guardian is
silently dead and nothing else tells you.

---

## §7 Build the APK

Only once §6 is green from outside.

```bash
cd frontend
npx eas-cli login
npx eas-cli whoami          # must be warfather0991, the owner in app.json
```

Pin the production URL in the build profile rather than relying on the committed
`.env`, which still holds a LAN IP. In `frontend/eas.json`, add `env` to `preview`:

```json
"preview": {
  "distribution": "internal",
  "android": { "buildType": "apk" },
  "env": {
    "EXPO_PUBLIC_API_BASE_URL": "https://meridian-backend.duckdns.org/api/v1",
    "EXPO_PUBLIC_SUPABASE_URL": "https://YOUR_REF.supabase.co",
    "EXPO_PUBLIC_SUPABASE_ANON_KEY": "YOUR_ANON_KEY"
  }
}
```

The anon key belongs in the APK — RLS is what guards the data, not its secrecy.
A service-role key never goes here.

```bash
npx eas-cli build --platform android --profile preview
```

**Check the build log for `[meridian] ./google-services.json is missing`.** If it
is there, §0.1 was not done and the APK has no push. Fix and rebuild.

The result is a URL like
`https://expo.dev/accounts/warfather0991/projects/Meridian/builds/<uuid>`.
Internal-distribution links are open to anyone holding the URL by default; there
is no sign-in, no form, no device registration on Android.

---

## §8 Give the judges the link

Send the build URL with instructions, because two steps are not obvious and one
looks alarming:

> **Meridian — install and try it**
>
> 1. Open this link on an **Android** phone: `<build URL>`
> 2. Tap **Install**. Android will warn that the app is not from Google Play —
>    this is normal for a prototype; choose **Install anyway**.
> 3. Create an account with any email. No confirmation email is needed.
> 4. When asked for location, choose **Allow**. Then, for background safety
>    alerts, open **Settings → Apps → Meridian → Permissions → Location** and
>    choose **Allow all the time**. Android does not allow an app to request
>    this from a dialog.
> 5. The app covers **Dhaka, Bangladesh**. [If you added the toggle:] Turn on
>    **View as Dhaka** in Profile to see the live map from anywhere in the world.

iPhone is not supported for this round: ad-hoc iOS distribution needs each
device's UDID registered at build time and a paid Apple Developer account.

### If something breaks mid-demo

| Symptom | Do this |
|---|---|
| Map empty, agents behind | `RISK_SURFACE_IMPL=seeded` in `backend/.env`, then recreate `api`. Serves the committed fixture, never touches the database. Every `source_id` starts `sample_`. |
| Routing slow or failing | `docker compose -f docker-compose.prod.yml restart osrm` |
| Push not arriving | `curl https://meridian-backend.duckdns.org/api/v1/notifications/config` — it reports the last Expo rejection, which is the only place that failure is visible. |
| Anything else | `docker compose -f docker-compose.prod.yml logs --tail 100 api worker` |

Redeploying after a code change:

```bash
cd /opt/meridian && git pull
docker compose -f docker-compose.prod.yml up -d --build api worker
```

Backend-only changes need no new APK. Anything in `frontend/` does.

---

## Appendix A — why this shape

**Why not a web link.** `MapScreen.web.tsx` exists, so a web build boots. But
background geofencing (`expo-task-manager`), zone alerts with the app closed,
FCM push, `expo-speech-recognition` and `react-native-maps` do not work there.
A web demo shows the map and the news feed and silently loses Guardian, Journey
Guardian and SOS — the three things worth judging. Expo Go is out for the same
reason: custom native modules need a dev build.

**Why not a managed free tier.** Measured RAM for the whole stack is ~1.65 GB
(see Appendix B), which no free tier offers always-on:

- **Render free** is 512 MB and sleeps after 15 minutes, with 30–60s cold starts.
  `journey_watch` runs *every minute*; a sleeping worker means nobody is watching
  a journey, which the agent catalogue calls the one failure that is silent by
  design.
- **Railway, Fly.io, Koyeb** have effectively ended always-on free tiers for new
  accounts in 2026.
- **Oracle Always Free** was halved to 2 OCPU / 12 GB in 2026, is ARM-only — you
  would have to confirm `osrm-backend` publishes `arm64` — and A1 capacity is
  frequently unavailable. Genuinely free when it works; not something to bet a
  deadline on.
- OSRM needs **1.5 GB of persistent disk**, which free tiers do not give.

**Why India, and why Contabo.** Every API request touches Supabase at
`ap-southeast-1`, so being near the database matters more than being near any one
judge. Singapore was the first choice — 49 ms from Dhaka — and was out of stock.
India is 51 ms and the shortest remaining hop to Singapore.

A European region would have been **free**, and was rejected for three reasons
that have nothing to do with speed:

- **Ingestion would likely break.** Ten Bangladeshi news sources, fetched from a
  European datacentre IP, are far likelier to be geo-blocked, rate-limited or
  Cloudflare-challenged — particularly DMP News and the Channel 24 scrape that
  drives headless Chromium. No fetches means no new flags, which is a blank map
  rather than a slow one.
- **Gemini's API availability is regional**, and `LLM_CHAIN_GEO` /
  `LLM_CHAIN_EXTRACT` both depend on it.
- **GDPR would come into scope**, since location history, SOS incidents and
  emergency contacts would be processed on EU soil — with four retention windows
  still sitting unsigned as `PROPOSED`.

Against the Bangladeshi providers (Hosttier ৳1,050, Web Host BD ৳1,600), Contabo
gives 8 GB and 100 GB for what they charge for 4 GB and 50 GB. The BDIX hosts
also optimise for the wrong audience: excellent for local visitors, but
international traffic is throttled — vendors commonly pair 1 Gbps BDIX with
50 Mbps IIG — and if the IIG side has trouble, a BDIX-hosted service becomes
unreachable from outside Bangladesh entirely.

**Why DuckDNS and not a registered domain.** The hostname is never seen by a
judge; it is an API endpoint compiled into the APK. A free DuckDNS subdomain gets
a genuine Let's Encrypt certificate and costs nothing. The trade is a dependency
on a free third-party service — which is why §3 says to keep the account secure.

**Why not the Play Store.** Review time aside, `app.json`'s `applicationId` is
`com.Meridian.app` with a capital M, and an `applicationId` can never be changed
after a first release. That is a known blocker, deliberately unfixed.

---

## Appendix B — the measurements this plan rests on

Taken 2026-10-16 from the running development stack.

| Container | RAM | Note |
|---|---|---|
| `meridian-api` | 166 MB | |
| `meridian-worker` | 909 MB | sentence-transformers holds the model |
| `meridian-osrm` | 560 MB | serving **all of Bangladesh**, MLD |
| `meridian-redis` | 13 MB | |
| **Total** | **~1.65 GB** | comfortable in 4 GB with 2 GB swap |

| Artefact | Size |
|---|---|
| `meridian-api:dev` image, as built today | **6.21 GB** |
| ↳ `torch` | 773 MB |
| ↳ `playwright` | 140 MB |
| ↳ `mediapipe`, `transformers`, `opencv`, `scipy`, `onnxruntime`, `pandas` | ~700 MB — **all orphaned**, no requirements file lists them |
| `osrm-data/` | 1.5 GB |

The orphans are why §1 splits the image: that running container predates ADR
0006 and nothing has rebuilt it since.

| Limit | Value |
|---|---|
| EAS Build free tier | 15 Android builds/month, 45-min cap, concurrency 1 |
| EAS internal distribution | public URL, 32-char UUID, no device registration on Android |

---

## Sources

- [Expo — internal distribution](https://docs.expo.dev/build/internal-distribution/)
- [Expo — pricing](https://expo.dev/pricing)
- [InfoQ — Oracle quietly halves free tier Ampere A1 limits](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- [Linuxiac — Oracle cuts free tier Ampere A1 resources in half](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)
- [State of Free Hosting 2026 — every free tier and its catch](https://snapdeploy.dev/state-of-free-hosting)
- [Render vs Railway vs Fly.io — pricing compared 2026](https://dev.to/pavel-hostim/render-vs-railway-vs-flyio-pricing-compared-2026-2e5p)
- [Cheapest cloud VPS 2026 — Hetzner vs DigitalOcean vs Vultr vs Linode](https://cloudmart.dev/blog/cheapest-vps-2026)
- [Self-hosted OSRM in Docker — serving memory by region](https://sumguy.com/self-hosted-osrm-docker/)
