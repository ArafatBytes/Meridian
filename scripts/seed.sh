#!/usr/bin/env bash
# =============================================================================
# Meridian — Prototype Gate check 2
# =============================================================================
# Bring a database up to the current schema.
#
#   ./scripts/seed.sh            apply SCHEMA.sql (idempotent) + VERIFY.sql
#   ./scripts/seed.sh --fresh    RESET.sql first — DESTROYS ALL APPLICATION DATA
#   ./scripts/seed.sh --verify   run VERIFY.sql only, change nothing
#
# Needs `psql` and DATABASE_URL in backend/.env. Without either, it prints the
# manual steps for the Supabase SQL Editor and exits 0 — this script is a
# convenience, not the source of truth.
#
# Until S02 (ADR 0004) there is no migration runner and no schema_migrations
# table. This applies whole files. After S02, this script calls
# scripts/migrate.py instead.
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQL_DIR="$ROOT/backend/migrations/supabase"

MODE=apply
for arg in "$@"; do
  case "$arg" in
    --fresh)  MODE=fresh ;;
    --verify) MODE=verify ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }

manual_instructions() {
  cat <<EOF

  Apply the schema by hand instead — Supabase dashboard → SQL Editor,
  paste each file in order:

EOF
  [ "$MODE" = fresh ] && echo "    1. $SQL_DIR/RESET.sql     (destroys data)"
  echo "    2. $SQL_DIR/SCHEMA.sql"
  echo "    3. $SQL_DIR/VERIFY.sql    (every row should read OK)"
  echo
  echo "  Full guide: backend/migrations/supabase/README.md"
  echo
}

bold "database"

# Pull DATABASE_URL out of backend/.env without sourcing the file (it contains
# values with spaces and '#' that a naive `source` would mangle).
DB_URL="${DATABASE_URL:-}"
if [ -z "$DB_URL" ] && [ -f "$ROOT/backend/.env" ]; then
  DB_URL="$(grep -E '^DATABASE_URL=' "$ROOT/backend/.env" | tail -1 | cut -d= -f2- | tr -d '"'"'"'' | xargs || true)"
fi

if [ -z "$DB_URL" ]; then
  printf '  \033[33m-\033[0m DATABASE_URL not set (checked env and backend/.env)\n'
  manual_instructions
  exit 0
fi

if ! command -v psql >/dev/null 2>&1; then
  printf '  \033[33m-\033[0m psql not on PATH\n'
  manual_instructions
  exit 0
fi

# psql speaks libpq, not SQLAlchemy. Strip the +asyncpg driver suffix.
PSQL_URL="${DB_URL/+asyncpg/}"

apply() {
  local file="$1"
  printf '  applying %s ... ' "$(basename "$file")"
  if psql "$PSQL_URL" --quiet --no-psqlrc -v ON_ERROR_STOP=1 -f "$file" >/tmp/meridian-seed.$$ 2>&1; then
    printf '\033[32mok\033[0m\n'
  else
    printf '\033[31mFAILED\033[0m\n'
    sed 's/^/      /' /tmp/meridian-seed.$$ | tail -30
    rm -f /tmp/meridian-seed.$$
    exit 1
  fi
  rm -f /tmp/meridian-seed.$$
}

if [ "$MODE" = fresh ]; then
  printf '\n  \033[31m⚠  --fresh DESTROYS ALL APPLICATION DATA in this database.\033[0m\n'
  printf '     Target: %s\n' "$(echo "$PSQL_URL" | sed -E 's#//[^@]*@#//***@#')"
  printf '     Type "destroy" to continue: '
  read -r confirm
  [ "$confirm" = "destroy" ] || { echo "  aborted"; exit 1; }
  apply "$SQL_DIR/RESET.sql"
fi

[ "$MODE" != verify ] && apply "$SQL_DIR/SCHEMA.sql"

printf '\n'
bold "verify"
psql "$PSQL_URL" --quiet --no-psqlrc -f "$SQL_DIR/VERIFY.sql"

# VERIFY.sql reports status in its result rows rather than via exit code, so
# scan the output for failures.
if psql "$PSQL_URL" --quiet --no-psqlrc -t -f "$SQL_DIR/VERIFY.sql" 2>/dev/null | grep -qE 'MISSING|FAIL'; then
  printf '\n  \033[31m✗ verification found problems — see the rows above\033[0m\n\n'
  exit 1
fi

printf '\n  \033[32m✓ schema verified\033[0m\n\n'
