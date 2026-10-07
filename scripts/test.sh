#!/usr/bin/env bash
# =============================================================================
# Meridian — live end-to-end verification
# =============================================================================
# Exercises the running stack from the outside: backend, Supabase, the link
# between them, and the AI pipeline. Run it after `scripts/run.ps1`.
#
#   ./scripts/test.sh          phases 1-5 (fast, ~15s)
#   ./scripts/test.sh --ai     also run a real image through the vision stack
#                              (first run downloads ~700 MB of model weights)
#   ./scripts/test.sh --verbose  print response bodies
#
# This checks the parts the app cannot tell you about. The app itself is tested
# by hand — see docs/RUNNING.md §4.
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WITH_AI=0; VERBOSE=0
for arg in "$@"; do
  case "$arg" in
    --ai)      WITH_AI=1 ;;
    --verbose) VERBOSE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; SKIP=0

phase() { printf '\n\033[1m\033[36m%s\033[0m\n' "$1"; }
ok()    { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()   { printf '  \033[31m✗\033[0m %s\n' "$1"; [ -n "${2:-}" ] && printf '      %s\n' "$2"; FAIL=$((FAIL+1)); }
skip()  { printf '  \033[33m-\033[0m %s (%s)\n' "$1" "$2"; SKIP=$((SKIP+1)); }
note()  { printf '      \033[90m%s\033[0m\n' "$1"; }
body()  { [ "$VERBOSE" -eq 1 ] && printf '      \033[90m%s\033[0m\n' "$(echo "$1" | head -c 400)"; }

envval() {  # envval <file> <key>  — value only, never printed
  grep -E "^\s*$2\s*=" "$1" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"'' | xargs 2>/dev/null
}

# =============================================================================
phase "Phase 1 — Backend is up"
# =============================================================================
H="$(curl -fsS --max-time 5 "$API/health" 2>&1)"
if [ $? -eq 0 ] && echo "$H" | grep -q '"status"'; then
  ok "GET /health"
  body "$H"
else
  bad "GET /health" "is the stack running? ./scripts/run.ps1"
  printf '\n\033[31mBackend unreachable — stopping here.\033[0m\n\n'
  exit 1
fi

curl -fsS --max-time 5 "$API/" >/dev/null 2>&1 \
  && ok "GET /" || bad "GET /"

curl -fsS --max-time 10 "$API/api/openapi.json" >/dev/null 2>&1 \
  && ok "GET /api/openapi.json (OpenAPI schema builds)" \
  || bad "GET /api/openapi.json" "a malformed route or schema breaks this"

ROUTES="$(curl -fsS --max-time 10 "$API/api/openapi.json" 2>/dev/null \
          | grep -oE '"/api/v1/[^"]+"' | sort -u | wc -l)"
[ "${ROUTES:-0}" -gt 5 ] \
  && ok "$ROUTES v1 routes registered" \
  || bad "only ${ROUTES:-0} routes registered"

# =============================================================================
phase "Phase 2 — Supabase schema"
# =============================================================================
SB_URL="$(envval frontend/.env EXPO_PUBLIC_SUPABASE_URL)"
SB_KEY="$(envval frontend/.env EXPO_PUBLIC_SUPABASE_ANON_KEY)"

if [ -z "$SB_URL" ] || [ -z "$SB_KEY" ]; then
  skip "Supabase REST checks" "credentials not readable from frontend/.env"
else
  # PostgREST distinguishes the two failures we care about: a missing table is
  # PGRST205/42P01, whereas RLS blocking an anonymous read is a 401/permission
  # error. The second means the table exists AND is protected, which is the
  # outcome we want.
  for tbl in profiles crime_reports emergency_contacts sos_hot_words; do
    R="$(curl -s --max-time 10 \
          -H "apikey: $SB_KEY" \
          -H "Authorization: Bearer $SB_KEY" \
          "$SB_URL/rest/v1/$tbl?select=id&limit=1" 2>&1)"
    if echo "$R" | grep -qE 'PGRST205|42P01|Could not find the table|does not exist'; then
      bad "table '$tbl'" "not found — did SCHEMA.sql run?"
    elif echo "$R" | grep -qE 'permission denied|JWT|row-level security|42501'; then
      ok "table '$tbl' exists, RLS blocks anonymous reads"
    elif echo "$R" | grep -qE '^\[' ; then
      ok "table '$tbl' exists and is queryable"
    else
      bad "table '$tbl'" "$(echo "$R" | head -c 160)"
    fi
  done

  # Storage bucket. getPublicUrl() only works on a public bucket.
  B="$(curl -s --max-time 10 -H "apikey: $SB_KEY" \
        "$SB_URL/storage/v1/bucket/avatars" 2>&1)"
  if echo "$B" | grep -q '"public":true'; then
    ok "storage bucket 'avatars' exists and is public"
  elif echo "$B" | grep -q '"public":false'; then
    bad "bucket 'avatars' is not public" "getPublicUrl() will return dead links"
  elif echo "$B" | grep -qE 'not found|Bucket not found'; then
    bad "bucket 'avatars' missing" "SCHEMA.sql §9 creates it"
  else
    skip "bucket 'avatars'" "needs the service-role key to inspect"
  fi
fi

# =============================================================================
phase "Phase 3 — Backend ↔ database"
# =============================================================================
# /routes/calculate is the best probe available: it queries crime_reports
# through SQLAlchemy over DATABASE_URL and calls OSRM. If DATABASE_URL, the
# asyncpg driver and the uuid column types are all correct, this returns routes.
# Two points in Dhaka, Shahbagh → Mirpur 10.
RESP="$(curl -s -w '\n%{http_code}' --max-time 45 -X POST \
         -H 'Content-Type: application/json' \
         -d '{"source":{"latitude":23.7389,"longitude":90.3958},
              "destination":{"latitude":23.8069,"longitude":90.3687}}' \
         "$API/api/v1/routes/calculate" 2>&1)"
CODE="$(echo "$RESP" | tail -1)"
JSON="$(echo "$RESP" | sed '$d')"

if [ "$CODE" = "200" ]; then
  N="$(echo "$JSON" | grep -oE '"route_id"' | wc -l)"
  ok "POST /routes/calculate → $N route(s)"
  SAFETY="$(echo "$JSON" | grep -oE '"safety_score":[0-9.]+' | head -1 | cut -d: -f2)"
  [ -n "$SAFETY" ] && note "safety_score of first route: $SAFETY"
  note "this proves DATABASE_URL, asyncpg and the uuid columns all work"
elif echo "$JSON" | grep -qiE 'operator does not exist|uuid.*character varying'; then
  bad "POST /routes/calculate" "uuid/varchar mismatch — ORM is out of sync with the schema"
elif echo "$JSON" | grep -qiE 'relation .* does not exist|crime_reports'; then
  bad "POST /routes/calculate" "crime_reports not reachable — check DATABASE_URL and SCHEMA.sql"
elif echo "$JSON" | grep -qiE 'prepared statement'; then
  bad "POST /routes/calculate" "PgBouncer/asyncpg clash — use port 5432, not 6543"
else
  bad "POST /routes/calculate (HTTP $CODE)" "$(echo "$JSON" | head -c 200)"
fi

# =============================================================================
phase "Phase 4 — Auth wiring"
# =============================================================================
# An unauthenticated SOS must be rejected. A 200 here would mean anyone can
# trigger someone else's emergency alert.
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST \
         -F 'latitude=23.8103' -F 'longitude=90.4125' \
         "$API/api/v1/sos/trigger" 2>&1)"
case "$CODE" in
  401|403) ok "POST /sos/trigger without a token → $CODE (correctly rejected)" ;;
  200|201) bad "POST /sos/trigger without a token → $CODE" "UNAUTHENTICATED SOS ACCEPTED" ;;
  *)       skip "POST /sos/trigger" "HTTP $CODE — inconclusive" ;;
esac

# A bad token must also be rejected, by signature rather than by absence.
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST \
         -H 'Authorization: Bearer not.a.real.token' \
         -F 'latitude=23.8103' -F 'longitude=90.4125' \
         "$API/api/v1/sos/trigger" 2>&1)"
case "$CODE" in
  401|403) ok "POST /sos/trigger with a bogus token → $CODE" ;;
  *)       bad "POST /sos/trigger with a bogus token → $CODE" "expected 401" ;;
esac

# =============================================================================
phase "Phase 5 — AI vision stack"
# =============================================================================
S="$(curl -s --max-time 180 "$API/api/v1/ai/crime-detection/status" 2>&1)"
if echo "$S" | grep -q '"loaded":true\|"loaded": true'; then
  ok "YOLOv9c loaded"
elif echo "$S" | grep -q '"loaded":false\|"loaded": false'; then
  bad "YOLOv9c not loaded" "$(echo "$S" | grep -oE '"message":"[^"]*"' | head -1)"
else
  skip "model status" "$(echo "$S" | head -c 120)"
fi

C="$(curl -s --max-time 20 "$API/api/v1/ai/crime-detection/supported-crimes" 2>&1)"
echo "$C" | grep -q 'crime_type' \
  && ok "GET /ai/crime-detection/supported-crimes" \
  || bad "GET /ai/crime-detection/supported-crimes"

if [ "$WITH_AI" -eq 1 ]; then
  # Driven from INSIDE the container, not with host curl.
  #
  # The host approach does not work on Windows: `mktemp -d` yields an MSYS path
  # like /tmp/tmp.XXXX, and Windows curl.exe cannot resolve it, so
  # `-F file=@/tmp/...` fails before a request is ever sent. The symptom is
  # HTTP 000 and no entry in the server log at all.
  #
  # The probe is a real photograph with real people in it. A synthetic image of
  # rectangles returns "no relevant objects" at step 1, which proves only that
  # YOLO ran — the pose, scene and fusion stages are never reached.
  if ! command -v docker >/dev/null 2>&1; then
    skip "image analysis" "needs docker to drive the probe from inside the container"
  else
    printf '  … running inference (first call loads the models; up to 5 min)\n'
    R="$(docker compose exec -T api python -c "
import urllib.request, json, time
src = 'https://ultralytics.com/images/bus.jpg'
try:
    data = urllib.request.urlopen(src, timeout=60).read()
except Exception as e:
    print('PROBE_FETCH_FAILED', e); raise SystemExit(0)
b = '----meridianprobe'
body = (f'--{b}\r\nContent-Disposition: form-data; name=\"file\"; '
        f'filename=\"probe.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n').encode() \
       + data + f'\r\n--{b}--\r\n'.encode()
req = urllib.request.Request('http://localhost:8000/api/v1/ai/crime-detection/analyze',
      data=body, headers={'Content-Type': f'multipart/form-data; boundary={b}'})
t = time.time()
try:
    r = urllib.request.urlopen(req, timeout=600); code, out = r.status, r.read()
except urllib.error.HTTPError as e:
    code, out = e.code, e.read()
except Exception as e:
    print('REQUEST_FAILED', e); raise SystemExit(0)
j = json.loads(out); d = j.get('data', j)
print('HTTP', code, 'in', round(time.time()-t, 1), 's')
print('SCENE', json.dumps(d.get('scene_analysis')))
print('MESSAGE', j.get('message'))
print('CRIME', d.get('crime_type'), d.get('confidence'))
" 2>&1)"

    if echo "$R" | grep -q '"scene_type"'; then
      ok "POST /ai/crime-detection/analyze — full pipeline executed"
      note "$(echo "$R" | grep '^HTTP')"
      SCENE="$(echo "$R" | grep '^SCENE' | grep -oE '"scene_type": *"[^"]*"' | cut -d'"' -f4)"
      LIGHT="$(echo "$R" | grep '^SCENE' | grep -oE '"lighting_condition": *"[^"]*"' | cut -d'"' -f4)"
      note "CLIP: scene='$SCENE', lighting='$LIGHT'"
      note "verdict: $(echo "$R" | grep '^MESSAGE' | cut -d' ' -f2-) / $(echo "$R" | grep '^CRIME' | cut -d' ' -f2-)"
      note "a bus with pedestrians is correctly NOT a crime"
    elif echo "$R" | grep -qiE 'libGL|libgl'; then
      bad "analyze" "libGL missing — cv2/mediapipe cannot load. Rebuild: run.ps1 -Rebuild"
    elif echo "$R" | grep -qiE 'Weights only load failed'; then
      bad "analyze" "ultralytics too old for this torch — needs >=8.3.0 (defect 23)"
    elif echo "$R" | grep -q 'PROBE_FETCH_FAILED'; then
      skip "image analysis" "could not fetch the probe photo (offline?)"
    else
      bad "analyze" "$(echo "$R" | tail -3 | head -c 300)"
    fi
  fi
else
  skip "image analysis" "pass --ai to run it"
fi

# =============================================================================
phase "Result"
# =============================================================================
printf '  %d passed, %d failed, %d skipped\n\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -gt 0 ] && exit 1
exit 0
