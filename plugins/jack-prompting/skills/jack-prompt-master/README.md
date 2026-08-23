# jack-prompt-master

Two-round self-refinement (plus an optional Codex round) for high-stakes coding prompts. Inspired by Garry Tan's *Metaprompting* essay and Claude Code's [adversarial-review guidance](https://code.claude.com/docs/en/best-practices.md#add-an-adversarial-review-step).

**Status:** v0.1.1 — project-scope, manual install. See `docs/plans/20260512-plan-prompt-master.md` for the full design.

## What it does

Given a rough draft prompt:

1. Extracts intent across 9 dimensions (reuses `prompt-master`'s extraction).
2. (Optional) Ingests local `./CLAUDE.md` so the prompt cites real project stack.
3. **Round 1 — inline rewrite.** Claude Code rewrites the draft into v1 in the main context, targeting the 7-criterion rubric. No subagent.
4. **Round 2 — "Grill yourself" (mandatory).** One fresh, isolated `general-purpose` subagent (model `fable`, not a fork — it sees only v1 + the criteria, never the conversation) asks the hardest skeptical-senior-engineer question per criterion, quotes v1's evidence or marks FAIL, then rewrites to v2. Returns strict JSON validated with `jq`. You get v2, a 7-row verdict table, and `score_v1 → score_v2`.
5. **Round 3 — Codex consult (optional, user-gated).** After Round 2 the skill asks: "v2 scored N/7. Consult Codex for a 3rd round?" Stop there (recommended at ≥6/7), or have Codex critique v2 and propose its own candidate, after which Claude Code synthesizes v3 inline. Codex never runs without that answer; if `codex` isn't on PATH the question is skipped.
6. Persists every round to `.prompts/YYYY-MM-DD_HHMMSS_round-k.{md,json}` for audit and auto-resume.
7. Outputs the final prompt as a copy-paste block — no auto-execution.

Why this shape: most of the gain comes from one strong rewrite plus one independent critique. A reviewer in a fresh context catches more than the author re-reading its own reasoning. Codex is a hedge you opt into, not a default cost.

## When to pick which skill

| Skill | Shape | Use when |
|---|---|---|
| `jack-meta-think` | Upstream question diagnosis + interview | You have a suspicion or a frustration, not a draft — the premise itself needs checking. Any domain, not just coding |
| `/prompt-enhance` | One-shot, in-line | Quick polish, low-stakes |
| `prompt-master` | One-shot, 9-dim extraction | Structured single rewrite |
| `jack-prompt-master` | Rewrite → isolated adversarial grill → optional Codex hedge | High-stakes coding prompt where output quality matters more than a minute of latency |

All coexist. None auto-deprecates the others, and there is no auto-chaining: `jack-meta-think` fixes *what* you are asking, `jack-prompt-master` fixes *how* you word it. Each emits a copy-paste block you route yourself.

## Install (project scope, for testing)

This skill currently lives at `.claude/skills/jack-prompt-master/` within this repo. Project-scope skills auto-load when Claude Code starts in this directory.

To promote to user scope (cross-project):

```bash
mv .claude/skills/jack-prompt-master ~/.claude/skills/
```

## Dependencies

- `jq` — sidecar JSON parsing, grill JSON schema validation. `brew install jq` / `apt install jq`.
- `sha256sum` or `shasum` — resume-key computation. Built-in on macOS (`shasum`) and Linux (`sha256sum`).
- `codex` (optional) — Round 3 only. If absent the Round 3 question is skipped; if it fails mid-run, v2 stays final and a degraded-hedge banner is printed. No Claude stand-in is dispatched.
- `gtimeout` / `timeout` (optional) — wraps the Codex call. macOS: `brew install coreutils` for `gtimeout`. Without it the skill relies on Codex's internal timeout.

The skill verifies all of these at Phase 0 and aborts with a clear message if hard deps are missing.

## Cost & latency

Rough estimates — actual cost depends on draft length, ingested context, and how much the grill rewrites. Not measured across many runs yet.

| Mode | Round 1 (inline) | Round 2 (grill subagent) | Rounds 1+2 total | + Round 3 (Codex + inline synth) |
|---|---|---|---|---|
| Context OFF (portable) | ~3k–5k | ~8k–12k | **~12k–18k** | +~6k–10k Anthropic (Codex billed separately) |
| Context ON (project)   | ~6k–9k | ~12k–18k | **~18k–28k** | +~8k–14k Anthropic (Codex billed separately) |

Round 2 is the largest line item because the subagent receives the full seed + rubric + grill protocol and returns v2 inside a JSON envelope. Versus the v0.1 tournament (~40k–125k), a stop-at-v2 run is roughly a third of the cost.

Wall time: Round 1 is a single inline completion; Round 2 is one subagent call (typically 1–3 min); Round 3 adds up to the 5-min Codex timeout plus one inline synthesis. Typical stop-at-v2 run: under ~5 min.

## Usage

```
/jack-prompt-master "<your draft prompt>"
```

If invoked without arguments, the skill will AskUserQuestion for the draft.

### Env knobs (all optional)

```bash
JPM_CODEX_ROUND=ask      # ask/yes/no — gate for the optional Round 3 Codex consult
JPM_CONTEXT=on           # on/off — default ON if ./CLAUDE.md exists
JPM_CONTEXT_CAP=6000     # bytes; truncation cap for ingested context
JPM_CODEX_EFFORT=medium  # low/medium/high
JPM_CODEX_TIMEOUT=300    # seconds
JPM_PROMPTS_DIR=./.prompts
```

## Output

1. Final prompt (copy-paste markdown block).
2. Score history table per round (`round | score | source`, source ∈ {claude-inline, fable-grill, codex-synth}).
3. Criteria-flip lines (v1→v2, and v2→v3 if run) for auditability.
4. Caveat banner if Round 3 was requested but Codex failed, or the grill's JSON had to be regex-recovered ("degraded").
5. Scope tag if project-mode was used.

## `.prompts/` persistence

- Every round writes `YYYY-MM-DD_HHMMSS_round-k.md` + sidecar `.json` to `./.prompts/`. The `.md` body contains the original draft, the round's input and output prompts, the verdicts (grill JSON / Codex critique), and the round's final prompt — full audit trail.
- After the loop ends, the skill writes a dedicated `YYYY-MM-DD_HHMMSS_FINAL.md` containing the copy-paste prompt + score history + caveats. This is the canonical retrievable artifact — grab it with `cat .prompts/*_FINAL.md`.
- Re-running with the same draft (sha256 match, including `scope` + `context_sha256`) offers resume.
- Terminal checkpoints (run completed) offer "show final prompt / start fresh", never "continue from round k+1".
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
- Test #8 confirms the Codex-failure path keeps v2 and prints the caveat.
- At least one full smoke run with the Round 3 Codex consult completes end-to-end.
- Side-by-side: a prompt produced by `jack-prompt-master` outperforms `prompt-master`'s single-shot output on at least one real coding task.
