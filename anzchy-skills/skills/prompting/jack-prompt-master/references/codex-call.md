# Codex call pattern (Candidate B)

Copied from `~/.claude/skills/office-hours/` Phase 3.5. Reuse this pattern verbatim in the skill's Bash dispatch for Candidate B.

## Bash pattern

```bash
# Tempfiles + trap
TMPERR=$(mktemp /tmp/jpm-codex-XXXXXXXX)
TMPOUT=$(mktemp /tmp/jpm-codex-out-XXXXXXXX)
PROMPT_FILE=$(mktemp /tmp/jpm-codex-prompt-XXXXXXXX.txt)
trap 'rm -f "$TMPERR" "$TMPOUT" "$PROMPT_FILE"' EXIT

# Write seed to PROMPT_FILE
#   Seed = <intent block> + <project-context block (if any)> + <draft or last synth>
#   + voice instruction: "Refine this draft into a stronger coding prompt. Output the prompt only."
cat > "$PROMPT_FILE" <<EOF
${VOICE_INSTRUCTIONS}

${INTENT_BLOCK}

${CONTEXT_BLOCK}

<draft>
${DRAFT_OR_SYNTH}
</draft>
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
| 0 | success — but check `wc -c < "$TMPOUT" == 0` for empty | empty → treat as failure → fallback |
| 124 | gtimeout/timeout fired (5 min exceeded) | fallback |
| anything else | codex error (auth, network, etc.) | fallback |

**Empty output despite exit 0** is also a failure (codex returned without writing anything).

## Fallback path

On any failure:

1. Read `$TMPERR` for diagnostics; log first line for user visibility.
2. Dispatch a second `Task` (subagent_type: general-purpose) with the system prompt at `references/fallback-voice.md` ("contrarian senior engineer").
3. Mark `B_source = claude-fallback` for this round. The output's score history table will surface this.
4. Print the degraded-hedge caveat banner at Phase 5 if any round fell back.

## Preflight gate

Before the first round, run `command -v codex` once. If missing, skip the codex call every round and go straight to the fallback Task dispatch — but still print the caveat banner so the user knows the tournament was Claude-vs-Claude.

## Voice instructions for Candidate B (Codex)

Pass this string at the top of `PROMPT_FILE`:

```
You are a contrarian senior staff engineer with 15+ years of experience reviewing other engineers' code. Your job is to refine the draft prompt below into a sharper coding prompt that another LLM will execute. Take a stance independent of what the previous reviewer might say. Output only the refined prompt — no commentary, no preamble, no "Here is the refined prompt:" intro.

Hard rules:
- Output the prompt text and nothing else.
- Do not emit a `scope:` line.
- Do not wrap in markdown fences.
- Do not include explanations of your choices.
```
