# Synthesizer guidance (Round 3, inline)

Used by Claude Code **inline in the main context** (no subagent) after the optional Codex consult. You compose **v3** of a coding prompt by taking the best parts of v2 (Round 2 output) and Codex's v3 candidate, guided by Codex's per-criterion critique and your own rubric check. Your output is a single revised prompt — nothing else.

## Inputs you will receive

1. v2's full prompt text (Candidate A below).
2. Codex's v3 candidate (Candidate B below).
3. Codex's per-criterion critique of v2, plus the Round 2 grill verdicts.
4. The rubric (for criterion definitions).

## Mandate

Compose v3 by merging strengths:

- For each criterion where **one candidate passed and the other failed**: keep the passing candidate's wording.
- For each criterion where **both passed**: keep whichever phrasing is tighter (shorter while still passing).
- For each criterion where **both failed**: write new content that would pass. Refer to the rubric's PASS examples for shape.
- Preserve the underlying task intent from the original draft (do not pivot to a different task).

## Output format — strict

The v3 block emitted to the user is **only** the revised prompt. No commentary, no headers, no "Here is v3:" preamble. Apply the preamble strip (`^(Sure|Here'?s|Okay|Got it)`) defensively, but a robust output starts directly with the prompt content.

**Do not emit:**

- `scope:` lines (parent owns scope metadata)
- Markdown frontmatter
- Round numbers, version labels
- Justification or commentary about your choices

## Failure contract

If the synthesized v3 is empty, one line or less, or self-scores lower than v2, keep v2 as the final prompt and say so in the caveats. Never return something worse than v2.

## Worked example (toy)

**Candidate A (v2):**
> Act as a senior Python engineer. Refactor `worker.py` to use asyncio. Output a unified diff.

**Candidate B (Codex v3 candidate):**
> Refactor the worker module. Make it async. If the database schema is ambiguous, ask before coding.

**Critique verdicts (abridged):**
- A passes role_clarity, output_format. Fails failure_mode_handling.
- B passes failure_mode_handling. Fails role_clarity, output_format.
- Both fail constraint_tightness, verifiability.

**Synthesized v3:**
> Act as a senior Python engineer. Refactor `worker.py` to use asyncio.
>
> Output a unified diff against `worker.py` only. No commentary outside the diff. Do not introduce new dependencies. Do not modify any other file.
>
> If the database schema is ambiguous, stop and ask before coding. If asyncio support is infeasible for any blocker (e.g., sync-only library in the call chain), list the blocker and stop.
>
> Output passes if `pytest -q` exits 0 and `mypy worker.py` reports no new errors.

Notice: A's role + format kept verbatim; B's ambiguity handling kept verbatim; both-failed criteria (constraints, verifiability) filled in with new content following rubric pass shapes.

## Anti-patterns

- Do not invent new requirements unrelated to the draft.
- Do not drop content that was passing in both candidates.
- Do not write meta-commentary ("I merged the role from A with the failure handling from B").
- Do not exceed roughly 2× the length of the longer input candidate.
