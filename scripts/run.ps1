# =============================================================================
# Meridian - start everything
# =============================================================================
#   .\scripts\run.ps1               backend in Docker + Expo on the host
#   .\scripts\run.ps1 -BackendOnly  just the containers
#   .\scripts\run.ps1 -Rebuild      force an image rebuild first
#   .\scripts\run.ps1 -Osrm         also start the local routing engine
#   .\scripts\run.ps1 -Down         stop everything
#   .\scripts\run.ps1 -Logs         tail the backend log
#
# Expo runs on the host rather than in a container on purpose - see the comment
# on the `expo` service in docker-compose.yml. The three reasons are broken file
# watching over bind mounts, host-addressing for the phone, and native builds
# needing the host SDKs anyway.
# =============================================================================

[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$Rebuild,
    [switch]$Osrm,
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
    Say  "    cd frontend; npx expo start -c"
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

$composeArgs = @('compose')
if ($Osrm) { $composeArgs += @('--profile', 'osrm') }
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

if ($BackendOnly) {
    Say ""
    Say "Backend only. Start the app yourself with:"
    Say "    cd frontend; npx expo start --clear"
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

Step "Starting Expo"
Say "    API for the app: $env:EXPO_PUBLIC_API_BASE_URL"
Say "    --clear is used because EXPO_PUBLIC_* is inlined at bundle time"
Say ""
Say "    Scan the QR code with Expo Go. Ctrl+C stops Expo;"
Say "    the containers keep running (.\scripts\run.ps1 -Down stops them)."
Say ""

Set-Location "$Root\frontend"
npx expo start --clear
