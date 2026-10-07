#!/usr/bin/env bash
# =============================================================================
# Meridian — Prototype Gate check 4
# =============================================================================
# The scripted demo for every sprint shipped so far.
#
# Rule 2 of the relay model says every push is a working prototype. This file is
# where that claim becomes falsifiable: each sprint appends a function asserting
# what it promised, and all of them run on every handoff. A sprint that breaks
# an earlier sprint's demo is caught here rather than by your partner.
#
#   ./scripts/smoke.sh          run every sprint's demo
#   ./scripts/smoke.sh S01      run one sprint's demo
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ONLY="${1:-}"
FAILED=()

bold()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()    { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()   { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED+=("$1"); }

# assert <description> <command...>
assert() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi
}

# refute <description> <command...>   — passes when the command FAILS
refute() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then bad "$desc"; else ok "$desc"; fi
}

# =============================================================================
# S01 — Unblock the repository
# Promise: a clean clone builds, and no secret is trackable.
# =============================================================================
demo_S01() {
  bold "S01 — clean clone builds, no secrets trackable"

  # The defect that made the repo unbuildable: frontend/src/lib was matched by a
  # bare `lib/` ignore rule, so the Supabase client was never committed.
  refute "frontend/src/lib/supabase.ts is NOT gitignored" \
    git check-ignore -q frontend/src/lib/supabase.ts
  assert "frontend/src/lib/supabase.ts exists" \
    test -f frontend/src/lib/supabase.ts
  assert "frontend/src/lib/supabase-storage.ts exists" \
    test -f frontend/src/lib/supabase-storage.ts
  assert "supabase.ts is tracked by git" \
    git ls-files --error-unmatch frontend/src/lib/supabase.ts

  # Python build artifacts must still be ignored — the fix anchored the rule
  # rather than deleting it.
  assert "backend/lib/ is still gitignored" \
    git check-ignore -q backend/lib/site-packages/x.py

  # .env IS committed, by decision (S02 handoff note): the repo is private and
  # syncing env files across two machines by hand was costing more than it
  # saved. So these assert the opposite of what they did on 2026-10-07.
  #
  # What is still checked is that the files exist and carry the keys the app
  # cannot start without — a committed .env that is missing DATABASE_URL fails
  # just as hard as an absent one, and now fails for both of us at once.
  assert "backend/.env exists"  test -f backend/.env
  assert "frontend/.env exists" test -f frontend/.env
  for k in DATABASE_URL JWT_SECRET_KEY; do
    assert "backend/.env has $k"  grep -qE "^\s*$k\s*=\s*\S" backend/.env
  done
  for k in EXPO_PUBLIC_SUPABASE_URL EXPO_PUBLIC_SUPABASE_ANON_KEY; do
    assert "frontend/.env has $k" grep -qE "^\s*$k\s*=\s*\S" frontend/.env
  done
  # The async engine cannot start without the driver suffix, and this is the
  # single most common way to break the backend.
  assert "DATABASE_URL uses the asyncpg driver" \
    grep -qE '^\s*DATABASE_URL\s*=.*\+asyncpg' backend/.env

  # Templates must stay committed whatever the .env policy is — they are the
  # only record of which variables exist.
  assert "backend/.env.example tracked" \
    git ls-files --error-unmatch backend/.env.example
  assert "frontend/.env.example tracked" \
    git ls-files --error-unmatch frontend/.env.example

  # A .env in a private repo is still a .env in a Docker build context.
  assert "backend/.dockerignore excludes .env" \
    grep -qE '^\.env$' backend/.dockerignore
  assert "frontend/.dockerignore excludes .env" \
    grep -qE '^\.env$' frontend/.dockerignore

  # Secrets are no longer hardcoded in the committed Expo config.
  refute "no Supabase URL hardcoded in app.json" \
    grep -q "supabase.co" frontend/app.json
  refute "no JWT literal hardcoded in app.json" \
    grep -q "eyJhbGciOi" frontend/app.json
  assert "supabase.ts reads config from the environment" \
    grep -q "EXPO_PUBLIC_SUPABASE_URL" frontend/src/lib/supabase.ts

  # Env templates exist and are complete enough to actually boot the app.
  assert "frontend/.env.example exists" test -f frontend/.env.example
  assert "backend/.env.example exists"  test -f backend/.env.example
  assert "backend template has SMTP_USER (SOS needs it)" \
    grep -q "^SMTP_USER=" backend/.env.example
  assert "backend template has SUPABASE_URL" \
    grep -q "^SUPABASE_URL=" backend/.env.example

  # The fresh-start schema the app runs on.
  assert "SCHEMA.sql exists" test -f backend/migrations/supabase/SCHEMA.sql
  assert "VERIFY.sql exists" test -f backend/migrations/supabase/VERIFY.sql
  assert "RESET.sql exists"  test -f backend/migrations/supabase/RESET.sql
  for t in profiles crime_reports emergency_contacts sos_hot_words; do
    assert "schema creates $t" \
      grep -q "create table if not exists public.$t" backend/migrations/supabase/SCHEMA.sql
  done
  assert "schema enables RLS on every table" \
    bash -c "[ \$(grep -c 'enable row level security' backend/migrations/supabase/SCHEMA.sql) -eq 7 ]"
  assert "schema creates the avatars bucket" \
    grep -q "storage.buckets" backend/migrations/supabase/SCHEMA.sql

  # ORM ids are uuid, matching the schema's FKs to auth.users. With String
  # columns, every backend lookup by user id raises
  # `operator does not exist: uuid = character varying` — i.e. SOS breaks.
  assert "ORM uses UUIDStr for ids" \
    bash -c "[ \$(grep -lc 'UUIDStr' backend/app/models/*.py | wc -l) -ge 5 ]"
  refute "no String-typed primary keys remain" \
    grep -q "Column(String, primary_key" backend/app/models/crime.py
  # types.py would shadow the stdlib `types` module; columns.py does not.
  assert "shared column types live in columns.py" \
    test -f backend/app/models/columns.py
  refute "no app/models/types.py (stdlib shadow)" \
    test -f backend/app/models/types.py

  # Superseded migrations moved aside so nobody runs the wrong one.
  refute "old create_users_table.sql not in migrations root" \
    test -f backend/migrations/create_users_table.sql
  assert "superseded migrations archived" \
    test -f backend/migrations/_superseded/README.md

  # The relay machinery itself.
  assert "PROGRESS.md exists"           test -f PROGRESS.md
  assert "IMPLEMENTATION_PLAN.md exists" test -f IMPLEMENTATION_PLAN.md
  assert "CONTRIBUTING.md exists"       test -f CONTRIBUTING.md
  assert "CI workflow exists"           test -f .github/workflows/ci.yml

  # The real test: does it compile? Only meaningful once deps are installed.
  if [ -d frontend/node_modules ]; then
    assert "frontend typechecks" \
      bash -c "cd '$ROOT/frontend' && npx tsc --noEmit"
  else
    printf '  \033[33m-\033[0m frontend typecheck skipped (run: cd frontend && npm ci)\n'
  fi
}

# =============================================================================
# S01b — Dockerised stack
# Promise: `docker compose up` gives a healthy API; one command starts both
# halves. Static checks only — the live checks are in `scripts/test.sh`.
# =============================================================================
demo_S01b() {
  bold "S01b — one-command stack"

  assert "root docker-compose.yml exists" test -f docker-compose.yml
  assert "backend Dockerfile exists"      test -f backend/Dockerfile
  assert "backend/.dockerignore exists"   test -f backend/.dockerignore
  assert "frontend/.dockerignore exists"  test -f frontend/.dockerignore
  assert "run.ps1 exists"                 test -f scripts/run.ps1
  assert "run.sh exists"                  test -f scripts/run.sh
  assert "run.sh is valid bash"           bash -n scripts/run.sh

  # The old backend/docker-compose.yml provisioned a Postgres that competes
  # with Supabase and a Celery beat that crashes on two phantom modules.
  refute "superseded backend/docker-compose.yml removed" \
    test -f backend/docker-compose.yml
  refute "no postgres service (the database is Supabase)" \
    grep -qE '^\s{2}postgres:' docker-compose.yml
  refute "no celery service (beat still points at phantom modules)" \
    grep -qE '^\s{2}celery' docker-compose.yml

  # Missing libgl1 is why `import cv2` and `import mediapipe` died at startup.
  assert "Dockerfile installs libgl1 (cv2/mediapipe need it)" \
    grep -q 'libgl1' backend/Dockerfile
  # The CUDA wheel is ~2.5 GB of GPU runtime that cannot be used here.
  assert "Dockerfile uses the CPU-only torch index" \
    grep -q 'download.pytorch.org/whl/cpu' backend/Dockerfile
  # The old healthcheck imported `requests`, which is not a dependency, so the
  # container was permanently 'unhealthy'.
  refute "healthcheck does not import requests" \
    grep -q 'import requests' backend/Dockerfile
  # ~700 MB of model weights must survive a container recreate.
  assert "model cache is a named volume" \
    grep -q 'model_cache:/cache' docker-compose.yml

  # Dead config that existed only to crash startup on a minimal .env.
  assert "SECRET_KEY has a default"    grep -qE 'SECRET_KEY: str = ' backend/app/core/config.py
  assert "POSTGRES_USER has a default" grep -qE 'POSTGRES_USER: str = ' backend/app/core/config.py
  assert "REDIS_URL has a default"     grep -qE 'REDIS_URL: str = ' backend/app/core/config.py

  # The hardcoded 192.168.0.103 was only ever right on one machine.
  assert "API_BASE_URL reads the environment" \
    grep -q 'EXPO_PUBLIC_API_BASE_URL' frontend/src/constants/app.constants.ts

  # PowerShell scripts must be pure ASCII.
  #
  # Windows PowerShell 5.1 reads a BOM-less .ps1 as Windows-1252. An em-dash
  # (U+2014) is UTF-8 E2 80 94, and 0x94 decodes to U+201D RIGHT DOUBLE
  # QUOTATION MARK -- which PowerShell treats as a string delimiter. One em-dash
  # inside a quoted string therefore terminates it early and the rest of the
  # file parses as code. run.ps1 died with 10 cascading errors from a single
  # dash; setup_venv.ps1 had 7 such characters.
  #
  # A UTF-8 BOM would also fix it, but then correctness depends on the BOM
  # surviving every editor, git filter and copy. A file with no byte above 0x7F
  # cannot be misread by any encoding.
  for ps1 in scripts/run.ps1 backend/setup_venv.ps1; do
    if [ -f "$ps1" ]; then
      refute "$ps1 is pure ASCII" \
        env LC_ALL=C grep -qP '[^\x00-\x7F]' "$ps1"
    fi
  done

  # The React family must be one version. react/react-dom/react-test-renderer
  # have to match exactly, and react-native's peer range has to accept it --
  # a caret on any of them lets npm pick a patch whose peers exclude the others,
  # which is what produced the ERESOLVE wall (defect 25).
  if [ -f frontend/package.json ]; then
    assert "react pinned exactly" \
      grep -qE '"react": *"19\.[0-9]+\.[0-9]+"' frontend/package.json
    assert "react-dom pinned exactly (must equal react)" \
      grep -qE '"react-dom": *"19\.[0-9]+\.[0-9]+"' frontend/package.json
    assert "react-native pinned exactly" \
      grep -qE '"react-native": *"0\.[0-9]+\.[0-9]+"' frontend/package.json
    refute "no @react-navigation/drawer (unused; drags in reanimated)" \
      grep -q '@react-navigation/drawer' frontend/package.json
    # `test -f` was the original check, and it passed while the file was
    # gitignored and untracked -- a false green on the exact defect it names.
    assert "package-lock.json committed (tracked, not merely present)" \
      git ls-files --error-unmatch frontend/package-lock.json
  fi
}

# =============================================================================
# S01c — Supply-chain integrity
# Promise: the repository contains no injected code, and the scanner that
# proves it actually detects the known sample.
# =============================================================================
demo_S01c() {
  bold "S01c — supply-chain integrity"

  assert "scan-injection.sh exists"     test -f scripts/scan-injection.sh
  assert "scan-injection.sh is valid bash" bash -n scripts/scan-injection.sh
  assert "repository scans clean"        bash scripts/scan-injection.sh --quiet

  # babel.config.js is the file that was infected. It runs on every Metro
  # bundle and every Jest invocation, so it is the highest-value persistence
  # point in the project. Keep it tiny and keep checking.
  assert "babel.config.js is small (<2 KB)" \
    bash -c '[ "$(wc -c < frontend/babel.config.js)" -lt 2048 ]'
  assert "babel.config.js has no long lines" \
    bash -c '[ "$(awk "{if(length>m)m=length}END{print m+0}" frontend/babel.config.js)" -lt 200 ]'
  refute "babel.config.js does not eval" \
    grep -q 'eval(' frontend/babel.config.js
  refute "babel.config.js does not spawn" \
    grep -q 'spawn' frontend/babel.config.js

  # Signature check for the specific actor, so a repeat is caught by name.
  refute "dead-drop wallet address absent from the repo" \
    git grep -qIF -- '0xa322E5f3D311D3080e6f0121063e9aDC2490Ef1a'
  refute "C2 payload header absent from the repo" \
    git grep -qiIF -- 'X-Payload-B64'

  # Guards must be wired in, not merely present on disk.
  assert "scanner runs in CI"         grep -q 'scan-injection.sh' .github/workflows/ci.yml
  assert "scanner runs in pre-commit" grep -q 'scan-injection' .pre-commit-config.yaml

  # No install-time execution vector.
  refute "package.json has no postinstall hook" \
    grep -qE '"(pre|post)install"\s*:' frontend/package.json
}

# =============================================================================
# Append the next sprint's demo here as demo_S02, demo_S03, ...
# Keep each one independent: no shared state, no ordering assumptions.
# =============================================================================

main() {
  local demos
  demos=$(declare -F | awk '{print $3}' | grep '^demo_S' | sort)

  if [ -n "$ONLY" ]; then
    if ! declare -F "demo_$ONLY" >/dev/null; then
      echo "no demo for '$ONLY'. available: $(echo "$demos" | sed 's/demo_//' | tr '\n' ' ')" >&2
      exit 2
    fi
    demos="demo_$ONLY"
  fi

  for d in $demos; do "$d"; done

  bold "result"
  if [ ${#FAILED[@]} -gt 0 ]; then
    printf '  \033[31m%d FAILED:\033[0m\n' "${#FAILED[@]}"
    for f in "${FAILED[@]}"; do printf '    - %s\n' "$f"; done
    printf '\n'
    exit 1
  fi
  printf '  \033[32mall demos pass\033[0m\n\n'
}

main
