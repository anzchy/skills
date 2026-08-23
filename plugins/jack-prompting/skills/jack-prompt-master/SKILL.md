---
name: jack-prompt-master
description: Two-round meta-prompting skill that refines a coding prompt — Phase 2 classifies the task, runs bounded repo reconnaissance on paths the draft names, and asks the user only decision-changing questions; Round 1 is an inline Claude rewrite under a provenance rule (no invented defaults) against a 7- or 9-criterion rubric; Round 2 is a mandatory "Grill yourself" adversarial review in a fresh, isolated Fable subagent that quotes evidence per criterion and rewrites to v2; Round 3 is an optional, user-gated Codex critique + synthesis. Use this skill when the user wants to elevate a rough or high-stakes prompt for downstream coding tasks. Trigger keywords - "tournament prompt", "iteratively refine prompt", "meta-prompting", "/jack-prompt-master", "improve this prompt with multiple rounds". Distinct from one-shot /prompt-enhance.
version: 0.1.2
---

# jack-prompt-master

Two-round self-refinement (plus an optional Codex round) for high-stakes coding prompts. Runs **inline** within a single skill invocation (not via `/loop`).

## When to invoke

- User types `/jack-prompt-master <draft>` or asks for a "tournament", "multi-round refinement", "meta-prompting" pass on a prompt.
- The draft is for a coding task and quality matters more than speed.
- For quick polish, use `/prompt-enhance` (one-shot) instead — this skill costs roughly 15k–35k tokens per run (more if the Codex round is taken).

## Why 2+1 rounds

Most of the gain comes from one strong rewrite plus one independent critique. A reviewer in a **fresh context** that only sees the artifact + criteria catches more than the author re-reading its own reasoning (see code.claude.com/docs/en/best-practices.md#add-an-adversarial-review-step). Codex is an opt-in hedge, not a default.

## Output disposition (explicit)

This skill produces a **copy-paste prompt block**. It does NOT auto-execute the prompt downstream, does NOT pipe to another sub-agent, does NOT continue the conversation as the refined prompt. The user pastes the final prompt into a fresh chat or another skill themselves.

## Configuration (env overrides)

| Knob                | Default                    | Env override                 |
| ------------------- | -------------------------- | ---------------------------- |
| JPM_CODEX_ROUND    | ask                        | `JPM_CODEX_ROUND` (ask/yes/no) |
| JPM_INTERVIEW      | ask                        | `JPM_INTERVIEW` (ask/auto)   |
| JPM_RECON          | on                         | `JPM_RECON` (on/off)         |
| JPM_RECON_CAP      | 4000 bytes                 | `JPM_RECON_CAP`              |
| CONTEXT_INGEST     | ON if `./CLAUDE.md` exists | `JPM_CONTEXT` (on/off)       |
| CONTEXT_BYTE_CAP  | 6000 bytes                 | `JPM_CONTEXT_CAP`            |
| CODEX_MODEL        | gpt-5.4                    | `JPM_CODEX_MODEL`            |
| CODEX_EFFORT       | medium                     | `JPM_CODEX_EFFORT`           |
| CODEX_TIMEOUT_SEC | 300                        | `JPM_CODEX_TIMEOUT`          |
| PROMPTS_DIR        | `./.prompts/`              | `JPM_PROMPTS_DIR`            |
| GITIGNORE_PROMPT   | ask once per project       | `JPM_GITIGNORE`              |
| DRAFT_MAX_BYTES   | 50000                      | `JPM_DRAFT_MAX`              |

AskUserQuestion answers always override env. Validate at Phase 0; abort on out-of-range.

`JPM_INTERVIEW=auto` never asks the user back: missing decisions are written into the prompt as labelled assumptions or open questions instead. Use it for unattended runs.

## Phase 0 — Pre-flight checks

Run these BEFORE Phase 0a. Abort cleanly on any failure with a clear message — do NOT silently degrade.

1. **Dependency probe** (Bash, one call):

   ```bash
   command -v jq >/dev/null || { echo "ABORT: jq missing — brew install jq / apt install jq"; exit 1; }
   command -v sha256sum >/dev/null || command -v shasum >/dev/null || { echo "ABORT: neither sha256sum nor shasum on PATH"; exit 1; }
   command -v codex >/dev/null && echo "CODEX_AVAILABLE=1" || echo "CODEX_AVAILABLE=0 — Round 3 (Codex consult) will be skipped"
   command -v gtimeout >/dev/null || command -v timeout >/dev/null || echo "WARN: no timeout wrapper — relying on codex internal timeout"
   ```

2. **Agent tool probe**: dispatch one `Agent` call with `subagent_type: general-purpose` asking the agent to reply with the single word `ok`. If the call errors or returns empty, abort: "ABORT: Agent tool / general-purpose sub-agent unavailable."

3. **Config validation**: read all `JPM_*` env vars; range-check each against the Configuration table above. Out-of-range → abort with the offending knob name.

## Phase 0a — Draft input

If `$ARGUMENTS` is empty:

- Call `AskUserQuestion` with a single question: "Paste your draft prompt:" (Header: "Draft"). Accept user-supplied text.
- If still empty after the AUQ, print usage `Usage: /jack-prompt-master "<draft prompt>"` and exit.

If `$ARGUMENTS` is non-empty:

- Write the draft verbatim to a tmpfile: `DRAFT_FILE=$(mktemp /tmp/jpm-draft-XXXXXXXX.txt)` and `printf '%s' "$ARGUMENTS" > "$DRAFT_FILE"`. Never inline a multi-line draft into shell args (it shell-mangles).
- Byte-check: if `wc -c < "$DRAFT_FILE"` > `DRAFT_MAX_BYTES`, warn and offer truncation at 10k chars via AUQ.

## Phase 1 — Context-ingest opt-in

If `./CLAUDE.md` exists (and `JPM_CONTEXT` is not `off`), run one AUQ for **CONTEXT\_INGEST**: "Adapt this prompt to the current project? Detected: `./CLAUDE.md` (N lines)." Options: `Yes, adapt (recommended)` / `No, keep portable` / `Yes but show me what's ingested first`. If user picks "show me first", `cat` the ingest preview then re-ask.

No round-count or pass-threshold questions — the round structure is fixed (2 + optional Codex).

## Phase 2 — Intent extraction + Recon + Interview + Context ingest + Resume check

1. **Intent extraction (semantic):** invoke the workflow at `~/.claude/skills/prompt-master/SKILL.md` against `$DRAFT_FILE`. Produce a structured intent block over the 9 dimensions (task / target\_tool / output\_format / constraints / input / context / audience / success\_criteria / examples). Mark each dimension `user-stated` or `unspecified` — never fill an unspecified dimension with a guessed value at this stage.

1a. **Task classification:** set `TASK_CLASS`:
   - `diagnosis` — the draft is about something that is broken, failing, flaky, slow, or "why does X happen" (fix / debug / investigate / root-cause).
   - `implementation` — everything else (add / build / refactor / migrate / write tests / review).
   Print one line: `Task class: diagnosis (9 criteria)` or `Task class: implementation (7 criteria)`. `N_CRITERIA` = 9 or 7. When unsure, pick `implementation`.

1b. **Reconnaissance (bounded, project-local):** skip if `JPM_RECON=off`. Otherwise, for each file path, directory, symbol, or command name that appears **in the draft text** (not guessed), and only inside the workspace root (`git rev-parse --show-toplevel` or `$PWD`):
   - Path exists → record its size, language, and the imports/top-level symbols relevant to the task (`rg`/`head`, never more than ~2k bytes per file).
   - Path missing → record `MISSING: <path>`.
   - Symbol → `rg -n --max-count 5 '<symbol>'` and record file:line hits.
   - Always check manifests once: `package.json` `scripts` block, `Makefile` targets, `pyproject.toml`/`Cargo.toml`/`go.mod` presence, CI config filenames. Record the **verbatim test/build/lint commands** found, or `NO_TEST_COMMAND_OBSERVED`.
   - Never read `node_modules/`, `vendor/`, `dist/`, `.git/`, `.env*`, or any file matching `*secret*|*key*|*.pem`. Hard cap total recon output at `JPM_RECON_CAP` bytes; truncate with `…[recon truncated]`.
   Every recorded fact is prefixed `observed <file>[:line]:` so it can be cited downstream. Write to `RECON_FILE`; if nothing was recorded, write `none`. Recon facts are a snapshot — v-prompts that cite them must still tell the downstream agent to re-verify before relying on them.

1c. **Interview (decision-impact gated):** from the intent block's `unspecified` dimensions and the recon results, list the decisions where **different plausible answers would lead to materially different implementations** (e.g. retry policy values, idempotency rules, breaking-change tolerance, which of two existing patterns to follow, target runtime). Ignore unspecified dimensions that do not change the work (audience, examples). Then:
   - `JPM_INTERVIEW=ask` (default) and the list is non-empty → one `AskUserQuestion` with at most **3** questions (the highest-impact ones), each with 2–4 concrete options plus "Let the prompt leave this as an open question". Record answers as `user-stated` in `INTERVIEW_FILE`.
   - `JPM_INTERVIEW=auto`, or the list is empty → write `none` to `INTERVIEW_FILE`. Every such decision MUST surface in the prompt as a labelled `assumption` or an explicit `open question` for the downstream agent — never as an unlabelled value.

2. **Context ingest** (if user opted in at Phase 1): run `bash references/context-ingest.sh > $CONTEXT_FILE`. The script reads `./CLAUDE.md` then `./AGENTS.md` (priority order), truncates at 6000 bytes on the last newline within the byte window, emits a `<project-context>...</project-context>` fenced block. If both files missing, emit empty file and flip `scope: portable`. Compute `CONTEXT_SHA256=$(sha256sum "$CONTEXT_FILE" | cut -d' ' -f1)`; if context is empty, set `CONTEXT_SHA256=none`.
3. **Compute resume key:** normalize the draft (collapse runs of whitespace, strip leading/trailing blank lines), then `DRAFT_SHA256=$(printf '%s' "$NORM_DRAFT" | sha256sum | cut -d' ' -f1)`. The resume key is the tuple `(DRAFT_SHA256, scope, CONTEXT_SHA256)`.
4. **Resume scan:** `ls .prompts/*.json 2>/dev/null` and parse each sidecar with `jq` to find a tuple match.
   - If a match exists and `terminal: false` (i.e. a run stopped after Round 1 or Round 2): AUQ "Resume from latest? Found `<filename>` — round k scored N/7 (or N/9). Continue to round k+1 / Start fresh (archive existing) / Show me the latest file first."
   - If a match exists and `terminal: true`: AUQ "Found a completed run for this exact draft (round k, score N/7 or N/9). Show the final prompt / Start fresh (archive existing) / Open the file." NEVER offer "continue from round k+1" on a terminal checkpoint.
   - On "Start fresh": move existing `.prompts/*.{md,json}` to `.prompts/archive/` (create archive dir; on filename collision append `.dup-$(date +%s)`).
   - Stale tuple (no match): skip the AUQ entirely; do NOT archive prior files.
5. **Seed construction:** the seed for Round 1 = `<intent block>\n<recon block>\n<interview block>\n<context block (if any)>\n<draft>`. On resume from round k, the seed is the "Final prompt" section of `.prompts/round-k.md` — but only read from disk at Phase 2 startup. During an active run, in-memory state is the source of truth.

## Phase 3 — Round 1: inline self-refinement (main context, no subagent)

Claude Code rewrites the draft into **v1** directly in the main context:

- Inputs: the seed (intent block + recon facts + interview answers + project context + draft), `TASK_CLASS`, and the active criteria in `references/rubric.md` (1–7, or 1–9 for `diagnosis`).
- Write v1 so that every active criterion would PASS with a quotable span. Preserve the draft's underlying task intent — do not pivot to a different task.
- **Provenance rule (hard):** every concrete value, policy, file fact, or command in v1 is either user-stated (draft / interview), `observed` (cite the recon file:line inline, e.g. "uses `fetch` (observed `src/api/client.ts:12`)"), labelled `(assumption — confirm)`, or phrased as an instruction for the downstream agent to discover/ask. Do not invent defaults. If recon reported `NO_TEST_COMMAND_OBSERVED`, v1 must tell the downstream agent to find the project's test command first and must not name one. If recon reported `MISSING: <path>`, say so in v1 rather than instructing the agent to "read <path>".
- Output v1 only. No preamble ("Sure", "Here's", …), no `scope:` line, no frontmatter, no commentary.

Print v1 as a fenced block, then write the Round 1 checkpoint (see "Checkpoint write" below) with `source=claude-inline`, `terminal=false`. No score is assigned in Round 1 — `score_v1` comes from the Round 2 grill.

## Phase 4 — Round 2: "Grill yourself" in an isolated context (mandatory)

Dispatch **ONE** `Agent` call:

- `subagent_type: general-purpose`, `model: fable`.
- **NOT `fork`.** The reviewer must not inherit conversation history — it sees only the artifact + criteria, which is the whole point of the adversarial review.
- The prompt is the full text of `references/grill-prompt.md` with the placeholders filled: `{{INTENT_BLOCK}}`, `{{CONTEXT_BLOCK_OR_none}}`, `{{RECON_FACTS_OR_none}}`, `{{INTERVIEW_ANSWERS_OR_none}}`, `{{TASK_CLASS}}`, `{{N_CRITERIA}}`, `{{V1_PROMPT}}`, and `{{RUBRIC_CRITERIA}}` (paste `references/rubric.md` sections 1–7, or 1–9 for `diagnosis`, plus the rubric's provenance vocabulary and intent-gate paragraphs). The prompt contains the literal heading `## Grill yourself`.

**Grill protocol** (enforced by `references/grill-prompt.md`): first an **intent gate** (hard-fail, unscored — lists every unlabelled scope/policy item v1 invented as `intent_drift`), then for each of the N criteria, the subagent asks itself the hardest question a skeptical senior engineer would ask, quotes the exact v1 text that answers it or marks FAIL with the missing piece, then rewrites v1 into **v2** fixing every FAIL. It returns strict JSON:

```json
{
  "intent_drift": [ "..." ],
  "verdicts": [ { "criterion": "...", "verdict": "PASS|FAIL", "quote": "...", "fix": "..." } ],
  "score_v1": 0,
  "score_v2": 0,
  "v2": "<prompt>"
}
```

**Validate with `jq -e`** (write the raw reply to `grill_output.json` first; strip surrounding markdown fences if present):

```bash
jq -e --argjson n "$N_CRITERIA" '
  (.intent_drift | type == "array")
  and (.verdicts | length == $n)
  and (.verdicts | map(select(.quote == "" or .quote == null)) | length == 0)
  and (.verdicts | map(.verdict) | all(. == "PASS" or . == "FAIL"))
  and (.score_v1 | type == "number") and (.score_v1 >= 0) and (.score_v1 <= $n)
  and (.score_v2 | type == "number") and (.score_v2 >= 0) and (.score_v2 <= $n)
  and (.v2 | type == "string") and ((.v2 | length) > 0)
' < grill_output.json > /dev/null
```

On `jq -e` non-zero: retry ONCE (same prompt) with the reminder "Emit valid JSON only, matching the schema exactly. No commentary." On second failure: regex-extract `score_v1` / `score_v2` / `v2` from the reply and flag the round's confidence as **"degraded"** in the output and FINAL.md caveats.

Apply the preamble strip `^(Sure|Here'?s|Okay|Got it)[^\n]*\n` to `v2`. If `v2` is empty after strip, retry once; on second empty, keep v1 as v2 and mark degraded.

**Print:**

1. v2 as a fenced block.
2. `Intent drift:` the `intent_drift` list, or `none`.
3. The N-row verdict table: `| criterion | verdict (v1) | quote | fix |`.
4. One line: `score_v1 → score_v2`, e.g. `4/7 → 7/7` (or `/9` for diagnosis).

Write the Round 2 checkpoint with `source=fable-grill`, `score=score_v2`. Set `terminal=true` if Codex is unavailable or `JPM_CODEX_ROUND=no` (no Round 3 possible); otherwise `terminal=false`, and re-persist Round 2 with `terminal=true` if the user stops at the Round 3 gate.

## Phase 4a — Round 3: optional Codex consult (user-gated)

**Gate.** Resolve `JPM_CODEX_ROUND`:

- If `codex` is not on PATH (`CODEX_AVAILABLE=0` from Phase 0): skip the question entirely and print one line — `ℹ️ Codex not on PATH — skipping optional Round 3; v2 is final.` Proceed to Phase 5.
- If `JPM_CODEX_ROUND=no`: skip the question; v2 is final.
- If `JPM_CODEX_ROUND=yes`: skip the question; run Round 3.
- Otherwise (`ask`, the default) — one `AskUserQuestion` (Header: "Round 3"): **"v2 scored N/7 (or N/9). Consult Codex for a 3rd round?"** Options:
  1. `Stop here — use v2 (recommended when ≥6/7, or ≥8/9 for diagnosis)`
  2. `Yes, Codex critique + synthesize v3`
  3. `Show v2 full text first` → print v2 in full, then re-ask with options 1–2 only.

**Never run Codex without this answer** (or an explicit `JPM_CODEX_ROUND=yes`).

**If yes:**

1. Send v2 + the rubric to Codex using the Bash pattern in `references/codex-call.md` (stdin via `codex exec -`, `gtimeout`/`timeout` wrapper, exit-code semantics). The instruction at the top of `PROMPT_FILE` asks Codex for (a) a per-criterion critique of v2 and (b) its own v3 candidate, in that order, separated by the literal line `---CANDIDATE---`.
2. Exit 0 with non-empty stdout → Claude Code synthesizes the final **v3 inline** (main context, no subagent) from v2 + Codex's critique + Codex's candidate, following `references/synthesizer-prompt.md`. Apply the preamble strip. Self-score v3 against the rubric (quote-then-verdict, same active criteria set, after the intent gate) to obtain `score_v3`.
3. Exit 124 / non-zero / empty stdout → **keep v2 as final** and print the degraded-hedge caveat:

   ```
   ⚠️  Cross-model hedge was degraded — Codex unavailable or failed (exit N).
       v2 is final. Re-run with Codex available for a stronger Round 3.
   ```

   Do NOT dispatch a Claude fallback voice in place of Codex — the point of Round 3 is the cross-model hedge; without Codex it is skipped, not simulated.

Write the Round 3 checkpoint with `source=codex-synth`, `score=score_v3`, `terminal=true`. If Codex failed, write no Round 3 checkpoint; instead re-persist Round 2 with `terminal=true`.

## Checkpoint write (every round)

Call `bash references/prompts-persist.sh` with the round artifact via stdin (markdown body) + sidecar JSON args. The script writes BOTH a human-readable `.md` and a sidecar `.json` — you must pass the markdown body to its stdin.

**The markdown body fed to stdin MUST contain:**

```
## Original draft
<verbatim draft>

## Project context (ingested)
<truncated CLAUDE.md / AGENTS.md content, or "none">

## Recon + interview
<task class, recon facts, interview Q&A — or "none">

## Round input
<the seed / prior-round prompt this round started from>

## Round output
<v1 | v2 | v3>

## Verdicts
<Round 1: "n/a — scored in Round 2" | Round 2: grill JSON pretty-printed | Round 3: Codex critique + self-score>

## Final prompt (this round's result)
<the round's output prompt text — the prompt the user receives if the run stops here>
```

The "Final prompt" section is mandatory on every checkpoint. The body is NOT optional — never invoke `prompts-persist.sh` with empty stdin.

**Sidecar fields** (all required): `round`, `date`, `draft_sha256`, `draft_word_count`, `scope`, `context_sha256`, `source` (`claude-inline` / `fable-grill` / `codex-synth`), `score` (0–7; Round 1 writes `0` — it is scored by the Round 2 grill), `terminal` (`true` on the last round written, else `false`).

Other persist-script behavior:

- Creates `.prompts/` if missing; on EROFS or chmod, falls back to `$TMPDIR/.prompts-$$/` and informs the user (skip resume next time).
- First-run-per-project: AUQ asks whether to add `.prompts/` to `.gitignore`. Remember the answer in `~/.gstack/projects/<slug>/.prompts-gitignore-prompted`.
- Writes `YYYY-MM-DD_HHMMSS_round-k.md` + `YYYY-MM-DD_HHMMSS_round-k.json`.

In-memory state remains the source of truth for the next round's seed. Disk is checkpoint-only.

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
exit_reason: $EXIT_REASON   # stop_after_v2 | codex_synth | codex_unavailable | codex_failed
---

# Final prompt — jack-prompt-master

$FINAL_PROMPT_BODY

---

## Score history

| round | score | source |
|-------|-------|--------|
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
   | round | score | source        |
   |-------|-------|---------------|
   | 1     | 4     | claude-inline |
   | 2     | 7     | fable-grill   |
   | 3     | 7     | codex-synth   |
   ```

   `source ∈ {claude-inline, fable-grill, codex-synth}`. Scores are out of 7 (`implementation`) or 9 (`diagnosis`); print the denominator in the table header. Round 1's score is `score_v1` as assessed by the Round 2 grill. Round 3 row appears only if Codex synthesis ran.

4. **Criteria flips** — one line per criterion that flipped PASS↔FAIL between v1 and v2 (and v2 → v3 if applicable), for auditability.

5. **Caveat banner** (only if Round 3 was requested but Codex failed, or Round 2 was flagged degraded):

   ```
   ⚠️  Cross-model hedge was degraded — Codex unavailable or failed.
       Re-run when Codex is available for a stronger Round 3.
   ```

6. **Scope tag** (parent-owned, not generated by sub-agents): if `scope: project`, print:

   ```
   ℹ️  This prompt cites <repo-name> conventions; remove the <project-context> reference if reusing elsewhere.
   ```

## Reference files

Load on demand:

- `references/rubric.md` — binary criteria (7 for implementation, 9 for diagnosis) with PASS/FAIL examples, provenance vocabulary, and the intent gate.
- `references/grill-prompt.md` — Round 2 subagent prompt ("Grill yourself" protocol + JSON schema + retry instructions).
- `references/synthesizer-prompt.md` — Round 3 inline synthesis guidance (v2 + Codex critique/candidate → v3) + worked example.
- `references/codex-call.md` — codex exec bash invocation pattern (stdin, gtimeout, exit codes).
- `references/context-ingest.sh` — reads CLAUDE.md / AGENTS.md, truncates to 6000 bytes on line boundary.
- `references/prompts-persist.sh` — writes round artifact + sidecar JSON to `.prompts/`; handles archive, gitignore prompt, read-only fallback.

## Distinctness vs other prompt skills

- `jack-meta-think` (upstream, domain-general): diagnoses whether the question is aimed at the truth or at agreement — embedded conclusions, missing timeline, missing ruled-out factors. This skill assumes the aim is already correct and only optimizes the wording; if the draft's premise is unverified, run `/jack-meta-think` first.
- `/prompt-enhance` (legacy, in `~/.claude/CLAUDE.md`): one-shot enhancement, quick polish.
- `prompt-master` (skill at `~/.claude/skills/prompt-master/`): one-shot 9-dim intent extraction → single prompt.
- `jack-prompt-master` (this skill): rewrite → isolated adversarial grill → optional Codex hedge, scored with a rubric at each step.

All coexist. No auto-deprecation, no auto-redirect, no auto-chaining. Pick based on stakes — and on whether the question or the wording is what needs work.
