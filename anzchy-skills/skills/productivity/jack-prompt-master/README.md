# jack-prompt-master

Tournament-based meta-prompting skill for high-stakes coding prompts. Inspired by Garry Tan's *Metaprompting* essay.

**Status:** v0.1.0 — project-scope, manual install. See `docs/plans/20260512-plan-prompt-master.md` for the full design.

## What it does

Given a rough draft prompt, run a multi-round tournament that:

1. Extracts intent across 9 dimensions (reuses `prompt-master`'s extraction).
2. (Optional) Ingests local `./CLAUDE.md` so the prompt cites real project stack.
3. Per round: generates **Candidate A** (Claude sub-agent, rigorous-engineer voice) and **Candidate B** (Codex, contrarian-engineer voice) **in parallel**.
4. Judges both with a 7-criterion binary rubric. Every verdict is quote-then-score (no false 1-100 precision).
5. Stops early when `max(score_A, score_B) >= threshold`; otherwise the synthesizer composes v(k+1) from the best parts and the next round runs.
6. Persists every round to `.prompts/YYYY-MM-DD_HHMMSS_round-k.{md,json}` for audit and auto-resume.
7. Outputs the final prompt as a copy-paste block — no auto-execution.

## When to pick which skill

| Skill | Shape | Use when |
|---|---|---|
| `/prompt-enhance` | One-shot, in-line | Quick polish, low-stakes |
| `prompt-master` | One-shot, 9-dim extraction | Structured single rewrite |
| `jack-prompt-master` | Multi-round tournament + Codex co-author + judge + synth | High-stakes coding prompt where output quality matters more than 30s of latency |

All three coexist. None auto-deprecates the others.

## Install (project scope, for testing)

This skill currently lives at `.claude/skills/jack-prompt-master/` within this repo. Project-scope skills auto-load when Claude Code starts in this directory.

To promote to user scope (cross-project):

```bash
mv .claude/skills/jack-prompt-master ~/.claude/skills/
```

## Dependencies

- `jq` — sidecar JSON parsing, judge schema validation. `brew install jq` / `apt install jq`.
- `sha256sum` or `shasum` — resume-key computation. Built-in on macOS (`shasum`) and Linux (`sha256sum`).
- `codex` (optional) — Candidate B's model. On failure or absence, falls back to a second Claude voice and prints a degraded-hedge banner.
- `gtimeout` / `timeout` (optional) — wraps the Codex call. macOS: `brew install coreutils` for `gtimeout`. Without it the skill relies on Codex's internal timeout.

The skill verifies all of these at Phase 0 and aborts with a clear message if hard deps are missing.

## Cost & latency

| Mode | Per-round Anthropic input | At MAX_ITER=3 | At MAX_ITER=7 |
|---|---|---|---|
| Context OFF (portable) | ~9k | ~40k | ~90k |
| Context ON (project)   | ~15k | ~55k | ~125k |

Wall time: round duration ≈ `max(Claude sub-agent latency, 5-min Codex timeout) + judge latency`. Worst-case at MAX_ITER=7 ≈ ~42 min if no early stop. Default MAX_ITER=3 keeps typical runs under ~15 min.

Codex usage is on a separate billing path.

## Usage

```
/jack-prompt-master "<your draft prompt>"
```

If invoked without arguments, the skill will AskUserQuestion for the draft.

### Env knobs (all optional)

```bash
JPM_MAX_ITER=3           # 2/3/5/7
JPM_PASS_THRESHOLD=6     # 5/6/7
JPM_CONTEXT=on           # on/off — default ON if ./CLAUDE.md exists
JPM_CONTEXT_CAP=6000     # bytes; truncation cap for ingested context
JPM_CODEX_EFFORT=medium  # low/medium/high
JPM_CODEX_TIMEOUT=300    # seconds
JPM_PROMPTS_DIR=./.prompts
```

## Output

1. Final prompt (copy-paste markdown block).
2. Score history table per round (`round | score_A | score_B | B_source | winner | synth_score`).
3. Criteria-flip lines for auditability.
4. Caveat banner if any round fell back to Claude-vs-Claude.
5. Scope tag if project-mode was used.

## `.prompts/` persistence

- Every round writes `YYYY-MM-DD_HHMMSS_round-k.md` + sidecar `.json` to `./.prompts/`. The `.md` body contains the original draft, both candidates, judge verdicts, synth output, and the round's winning prompt — full audit trail.
- After the loop ends, the skill writes a dedicated `YYYY-MM-DD_HHMMSS_FINAL.md` containing the copy-paste prompt + score history + caveats. This is the canonical retrievable artifact — grab it with `cat .prompts/*_FINAL.md`.
- Re-running with the same draft (sha256 match, including `scope` + `context_sha256`) offers resume.
- Terminal checkpoints (early-stop or max-iter reached) offer "show final prompt / start fresh", never "continue from round k+1".
- The skill prompts (once per project) to add `.prompts/` to `.gitignore`.

## Privacy boundary

`.prompts/` contains full draft prompts + any ingested project context (which may include API keys-adjacent stack docs, internal naming, etc.). Treat as you'd treat the source repo — gitignore, don't push, don't sync.

## v2 deferred

- Cross-task rubric swap (auto-detect non-coding intent).
- Runtime test lane (generate a test task, run candidate prompt through Claude, verify output).
- Caching of v1 across same-draft re-runs.
- "Strongest divergence from Codex" diff in the output.
- Telemetry / `.history.jsonl`.

See `docs/plans/20260512-plan-prompt-master.md` "Scope (deferred to v2)" for the full list.

## Design provenance

The full design doc with all three review rounds (Round 1 self-review, Round 2 addendum review, Round 3 independent Codex review) lives at `docs/plans/20260512-plan-prompt-master.md`. The skill ships when:

- Test plan rows #1–#9 pass against real Claude.
- Test #8 confirms the Codex fallback path works.
- At least one full smoke run with real Codex (no fallback) completes end-to-end.
- Side-by-side: a prompt produced by `jack-prompt-master` outperforms `prompt-master`'s single-shot output on at least one real coding task.
