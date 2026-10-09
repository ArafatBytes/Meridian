#!/usr/bin/env bash
# =============================================================================
# Meridian — start everything  (macOS / Linux; see run.ps1 for Windows)
# =============================================================================
#   ./scripts/run.sh                backend in Docker + Expo on the host
#   ./scripts/run.sh --backend-only just the containers
#   ./scripts/run.sh --rebuild      force an image rebuild first
#   ./scripts/run.sh --osrm         also start the local routing engine
#   ./scripts/run.sh --down         stop everything
#   ./scripts/run.sh --logs         tail the backend log
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_ONLY=0; REBUILD=0; OSRM=0
for arg in "$@"; do
  case "$arg" in
    --backend-only) BACKEND_ONLY=1 ;;
    --rebuild)      REBUILD=1 ;;
    --osrm)         OSRM=1 ;;
    --down)         echo "==> Stopping"; docker compose --profile osrm --profile mobile down; exit 0 ;;
    --logs)         docker compose logs -f api; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[32m[ok]\033[0m %s\n' "$1"; }
warn() { printf '    \033[33m[!] \033[0m %s\n' "$1"; }
die()  { printf '\n    \033[31m[x] \033[0m %s\n\n' "$1"; exit 1; }

# -----------------------------------------------------------------------------
# 1. Preflight
# -----------------------------------------------------------------------------
step "Preflight"
command -v docker >/dev/null 2>&1 || die "Docker is not installed."
docker info >/dev/null 2>&1 || die "Docker is not running. Start it and try again."
ok "Docker is running"

[ -f backend/.env ]  || die "backend/.env is missing. Copy backend/.env.example.
         Guide: backend/migrations/supabase/README.md"
[ -f frontend/.env ] || die "frontend/.env is missing. Copy frontend/.env.example."
ok "env files present"

# Names only — never print values.
for key in DATABASE_URL JWT_SECRET_KEY; do
  grep -qE "^\s*${key}\s*=\s*\S" backend/.env || die "backend/.env is missing $key"
done
for key in EXPO_PUBLIC_SUPABASE_URL EXPO_PUBLIC_SUPABASE_ANON_KEY; do
  grep -qE "^\s*${key}\s*=\s*\S" frontend/.env || die "frontend/.env is missing $key"
done
ok "required keys present"

DB_LINE="$(grep -E '^\s*DATABASE_URL\s*=' backend/.env | tail -1 || true)"
case "$DB_LINE" in
  *+asyncpg*) ;;
  *) die "DATABASE_URL must use the asyncpg driver: postgresql+asyncpg://...
         The async engine cannot start without it." ;;
esac
case "$DB_LINE" in
  *:6543/*)
    warn "DATABASE_URL uses port 6543 (PgBouncer, transaction mode)."
    warn "asyncpg's prepared-statement cache breaks against it, intermittently."
    warn "Use port 5432 (session pooler) instead." ;;
esac

# -----------------------------------------------------------------------------
# 2. LAN IP
# -----------------------------------------------------------------------------
step "Network"
# HOST_LAN_IP is honoured when you set it, and detection runs otherwise.
#
# The PowerShell twin needs extra care here and this does not: `export` lives in
# this subshell and dies with it, so a second run cannot inherit the first run's
# address. In PowerShell `$env:` changes persist for the whole session, which
# made re-running it in the same window pin a stale IP. See run.ps1.
LAN_IP="${HOST_LAN_IP:-}"
if [ -z "$LAN_IP" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
  else
    LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || true)"
  fi
fi
if [ -z "$LAN_IP" ]; then
  warn "Could not detect a LAN IP. Falling back to localhost — a physical phone will NOT connect."
  warn "Set it manually:  export HOST_LAN_IP=192.168.x.x"
  LAN_IP=127.0.0.1
else
  ok "LAN IP: $LAN_IP"
  # EXPO_PUBLIC_* values are inlined into the bundle at build time, so a cached
  # Metro bundle keeps calling the previous address however many times you
  # restart or rescan the QR. Switching networks needs the cache cleared.
  printf '        if you changed networks since the last run: cd frontend && npx expo start -c\n'
fi
export HOST_LAN_IP="$LAN_IP"
export EXPO_PUBLIC_API_BASE_URL="http://${LAN_IP}:8000/api/v1"

# -----------------------------------------------------------------------------
# 3. Containers
# -----------------------------------------------------------------------------
step "Backend"
ARGS=(compose)
[ "$OSRM" -eq 1 ] && ARGS+=(--profile osrm)
ARGS+=(up -d)
[ "$REBUILD" -eq 1 ] && ARGS+=(--build)

echo "    docker ${ARGS[*]}"
echo "    (first build pulls torch and friends — 5-12 minutes, then cached)"
docker "${ARGS[@]}" || die "docker compose up failed. See the output above."

# -----------------------------------------------------------------------------
# 4. Wait for /health
# -----------------------------------------------------------------------------
step "Waiting for the API"
echo "    importing torch, mediapipe, cv2 and transformers takes 15-40s on a cold start"
HEALTHY=0
for i in $(seq 1 60); do
  if curl -fsS --max-time 3 http://localhost:8000/health >/dev/null 2>&1; then
    HEALTHY=1; break
  fi
  STATE="$(docker inspect -f '{{.State.Status}}' meridian-api 2>/dev/null || true)"
  if [ -n "$STATE" ] && [ "$STATE" != running ]; then
    echo; warn "container is '$STATE' — last 40 log lines:"
    docker compose logs --tail=40 api
    die "API container stopped. The usual cause is a bad value in backend/.env."
  fi
  sleep 2
  [ $((i % 5)) -eq 0 ] && echo "    still waiting... ($((i * 2))s)"
done

if [ "$HEALTHY" -ne 1 ]; then
  warn "No healthy response after 120s. Last 40 log lines:"
  docker compose logs --tail=40 api
  die "API did not become healthy."
fi
ok "API healthy at http://localhost:8000"
ok "docs           http://localhost:8000/api/docs"
ok "from a phone   http://${LAN_IP}:8000/api/v1"

if [ "$BACKEND_ONLY" -eq 1 ]; then
  echo; echo "Backend only. Start the app yourself with:"
  echo "    cd frontend && npx expo start --clear"; echo
  exit 0
fi

# -----------------------------------------------------------------------------
# 5. Frontend
# -----------------------------------------------------------------------------
step "Frontend"
if [ ! -d frontend/node_modules ]; then
  warn "node_modules missing — running npm install (a few minutes, once)"
  (cd frontend && npm install --no-audit --no-fund) || die "npm install failed."
  ok "dependencies installed"
  [ -f frontend/package-lock.json ] && \
    warn "COMMIT frontend/package-lock.json so both machines resolve the same tree."
fi

NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
if [ "$NODE_MAJOR" -gt 22 ]; then
  warn "Node $NODE_MAJOR detected. Expo SDK 54 targets Node 20/22."
  warn "If Metro misbehaves, install Node 22 LTS before blaming the code."
fi

step "Starting Expo"
echo "    API for the app: $EXPO_PUBLIC_API_BASE_URL"
echo "    --clear is used because EXPO_PUBLIC_* is inlined at bundle time"
echo
echo "    Scan the QR code with Expo Go. Ctrl+C stops Expo;"
echo "    the containers keep running (./scripts/run.sh --down stops them)."
echo
cd frontend && npx expo start --clear
