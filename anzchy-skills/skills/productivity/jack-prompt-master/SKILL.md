---
name: jack-prompt-master
description: Tournament-based meta-prompting skill that iteratively refines a prompt across multiple rounds using parallel Claude + Codex candidate generation, an LLM-as-judge with binary 7-criterion rubric and quoted evidence, and a synthesizer that composes the next version from the best parts of each. Use this skill when the user wants to elevate a rough or high-stakes prompt for downstream coding tasks. Trigger keywords - "tournament prompt", "iteratively refine prompt", "meta-prompting", "/jack-prompt-master", "improve this prompt with multiple rounds". Distinct from one-shot /prompt-enhance.
version: 0.1.0
---

# jack-prompt-master

Tournament-based meta-prompting for high-stakes coding prompts. Runs **inline** within a single skill invocation (not via `/loop`).

## When to invoke

- User types `/jack-prompt-master <draft>` or asks for a "tournament", "multi-round refinement", "meta-prompting" pass on a prompt.
- The draft is for a coding task and quality matters more than speed.
- For quick polish, use `/prompt-enhance` (one-shot) instead — this skill costs \~40k–125k tokens per run.

## Output disposition (explicit)

This skill produces a **copy-paste prompt block**. It does NOT auto-execute the prompt downstream, does NOT pipe to another sub-agent, does NOT continue the conversation as the refined prompt. The user pastes the final prompt into a fresh chat or another skill themselves.

## Configuration (env overrides)

| Knob                | Default                    | Env override                 |
| ------------------- | -------------------------- | ---------------------------- |
| MAX_ITER           | heuristic (2/3/5)          | `JPM_MAX_ITER`               |
| PASS_THRESHOLD     | 6 of 7                     | `JPM_PASS_THRESHOLD` (5/6/7) |
| CONTEXT_INGEST     | ON if `./CLAUDE.md` exists | `JPM_CONTEXT` (on/off)       |
| CONTEXT_BYTE_CAP  | 6000 bytes                 | `JPM_CONTEXT_CAP`            |
| CODEX_MODEL        | gpt-5.4                    | `JPM_CODEX_MODEL`            |
| CODEX_EFFORT       | medium                     | `JPM_CODEX_EFFORT`           |
| CODEX_TIMEOUT_SEC | 300                        | `JPM_CODEX_TIMEOUT`          |
| PROMPTS_DIR        | `./.prompts/`              | `JPM_PROMPTS_DIR`            |
| GITIGNORE_PROMPT   | ask once per project       | `JPM_GITIGNORE`              |
| DRAFT_MAX_BYTES   | 50000                      | `JPM_DRAFT_MAX`              |
| JUDGE_RETRY_COUNT | 1                          | `JPM_JUDGE_RETRY`            |
| SYNTH_RETRY_COUNT | 1                          | `JPM_SYNTH_RETRY`            |

AskUserQuestion answers always override env. Validate at Phase 0; abort on out-of-range.

## Phase 0 — Pre-flight checks

Run these BEFORE Phase 0a. Abort cleanly on any failure with a clear message — do NOT silently degrade.

1. **Dependency probe** (Bash, one call):

   ```bash
   command -v jq >/dev/null || { echo "ABORT: jq missing — brew install jq / apt install jq"; exit 1; }
   command -v sha256sum >/dev/null || command -v shasum >/dev/null || { echo "ABORT: neither sha256sum nor shasum on PATH"; exit 1; }
   command -v codex >/dev/null || echo "WARN: codex not on PATH — fallback voice will be used every round"
   command -v gtimeout >/dev/null || command -v timeout >/dev/null || echo "WARN: no timeout wrapper — relying on codex internal timeout"
   ```

2. **Task tool probe**: dispatch one `Task` call with `subagent_type: general-purpose` asking the agent to reply with the single word `ok`. If the call errors or returns empty, abort: "ABORT: Task tool / general-purpose sub-agent unavailable."

3. **Config validation**: read all `JPM_*` env vars; range-check each against the Configuration table above. Out-of-range → abort with the offending knob name.

## Phase 0a — Draft input

If `$ARGUMENTS` is empty:

- Call `AskUserQuestion` with a single question: "Paste your draft prompt:" (Header: "Draft"). Accept user-supplied text.
- If still empty after the AUQ, print usage `Usage: /jack-prompt-master "<draft prompt>"` and exit.

If `$ARGUMENTS` is non-empty:

- Write the draft verbatim to a tmpfile: `DRAFT_FILE=$(mktemp /tmp/jpm-draft-XXXXXXXX.txt)` and `printf '%s' "$ARGUMENTS" > "$DRAFT_FILE"`. Never inline a multi-line draft into shell args (it shell-mangles).
- Byte-check: if `wc -c < "$DRAFT_FILE"` > `DRAFT_MAX_BYTES`, warn and offer truncation at 10k chars via AUQ.

## Phase 1 — Heuristic + MAX\_ITER + PASS\_THRESHOLD selection

1. Run `bash references/heuristic.sh "$DRAFT_FILE"`. Capture stdout as `HEURISTIC_JSON`.
2. Parse `recommended_max_iter` with `jq`. On any parse failure: default to 3, warn the user, continue.
3. Call `AskUserQuestion` (one call, two questions):
   - **Q1 (Header: "Rounds")** — "MAX\_ITER (max tournament rounds)?" Options: `2 / 3 / 5 / 7`. The option matching `recommended_max_iter` gets the `(recommended)` label.
   - **Q2 (Header: "Pass bar")** — "Pass threshold (criteria that must pass)?" Options: `5 of 7 / 6 of 7 (recommended) / 7 of 7`.
4. If `./CLAUDE.md` exists, run an additional AUQ for **CONTEXT\_INGEST**: "Adapt this prompt to the current project? Detected: `./CLAUDE.md` (N lines)." Options: `Yes, adapt (recommended)` / `No, keep portable` / `Yes but show me what's ingested first`. If user picks "show me first", `cat` the ingest preview then re-ask.

## Phase 2 — Intent extraction + Context ingest + Resume check

1. **Intent extraction (semantic, NOT heuristic):** invoke the workflow at `~/.claude/skills/prompt-master/SKILL.md` against `$DRAFT_FILE`. Produce a structured intent block over the 9 dimensions (task / target\_tool / output\_format / constraints / input / context / audience / success\_criteria / examples). The Phase 1 keyword heuristic is purely for bucketing — Phase 2 is the real extraction.
2. **Context ingest** (if user opted in at Phase 1): run `bash references/context-ingest.sh > $CONTEXT_FILE`. The script reads `./CLAUDE.md` then `./AGENTS.md` (priority order), truncates at 6000 bytes on the last newline within the byte window, emits a `<project-context>...</project-context>` fenced block. If both files missing, emit empty file and flip `scope: portable`. Compute `CONTEXT_SHA256=$(sha256sum "$CONTEXT_FILE" | cut -d' ' -f1)`; if context is empty, set `CONTEXT_SHA256=none`.
3. **Compute resume key:** normalize the draft (collapse runs of whitespace, strip leading/trailing blank lines), then `DRAFT_SHA256=$(printf '%s' "$NORM_DRAFT" | sha256sum | cut -d' ' -f1)`. The resume key is the tuple `(DRAFT_SHA256, scope, CONTEXT_SHA256)`.
4. **Resume scan:** `ls .prompts/*.json 2>/dev/null` and parse each sidecar with `jq` to find a tuple match.
   - If a match exists and `terminal: false`: AUQ "Resume from latest? Found `<filename>` — round k winner scored N/7. Continue to round k+1 / Start fresh (archive existing) / Show me the latest file first."
   - If a match exists and `terminal: true`: AUQ "Found a completed run for this exact draft (round k, score N/7). Show the final prompt / Start fresh (archive existing) / Open the file." NEVER offer "continue from round k+1" on a terminal checkpoint.
   - On "Start fresh": move existing `.prompts/*.{md,json}` to `.prompts/archive/` (create archive dir; on filename collision append `.dup-$(date +%s)`).
   - Stale tuple (no match): skip the AUQ entirely; do NOT archive prior files.
5. **Seed construction:** the seed passed to candidates in round 1 = `<intent block>\n<context block (if any)>\n<draft>`. On resume from round k, seed = `<intent>\n<context>\n<synth output from .prompts/round-k.md>` — but only read from disk at Phase 2 startup. During an active run, in-memory state is the source of truth.

## Phase 3 — Tournament loop

For each `k` from 1..MAX\_ITER:

### Parallel Dispatch Contract (READ BEFORE EVERY ROUND)

Round k MUST emit a **single assistant message** containing two `tool_use` blocks:

1. `Task` (subagent\_type: `general-purpose`) — Candidate A (Claude "rigorous engineer" voice)
2. `Bash` — Codex exec (Candidate B); OR a second `Task` with `references/fallback-voice.md` as system prompt if `codex` is not on PATH or known broken from a prior round.

Splitting A and B across two assistant messages **serializes** them and doubles round latency. At MAX\_ITER=7 this turns a 42-min budget into \~70+ min. The judge dispatch goes in the **next** assistant message, after both candidate results return.

**Concrete shape:**

```
[round-k assistant message]
  tool_use: Task   (Candidate A — Claude sub-agent)
  tool_use: Bash   (Candidate B — codex exec)

[round-k results return together]

[next assistant message]
  tool_use: Task   (Judge — rates both)

[judge result returns]

[if not early-stop, next assistant message]
  tool_use: Task   (Synthesizer)
```

### Candidate A (Claude sub-agent, voice = rigorous engineer)

Dispatch via `Task` with `subagent_type: general-purpose`. Self-contained prompt: paste seed + voice instructions + "Output the refined prompt only. Do not start with 'Sure', 'Here's', 'Okay', or any preamble. Do not emit a `scope:` line."

After receiving the result, strip preamble regex `^(Sure|Here'?s|Okay|Got it)[^\n]*\n` from the start.

If empty: retry once with same prompt; on second empty, mark candidate as `<empty>` and let the judge see it (it will FAIL all criteria).

### Candidate B (Codex via Bash)

Use the pattern in `references/codex-call.md`. Critical bits:

- Write seed to `PROMPT_FILE` via `mktemp`.
- Pipe via **stdin** (`codex exec -`), not argv — avoids ARG\_MAX.
- Wrap with `gtimeout 300` (macOS) or `timeout 300` (Linux); detect at runtime.
- Capture stdout → TMPOUT (candidate), stderr → TMPERR (diagnostics).
- Exit semantics: 0 = success (unless TMPOUT is empty — also failure), 124 = timeout, other = failure.
- On any failure: fall back to a second `Task` dispatch using `references/fallback-voice.md` ("contrarian senior engineer") and mark this round's `B_source = claude-fallback`.

Apply the same preamble strip to B's output.

### Judge (next assistant message, single Task)

Dispatch one `Task` with the system prompt at `references/judge-prompt.md` and pass: rubric, both candidates, threshold. The judge must emit strict JSON per the schema in `references/judge-prompt.md`.

**Validate every judge response with ********`jq -e`********:**

```bash
jq -e '
  (.verdicts | length == 14)
  and (.verdicts | map(select(.quote == "" or .quote == null)) | length == 0)
  and (.verdicts | map(.verdict) | all(. == "PASS" or . == "FAIL"))
  and (.score_A | type == "number") and (.score_A >= 0) and (.score_A <= 7)
  and (.score_B | type == "number") and (.score_B >= 0) and (.score_B <= 7)
  and (.winner == "A" or .winner == "B" or .winner == "tie")
' < judge_output.json > /dev/null
```

On `jq -e` non-zero: retry ONCE with reminder "Emit valid JSON only, matching the schema exactly. No commentary." On second failure: regex-extract `score_A` / `score_B` / `winner` and flag the round's confidence as "degraded" in the output.

If `JPM_JUDGE_FIXTURE` env var is set, skip the Task call and read the JSON from that path verbatim (test harness only).

### Round decision

- **Early stop:** if `max(score_A, score_B) >= PASS_THRESHOLD`, the winner becomes the final prompt. Write the checkpoint with `terminal: true` and `early_stop: true`. Exit loop.
- **Both fail all:** if `max(score_A, score_B) == 0`, do NOT call the synthesizer. Return the higher-scoring candidate (A on tie) with a caveat banner: `⚠️ Both candidates failed all criteria. Returning best of bad options.` Write checkpoint with `terminal: true`. Exit loop.
- **Continue:** dispatch the Synthesizer (next assistant message, `Task` with `references/synthesizer-prompt.md`). Inputs: candidate A, candidate B, judge JSON. Output: v(k+1) prompt only. Apply preamble strip + length check.
  - Synth empty / preamble-only after strip → retry once with stricter prompt. If retry also fails → use higher-scoring candidate as next round's seed. Never crash the loop on synth failure.

### Checkpoint write (every round, after the decision)

Call `bash references/prompts-persist.sh` with the round artifact via stdin (markdown body) + sidecar JSON args. The script writes BOTH a human-readable `.md` and a sidecar `.json` — you must pass the markdown body to its stdin.

**The markdown body fed to stdin MUST contain:**

```
## Original draft
<verbatim draft>

## Project context (ingested)
<truncated CLAUDE.md / AGENTS.md content, or "none">

## Candidate A (Claude)
<full A output>

## Candidate B (codex or claude-fallback)
<full B output>

## Judge verdicts
<judge JSON, pretty-printed>

## Synthesized v(k+1) (seed for next round)
<synth output, or "n/a — early stop" or "n/a — both failed">

## Final prompt (this round's winner or synth)
<the actual final-prompt text — winner of early-stop OR synth of continuing round>
```

The "Final prompt" section is mandatory on every checkpoint. On early-stop or terminal rounds, this is the prompt the user receives. The body is NOT optional — never invoke `prompts-persist.sh` with empty stdin.

Other persist-script behavior:

- Creates `.prompts/` if missing; on EROFS or chmod, falls back to `$TMPDIR/.prompts-$$/` and informs the user (skip resume next time).
- First-run-per-project: AUQ asks whether to add `.prompts/` to `.gitignore`. Remember the answer in `~/.gstack/projects/<slug>/.prompts-gitignore-prompted`.
- Writes `YYYY-MM-DD_HHMMSS_round-k.md` (human, with body above) + `YYYY-MM-DD_HHMMSS_round-k.json` (sidecar with frontmatter fields for resume).

In-memory state remains the source of truth for the next round's seed. Disk is checkpoint-only.

## Phase 4 — Max-iter exit (no early stop)

If the loop completes MAX\_ITER rounds without `score >= PASS_THRESHOLD`:

- Pick the highest-scoring candidate across all rounds (not just the last).
- Print the failing criteria with the judge's verbatim quoted reasons so the user can fix manually.
- Mark the final checkpoint `terminal: true`, `early_stop: false`.

## Phase 5 — Output

**Step 1 — Persist the final prompt to disk (mandatory, before printing).**

Write a dedicated final-prompt markdown file alongside the round checkpoints. This is the canonical retrievable artifact — users should be able to `cat .prompts/<timestamp>_FINAL.md` after the skill exits without scanning a multi-section round file.

```bash
FINAL_PATH="${JPM_PROMPTS_DIR:-./.prompts}/$(date -u +%Y-%m-%d_%H%M%S)_FINAL.md"
cat > "$FINAL_PATH" <<EOF
---
kind: final_prompt
date: $(date -u +%Y-%m-%dT%H:%M:%SZ)
draft_sha256: $DRAFT_SHA256
scope: $SCOPE
rounds_run: $ROUNDS_RUN
final_score: $FINAL_SCORE
exit_reason: $EXIT_REASON   # early_stop | max_iter | both_failed
---

# Final prompt — jack-prompt-master tournament

$FINAL_PROMPT_BODY

---

## Score history

| round | score_A | score_B | B_source | winner | synth_score |
|-------|---------|---------|----------|--------|-------------|
$SCORE_HISTORY_ROWS

## Criteria flips

$CRITERIA_FLIPS

## Caveats

$CAVEAT_BANNER_OR_NONE
EOF
echo "Final prompt saved to: $FINAL_PATH"
```

If `.prompts/` was fallback-tmpdir'd at checkpoint time, the FINAL.md goes to the same fallback path — never silently split locations.

**Step 2 — Print to the conversation:**

1. **Final prompt** as a fenced markdown block (copy-paste ready). No auto-execution.

2. **Saved-to path** — one line: `✅ Saved to <FINAL_PATH>` (so the user knows the file exists without scrolling).

3. **Score history table:**

   ```
   | round | score_A | score_B | B_source         | winner | synth_score |
   |-------|---------|---------|------------------|--------|-------------|
   | 1     | 4       | 5       | codex            | B      | 5           |
   | 2     | 6       | 6       | codex            | A      | —           |
   ```

   `B_source ∈ {codex, claude-fallback}`. `synth_score` is the score the synthesizer's output would get if scored (skip column if early-stop).

4. **Criteria flips** — one line per criterion that flipped PASS↔FAIL across rounds (auditability).

5. **Caveat banner** (only if any round's `B_source == claude-fallback`):

   ```
   ⚠️  Cross-model hedge was degraded in rounds {X, Y} — Codex unavailable.
       Re-run when Codex is available for a stronger tournament.
   ```

6. **Scope tag** (parent-owned, not generated by sub-agents): if `scope: project`, print:

   ```
   ℹ️  This prompt cites <repo-name> conventions; remove the <project-context> reference if reusing elsewhere.
   ```

## Reference files

Load on demand:

- `references/rubric.md` — 7 binary criteria with PASS/FAIL examples per criterion.
- `references/judge-prompt.md` — judge sub-agent system prompt + JSON schema + retry instructions.
- `references/synthesizer-prompt.md` — synthesizer sub-agent system prompt + worked example.
- `references/codex-call.md` — codex exec bash invocation pattern (stdin, gtimeout, exit codes).
- `references/fallback-voice.md` — "contrarian senior engineer" voice for when Codex is unavailable.
- `references/heuristic.sh` — Phase 1 bash draft-complexity scorer (word\_count, dims\_present, ambiguity\_markers, recommended\_max\_iter).
- `references/context-ingest.sh` — reads CLAUDE.md / AGENTS.md, truncates to 6000 bytes on line boundary.
- `references/prompts-persist.sh` — writes round artifact + sidecar JSON to `.prompts/`; handles archive, gitignore prompt, read-only fallback.

## Distinctness vs other prompt skills

- `/prompt-enhance` (legacy, in `~/.claude/CLAUDE.md`): one-shot enhancement, quick polish.
- `prompt-master` (skill at `~/.claude/skills/prompt-master/`): one-shot 9-dim intent extraction → single prompt.
- `jack-prompt-master` (this skill): multi-round tournament with Codex co-author, judged with rubric, synthesized between rounds.

All three coexist. No auto-deprecation, no auto-redirect. Pick based on stakes.
