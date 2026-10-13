# =============================================================================
# Meridian - start everything
# =============================================================================
#   .\scripts\run.ps1               backend in Docker + Expo on the host
#   .\scripts\run.ps1 -BackendOnly  just the containers
#   .\scripts\run.ps1 -Rebuild      force a Docker image rebuild first
#   .\scripts\run.ps1 -Build        force a native Android rebuild
#   .\scripts\run.ps1 -NoOsrm       skip the local routing engine
#   .\scripts\run.ps1 -Osrm         force it even if the graph looks unbuilt
#   .\scripts\run.ps1 -Down         stop everything
#   .\scripts\run.ps1 -Logs         tail the backend log
#
# Expo runs on the host rather than in a container on purpose - see the comment
# on the `expo` service in docker-compose.yml. The three reasons are broken file
# watching over bind mounts, host-addressing for the phone, and native builds
# needing the host SDKs anyway.
#
# With a phone attached over USB this does the whole job: backend up, the app
# pointed at this machine, the APK rebuilt only if the native config has moved
# since the last build, and the app opened. Nothing to remember.
# =============================================================================

[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$Rebuild,
    [switch]$Build,
    [switch]$Osrm,
    [switch]$NoOsrm,
    [switch]$Down,
    [switch]$Logs
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Say  { param($m) Write-Host $m }
function Step { param($m) Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "    [ok] $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "    [!]  $m" -ForegroundColor Yellow }
function Die  { param($m) Write-Host ""; Write-Host "    [x]  $m" -ForegroundColor Red; Write-Host ""; exit 1 }

# -----------------------------------------------------------------------------
# Short-circuit subcommands
# -----------------------------------------------------------------------------
if ($Down) {
    Step "Stopping"
    docker compose --profile osrm --profile mobile down
    Ok "stopped"
    exit 0
}
if ($Logs) {
    docker compose logs -f api
    exit 0
}

# -----------------------------------------------------------------------------
# 1. Preflight - fail here with a clear message rather than deep inside Docker
# -----------------------------------------------------------------------------
Step "Preflight"

try { docker info --format '{{.ServerVersion}}' | Out-Null }
catch { Die "Docker is not running. Start Docker Desktop and try again." }
Ok "Docker is running"

if (-not (Test-Path "$Root\backend\.env")) {
    Die "backend\.env is missing. Copy backend\.env.example and fill it in.`n         Guide: backend\migrations\supabase\README.md"
}
if (-not (Test-Path "$Root\frontend\.env")) {
    Die "frontend\.env is missing. Copy frontend\.env.example and fill it in."
}
Ok "env files present"

# The backend will not start without DATABASE_URL, and the app throws at import
# without the two Supabase values. Check names only - never print values.
$backendEnv  = Get-Content "$Root\backend\.env"  -Raw
$frontendEnv = Get-Content "$Root\frontend\.env" -Raw

foreach ($key in @('DATABASE_URL', 'JWT_SECRET_KEY')) {
    if ($backendEnv -notmatch "(?m)^\s*$key\s*=\s*\S") { Die "backend\.env is missing $key" }
}
foreach ($key in @('EXPO_PUBLIC_SUPABASE_URL', 'EXPO_PUBLIC_SUPABASE_ANON_KEY')) {
    if ($frontendEnv -notmatch "(?m)^\s*$key\s*=\s*\S") { Die "frontend\.env is missing $key" }
}
Ok "required keys present"

# asyncpg driver and the PgBouncer port are the two mistakes that produce
# confusing failures much later, so catch them now.
if ($backendEnv -match '(?m)^\s*DATABASE_URL\s*=.*' ) {
    $dbLine = ($backendEnv | Select-String -Pattern '(?m)^\s*DATABASE_URL\s*=.*').Matches[0].Value
    if ($dbLine -notmatch '\+asyncpg') {
        Die "DATABASE_URL must use the asyncpg driver: postgresql+asyncpg://...`n         The async engine cannot start without it."
    }
    if ($dbLine -match ':6543/') {
        Warn "DATABASE_URL uses port 6543 (PgBouncer, transaction mode)."
        Warn "asyncpg's prepared-statement cache breaks against it, intermittently."
        Warn "Use port 5432 (session pooler) instead."
    }
}

# -----------------------------------------------------------------------------
# 2. LAN IP - what the phone will use to reach Metro and the API
# -----------------------------------------------------------------------------
Step "Network"

# Always look at the network first, whatever a leftover variable says.
$adapters = @(Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' })
$detectedIp = ($adapters | Select-Object -First 1).IPv4Address.IPAddress

# Every address this machine currently answers on, used below to reject an
# override that points somewhere this machine is not.
$ownIps = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty IPAddress)

if ($adapters.Count -gt 1) {
    # Common when a hotspot is up alongside ethernet. Say which one was taken,
    # because picking the wrong one leaves the phone unable to reach the API.
    Warn "More than one network is up. Using the first; set `$env:HOST_LAN_IP to pick another:"
    foreach ($a in $adapters) {
        Say "    $($a.InterfaceAlias) -> $($a.IPv4Address.IPAddress)"
    }
}

# HOST_LAN_IP is honoured only when *you* set it.
#
# This script writes that same variable below, and `$env:` changes persist for
# the whole PowerShell session - so reading it back unconditionally meant a
# second run in the same window reused the first run's address and never looked
# at the network again. Moving between a router and a phone hotspot then left
# the app calling an IP that no longer existed, while every part of the restart
# appeared to succeed. The marker below is how we tell your value from our own.
$previousIp = $env:HOST_LAN_IP
$lanIp = $env:HOST_LAN_IP
if ($lanIp -and $lanIp -eq $env:MERIDIAN_LAN_IP_AUTOSET) {
    $lanIp = $null
}
# An override naming an address this machine does not hold is always stale, not
# deliberate - a window left open from before the laptop changed networks, or
# carried over from a version of this script that did not write the marker. The
# marker check alone cannot catch that case, and the symptom is nasty: Metro
# picks its own address and prints the right one, while the app is built against
# the wrong one, so everything looks correct except the phone.
if ($lanIp -and ($ownIps -notcontains $lanIp)) {
    Warn "HOST_LAN_IP is $lanIp, which is not an address on this machine - ignoring it."
    Warn "This usually means the laptop changed networks since that value was set."
    $lanIp = $null
}
$manual = [bool]$lanIp
if (-not $lanIp) { $lanIp = $detectedIp }

if (-not $lanIp) {
    Warn "Could not detect a LAN IP. Falling back to localhost - a physical phone will NOT be able to connect."
    Warn "Set it manually:  `$env:HOST_LAN_IP = '192.168.x.x'"
    $lanIp = '127.0.0.1'
} elseif ($manual) {
    Ok "LAN IP: $lanIp (from HOST_LAN_IP; detected $detectedIp)"
} else {
    Ok "LAN IP: $lanIp"
}

# The address moved. This is the moment the app breaks silently, so say so here
# rather than letting it surface as "Network error" on the phone: EXPO_PUBLIC_*
# values are inlined into the bundle at build time, and a cached bundle keeps
# serving the old address however many times you restart or rescan the QR.
if ($previousIp -and $previousIp -ne $lanIp) {
    Warn "LAN IP changed: $previousIp -> $lanIp"
    Warn "Metro has the old address baked into its cache. Start it with -c:"
    Say  "    cd frontend; npx expo start -c --dev-client --scheme meridian"
}

$env:HOST_LAN_IP = $lanIp
# Remembers that the value above is ours, not yours. See the note above.
$env:MERIDIAN_LAN_IP_AUTOSET = $lanIp
# Overrides the value in frontend/.env so the app reaches the backend on this
# machine rather than on whatever IP was hardcoded.
$env:EXPO_PUBLIC_API_BASE_URL = "http://${lanIp}:8000/api/v1"

# -----------------------------------------------------------------------------
# 3. Containers
# -----------------------------------------------------------------------------
Step "Backend"

# -----------------------------------------------------------------------------
# The local routing engine, started by default when its graph is built
# -----------------------------------------------------------------------------
# `osrm` sits behind a compose profile, so a plain `docker compose up -d` leaves
# it out. That was right when the profile was added: the service needs a ~1 GB
# download and 10-30 minutes of preprocessing, and a container pointed at a graph
# that does not exist crash-loops with a message about a missing `.fileIndex`
# that explains nothing to someone on a fresh clone.
#
# It was also quietly expensive, because NOTHING SAID IT WAS MISSING. The backend
# is configured with OSRM_BASE_URL=http://osrm:5000, finds nothing there, falls
# back to router.project-osrm.org, and every route comes back labelled "Routed by
# a public demo server". The app works, so the fallback survives for days:
# slower routes over the internet, on a stranger's rate limiter, and no detour
# alternatives at all -- `fetch_routes_via` deliberately has no demo fallback, so
# "4 minutes longer, avoids two flagged corridors" can never appear.
#
# So the profile is now decided by whether the graph is actually there, which is
# the thing the profile was always a proxy for.
#
# `.osrm.cell_metrics`, not `.osrm`: it is written by `osrm-customize`, the LAST
# of the three preprocessing steps. A half-finished build leaves `.osrm` and
# `.osrm.ebg` behind, and `osrm-routed --algorithm mld` cannot start from those --
# so testing for `.osrm` would start a container that crash-loops, which is the
# failure the profile existed to prevent.
#
# The filename matches the `command:` on the osrm service in docker-compose.yml.
# Change one and change the other.
$osrmGraph = Join-Path $Root 'osrm-data\bangladesh-latest.osrm.cell_metrics'
$osrmReady = Test-Path $osrmGraph
$withOsrm = $false

if ($NoOsrm) {
    Warn "skipping the routing engine (-NoOsrm); routes will use the public demo server"
} elseif ($Osrm -or $osrmReady) {
    $withOsrm = $true
    if (-not $osrmReady) {
        Warn "-Osrm given but the graph looks unbuilt; the container may crash-loop"
    }
} else {
    Warn "no local routing graph in osrm-data\ - routes will fall back to the public"
    Warn "demo server (slower, rate-limited, and no detour alternatives)."
    Warn "Build it once: see the osrm service in docker-compose.yml."
}

$composeArgs = @('compose')
if ($withOsrm) { $composeArgs += @('--profile', 'osrm') }
$composeArgs += @('up', '-d')
if ($Rebuild) { $composeArgs += '--build' }

Say "    docker $($composeArgs -join ' ')"
Say "    (first build pulls torch and friends - 5-12 minutes, then cached)"
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { Die "docker compose up failed. See the output above." }

# -----------------------------------------------------------------------------
# 4. Wait for /health
# -----------------------------------------------------------------------------
Step "Waiting for the API"
Say "    importing torch, mediapipe, cv2 and transformers takes 15-40s on a cold start"

$healthy = $false
foreach ($i in 1..60) {
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }

    # Stop waiting if the container has died - otherwise this spins for a minute
    # on an error that is already in the logs.
    $state = (docker inspect -f '{{.State.Status}}' meridian-api 2>$null)
    if ($state -and $state -ne 'running') {
        Say ""
        Warn "container is '$state' - last 40 log lines:"
        docker compose logs --tail=40 api
        Die "API container stopped. The usual cause is a bad value in backend\.env."
    }
    Start-Sleep -Seconds 2
    if ($i % 5 -eq 0) { Say "    still waiting... ($($i * 2)s)" }
}

if (-not $healthy) {
    Warn "No healthy response after 120s. Last 40 log lines:"
    docker compose logs --tail=40 api
    Die "API did not become healthy."
}
Ok "API healthy at http://localhost:8000"
Ok "docs           http://localhost:8000/api/docs"
Ok "from a phone   http://${lanIp}:8000/api/v1"

# -----------------------------------------------------------------------------
# 4b. Which routing engine actually answered
# -----------------------------------------------------------------------------
# Said out loud, because the alternative is finding out from a caveat on a route
# card three days later. The backend's fallback to the public demo server is
# deliberate and loud in the LOGS; this puts it where someone starting the stack
# will actually see it.
#
# A real query rather than a container-status check: `osrm-routed` accepts
# connections before its graph is fully mapped, so "the container is up" and
# "routing works" are not the same statement. The two points are on Mirpur Road.
if ($withOsrm) {
    $probe = 'http://localhost:5000/route/v1/driving/90.3654,23.8041;90.3712,23.8103?overview=false'
    $routedLocally = $false
    foreach ($i in 1..15) {
        try {
            $r = Invoke-RestMethod -Uri $probe -TimeoutSec 3
            if ($r.code -eq 'Ok') { $routedLocally = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if ($routedLocally) {
        Ok "routing        local engine (osrm-data\bangladesh-latest)"
    } else {
        Warn "the osrm container did not answer in 30s. Routes will fall back to the"
        Warn "public demo server, and route cards will say so. Logs:"
        Warn "    docker compose --profile osrm logs --tail=40 osrm"
    }
} else {
    Warn "routing        public demo server (router.project-osrm.org)"
}

if ($BackendOnly) {
    Say ""
    Say "Backend only. Start the app yourself with:"
    Say "    cd frontend; npx expo start --clear --dev-client --scheme meridian"
    Say ""
    exit 0
}

# -----------------------------------------------------------------------------
# 5. Frontend
# -----------------------------------------------------------------------------
Step "Frontend"

if (-not (Test-Path "$Root\frontend\node_modules")) {
    Warn "node_modules missing - running npm install (a few minutes, once)"
    Push-Location "$Root\frontend"
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { Pop-Location; Die "npm install failed." }
    Pop-Location
    Ok "dependencies installed"

    if (-not (Test-Path "$Root\frontend\package-lock.json")) {
        Warn "package-lock.json still absent - nothing to commit?"
    } else {
        Warn "COMMIT frontend/package-lock.json so both machines resolve the same tree."
    }
}

$nodeMajor = (node --version) -replace '^v(\d+).*', '$1'
if ([int]$nodeMajor -gt 22) {
    Warn "Node $nodeMajor detected. Expo SDK 54 targets Node 20/22."
    Warn "If Metro misbehaves, install Node 22 LTS before blaming the code."
}

# -----------------------------------------------------------------------------
# 5a. The phone
# -----------------------------------------------------------------------------
# Expo Go cannot run this app any more. Background geofencing, on-device speech
# recognition and notification channels are all native, so the phone runs a
# locally built dev build and reaches Metro over USB.
#
# Three things have to be true, and each fails with a symptom pointing
# somewhere else:
#
#   a device is attached      -> "no devices/emulators found", from gradle
#   the APK matches app.json  -> a native module is missing at runtime, which
#                                surfaces as "undefined is not a function"
#   adb reverse maps 8081     -> red screen, "could not connect to the
#                                development server"
#
# So all three are checked here instead of being discovered one at a time.
Step "Android device"

$package = 'com.Meridian.app'
$device = $null

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    Warn "adb is not on PATH. Add this, then open a new terminal:"
    Say  "        %LOCALAPPDATA%\Android\Sdk\platform-tools"
} else {
    $device = (adb devices) |
        Where-Object { $_ -match '^(\S+)\s+device$' } |
        ForEach-Object { $Matches[1] } |
        Select-Object -First 1

    if (-not $device) {
        # 'unauthorized' is its own state with its own fix: the phone is seen,
        # but it has not accepted this computer's key.
        $pending = (adb devices) | Where-Object { $_ -match '\s+(unauthorized|offline)$' }
        if ($pending) {
            Warn "A phone is attached but not usable yet:"
            $pending | ForEach-Object { Say "        $_" }
            Warn "Unlock it and accept the 'Allow USB debugging' prompt."
        } else {
            Warn "No phone attached. Plug one in with USB debugging on."
        }
    } else {
        Ok "device $device"
    }
}

# Metro already listening is the trap worth failing on. A second bundler moves
# to 8082, adb reverse maps 8081 only, and the app then cannot find a bundle at
# all - which looks nothing like "you have two bundlers running".
# The test is "is anything listening", not "does Metro answer". A bundler whose
# file watcher died - which is what happens when node_modules or android/ is
# replaced underneath it - keeps the socket and answers nothing at all. That
# passed a /status check, and then `expo start` found the port taken and offered
# to move to 8082, which adb reverse does not map. The symptom is a red screen
# on a phone that is wired up correctly.
$holder = Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($holder) {
    $owner = (Get-Process -Id $holder.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    $alive = $false
    try {
        $metro = Invoke-WebRequest -Uri 'http://localhost:8081/status' -TimeoutSec 3 -UseBasicParsing
        $alive = $metro.Content -match 'packager-status:running'
    } catch { }
    if ($alive) {
        Die "Metro is already running on port 8081 (pid $($holder.OwningProcess), $owner).`n         Stop it with Ctrl+C in its terminal, then run this again."
    }
    Die "Port 8081 is held by pid $($holder.OwningProcess) ($owner), which is not`n         answering as a bundler - a wedged Metro, most likely.`n         Stop it:  Stop-Process -Id $($holder.OwningProcess) -Force`n         Then run this again. Letting Expo move to 8082 would break adb reverse."
}

# -----------------------------------------------------------------------------
# 5b. Build only when the native side has actually moved
# -----------------------------------------------------------------------------
# The stamp is a hash of app.json and package.json - between them, every input
# that changes the APK: plugins, permissions, the bundle id, the native
# dependency list. JS is deliberately not in it, because JS comes from Metro
# and never needs a rebuild.
#
# It over-triggers slightly (editing a scripts entry in package.json counts),
# and that is the right way round: a needless three-minute build is an
# annoyance, a skipped one is half an hour spent debugging a native module that
# was never in the APK.
$stampFile = "$Root\frontend\android\.meridian-build-stamp"

function Get-NativeStamp {
    $text = ''
    foreach ($f in @('app.json', 'package.json')) {
        $text += (Get-Content "$Root\frontend\$f" -Raw)
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $hash = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text))
    return ([System.BitConverter]::ToString($hash)).Replace('-', '')
}

$stamp = Get-NativeStamp
$needsBuild = $false
$reason = ''

if ($Build) {
    $needsBuild = $true; $reason = '-Build was passed'
} elseif (-not (Test-Path "$Root\frontend\android")) {
    $needsBuild = $true; $reason = 'there is no native project yet'
} elseif ($device -and -not ((adb -s $device shell pm list packages $package) -match $package)) {
    $needsBuild = $true; $reason = "$package is not installed on this phone"
} elseif (-not (Test-Path $stampFile)) {
    $needsBuild = $true; $reason = 'no build stamp, so what is installed is unknown'
} elseif ((Get-Content $stampFile -Raw).Trim() -ne $stamp) {
    $needsBuild = $true; $reason = 'app.json or package.json changed since the last build'
}

if ($needsBuild -and -not $device) {
    Warn "A build is needed ($reason) but no phone is attached."
    Warn "Metro will still start. Plug the phone in and re-run to build."
} elseif ($needsBuild) {
    Step "Building the app"
    Say  "    reason: $reason"
    Say  "    2-6 minutes cold, under a minute once gradle has its cache"
    Say  ""
    Set-Location "$Root\frontend"
    # app.json is half the build stamp - but `expo run:android` only runs
    # prebuild when the android/ folder is MISSING (ensureNativeProject.js in
    # @expo/cli checks nothing else). With the folder present it compiles
    # whatever AndroidManifest.xml is already on disk, so a change to app.json
    # would trigger a rebuild here and then not be in the APK that came out of
    # it. That is worse than not rebuilding at all: the stamp would say the
    # phone matches app.json while it did not.
    #
    # Safe to re-run. android/ is gitignored and generated in full from app.json
    # plus the config plugins - `git log` shows no hand edit has ever landed in
    # it. --no-install because installing packages is not this script's job and
    # doubles the time.
    npx expo prebuild --platform android --no-install
    if ($LASTEXITCODE -ne 0) {
        Set-Location $Root
        Die "expo prebuild failed. A bad value in app.json is the usual cause."
    }
    # --no-bundler: build and install only. Metro starts once, below, by the
    # same path a no-build run uses - one way the dev server gets started
    # rather than two that can drift apart.
    npx expo run:android --no-bundler
    if ($LASTEXITCODE -ne 0) {
        Set-Location $Root
        Die "the Android build failed. The gradle output above says why."
    }
    Set-Location $Root
    # Written only after a build that actually succeeded.
    Set-Content -Path $stampFile -Value $stamp -Encoding ascii
    # `expo run:android` launches the app as soon as it is installed, which is
    # before Metro exists on this path - so the app comes up on the red "could
    # not connect" screen and stays there. Closing it here lets the launcher
    # job below start it once, cleanly, with a bundler to talk to.
    adb -s $device shell am force-stop $package | Out-Null
    Ok "built, installed, stamped"
} else {
    Ok "the installed app matches app.json - no build needed"
}

# Idempotent, and re-asserted on every run on purpose: the mapping lives in the
# adb session, so unplugging the phone silently loses it.
if ($device) {
    adb -s $device reverse tcp:8081 tcp:8081 | Out-Null
    Ok "adb reverse: the phone's 8081 -> this machine"
}

# -----------------------------------------------------------------------------
# 6. Metro
# -----------------------------------------------------------------------------
Step "Starting Expo"
Say "    API for the app: $env:EXPO_PUBLIC_API_BASE_URL"
Say "    --clear is used because EXPO_PUBLIC_* is inlined at bundle time"
Say "    --dev-client is why 'a' and the QR open Meridian and not Expo Go"
Say "    --scheme meridian is named because ios/ has no scheme to agree with"
Say ""

if ($device) {
    Say "    Meridian opens on $device by itself once Metro is ready."

    # Metro holds the terminal, so the launch cannot come after it. A job that
    # waits for the bundler and then starts the app is the whole reason this is
    # one command rather than two things to remember.
    Start-Job -ArgumentList $package -ScriptBlock {
        param($pkg)
        foreach ($i in 1..90) {
            try {
                $r = Invoke-WebRequest -Uri 'http://localhost:8081/status' -TimeoutSec 2 -UseBasicParsing
                if ($r.Content -match 'packager-status:running') { break }
            } catch { }
            Start-Sleep -Seconds 1
        }
        # Expo Go, closed first. It is still installed, it still claims the
        # `exp://` scheme, and `launchMode="singleTask"` means a foregrounded
        # Expo Go is simply what the phone shows - so the launch below would
        # put Meridian behind it. A no-op when it is not running.
        adb shell am force-stop host.exp.exponent
        # monkey, not am start: it finds the launcher activity itself, so this
        # does not have to know the activity's name or follow it if it changes.
        adb shell monkey -p $pkg -c android.intent.category.LAUNCHER 1
    } | Out-Null
}

Say "    Ctrl+C stops Expo; the containers keep running (.\scripts\run.ps1 -Down stops them)."
Say ""

Set-Location "$Root\frontend"
# --dev-client, and it is not optional.
#
# Expo Go cannot run this app - the native modules are not in it - but the CLI
# does not know that. Left to itself it targets Expo Go, so pressing `a` ran
#
#     am start -a android.intent.action.VIEW -d exp://192.168.0.187:8081
#
# which opened Expo Go over the top of the dev build that was already running
# correctly, and filled the log with "Android Push notifications ... removed
# from Expo Go with the release of SDK 53". It looked exactly like the app was
# broken.
#
# --dev-client switches the target (resolveOptions.js: a literal flag wins over
# the expo-dev-client dependency check, so the package does not have to be
# installed). The URL becomes `meridian://expo-development-client/?url=...`,
# which is why app.json now sets `"scheme": "meridian"` - without a scheme
# `constructDevClientUrl` returns null and the CLI falls back to opening the
# http URL in a browser. The scheme reaches the manifest through the prebuild
# above; the `?url=` is ignored by a build with no dev-client package in it,
# which is harmless, because such a build reads Metro off localhost:8081 anyway.
#
# --scheme is named rather than inferred. `resolveSchemeAsync` otherwise asks
# for a scheme that the ios/ AND android/ projects BOTH declare, and
# frontend/ios/ is left over from an old prebuild with no CFBundleURLSchemes in
# it - so the intersection is empty, the CLI warns "Could not find a shared URI
# scheme", and deep links are off again. A literal --scheme returns before that
# lookup runs, so what is or is not in ios/ stops mattering.
npx expo start --clear --dev-client --scheme meridian
