# Rubric — 7 binary criteria, quote-then-score

Every criterion is binary: **PASS** or **FAIL**. The judge MUST quote a verbatim span from the candidate before assigning a verdict. No quote → invalid → re-judge.

A candidate's **score** = number of PASS verdicts (0–7). The skill's pass threshold defaults to 6 of 7.

---

## 1. Role clarity

**Pass means:** The prompt explicitly names the kind of engineer, agent, or reviewer the LLM should be (e.g. "senior backend engineer", "code reviewer focused on security", "Next.js + Supabase specialist").

- **PASS example:** "Act as a senior Python engineer reviewing a junior's PR." → quote names role.
- **FAIL example:** "Help me with this code." → no role named.

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

**Pass means:** The prompt states how to know the output is correct — tests to run, success criteria, examples of expected behavior, validation steps.

- **PASS example:** "Output passes if `npm test` exits 0 and `tsc --noEmit` shows no new errors. Run `npm run lint` and ensure no new warnings."
- **FAIL example:** No tests, no criteria, no examples. (Reader must guess what "correct" means.)

---

## Judge protocol summary

1. For each candidate (A and B), for each of the 7 criteria:
   1. Find a verbatim quote from the candidate's prompt that addresses (or fails to address) the criterion.
   2. If no relevant span exists, quote the closest candidate text and verdict FAIL.
   3. Output: `{candidate, criterion, quote, verdict, why}`.
2. Total: 7 criteria × 2 candidates = **14 verdicts**. Length must be exactly 14.
3. `score_A` = count of A's PASS verdicts (0–7). `score_B` = count of B's PASS verdicts (0–7).
4. `winner` = whichever has higher score; `tie` if equal.
5. `early_stop` = true iff `max(score_A, score_B) >= threshold`.
