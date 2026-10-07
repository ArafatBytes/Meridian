#!/usr/bin/env bash
# =============================================================================
# Meridian - injected-code scanner
# =============================================================================
# Written after malware was found in frontend/babel.config.js, where ~26 KB of
# obfuscated code sat after the closing brace behind ~400 spaces, present since
# the initial commit. babel.config.js runs on every Metro bundle and every Jest
# run, so it executed constantly and silently.
#
#   ./scripts/scan-injection.sh            scan tracked + untracked files
#   ./scripts/scan-injection.sh --quiet    exit code only, for hooks and CI
#
# Exit 0 = clean, 1 = something needs a human.
#
# This reads files as TEXT ONLY. It never imports, requires or executes
# anything it scans.
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

say() { [ "$QUIET" -eq 0 ] && printf '%s\n' "$*"; return 0; }

FINDINGS=0

# -----------------------------------------------------------------------------
# 1. Config and entry files must stay small
# -----------------------------------------------------------------------------
# These are the high-value persistence targets: each one executes on build or
# on app start, and each should be a handful of lines. A size anomaly here is
# the single strongest signal available.
#
#   file:max_bytes
LIMITS="
frontend/babel.config.js:2048
frontend/metro.config.js:4096
frontend/index.js:2048
frontend/jest.config.js:4096
frontend/jest.setup.js:4096
frontend/.eslintrc.js:4096
frontend/.prettierrc.js:1024
frontend/app.json:16384
frontend/tsconfig.json:4096
"
say ""
say "config file sizes"
while IFS=: read -r f limit; do
  [ -z "$f" ] && continue
  [ -f "$f" ] || continue
  size=$(wc -c < "$f" | tr -d ' ')
  if [ "$size" -gt "$limit" ]; then
    say "  FAIL  $f is $size bytes (limit $limit)"
    say "        A config file this large almost certainly has something appended."
    FINDINGS=$((FINDINGS+1))
  else
    say "  ok    $f ($size/$limit bytes)"
  fi
done <<< "$LIMITS"

# -----------------------------------------------------------------------------
# 2. No absurdly long lines in source
# -----------------------------------------------------------------------------
# Obfuscators emit one enormous line. Minified vendor code is excluded by path.
say ""
say "long lines (>2000 chars)"
LONG=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in
    *node_modules/*|*/android/*|*/ios/*|*.md|*.lock|*package-lock.json|*.min.js|*.map) continue ;;
  esac
  case "$f" in
    *.js|*.jsx|*.ts|*.tsx|*.json|*.py|*.sh|*.ps1|*.yml|*.yaml) ;;
    *) continue ;;
  esac
  max=$(awk '{ if (length > m) m = length } END { print m+0 }' "$f")
  if [ "$max" -gt 2000 ]; then
    say "  FAIL  $f has a ${max}-char line"
    FINDINGS=$((FINDINGS+1)); LONG=$((LONG+1))
  fi
done < <(git ls-files; git ls-files --others --exclude-standard)
[ "$LONG" -eq 0 ] && say "  ok    none"

# -----------------------------------------------------------------------------
# 3. Known-bad indicators from the incident
# -----------------------------------------------------------------------------
# The dead-drop resolver, so a re-infection by the same actor is caught by
# signature rather than only by shape.
say ""
say "known indicators"
IOC=0
for pat in \
    '0xa322E5f3D311D3080e6f0121063e9aDC2490Ef1a' \
    'eth_getTransactionCount' \
    'X-Payload-B64' \
    'x-payload-b64' \
    '/0x/cls' \
    'windowsHide'
do
  # The incident write-up, this scanner and the smoke test all contain these
  # strings on purpose -- the whole point is to detect them elsewhere. Excluding
  # them keeps the signature check meaningful instead of permanently red.
  if git grep -lIF -- "$pat" --        ':!docs/SECURITY-INCIDENT-*.md'        ':!scripts/scan-injection.sh'        ':!scripts/smoke.sh'        ':!PROGRESS.md'        ':!IMPLEMENTATION_PLAN.md' >/dev/null 2>&1; then
    say "  FAIL  indicator present in tracked files: $pat"
    git grep -lIF -- "$pat" --        ':!docs/SECURITY-INCIDENT-*.md' ':!scripts/scan-injection.sh'        ':!scripts/smoke.sh' ':!PROGRESS.md' ':!IMPLEMENTATION_PLAN.md'        2>/dev/null | sed 's/^/          /' | while read -r l; do say "$l"; done
    FINDINGS=$((FINDINGS+1)); IOC=$((IOC+1))
  fi
done
[ "$IOC" -eq 0 ] && say "  ok    none"

# -----------------------------------------------------------------------------
# 4. Dynamic execution in config and entry files
# -----------------------------------------------------------------------------
# These files have no legitimate reason to eval, spawn, or open a socket.
say ""
say "dynamic execution in config/entry files"
DYN=0
for f in frontend/babel.config.js frontend/metro.config.js frontend/index.js \
         frontend/jest.config.js frontend/jest.setup.js frontend/.eslintrc.js; do
  [ -f "$f" ] || continue
  # jest.setup.js legitimately calls jest.mock; exclude that one token.
  if grep -nE "\beval\s*\(|new[[:space:]]+Function\s*\(|child_process|\bspawn\s*\(|require\(['\"](https?|net|dns|tls|zlib)['\"]\)" "$f" \
       | grep -v 'jest\.mock' >/dev/null 2>&1; then
    say "  FAIL  $f performs dynamic execution or opens a socket"
    grep -nE "\beval\s*\(|new[[:space:]]+Function\s*\(|child_process|\bspawn\s*\(|require\(['\"](https?|net|dns|tls|zlib)['\"]\)" "$f" \
      | head -5 | cut -c1-110 | sed 's/^/          /;s/$/ .../'
    FINDINGS=$((FINDINGS+1)); DYN=$((DYN+1))
  fi
done
[ "$DYN" -eq 0 ] && say "  ok    none"

# -----------------------------------------------------------------------------
# 5. npm lifecycle hooks
# -----------------------------------------------------------------------------
# preinstall/postinstall/prepare run automatically on `npm install` and are a
# standard supply-chain execution vector.
say ""
say "npm lifecycle hooks"
HOOKS="$(python -c "
import json,sys
try: s=json.load(open('frontend/package.json',encoding='utf-8')).get('scripts',{})
except Exception: sys.exit(0)
print(' '.join(k for k in s if k in
 ('preinstall','install','postinstall','prepare','prepublish','prepublishOnly')))
" 2>/dev/null || true)"
if [ -n "${HOOKS// /}" ]; then
  say "  WARN  package.json defines: $HOOKS"
  say "        These execute on npm install. Confirm each is intentional."
  FINDINGS=$((FINDINGS+1))
else
  say "  ok    none"
fi

# -----------------------------------------------------------------------------
say ""
if [ "$FINDINGS" -gt 0 ]; then
  say "RESULT: $FINDINGS finding(s) - investigate before building or committing."
  exit 1
fi
say "RESULT: clean"
exit 0
