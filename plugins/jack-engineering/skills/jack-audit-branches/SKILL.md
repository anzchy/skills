---
name: jack-audit-branches
description: |
  Audit all remote branches with prefix `fix/audit` using codex-toolkit mini audit,
  merge clean branches to master with --no-ff (including Closes #N in merge commit to
  close the linked GitHub issue), run full gates, push, and close remaining issues.
  Use when asked to "audit fix branches", "jack-audit-branches", or "audit and merge fix/audit".
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - ToolSearch
  - AskUserQuestion
---

# jack-audit-branches

Audit all unmerged `fix/audit-*` remote branches, merge clean ones to master,
and close the linked GitHub issues.

---

## Phase 0 — Pre-flight

```bash
git branch --show-current
git status --porcelain
git fetch origin --quiet
```

- If not on `master`: `git checkout master && git pull origin master --quiet`
- If working tree is dirty: stop, tell the user what's blocking

---

## Phase 1 — Discover unmerged branches

```bash
git fetch origin
git branch -r | grep "origin/fix/audit-" | sed 's/  origin\///'
```

For each branch found, check whether it has commits not yet on master:

```bash
git log --oneline origin/<branch> --not master | wc -l | tr -d ' '
```

If count is `0`: branch is already merged — **skip silently**.

Collect the remaining list as `PENDING_BRANCHES`. If empty: report "No unmerged fix/audit-* branches found." and stop.

Print the list before proceeding:
```
Found N unmerged fix/audit-* branches:
  fix/audit-91   (#91)
  fix/audit-103  (#103)
  ...
```

---

## Phase 2 — Per-branch audit + gate

For **each** branch in `PENDING_BRANCHES`, run the following in sequence.

### 2a. Extract issue number

The issue number is the numeric suffix: `fix/audit-143` → `143`.

```bash
ISSUE_N=$(echo "<branch>" | grep -oE '[0-9]+$')
```

### 2b. Create a git worktree

```bash
WORKTREE=/tmp/jack-audit-${ISSUE_N}
git worktree add "$WORKTREE" "origin/<branch>" --detach 2>/dev/null \
  || git worktree add "$WORKTREE" "origin/<branch>" --detach -f
```

### 2c. Identify changed files (code only, skip docs/json/yaml/css/images)

```bash
CHANGED_FILES=$(git diff --name-only master..origin/<branch> \
  | grep -E '\.(rs|ts|tsx|js|jsx|py|go|sh)$' \
  | sed "s|^|${WORKTREE}/|")
```

If `CHANGED_FILES` is empty, audit all changes with `git diff --name-only master..origin/<branch>`.

### 2d. Cargo check (if any .rs files changed)

```bash
RS_COUNT=$(git diff --name-only master..origin/<branch> | grep '\.rs$' | wc -l | tr -d ' ')
```

If `RS_COUNT > 0`:
```bash
cd "$WORKTREE/src-tauri" && cargo check 2>&1
```

If cargo check fails → mark branch as `GATE_FAILED: <error summary>` and skip to next branch. Do NOT merge a branch that fails cargo check.

### 2e. Invoke mini audit via Codex companion script

The OpenAI Codex plugin runs through a local companion script, not an MCP tool.
Invoke it with Bash.

#### Step 1: Locate the companion script

```bash
CODEX_SCRIPT=$(find "${HOME}/.claude/plugins/cache/openai-codex" \
  -name "codex-companion.mjs" | sort | tail -1)
```

If `CODEX_SCRIPT` is empty (plugin not installed) → skip to **Fallback** below.

#### Step 2: Verify Codex is available and authenticated

```bash
node "$CODEX_SCRIPT" setup --json 2>/dev/null
```

Check the JSON output:
- If `codex.available` is `false` → skip to **Fallback** (Codex CLI not installed)
- If `auth.loggedIn` is `false` → stop and tell the user to run `/codex:setup`

#### Step 3: Run the audit task

Build the audit prompt with the branch's changed files and diff. Run Codex **in the worktree
directory** using `-C` so it reads the branch version of the files:

```bash
DIFF_STAT=$(git diff master..origin/<branch> --stat)
FILE_LIST=$(git diff --name-only master..origin/<branch> | grep -E '\.(rs|ts|tsx|js|jsx)$' | tr '\n' ' ')

node "$CODEX_SCRIPT" task \
  --effort medium \
  -C "$WORKTREE" \
  "Mini audit of changes in fix/audit-${ISSUE_N}:

Files changed: ${FILE_LIST}
Diff summary:
${DIFF_STAT}

Dimension 1: Logic & Correctness — race conditions, edge cases, missing await, stale closures
Dimension 2: Duplication — copy-paste code, repeated patterns
Dimension 3: Dead Code — unused imports, unreachable branches, commented-out code
Dimension 4: Refactoring Debt — functions >30 lines, nesting >3 levels, unclear names
Dimension 5: Shortcuts & Patches — TODOs, hardcoded values, incomplete error handling

Report each issue as: file:line | dimension | severity(High/Medium/Low) | issue | fix

End with exactly one of:
VERDICT: CLEAN
VERDICT: NEEDS ATTENTION
VERDICT: NEEDS WORK"
```

Capture stdout. The companion script returns Codex output verbatim — present it as-is.

#### Step 4: Parse verdict

Read the last `VERDICT:` line in the output:

- `VERDICT: CLEAN` → **MERGE_READY**
- `VERDICT: NEEDS ATTENTION` → scan for any `High` or `Critical` lines:
  - None found → **MERGE_READY**
  - Any found → **AUDIT_FAILED**
- `VERDICT: NEEDS WORK` → **AUDIT_FAILED**

**Important:** treat pre-existing issues not introduced by this branch as informational — do not
block the merge on them. Cross-check any High/Critical finding against
`git diff master..origin/<branch>` to confirm the finding is in the branch's own changed lines
before marking as `AUDIT_FAILED`.

#### Fallback (Codex unavailable)

Read each changed file from the worktree with the Read tool. Manually apply the 5 dimensions above.
Report findings in the same `file:line | dim | severity | issue | fix` format and assign a verdict yourself.

### 2f. Record decision

After processing each branch, record one of:
- `MERGE_READY`   — audit clean, cargo check passed
- `AUDIT_FAILED`  — codex found High/Critical issues
- `GATE_FAILED`   — cargo check failed
- `ALREADY_MERGED` — 0 new commits over master

---

## Phase 3 — Merge all MERGE_READY branches

Return to master:
```bash
git checkout master
```

For each `MERGE_READY` branch **in the order they were discovered** (oldest first):

```bash
ISSUE_N=$(echo "<branch>" | grep -oE '[0-9]+$')
BRANCH_TITLE=$(gh issue view "$ISSUE_N" --json title --jq '.title' 2>/dev/null || echo "<branch>")

git merge --no-ff "origin/<branch>" -m "$(cat <<MSG
Merge branch '<branch>' into master

Closes #${ISSUE_N}

Co-Authored-By: Claude <noreply@anthropic.com>
MSG
)"
```

**If the merge produces a compile error** (detected by running `cargo check` immediately after):
1. Try to fix the error — it is usually a missing `Display` impl (`{}` → `{:?}`), an unused import, or a type mismatch introduced by two branches touching the same file
2. Commit the fix: `git commit -m "fix(compile): resolve merge conflict from <branch>"`
3. If you cannot fix it in 1 attempt: `git revert HEAD --no-edit` to undo the merge, mark the branch as `GATE_FAILED`, and continue

After all merges, report a merge summary:
```
Merged: fix/audit-91, fix/audit-103, fix/audit-112 ...
Skipped (audit): fix/audit-135
Skipped (gate):  fix/audit-143
```

---

## Phase 4 — Full gate on master

Run the complete gate suite after all merges:

```bash
# 1. Frontend build
pnpm build

# 2. Frontend tests
pnpm test:run

# 3. Rust compile check (always)
cd src-tauri && cargo check

# 4. Rust tests
cargo test
```

All four must pass. If any fail:
- Diagnose the root cause (read the error, check the relevant file)
- Apply the minimum fix
- Commit: `git commit -m "fix(<scope>): <reason> after branch merge"`
- Re-run the failing gate to confirm

If gates cannot be made green after 2 attempts: stop, report the failure, and do NOT push.

---

## Phase 5 — Push, close issues, delete remote branches

Only run this phase if Phase 4 gates are green.

### Push master
```bash
git push origin master
```

### Close GitHub issues

For **each successfully merged branch**:

```bash
ISSUE_N=$(echo "<branch>" | grep -oE '[0-9]+$')
MERGE_SHA=$(git log --oneline --merges --grep="Closes #${ISSUE_N}" -1 --format="%h")

gh issue close "$ISSUE_N" \
  --comment "Fixed and merged to master in ${MERGE_SHA}. Closed by jack-audit-branches skill."
```

**Why close manually?** GitHub only fires the issue-close webhook when a PR with "Closes #N"
in its body is merged. A direct push — even with "Closes #N" in a commit message — does not
re-trigger the webhook for commits already known to the remote. Manual `gh issue close`
ensures the issue is closed regardless of whether a PR was created.

### Delete remote branches

For **each successfully merged branch**:

```bash
git push origin --delete "<branch>"
```

### Clean up worktrees

```bash
for N in <all issue numbers processed>; do
  git worktree remove /tmp/jack-audit-${N} --force 2>/dev/null || true
done
git worktree prune
```

---

## Phase 6 — Summary report

Print a final table:

```
┌─────────────────────────────────────────────────────────────────┐
│  jack-audit-branches — Run Summary                              │
├────────────────┬──────────────────┬────────────────────────────┤
│  Branch        │  Issue  │  Result                             │
├────────────────┼─────────┼────────────────────────────────────┤
│  fix/audit-91  │  #91    │  ✓ MERGED + CLOSED                 │
│  fix/audit-103 │  #103   │  ✓ MERGED + CLOSED                 │
│  fix/audit-135 │  #135   │  ✗ AUDIT_FAILED (High: ...)        │
│  fix/audit-143 │  #143   │  ✗ GATE_FAILED (cargo check error) │
└────────────────┴─────────┴────────────────────────────────────┘

Master pushed to origin.
Branches deleted: fix/audit-91, fix/audit-103
Remaining open: fix/audit-135, fix/audit-143 (need manual review)
```

For any `AUDIT_FAILED` or `GATE_FAILED` branches, print the specific finding or
error so the user knows exactly what to fix.

---

## Rules

- Never commit directly from a worktree — all merges happen on `master`
- Merge commit MUST contain `Closes #N` (not just the branch commit) — see Phase 3
- If a branch touches the same file as a previously merged branch, cargo check will
  catch any conflicts; fix before continuing
- Do not merge a branch that fails cargo check in Phase 2d
- Do not push if Phase 4 gates are not green
- AskUserQuestion is allowed only if: (a) working tree is dirty at start, or
  (b) an AUDIT_FAILED branch has medium-severity findings where you want user guidance
