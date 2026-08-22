---
name: gh-pr
description: Open a GitHub Pull Request with the `gh` CLI: pushes the current branch to origin and creates a PR against a target branch (default main). Use when the user types /gh-pr or asks to open a pull request for the current branch.
---

# gh-pr

Create GitHub Pull Requests using the `gh` CLI. Pushes the current branch and creates a PR to merge into the target branch (default: main).

## Usage

```
/gh-pr [target-branch]
```

- If no target branch specified, defaults to `main`
- Automatically pushes the current branch to origin
- Generates a comprehensive PR description

## Workflow

When this skill is invoked, follow these steps:

### Step 1: Gather Information

Run these commands in parallel to understand the changes:

```bash
# Get current branch name
git branch --show-current

# Get commits that will be in the PR
git log main..HEAD --oneline

# Get file change statistics
git diff main...HEAD --stat

# Get recent commit messages for context
git log main..HEAD --format="%s%n%b" | head -50
```

### Step 2: Check Remote Status

```bash
# Check if branch exists on remote
git ls-remote --heads origin $(git branch --show-current)

# Check if there are unpushed commits
git status -sb
```

### Step 3: Push Branch

```bash
git push -u origin $(git branch --show-current)
```

### Step 4: Generate PR Description

Create a comprehensive PR description with this structure:

```markdown
## Summary
<1-3 sentence overview of what this PR does and why>

## Changes
- <bullet point list of key changes, grouped by category if needed>

## Technical Details
<Optional: architecture decisions, implementation notes>

## Testing
- [x] <tests that were run>
- [ ] <tests that should be run but weren't>

## Screenshots/Demo
<if UI changes, describe what changed visually>

## Related Issues
Closes #<issue-number>
Relates to #<other-issue>

## Checklist
- [x] Code follows project conventions
- [x] Self-reviewed the code
- [ ] Added/updated tests
- [ ] Updated documentation

## Follow-up Tasks
- [ ] <known gaps or future improvements>
```

### Step 5: Create PR

```bash
gh pr create --base <target-branch> --title "<type>(<scope>): <short summary>" --body "$(cat <<'EOF'
<generated PR description>

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Step 6: Report Result

After creating the PR, display:
- PR URL
- PR number
- Title
- Target branch
- Number of commits
- Files changed summary

## PR Title Convention

Follow Conventional Commits format:
- `feat(scope):` - New features
- `fix(scope):` - Bug fixes
- `docs(scope):` - Documentation
- `refactor(scope):` - Code restructuring
- `chore(scope):` - Maintenance tasks
- `perf(scope):` - Performance improvements

## Examples

### Basic Usage
```
User: /gh-pr
Claude: Creates PR from current branch to main
```

### Specify Target Branch
```
User: /gh-pr develop
Claude: Creates PR from current branch to develop
```

## Error Handling

- If `gh` CLI is not installed, provide installation instructions
- If not authenticated, run `gh auth login`
- If branch has no commits ahead of target, warn user
- If PR already exists, show the existing PR URL

## Requirements

- `gh` CLI installed and authenticated
- Git repository with remote origin configured
- At least one commit ahead of target branch
