#!/usr/bin/env bash
# heuristic.sh — Phase 1 draft-complexity scorer.
# Pure bash, no sub-agent dispatch. Three signals: word count, 9-dim presence, ambiguity markers.
# Emits a JSON object to stdout. Parent skill parses with `jq`.
#
# Usage: bash references/heuristic.sh <draft_file>
#
# Output schema:
#   {
#     "word_count": int,                     # `wc -w` — words, not LLM tokens (~25% undercount)
#     "dims_present": ["task","input",...],  # which of the 9 dims have ≥1 keyword match
#     "dim_count": int,                      # length of dims_present
#     "ambiguity_markers": int,              # count of ambiguity keyword occurrences
#     "recommended_max_iter": int            # 2 / 3 / 5
#   }

set -euo pipefail

DRAFT_FILE=${1:-}
if [ -z "$DRAFT_FILE" ] || [ ! -f "$DRAFT_FILE" ]; then
  echo "ERROR: usage: $0 <draft_file>" >&2
  exit 1
fi

# Word count (NB: this measures `wc -w` words, NOT LLM tokens.
# Bucket boundaries below are calibrated against `wc -w` directly — do not swap
# in a real tokenizer without re-calibrating.)
WORD_COUNT=$(wc -w < "$DRAFT_FILE" | tr -d ' ')

# 9-dim keyword detection. Keywords derived from
# ~/.claude/skills/prompt-master/SKILL.md Intent Extraction table.
declare -A DIM_PATTERNS=(
  [task]='write|refactor|build|fix|generate|implement|design'
  [target_tool]='claude|gpt|codex|copilot|llm|model|agent'
  [output_format]='diff|file|snippet|json|markdown|code block|lines'
  [constraints]='must|must not|never|only|max |min |≤|≥|no more than'
  [input]='given|input|source|file|paste|attached|see'
  [context]='codebase|repo|stack|framework|using|written in'
  [audience]='user|reader|junior|senior|beginner|team'
  [success_criteria]='passes|tests|when|criteria|definition of done'
  [examples]='example|e\.g\.|for instance|sample|like'
)

DIMS_PRESENT=()
for dim in task target_tool output_format constraints input context audience success_criteria examples; do
  pattern=${DIM_PATTERNS[$dim]}
  if grep -iqE "$pattern" "$DRAFT_FILE"; then
    DIMS_PRESENT+=("$dim")
  fi
done
DIM_COUNT=${#DIMS_PRESENT[@]}

# Ambiguity markers — count occurrences, not unique matches.
# `|| true` shields grep's exit-1-on-no-match from `set -o pipefail`.
AMBIGUITY_MARKERS=$( { grep -iEo 'improve|better|somehow|etc|things|stuff|fix|polish|enhance' "$DRAFT_FILE" 2>/dev/null || true; } | wc -l | tr -d ' ')

# Bucket → recommended MAX_ITER.
# Tiebreaker: when multiple buckets match, prefer higher MAX_ITER (safer for ambiguous drafts).
RECOMMENDED=3
if [ "$WORD_COUNT" -le 80 ] && [ "$DIM_COUNT" -ge 7 ] && [ "$AMBIGUITY_MARKERS" -le 1 ]; then
  RECOMMENDED=2
fi
if [ "$WORD_COUNT" -ge 80 ] && [ "$WORD_COUNT" -le 300 ] && [ "$DIM_COUNT" -ge 4 ] && [ "$DIM_COUNT" -le 6 ] && [ "$AMBIGUITY_MARKERS" -ge 2 ] && [ "$AMBIGUITY_MARKERS" -le 4 ]; then
  RECOMMENDED=3
fi
if [ "$WORD_COUNT" -gt 300 ] || [ "$DIM_COUNT" -le 3 ] || [ "$AMBIGUITY_MARKERS" -ge 5 ]; then
  RECOMMENDED=5
fi

# Emit JSON. Use jq for safe array serialization if available; else hand-build.
if command -v jq >/dev/null 2>&1; then
  printf '%s\n' "${DIMS_PRESENT[@]}" | jq -R . | jq -s --argjson wc "$WORD_COUNT" --argjson dc "$DIM_COUNT" --argjson am "$AMBIGUITY_MARKERS" --argjson mi "$RECOMMENDED" '{
    word_count: $wc,
    dims_present: .,
    dim_count: $dc,
    ambiguity_markers: $am,
    recommended_max_iter: $mi
  }'
else
  # Fallback: hand-build JSON (parent should have errored at Phase 0 if jq missing, but be safe).
  dims_json=$(printf '"%s",' "${DIMS_PRESENT[@]}")
  dims_json="[${dims_json%,}]"
  printf '{"word_count":%s,"dims_present":%s,"dim_count":%s,"ambiguity_markers":%s,"recommended_max_iter":%s}\n' \
    "$WORD_COUNT" "$dims_json" "$DIM_COUNT" "$AMBIGUITY_MARKERS" "$RECOMMENDED"
fi
