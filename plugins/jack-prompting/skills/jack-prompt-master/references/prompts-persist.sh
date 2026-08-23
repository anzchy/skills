#!/usr/bin/env bash
# prompts-persist.sh — write a round checkpoint to .prompts/.
#
# Side effects:
#   - Creates .prompts/ if missing (in $PROMPTS_DIR, default ./.prompts/).
#   - On EROFS / chmod: falls back to $TMPDIR/.prompts-$$/ and prints fallback path to stderr.
#   - Writes two files per round: <prefix>.md (human) + <prefix>.json (sidecar for resume).
#   - On first use per project, may emit a gitignore prompt marker so the parent skill can AUQ.
#
# Inputs:
#   - Markdown body: stdin
#   - Sidecar fields: positional args as KEY=VALUE pairs.
#
# Required sidecar fields:
#   round, date, draft_sha256, draft_word_count, scope, context_sha256,
#   source, score, terminal
#
#   source ∈ {claude-inline, fable-grill, codex-synth}
#   score  = 0–7 (Round 1 writes 0; it is scored by the Round 2 grill)
#
# Usage:
#   bash prompts-persist.sh \
#     round=2 date=2026-05-12T19:39:12Z draft_sha256=8f4e... \
#     draft_word_count=142 scope=project context_sha256=a91b... \
#     source=fable-grill score=6 terminal=false \
#     < round-body.md
#
# Output to stdout: the path of the written .md file.

set -euo pipefail

PROMPTS_DIR=${JPM_PROMPTS_DIR:-./.prompts}

# Probe write access; fall back to tmpdir on failure.
if ! mkdir -p "$PROMPTS_DIR" 2>/dev/null; then
  PROMPTS_DIR="${TMPDIR:-/tmp}/.prompts-$$"
  mkdir -p "$PROMPTS_DIR"
  printf 'ℹ️  .prompts/ not writable — falling back to %s (resume disabled this run)\n' "$PROMPTS_DIR" >&2
elif ! ( touch "$PROMPTS_DIR/.write-probe" 2>/dev/null && rm -f "$PROMPTS_DIR/.write-probe" ); then
  PROMPTS_DIR="${TMPDIR:-/tmp}/.prompts-$$"
  mkdir -p "$PROMPTS_DIR"
  printf 'ℹ️  .prompts/ not writable — falling back to %s (resume disabled this run)\n' "$PROMPTS_DIR" >&2
fi

# Parse KEY=VALUE args into an associative array.
declare -A F
for arg in "$@"; do
  case "$arg" in
    *=*) F["${arg%%=*}"]="${arg#*=}" ;;
    *) printf 'ERROR: bad arg (need KEY=VALUE): %s\n' "$arg" >&2; exit 1 ;;
  esac
done

# Validate required fields.
for key in round date draft_sha256 draft_word_count scope context_sha256 source score terminal; do
  if [ -z "${F[$key]:-}" ]; then
    printf 'ERROR: missing required field: %s\n' "$key" >&2
    exit 1
  fi
done

# Filename: YYYY-MM-DD_HHMMSS_round-k.md  (lex-sortable, HHMMSS disambiguates same-day runs).
TS=$(date -u +%Y-%m-%d_%H%M%S)
PREFIX="${PROMPTS_DIR}/${TS}_round-${F[round]}"
MD_PATH="${PREFIX}.md"
JSON_PATH="${PREFIX}.json"

# Read body from stdin.
BODY=$(cat)

# Write markdown with frontmatter.
cat > "$MD_PATH" <<EOF
---
round: ${F[round]}
date: ${F[date]}
draft_sha256: ${F[draft_sha256]}
draft_word_count: ${F[draft_word_count]}
scope: ${F[scope]}
context_sha256: ${F[context_sha256]}
source: ${F[source]}
score: ${F[score]}
terminal: ${F[terminal]}
---

${BODY}
EOF

# Write sidecar JSON (parseable by jq, no yq dependency).
if command -v jq >/dev/null 2>&1; then
  jq -n \
    --argjson round "${F[round]}" \
    --arg date "${F[date]}" \
    --arg draft_sha256 "${F[draft_sha256]}" \
    --argjson draft_word_count "${F[draft_word_count]}" \
    --arg scope "${F[scope]}" \
    --arg context_sha256 "${F[context_sha256]}" \
    --arg source "${F[source]}" \
    --argjson score "${F[score]}" \
    --argjson terminal "${F[terminal]}" \
    --arg md_path "$MD_PATH" \
    '{
      round: $round,
      date: $date,
      draft_sha256: $draft_sha256,
      draft_word_count: $draft_word_count,
      scope: $scope,
      context_sha256: $context_sha256,
      source: $source,
      score: $score,
      terminal: $terminal,
      md_path: $md_path
    }' > "$JSON_PATH"
else
  printf 'ERROR: jq required for sidecar JSON (should have been gated at Phase 0)\n' >&2
  exit 1
fi

# Emit MD path to stdout for the parent.
printf '%s\n' "$MD_PATH"
