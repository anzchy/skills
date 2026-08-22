---
name: gh-commit
description: Create atomic git commits following Conventional Commits: analyzes staged and unstaged changes, groups them into logical commits, generates structured messages, and handles branch selection. Use when the user types /gh-commit or asks to commit changes with a conventional-commit message.
---

# Git Commit Skill

**Trigger**: `/gh-commit [optional: description of what to commit]`

## Purpose

Create professional, atomic git commits following Conventional Commits specification. Analyzes changes, generates structured commit messages, handles branch selection, and optionally prepares PR descriptions.

## Execution Flow

### Step 1: Analyze Changes

Run in parallel:
```bash
git status                    # See staged/unstaged files
git diff --cached             # See staged changes
git diff                      # See unstaged changes (if relevant)
git log --oneline -5          # Check recent commit style
```

### Step 2: Determine Commit Type

| Type | Use Case | Example Files |
|------|----------|---------------|
| `feat` | New features | `src/`, new modules |
| `fix` | Bug fixes | Any bugfix |
| `docs` | Documentation only | `*.md`, comments |
| `style` | Formatting (no logic) | Whitespace, linting |
| `refactor` | Code restructure (no behavior change) | Reorganization |
| `test` | Test changes | `test_*.py`, `*.test.js` |
| `chore` | Build/deps/config | `package.json`, configs |
| `perf` | Performance | Optimizations |

**Multiple types**: Choose most significant or create separate atomic commits.

### Step 3: Generate Commit Message

Format:
```
<type>(<scope>): <short summary>   # 50 chars max, imperative mood

<body: explain WHY, not WHAT>      # 72 chars/line

<footer>                           # Closes #123, BREAKING CHANGE:, Tested:
```

Guidelines:
- **Subject**: 50 chars max, imperative mood ("Add" not "Added"), lowercase after colon
- **Scope**: Component name from codebase (e.g., `feat(editor):` not `feat(ui):`)
- **Body**: 72 chars/line, explain motivation and context
- **Footer**: `Closes #123`, `BREAKING CHANGE:`, `Tested:`, `Follow-up:`

### Step 4: Present Draft

Show user:
1. **Files to be committed** (with change summary)
2. **Proposed commit type and scope**
3. **Full commit message** (subject + body + footer)
4. **Wait for confirmation** before proceeding

### Step 5: Select Target Branch

Use AskUserQuestion to confirm target branch:

```bash
git branch --list --format='%(refname:short)' | grep -v 'backup/'
git branch --show-current
```

Options:
- **Current branch** (recommended if changes match)
- **master/main**
- **Other feature branches**

If switching needed:
```bash
git checkout <selected-branch>
git branch --show-current
```

### Step 6: Create Commit

```bash
git add <files>
git commit -m "$(cat <<'EOF'
<commit message>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
git status
```

### Step 7: PR Template (if applicable)

```markdown
## Summary
<1-3 sentences>

## Changes
- <bullet points>

## Testing
- [x] <completed tests>
- [ ] <pending tests>

## Related Issues
Closes #<number>

## Breaking Changes
<if any, describe migration path>
```

## Rules

1. **Never commit without user approval**
2. **Always ask which branch to commit to**
3. **Scope should be specific** (e.g., `feat(editor):` not `feat(ui):`)
4. **Explain WHY, not WHAT** - code shows what, commit shows why
5. **Keep commits atomic** - one logical change per commit
6. **Reference issues** when applicable
7. **Document testing** - note what was/wasn't tested
8. **Flag follow-ups** - be honest about gaps

## Examples

**Feature:**
```
feat(mcp): add document sync to Shadow Store

Enable real-time document state synchronization from frontend
Zustand store to Rust Shadow Store for MCP access.

Debounce 300ms for content changes, immediate for open/close.

Tested: Manual sync verification with 5 documents
Relates to #007
```

**Fix:**
```
fix(search): escape regex metacharacters in search terms

Users entering ".", "*", "+" caused "Invalid regex" errors.
Now escape special chars before passing to re.search().

Tested: Search for "3.14", "C++", "[test]" all work
Closes #42
```

**Docs:**
```
docs(specs): add MCP server implementation plan

Complete specification for Claude Code integration via MCP.
Includes architecture, API contracts, and 54 implementation tasks.

No code changes - documentation only.
```

---

Now proceed with Step 1: Analyze the current git status and staged changes.
