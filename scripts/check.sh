#!/usr/bin/env bash
# =============================================================================
# Meridian — Prototype Gate check 1
# =============================================================================
# Lint, types, and tests for both halves of the stack.
#
#   ./scripts/check.sh            run everything that is installed; skip the rest
#   ./scripts/check.sh --strict   a missing tool is a failure (used by CI)
#   ./scripts/check.sh --backend  backend only
#   ./scripts/check.sh --frontend frontend only
#
# Run this when you TAKE the baton (to confirm you got a green trunk) and before
# you PASS it. See IMPLEMENTATION_PLAN.md §3.2.
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STRICT=0
RUN_BACKEND=1
RUN_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --strict)   STRICT=1 ;;
    --backend)  RUN_FRONTEND=0 ;;
    --frontend) RUN_BACKEND=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

FAILED=()
SKIPPED=()

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED+=("$1"); }
skip() {
  if [ "$STRICT" -eq 1 ]; then
    printf '  \033[31m✗\033[0m %s (tool missing, --strict)\n' "$1"; FAILED+=("$1")
  else
    printf '  \033[33m-\033[0m %s (skipped: %s)\n' "$1" "$2"; SKIPPED+=("$1")
  fi
}

# run <label> <command...>
# A missing tool is a skip (or a failure under --strict); a tool that runs and
# reports problems is always a failure. Distinguishing the two is the whole
# point: "not installed" and "your code is broken" are different answers.
run() {
  local label="$1"; shift
  if "$@" >/tmp/meridian-check.$$ 2>&1; then
    pass "$label"
    rm -f /tmp/meridian-check.$$
    return
  fi
  # Tool absent rather than code broken?
  if grep -qiE 'No module named|command not found|is not recognized|ENOENT|not found' \
       /tmp/meridian-check.$$; then
    skip "$label" "not installed"
    rm -f /tmp/meridian-check.$$
    return
  fi
  fail "$label"
  sed 's/^/      /' /tmp/meridian-check.$$ | tail -40
  rm -f /tmp/meridian-check.$$
}

# py_run <label> <python-module> <args...>
py_run() {
  local label="$1" module="$2"; shift 2
  if ! "$PY" -c "import $module" >/dev/null 2>&1; then
    skip "$label" "pip install $module"; return
  fi
  run "$label" "$PY" -m "$module" "$@"
}

# ---------------------------------------------------------------- backend ----
if [ "$RUN_BACKEND" -eq 1 ]; then
  bold "backend"
  if [ ! -d backend ]; then
    skip "backend" "no backend/ directory"
  else
    # Prefer the venv's interpreter so we lint what actually runs.
    PY=python
    for candidate in backend/venv/Scripts/python.exe backend/venv/bin/python; do
      [ -x "$candidate" ] && PY="$ROOT/$candidate" && break
    done

    if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
      skip "backend lint/types/tests" "no python interpreter"
    else
      # The project floor is 3.11. Warn loudly on anything else — a version
      # mismatch between the two of us produces bugs that only one can see.
      PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown)"
      case "$PYVER" in
        3.11|3.12) ;;
        *) printf '  \033[33m!\033[0m python %s — project targets 3.11/3.12 (use backend/venv)\n' "$PYVER" ;;
      esac

      py_run "ruff"        ruff check backend
      py_run "ruff format" ruff format --check backend
      py_run "mypy"        mypy --config-file backend/pyproject.toml backend/app
      # No tests exist before S03; an empty run is not a failure.
      if [ -d backend/tests ] && compgen -G "backend/tests/**/test_*.py" >/dev/null 2>&1; then
        py_run "pytest" pytest backend/tests -q
      else
        skip "pytest" "no test files yet (first land in S03)"
      fi
    fi
  fi
fi

# --------------------------------------------------------------- frontend ----
if [ "$RUN_FRONTEND" -eq 1 ]; then
  bold "frontend"
  if [ ! -d frontend/node_modules ]; then
    skip "frontend tsc/eslint/jest" "node_modules missing — run 'npm ci' in frontend/"
  else
    # Placeholders so src/lib/supabase.ts does not throw at import time during
    # a typecheck or a test run. Nothing here reaches a real project.
    export EXPO_PUBLIC_SUPABASE_URL="${EXPO_PUBLIC_SUPABASE_URL:-https://check-placeholder.supabase.co}"
    export EXPO_PUBLIC_SUPABASE_ANON_KEY="${EXPO_PUBLIC_SUPABASE_ANON_KEY:-check-placeholder}"

    run "tsc"    bash -c "cd '$ROOT/frontend' && npx tsc --noEmit"
    run "eslint" bash -c "cd '$ROOT/frontend' && npx eslint . --max-warnings=${ESLINT_MAX_WARNINGS:-105}"
    run "jest"   bash -c "cd '$ROOT/frontend' && npx jest --passWithNoTests --silent"
  fi
fi

# ----------------------------------------------------------------- report ----
bold "result"
if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf '  %d skipped: %s\n' "${#SKIPPED[@]}" "$(IFS=', '; echo "${SKIPPED[*]}")"
fi
if [ ${#FAILED[@]} -gt 0 ]; then
  printf '  \033[31m%d FAILED: %s\033[0m\n\n' "${#FAILED[@]}" "$(IFS=', '; echo "${FAILED[*]}")"
  exit 1
fi
printf '  \033[32mall green\033[0m\n\n'
