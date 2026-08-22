---
name: jack-audit-fable
description: Claude-native code auditor — full 9-dimension or fast 5-dimension audit of uncommitted changes, staged changes, recent commits, specific paths, or the entire codebase, run by a single read-only subagent on the latest Opus model (Fable 5 only if the user explicitly asks). No Codex, no external CLI, no MCP dependency. Use whenever the user asks to audit code, review code quality, find bugs/dead code/duplication/security issues/refactoring debt, says "audit this", "审计", "代码审查", or invokes /jack-audit-fable. Prefer this over cc-suite:audit when the user wants a native/offline audit or Codex is unavailable.
argument-hint: "[scope] [--full | --mini] [--fable]"
---

# jack-audit-fable — Claude-Native Code Audit

A port of `cc-suite:audit` that runs on a Claude subagent instead of firing Codex. Same
dimensions, same report shape, same findings-file persistence — but the analysis is done
by **exactly one** read-only subagent that covers all 5 or 9 dimensions across every
in-scope file. There is no external model to fail, so there is no fallback step.

**One agent, many dimensions.** Never split the audit into one agent per dimension (5 or
9 agents), and never fan out one agent per file batch. Dimensions overlap — a duplication
finding and a dead-code finding on the same function are one story, and split agents
report it three times while each misses the cross-file context the others hold. A single
auditor reading the whole scope produces fewer, better findings.

**Hard constraint: the audit is read-only.** Never edit, create, or delete project files
during the audit (the findings file in Step 4 is the only write). The audit subagent
must be told the same.

## User Input

```text
$ARGUMENTS
```

## Step 1: Determine Audit Type & Model

### Model

| Condition | `model` passed to the Agent tool |
|-----------|----------------------------------|
| Default — no explicit model request | `"opus"` (latest Opus) |
| User explicitly demands Fable 5 (`--fable` flag, "用 Fable 5", "run this on Fable") | `"fable"` |

Strip `--fable` from the scope arguments after parsing. Never infer Fable 5 from this
skill's name, from the session's current model, or from a previous invocation — only an
explicit ask in the current request switches it. Whichever model runs, name it truthfully
in the report header.

### Audit depth

Parse `$ARGUMENTS` for `--full` or `--mini` (remove the flag from scope arguments):

| Condition | Audit type |
|-----------|------------|
| `--full` flag present | Full (9 dimensions) |
| `--mini` flag present | Mini (5 dimensions) |
| Neither | Ask the user (below, in Chinese per user preference) |

If asking:

```
AskUserQuestion:
  question: "选择哪种审计深度?"
  header: "审计深度"
  options:
    - label: "Mini(5 维)(推荐)"
      description: "逻辑正确性、重复代码、死代码、重构债、临时补丁 — 快速"
    - label: "Full(9 维)"
      description: "另加安全、性能、规范、依赖、文档 — 全面但更慢"
```

## Step 2: Scope & Files

### Parse remaining arguments to determine scope

| Input | Scope |
|-------|-------|
| (empty) | Uncommitted changes (`git diff HEAD --name-only`) |
| `staged` | Staged changes only (`git diff --cached --name-only`) |
| `commit -1` | Last commit (`git diff HEAD~1 --name-only`) |
| `commit -N` | Last N commits (`git diff HEAD~N --name-only`) |
| `all` | Entire codebase (scan `src/`, `lib/`, `app/`, `scripts/`, or the project's main source dirs) |
| `path/to/dir` or `path/to/file` | Specific directory or file |

Note: unlike cc-suite, `--full` here means audit *depth* (9 dimensions), not whole-repo
scope — use `all` for whole-repo scope. `/jack-audit-fable all --full` does both.

**If scope is empty** (no changed files found), respond: "No changes detected in scope.
Nothing to audit." and STOP.

### File filtering

Skip non-code files (`*.md`, `*.json`, `*.yaml`, `*.css`, images, lockfiles) unless
specifically requested.

For **mini audits**, also skip test files — mini focuses on production code quality, and
test files carry intentional duplication that would generate noise:

- `*.test.*`, `*.spec.*`, `*_test.*`, `*_spec.*`, `test_*.py`
- Files under `__tests__/`, `test/`, `tests/`, `spec/` directories
- Test helpers/fixtures: `**/fixtures/**`, `**/mocks/**`, `**/stubs/**`

For **full audits**, include test files — Dimension 7 (Testing & Validation) needs them.

If the project's rules (e.g. `.claude/rules/`, `CLAUDE.md`) define skip patterns or
grandfathered files, respect them and say so in the report.

### Trivial scope check

This check applies only to diff-based scopes (uncommitted / staged / commit ranges).
Path scopes audit the file's full current content — skip the check entirely.

Get the diff (`git diff HEAD` / `--cached` / `HEAD~N`). Classify as trivial only if
ALL are true:

- Total code changes ≤ 5 lines (excluding blanks and comments)
- Purely mechanical: typos, formatting, whitespace, import reordering, comment edits, version bumps
- No logic, control flow, or data handling changes whatsoever

NEVER trivial if ANY apply: any logic/conditional/loop/data-flow change (even one
character like `>` vs `>=`); security-sensitive paths (auth, crypto, permissions,
payments, sessions); dependencies added/removed; runtime-affecting config changes;
changes to error handling or validation.

If trivial, ask (Chinese):

```
AskUserQuestion:
  question: "这是一个琐碎改动({N} 行 — {描述,如'注释里的拼写修正'}),审计大概率无发现。仍要继续吗?"
  header: "范围"
  options:
    - label: "跳过(推荐)"
      description: "改动太小,不值得审计"
    - label: "仍然审计"
      description: "无论如何执行审计"
```

If "跳过" → respond "Scope too trivial — no issues expected." and STOP.

## Step 3: Audit Execution — one agent, all dimensions

Spawn **exactly one** subagent via the Agent tool. Not one per dimension, not one per
file batch — one auditor that reads every in-scope file and evaluates all 5 (mini) or
9 (full) dimensions itself.

Agent tool parameters:

- `subagent_type`: `"general-purpose"`
- `model`: `"opus"`, or `"fable"` if Step 1 selected Fable 5
- `description`: `"Mini code audit"` / `"Full code audit"`
- `prompt`: must contain, in this order —
  1. The persona line (below)
  2. The read-only constraint: read and analyze only; never edit, create, or delete any file
  3. The full file list as absolute paths, and the instruction to Read each file **in
     full**, not just the diff hunks — findings need surrounding context
  4. For diff-based scopes: the diff itself (or the command to get it), so the auditor
     can distinguish new issues from pre-existing ones — flag both, mark pre-existing as such
  5. The complete dimension checklist for the chosen audit type, verbatim from below
  6. The exact finding format, plus: "your final message IS the data — return only the
     findings table rows, no prose, no preamble"

**Persona**: "You are a thorough security and code quality auditor." (full) /
"You are a fast code quality reviewer focused on logic, duplication, and dead code." (mini)

**If the scope is large** (say, more than ~25 files), do not fan out — instead tell the
auditor to prioritize: cover every file at least at the dead-code/duplication level, and
spend its depth on the files with the most logic, the most churn, or the most
security-sensitive surface. Then say in the report's Notes which files got only shallow
coverage. A single agent that admits partial depth beats nine agents that each claim
completeness over a sliver.

**Inline fallback**: if the subagent errors out or returns nothing usable, run the same
checklist yourself inline and label the report header `Model: {model} (inline fallback —
subagent unavailable)`. Never report a model as the auditor when it did not do the audit.

**Anti-hallucination gate**: every finding must cite a real `file:line` the auditor
actually read. Before reporting, spot-check a sample of the returned findings against the
source yourself, and drop or correct any whose line numbers don't hold up. A
plausible-sounding finding at a wrong line number is worse than no finding.

**Cross-file findings**: a finding may involve files outside the scope (e.g. a scoped
module's contract with its callers). Anchor the finding at an in-scope `file:line` and
name the external files in the issue text — never anchor at an out-of-scope line.

**Project rules win on severity**: if the repo's own rules (`.claude/rules/`,
`CLAUDE.md`) explicitly permit a pattern the checklist would flag (e.g. "no defensive
checks for internal callers", grandfathered file sizes), downgrade or drop the finding
and note the rule in the report rather than fighting it.

### Mini Audit checklist (5 dimensions)

Audit each file for:

**Dimension 1: Logic & Correctness**
- Race conditions, edge cases, off-by-one errors
- Async issues: missing await, unhandled promises
- State mutations: unexpected side effects, stale closures

**Dimension 2: Duplication**
- Copy-paste code, repeated patterns, DRY violations
- Near-duplicates: functions differing by 1-2 lines

**Dimension 3: Dead Code**
- Unused imports, unreachable branches, commented-out code
- Unused variables, orphaned functions

**Dimension 4: Refactoring Debt**
- Long functions (>30 lines), deep nesting (>3 levels)
- Unclear names, missing abstractions, god objects

**Dimension 5: Shortcuts & Patches**
- TODOs left behind, hardcoded values, workarounds
- Incomplete error handling, quick fixes, backward-compat shims

Finding format: `file:line | dimension | severity(High/Medium/Low) | issue | fix`

### Full Audit checklist (9 dimensions)

Audit each file for:

**Dimension 1: Redundant & Low-Value Code**
- Dead code: unreachable paths, unused functions/imports, commented-out code
- Duplicate code: copy-paste patterns, repeated logic
- Useless code: unused variables, no-op operations, empty catch blocks

**Dimension 2: Security & Risk Management**
- Input validation: SQL injection, XSS, command injection, path traversal
- Sensitive data: hard-coded secrets, logged credentials, unencrypted data
- Auth/authz: weak passwords, broken access control, session issues
- Cryptography: weak algorithms, improper key management

**Dimension 3: Code Correctness & Reliability**
- Logic errors: edge cases, boundary conditions, race conditions
- Runtime risks: null dereference, array bounds, division by zero
- Error handling: missing try-catch, swallowed exceptions, silent failures
- Resource leaks: unclosed files, connections, memory

**Dimension 4: Compliance & Standards**
- Coding standards: naming conventions, code structure
- Framework conventions: proper API usage, deprecated features
- License compliance: GPL, MIT, Apache compatibility

**Dimension 5: Maintainability & Readability**
- Complexity: cyclomatic complexity >15, nested conditionals
- Size: functions >50 lines, classes >500 lines
- Magic numbers, DRY violations

**Dimension 6: Performance & Efficiency**
- Algorithm efficiency: O(n^2) that could be O(n log n)
- Database: N+1 queries, missing indexes, no pagination
- Memory: excessive allocations; I/O: blocking operations

**Dimension 7: Testing & Validation**
- Coverage gaps: critical paths without tests
- Test quality: flaky tests, missing edge cases, missing integration tests

**Dimension 8: Dependency & Environment Safety**
- Known CVEs, outdated/abandoned packages
- Config security: secrets in configs, missing .gitignore

**Dimension 9: Documentation & Knowledge Transfer**
- Missing docs: undocumented public APIs
- Outdated comments, incomplete setup instructions

Finding format: `file:line | severity(Critical/High/Medium/Low) | dimension | issue | fix`

## Step 4: Report

Before rendering the report, if the audit produced at least one finding, write the
merged findings to `.jack-audits/audit-{YYYYMMDD-HHMMSS}-findings.md` (create the
directory if missing; if the repo has a `.gitignore` and `.jack-audits/` is not in it,
suggest adding it). The persisted file uses the report's findings table plus one extra
`Status` column, initialized to `open` for every row (a later fix pass flips rows to
`fixed`/`wontfix`). Mention the path in the report header. A durable findings file survives context compaction and lets a later
fix pass start from the audit's exact output instead of re-auditing. If the write
fails, note it and continue — the inline report is the primary output.

### Mini Report

```markdown
# Mini Audit Report (jack-audit-fable)

**Date**: {today}
**Scope**: {what was audited}
**Files**: {count}
**Model**: {Opus 5 | Fable 5} (single audit subagent, 5 dimensions)
**Findings file**: {path or "not persisted"}
**Verdict**: CLEAN / NEEDS ATTENTION / NEEDS WORK

## Findings

| File:Line | Dim | Severity | Issue | Fix |
|-----------|-----|----------|-------|-----|

## Summary by Dimension

| Dimension | High | Medium | Low |
|-----------|------|--------|-----|
| 1. Logic & Correctness | | | |
| 2. Duplication | | | |
| 3. Dead Code | | | |
| 4. Refactoring Debt | | | |
| 5. Shortcuts & Patches | | | |

## Action Items

1. **[High]** {action} - {file:line}

## Notes

- For security/performance/dependency coverage, rerun with `--full`
- {any files that got only shallow coverage, per the large-scope rule}
```

### Full Report

Same header block as Mini (with `9 dimensions` in the Model line), then:

```markdown
## Executive Summary

**Overall Risk Score**: Critical / High / Medium / Low

| Dimension | Critical | High | Medium | Low |
|-----------|----------|------|--------|-----|
| (all 9 dimensions) | | | | |

**Verdict**: PASS / NEEDS WORK / BLOCKED

## Findings by Dimension

(one `| File:Line | Severity | Issue | Fix |` table per dimension; omit dimensions
with zero findings and say so in one line)

## Top Priority Actions

1. **[Critical]** {action} - {file:line}
2. **[High]** {action} - {file:line}

## Positive Observations

- (well-structured patterns or commendable practices found)
```

Empty-dimension tables are noise — collapse them. Rank Action Items by severity, then
by blast radius. Keep the final verdict honest: CLEAN means you actually found nothing,
not that you ran out of patience.
