#!/usr/bin/env bash
# check_leaks.sh — generic privacy / secret leak gate.
#
# This script is intentionally generic: it contains no project-specific
# identifiers, so it is safe to publish. Any project-specific secrets belong
# in the gitignored denylist file (see below), never in this script.
#
# Modes:
#   1. Working-tree mode (no arguments):
#        bash scripts/check_leaks.sh
#      Scans the content of every git-tracked file (via `git ls-files`).
#   2. Range mode:
#        bash scripts/check_leaks.sh <git-range>      # e.g. main~3..main
#      Scans the added lines of the patch text for that range via
#      `git log -p <range>`.
#
# Generic patterns always run. An OPTIONAL, gitignored denylist at
# scripts/leak_denylist.local supplies extra grep (PCRE) regexes, one per
# line; blank lines and lines starting with `#` are ignored. If the denylist
# file is absent, only the generic patterns run.
#
# Exit codes: 0 = clean, 1 = leak(s) found, 2 = usage/environment error.

set -uo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "check_leaks: not inside a git repository" >&2
    exit 2
}
cd "$repo_root" || exit 2

# Files that legitimately contain pattern literals and therefore must never be
# scanned (their own contents would otherwise flag as leaks).
SELF_FILES=(
    "scripts/check_leaks.sh"
    "scripts/pre-push"
    "scripts/leak_denylist.local"
)

# --- generic patterns (PCRE, compatible with `grep -P`) --------------------
# The token pattern is `(?i)(token|secret|api[_-]?key|password)\s*[:=]` with
# the value position restricted to a quoted literal. This keeps it from
# flagging benign variable reads/assignments such as `token = argv[i]` while
# still catching real assignments like `token = "abc"`.
PATTERNS=(
    '192\.168\.'
    '10\.0\.'
    '172\.(1[6-9]|2[0-9]|3[01])\.'
    '/home/'
    '(?i)(token|secret|api[_-]?key|password)\s*[:=]\s*["'"'"']'
    '\.pages\.dev'
    'CLOUDFLARE'
)

# --- optional local denylist ----------------------------------------------
DENYLIST="scripts/leak_denylist.local"
if [ -f "$DENYLIST" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # strip surrounding whitespace
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -z "$line" ] && continue
        case "$line" in
            \#*) continue ;;
        esac
        PATTERNS+=("$line")
    done < "$DENYLIST"
fi

is_self() {
    local f
    for f in "${SELF_FILES[@]}"; do
        [ "$1" = "$f" ] && return 0
    done
    return 1
}

FOUND=0

# ---------------------------------------------------------------------------
# Mode 1: scan the content of every git-tracked file.
# ---------------------------------------------------------------------------
scan_working_tree() {
    local file pattern
    echo "check_leaks: scanning git-tracked working tree"
    while IFS= read -r -d '' file; do
        is_self "$file" && continue
        [ -f "$file" ] || continue
        for pattern in "${PATTERNS[@]}"; do
            if grep -IqP -e "$pattern" -- "$file" 2>/dev/null; then
                printf '  LEAK  %s\n        matches pattern: %s\n' "$file" "$pattern"
                FOUND=$((FOUND + 1))
            fi
        done
    done < <(git ls-files -z)
}

# ---------------------------------------------------------------------------
# Mode 2: scan the added lines of a git range's patch text.
# ---------------------------------------------------------------------------
scan_range() {
    local range="$1"
    local line file="" added pattern
    echo "check_leaks: scanning patch of range $range"
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            '+++ b/'*) file="${line#+++ b/}" ; continue ;;
            '+++ '*)   file="" ; continue ;;
        esac
        # only inspect added content lines
        case "$line" in
            '+')  added="" ;;
            '+'*) added="${line#+}" ;;
            *)    continue ;;
        esac
        for pattern in "${PATTERNS[@]}"; do
            if printf '%s\n' "$added" | grep -Pq -e "$pattern" 2>/dev/null; then
                printf '  LEAK  %s (range %s)\n        matches pattern: %s\n        line: %s\n' \
                    "${file:-<unknown>}" "$range" "$pattern" "$added"
                FOUND=$((FOUND + 1))
            fi
        done
    done < <(git log -p --no-color "$range" -- . \
        ':(exclude)scripts/check_leaks.sh' \
        ':(exclude)scripts/pre-push' \
        ':(exclude)scripts/leak_denylist.local' 2>/dev/null)
}

if [ "$#" -ge 1 ]; then
    scan_range "$1"
else
    scan_working_tree
fi

echo ""
if [ "$FOUND" -gt 0 ]; then
    echo "check_leaks: FAILED — $FOUND leak match(es) found"
    exit 1
fi

echo "check_leaks: no leaks found"
exit 0
