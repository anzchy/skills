# Rubric — binary criteria, quote-then-score

Every criterion is binary: **PASS** or **FAIL**. The reviewer (Round 2 grill, Round 3 self-score) MUST quote a verbatim span from the prompt before assigning a verdict. No quote → invalid → re-review.

**Criteria count depends on task class** (set at Phase 2):

- `implementation` (default): criteria 1–7 → score 0–7. Stop bar: 6/7.
- `diagnosis` (bug / "why does X happen" / "fix the failing Y"): criteria 1–9 → score 0–9. Stop bar: 8/9.

A prompt's **score** = number of PASS verdicts.

**Provenance vocabulary** (used by criteria 1 and 7): every concrete detail in a prompt is one of `user-stated` (in the draft or an interview answer), `observed` (found in the repo by Phase 2 reconnaissance — cite the file), `assumption` (labelled as such in the prompt text), or `open question` (the prompt tells the downstream agent to discover or ask). A detail that is none of these is a **fabrication**.

**Intent gate (not scored, hard-fail):** the reviewer first checks that the prompt still asks for the task in `<intent>` and does not add scope or policy the user never stated and that is not labelled `assumption`. If the gate fails, the prompt's score is reported but the reviewer must fix the drift in the rewrite before anything else.

---

## 1. Provenance (anti-fabrication)

**Pass means:** Every concrete value, policy, or project fact in the prompt is either user-stated, observed (cited), labelled as an assumption, or turned into an explicit open question. No invented defaults presented as requirements.

- **PASS example:** "Defaults (assumption — confirm before merging): 3 retries, 200 ms base." / "The client uses `fetch` (observed in `src/api/client.ts:12`)."
- **FAIL example:** "Defaults: 3 retries, 200 ms base, multiplier 2, max 5 s." when the draft never mentioned any of these and nothing in the repo establishes them → fabricated policy.

Why this replaces "role clarity": a persona line ("Act as a senior engineer") is a free rubric point that says nothing about whether the prompt will execute correctly. A prompt may still open with a role; it just isn't scored.

## 2. Context sufficiency

**Pass means:** The codebase, stack, framework, or prior decisions are stated or referenced. If context ingestion was used, the prompt cites the project's actual stack.

- **PASS example:** "We use Next.js 14 App Router with Supabase RLS and OAuth via Google. The auth middleware is in `src/middleware.ts`." → concrete context.
- **FAIL example:** "Refactor the auth code." → no stack, no file, no prior decision.

## 3. Task specificity

**Pass means:** The prompt names a concrete operation, not a vague verb. "Refactor `X` so it does `Y` under condition `Z`" passes; "improve this" fails.

- **PASS example:** "Replace the polling loop in `worker.ts` with an event-driven subscription on the `jobs` table."
- **FAIL example:** "Make this code better." / "Polish the UX." / "Optimize this."

## 4. Output format

**Pass means:** The expected output shape is explicit and unambiguous. Pick one: unified diff, full file, code block snippet, line range, prose explanation, JSON, markdown. Mixed is fine if the prompt says so.

- **PASS example:** "Return a unified diff against `src/auth.ts` only. No commentary outside the diff."
- **FAIL example:** "Show me the changes." → format unspecified.

## 5. Constraint tightness

**Pass means:** The prompt states what NOT to do — scope boundaries, style restrictions, security constraints, dependency limits.

- **PASS example:** "Do not introduce new dependencies. Do not modify any file outside `src/auth/`. Do not log secrets."
- **FAIL example:** No constraints stated at all. (Just "be careful" is not a constraint.)

## 6. Failure-mode handling

**Pass means:** The prompt tells the LLM what to do if input is ambiguous, the task is infeasible, or required context is missing.

- **PASS example:** "If the migration cannot be applied without downtime, stop and ask. If the schema is ambiguous, list the assumptions before coding."
- **FAIL example:** No instruction for ambiguity / missing context / infeasible cases.

## 7. Verifiability

**Pass means:** The prompt states how to know the output is correct — tests to run, success criteria, examples of expected behavior, validation steps — **and any named command is project-observed**. A command counts as observed only if reconnaissance found it (a `scripts` entry in `package.json`, a Makefile target, a CI step, a pytest/cargo/go config). If no command was observed, the prompt must instruct the downstream agent to discover the project's test/build command (or ask) before relying on it. Naming a command that does not exist in the project is a FAIL even if the sentence is well-formed.

- **PASS example:** "Output passes if `npm test` (observed: `package.json` scripts.test) exits 0 and `tsc --noEmit` shows no new errors."
- **PASS example (nothing observed):** "Before coding, find the project's test command (`package.json` scripts, Makefile, CI config) and state it. Done when that command exits 0 and the new tests for X, Y, Z pass."
- **FAIL example:** No tests, no criteria, no examples. (Reader must guess what "correct" means.)
- **FAIL example:** "Done when `npm test` exits 0" in a repo with no `package.json`.

## 8. Timeline & reproduction (diagnosis only)

**Pass means:** The prompt states what changed between working and broken — before/after state, when it started, what happened in between (deploy, upgrade, config change) — and gives concrete reproduction: the command or steps, the observed output/error verbatim, and whether it is consistent or intermittent. A failure is a *change*; a prompt that only describes the broken state fails.

- **PASS example:** "Worked on main at `a1b2c3`; fails since the Node 20 upgrade yesterday. Repro: `npm run e2e -- --grep login` → `TimeoutError: token refresh` on ~1 in 3 runs."
- **FAIL example:** "Login is broken, please fix." → no before/after, no repro, no error text.

## 9. Ruled-out causes (diagnosis only)

**Pass means:** The prompt lists what has already been tried or eliminated, with the evidence, so the downstream agent does not re-investigate it — or explicitly says nothing has been ruled out yet.

- **PASS example:** "Already ruled out: network (same failure against localhost), stale cache (reproduces after `rm -rf node_modules/.cache`). Not yet checked: clock skew."
- **FAIL example:** No mention of prior attempts; the agent will start from zero and may repeat the user's own dead ends.

---

## Review protocol summary

1. Run the intent gate first (hard-fail, not scored).
2. For each criterion in the active set (1–7, or 1–9 for `diagnosis`):
   1. Find a verbatim quote from the prompt that addresses (or fails to address) the criterion.
   2. If no relevant span exists, quote the closest text and verdict FAIL.
   3. Output: `{criterion, verdict, quote, fix}`.
3. Total: **exactly N verdicts**, N = 7 or 9 per task class.
4. `score` = count of PASS verdicts (0–N).
5. In Round 2 this is applied to v1 (`score_v1`) and then to the rewritten v2 (`score_v2`); in Round 3 to the synthesized v3 (`score_v3`).
