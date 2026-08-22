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
#   max_iter, pass_threshold, B_source, score_A, score_B, winner,
#   early_stop, terminal
#
# Usage:
#   bash prompts-persist.sh \
#     round=2 date=2026-05-12T19:39:12Z draft_sha256=8f4e... \
#     draft_word_count=142 scope=project context_sha256=a91b... \
#     max_iter=3 pass_threshold=6 B_source=codex \
#     score_A=5 score_B=6 winner=B early_stop=false terminal=false \
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
for key in round date draft_sha256 draft_word_count scope context_sha256 max_iter pass_threshold B_source score_A score_B winner early_stop terminal; do
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
max_iter: ${F[max_iter]}
pass_threshold: ${F[pass_threshold]}
B_source: ${F[B_source]}
score_A: ${F[score_A]}
score_B: ${F[score_B]}
winner: ${F[winner]}
early_stop: ${F[early_stop]}
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
    --argjson max_iter "${F[max_iter]}" \
    --argjson pass_threshold "${F[pass_threshold]}" \
    --arg B_source "${F[B_source]}" \
    --argjson score_A "${F[score_A]}" \
    --argjson score_B "${F[score_B]}" \
    --arg winner "${F[winner]}" \
    --argjson early_stop "${F[early_stop]}" \
    --argjson terminal "${F[terminal]}" \
    --arg md_path "$MD_PATH" \
    '{
      round: $round,
      date: $date,
      draft_sha256: $draft_sha256,
      draft_word_count: $draft_word_count,
      scope: $scope,
      context_sha256: $context_sha256,
      max_iter: $max_iter,
      pass_threshold: $pass_threshold,
      B_source: $B_source,
      score_A: $score_A,
      score_B: $score_B,
      winner: $winner,
      early_stop: $early_stop,
      terminal: $terminal,
      md_path: $md_path
    }' > "$JSON_PATH"
else
  printf 'ERROR: jq required for sidecar JSON (should have been gated at Phase 0)\n' >&2
  exit 1
fi

# Emit MD path to stdout for the parent.
printf '%s\n' "$MD_PATH"
