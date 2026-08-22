---
name: jack-auto-fix
description: |
  Find the oldest open GitHub issue and fix it end-to-end: fix → PR → review → merge.
  Use when asked to "jack-auto-fix", "fix oldest issue", or "run the auto-fix pipeline".
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
  - Skill
---

# Auto Fix: Oldest Issue End-to-End

When this skill is invoked, run the full pipeline — find the oldest open issue,
fix it, open a PR, review it (if applicable), and merge if clean.

---

## Arguments

| Invocation | Behavior |
|------------|----------|
| `/jack-auto-fix --full` | Fix → PR → `/review` → merge |
| `/jack-auto-fix --mini` | Fix → PR → auto-merge (no review) |
| `/jack-auto-fix` | Claude picks `--full` or `--mini` automatically (see Mode Router below) |

---

## Mode Router (no-arg invocation only)

When invoked with no arguments, decide the mode **before** running Step 0.

Fetch the oldest eligible issue first (same query as Step 1 below), then classify:

**Choose `--mini` if ALL of the following are true:**
- Issue has label `bug` (not `feature` / `enhancement`)
- Issue body describes a localised, mechanical change: dependency upgrade, config fix, single-file CSS/style fix, typo, or copy change
- Body does NOT mention cross-cutting concerns, API changes, or user-visible behaviour shifts
- Estimated files touched ≤ 3

**Choose `--full` for everything else:**
- Feature or enhancement labels
- Bug that likely touches logic or multiple files
- Ambiguous / no labels
- Any mention of security, auth, data loss, or IPC changes

Print your decision and reasoning in one line before proceeding:

```
AUTO MODE: --mini  (reason: dependency bump, ≤3 files, no behaviour change)
AUTO MODE: --full  (reason: feature/logic change — review warranted)
```

Then execute the chosen mode from Step 0 onward.

---

## Step 0: Pre-flight

```bash
# Must be on master with a clean tree
git branch --show-current
git status --porcelain
```

If not on master: `git checkout master && git pull origin master --quiet`.
If working tree is dirty: stop and tell the user what files are blocking.

Check for stale auto-fix branches:
```bash
git branch | grep "fix/issue-"
```
If any exist, tell the user and ask:
- A) Delete the stale branch and proceed
- B) Stop so you can investigate it first

---

## Step 1: Find the oldest eligible issue

```bash
SKIP_LABELS="epic,blocked,needs-design,wontfix"

gh issue list \
  --state open \
  --limit 100 \
  --json number,title,createdAt,labels \
  | jq --arg skip "$SKIP_LABELS" '
      [.[] | select(
        .labels | map(.name) |
        any(. as $l | ($skip | split(",")) | any(. == $l))
        | not
      )]
      | sort_by(.createdAt)
      | .[0]
    '
```

If no eligible issues: report "No eligible open issues — nothing to do." and stop.

Check whether the issue already has an open PR:
```bash
gh pr list --state open --json number,body \
  | jq -r --arg n "<ISSUE_NUMBER>" \
    '.[] | select(.body | test("(fixes|closes|resolves) #" + $n; "i")) | .number'
```

If a PR already exists: report "Issue #N already has open PR #M — skipping." and stop.

Tell the user which issue was selected and confirm you are proceeding.

---

## Step 2: Fix the issue

Run the fix-issue skill:

```
/fix-issue #<ISSUE_NUMBER>
```

This runs all six phases: fetch, branch, fix, Codex audit, gate, PR creation.

**Autonomous decisions** (do not use AskUserQuestion for these):
- Classify issue type from labels + body
- Ambiguous type → treat as bug
- Branch already exists → delete and recreate
- Feature touching >8 files → stop, report `TOO_COMPLEX`, ask user if they want to handle it manually
- Question-type issue → post answer as gh comment, report `QUESTION_ANSWERED`, stop
- Codex MCP unavailable → skip to manual mini-audit
- Gate fails 3 times → report `GATE_FAIL`, stop

After Phase 6, extract the PR number from the `gh pr create` output.

---

## Step 3: Review the PR  *(--full mode only)*

*Skip this step entirely in `--mini` mode — proceed directly to Step 4.*

Run the review skill:

```
/review #<PR_NUMBER>
```

**Autonomous decisions**:
- Apply all AUTO-FIX findings directly
- For ASK findings: apply if the fix is clearly correct; skip if genuinely ambiguous
- Do not use AskUserQuestion for individual findings — batch any real blockers into one question at the end if needed

---

## Step 4: Merge

**`--full` mode** — merge based on review completion status:

- **DONE or DONE_WITH_CONCERNS:**
  ```bash
  gh pr merge <PR_NUMBER> --merge
  ```
  Then report: `✓ Issue #<N> → PR #<PR_NUMBER> merged to master`

- **BLOCKED:**
  Report: `✗ Review blocked — PR #<PR_NUMBER> left open for manual inspection`
  Do not merge. List the blocking findings so the user knows what to address.

**`--mini` mode** — merge immediately after PR creation (no review gate):

```bash
gh pr merge <PR_NUMBER> --merge
```
Then report: `✓ Issue #<N> → PR #<PR_NUMBER> merged to master (mini mode — no review)`

---

## Step 5: Report outcome

Print a one-line summary:

```
RESULT: SUCCESS   Issue #42 → PR #99 merged [--full | --mini]
RESULT: SKIPPED   No eligible issues
RESULT: TOO_COMPLEX  Issue #42 is a large feature — run /fix-issue manually
RESULT: GATE_FAIL    Tests could not pass after 3 attempts
RESULT: BLOCKED      Review found a blocker — see above (--full mode only)
RESULT: QUESTION_ANSWERED  Issue #42 was a question — answered via gh comment
```
