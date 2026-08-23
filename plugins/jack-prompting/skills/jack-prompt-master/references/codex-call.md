# Codex call pattern (Round 3, optional)

Copied from `~/.claude/skills/office-hours/` Phase 3.5. Reuse this pattern verbatim in the skill's Bash dispatch for the user-gated Round 3 Codex consult. Never run this before the Round 3 AskUserQuestion (or `JPM_CODEX_ROUND=yes`) has been answered.

## Bash pattern

```bash
# Tempfiles + trap
TMPERR=$(mktemp /tmp/jpm-codex-XXXXXXXX)
TMPOUT=$(mktemp /tmp/jpm-codex-out-XXXXXXXX)
PROMPT_FILE=$(mktemp /tmp/jpm-codex-prompt-XXXXXXXX.txt)
trap 'rm -f "$TMPERR" "$TMPOUT" "$PROMPT_FILE"' EXIT

# Write the Round 3 request to PROMPT_FILE
#   = <voice instructions> + <rubric> + <intent block> + <project-context block (if any)> + <v2>
cat > "$PROMPT_FILE" <<EOF
${VOICE_INSTRUCTIONS}

<rubric>
${RUBRIC_CRITERIA}
</rubric>

${INTENT_BLOCK}

${CONTEXT_BLOCK}

<v2>
${V2_PROMPT}
</v2>
EOF

# Pick timeout wrapper (macOS uses gtimeout from Homebrew coreutils)
TIMEOUT_BIN=$(command -v gtimeout || command -v timeout)

# Working directory: repo root if in a repo, else $PWD
WORKDIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Codex exec — stdin via `codex exec -`, NOT argv
#   Why stdin: a 6k context + 300-word draft + intent block easily exceeds shell
#   ARG_MAX on some systems (8 KiB on older bash, ~256 KiB typical). Stdin is unbounded.
if [ -n "$TIMEOUT_BIN" ]; then
  "$TIMEOUT_BIN" "${JPM_CODEX_TIMEOUT:-300}" codex exec - \
    -C "$WORKDIR" \
    -s read-only \
    -c "model_reasoning_effort=\"${JPM_CODEX_EFFORT:-medium}\"" \
    < "$PROMPT_FILE" > "$TMPOUT" 2>"$TMPERR"
else
  echo "WARN: no gtimeout/timeout — relying on codex internal timeout" >&2
  codex exec - \
    -C "$WORKDIR" \
    -s read-only \
    -c "model_reasoning_effort=\"${JPM_CODEX_EFFORT:-medium}\"" \
    < "$PROMPT_FILE" > "$TMPOUT" 2>"$TMPERR"
fi
CODEX_EXIT=$?
```

## Exit-code semantics

| Exit | Meaning | Skill response |
|---|---|---|
| 0 | success — but check `wc -c < "$TMPOUT" == 0` for empty | empty → treat as failure → keep v2 |
| 124 | gtimeout/timeout fired (5 min exceeded) | keep v2 |
| anything else | codex error (auth, network, etc.) | keep v2 |

**Empty output despite exit 0** is also a failure (codex returned without writing anything).

## Failure path

On any failure (exit 124, non-zero exit, or empty stdout):

1. Read `$TMPERR` for diagnostics; log first line for user visibility.
2. **Keep v2 as the final prompt.** Do not substitute a Claude voice for Codex — Round 3 exists for the cross-model hedge; without Codex it is skipped, not simulated.
3. Print the degraded-hedge caveat banner at Phase 5 and set `exit_reason: codex_failed`.

## Preflight gate

At Phase 0, run `command -v codex` once. If missing, the Round 3 AskUserQuestion is skipped entirely and the skill prints one line saying so; v2 is final.

## Voice instructions for Round 3 (Codex)

Pass this string at the top of `PROMPT_FILE`:

```
You are a contrarian senior staff engineer with 15+ years of experience reviewing other engineers' code. Below is v2 of a coding prompt that another LLM will execute, plus the rubric it is judged by (7 criteria for implementation tasks, 9 for diagnosis). Any concrete value in v2 must be user-stated, observed in the repo, labelled as an assumption, or posed as an open question — treat unlabelled values as fabrication. Do two things, in this order:

1. CRITIQUE: for each rubric criterion, quote the exact v2 span that addresses it (or say none), give PASS or FAIL, and name the concrete weakness a skeptical reviewer would exploit. Take a stance independent of whatever the previous reviewer concluded.
2. Then emit the literal line ---CANDIDATE--- followed by your own rewritten v3 candidate that fixes every weakness you found.

Hard rules for the candidate section:
- Output the prompt text and nothing else after ---CANDIDATE---.
- Do not emit a `scope:` line.
- Do not wrap in markdown fences.
- Do not include explanations of your choices after the separator.
```

The parent splits stdout on `---CANDIDATE---`: everything before is the critique, everything after is Codex's candidate. If the separator is missing, treat the whole output as the critique and synthesize v3 from v2 + critique only.
