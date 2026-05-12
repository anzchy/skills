#!/usr/bin/env bash
# context-ingest.sh — read project CLAUDE.md / AGENTS.md, truncate to 6000 bytes
# on a line boundary, emit a fenced <project-context> block to stdout.
#
# Priority order:
#   1. ./CLAUDE.md  (project root)
#   2. ./AGENTS.md  (Codex convention)
#   3. (nothing — emit empty output; parent flips scope: portable)
#
# The user-global ~/.claude/CLAUDE.md is already in Claude Code's conversation context,
# so NOT included here as a fallback to avoid double-loading.
#
# Usage: bash references/context-ingest.sh > "$CONTEXT_FILE"
#
# Env knob: JPM_CONTEXT_CAP (default 6000 bytes).

set -euo pipefail

CAP=${JPM_CONTEXT_CAP:-6000}

SOURCE=""
if [ -f ./CLAUDE.md ]; then
  SOURCE=./CLAUDE.md
elif [ -f ./AGENTS.md ]; then
  SOURCE=./AGENTS.md
fi

if [ -z "$SOURCE" ]; then
  # Empty output — parent treats as portable mode.
  exit 0
fi

ORIG_BYTES=$(wc -c < "$SOURCE" | tr -d ' ')

if [ "$ORIG_BYTES" -le "$CAP" ]; then
  # Fits — emit verbatim inside fenced block.
  printf '<project-context source="%s">\n' "$SOURCE"
  cat "$SOURCE"
  # Ensure trailing newline before close tag.
  tail -c1 "$SOURCE" | od -An -c | grep -q '\\n' || printf '\n'
  printf '</project-context>\n'
  exit 0
fi

# Truncate. `head -c $CAP` may cut a multibyte UTF-8 char; trim back to the last
# newline within the byte window to avoid invalid UTF-8 and partial lines.
TMP=$(mktemp /tmp/jpm-ctx-XXXXXXXX)
trap 'rm -f "$TMP"' EXIT

head -c "$CAP" "$SOURCE" > "$TMP"

# Find last newline byte offset within TMP. If a newline exists, truncate there.
LAST_NL=$(awk 'BEGIN{RS="\n"; FS=""} {p=p+length($0)+1} END{print p-length($0)-1}' "$TMP" 2>/dev/null || echo 0)
if [ "$LAST_NL" -gt 0 ]; then
  head -c "$LAST_NL" "$TMP" > "${TMP}.trim"
  mv "${TMP}.trim" "$TMP"
fi

printf '<project-context source="%s" truncated="true" orig_bytes="%s" cap_bytes="%s">\n' "$SOURCE" "$ORIG_BYTES" "$CAP"
cat "$TMP"
printf '\n</project-context>\n'

# Print human-visible banner to stderr (parent surfaces to user).
printf 'ℹ️  context truncated from %s → %s bytes\n' "$ORIG_BYTES" "$CAP" >&2
