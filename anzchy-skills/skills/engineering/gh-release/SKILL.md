---
name: gh-release
description: Cut a GitHub Release with a git tag using the `gh` CLI: prompts for the version tag and generates release notes from the commits since the previous tag. Use when the user types /gh-release or asks to tag and publish a release.
---

# gh-release

Create GitHub Releases with git tags using the `gh` CLI. Prompts for version tag and generates a comprehensive release notes from commits.

## Usage

```
/gh-release
```

## Workflow

When this skill is invoked, follow these steps:

### Step 1: Check Current State

Run these commands to understand the current state:

```bash
# Get latest tags
git tag --sort=-v:refname | head -10

# Get current branch
git branch --show-current

# Get latest commit
git log -1 --oneline

# Check if there are uncommitted changes
git status --porcelain
```

### Step 2: Prompt for Version Tag

Use `AskUserQuestion` to ask the user for the version tag:

```
Question: "What version tag should this release have?"
Options:
- Suggest next version based on latest tag (e.g., if latest is v1.2.0, suggest v1.2.1, v1.3.0, v2.0.0)
- Custom (let user type their own)
```

**Version format examples:**
- `v1.0.0` - Semantic versioning
- `2026.2.1` - Date-based versioning
- `v1.0.0-beta.1` - Pre-release

### Step 3: Gather Commits Since Last Release

```bash
# Get the previous tag
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

# If no previous tag, get all commits
if [ -z "$PREV_TAG" ]; then
  git log --oneline --no-merges | head -50
else
  git log ${PREV_TAG}..HEAD --oneline --no-merges
fi
```

### Step 4: Categorize Changes

Parse commit messages and categorize them:

**Categories:**
- **Features** - `feat:`, `feature:`, `add:`
- **Fixes** - `fix:`, `bugfix:`, `hotfix:`
- **Documentation** - `docs:`, `doc:`
- **Performance** - `perf:`
- **Refactoring** - `refactor:`
- **Security** - `security:`, commits mentioning CVE/CWE/GHSA
- **Breaking Changes** - commits with `BREAKING CHANGE:` or `!:`
- **Other** - everything else

### Step 5: Generate Release Notes

Create release notes with this structure:

```markdown
## <App Name> <Version>

### Changes

#### Features
- <feature description> (#<PR number>) Thanks @<contributor>

#### Fixes
- <fix description> (#<PR number>) Thanks @<contributor>

#### Documentation
- <doc changes>

#### Security
- <security fixes with CVE/CWE references if applicable>

#### Other
- <other changes>

### Contributors
Thanks to all contributors: @user1, @user2, ...

### Full Changelog
https://github.com/<owner>/<repo>/compare/<prev-tag>...<new-tag>
```

### Step 5.5: Update CHANGELOG.md (before tagging)

This step runs **before** creating the git tag so the CHANGELOG commit is included in
the release. If `CHANGELOG.md` does not exist in the repo root, create it with the
standard Keep a Changelog header and `## [Unreleased]` section before proceeding.

**Rules (non-negotiable):**
- Always use `Edit` with exact `old_string` — never `Write` on CHANGELOG.md.
- Never delete, reorder, or replace existing entries. Insert only.
- Preserve any existing `## [Unreleased]` section exactly as found.

**1. Read the file to find the insertion point.**

```bash
head -80 CHANGELOG.md
```

Find the first line that matches `^## \[` followed by a version number (not `Unreleased`).
That line is the `<first-versioned-section>` anchor used in the Edit below.

If no versioned section exists yet (file is empty or only has `[Unreleased]`), insert
after the last line of the `[Unreleased]` block (or after the header if no Unreleased).

**2. Format the entry** using the categorized changes from Step 4:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- <user-facing description> (closes #N)

### Fixed
- <user-facing description> (closes #N)

### Changed
- <user-facing description>

### Security
- <description> (CVE/GHSA reference if applicable)

---

```

- Omit any category that has no entries.
- Write from the user's perspective ("You can now…" → just "Description").
- Include issue/PR references as `(closes #N)` where known.
- End the block with `---` and a blank line so it visually separates from the next entry.

**3. Insert using Edit:**

```
old_string: "<first-versioned-section>"   ← exact text of that ## [...] line
new_string:  "<new entry>\n\n<first-versioned-section>"
```

**4. Update the link references** at the bottom of CHANGELOG.md:

- Update `[Unreleased]` to compare against the new tag: `compare/vX.Y.Z...HEAD`
- Add a new link for the version: `[X.Y.Z]: https://github.com/<owner>/<repo>/compare/v<prev>...vX.Y.Z`

**5. Commit the CHANGELOG update:**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG entry for vX.Y.Z

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Do **not** push yet — the tag creation in Step 6 will be a separate push.

---

### Step 6: Create Tag and Release

```bash
# Create annotated tag
git tag -a <version> -m "Release <version>"

# Push branch + tag together so CHANGELOG commit and tag land atomically
git push origin HEAD <version>

# Create GitHub release
gh release create <version> \
  --title "<App Name> <version>" \
  --notes "$(cat <<'EOF'
<generated release notes>
EOF
)"
```

### Step 7: Report Result

After creating the release, display:
- Release URL
- Tag name
- Number of commits included
- Previous version (if any)
- Whether CHANGELOG.md was updated

## Options

### Draft Release
```bash
gh release create <version> --draft --notes "..."
```

### Pre-release
```bash
gh release create <version> --prerelease --notes "..."
```

### With Assets
```bash
gh release create <version> --notes "..." ./build/*.zip
```

## Examples

### Basic Release
```
User: /gh-release
Claude: Checks latest tag (v1.2.0), prompts for version
User: v1.3.0
Claude: Creates tag, generates notes, publishes release
```

### First Release
```
User: /gh-release
Claude: No previous tags found, prompts for initial version
User: v1.0.0
Claude: Creates initial release with all commits
```

## Error Handling

- If uncommitted changes exist, warn user and ask to proceed
- If tag already exists, offer to use a different tag
- If `gh` CLI not authenticated, provide `gh auth login` instructions
- If no commits since last tag, warn user

## Commit Message Parsing

The skill parses conventional commits format:
```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Special patterns recognized:**
- `Thanks @username` or `by @username` - contributor attribution
- `(#123)` or `Closes #123` - PR/issue references
- `BREAKING CHANGE:` - breaking change marker
- `CVE-`, `CWE-`, `GHSA-` - security references

## Requirements

- `gh` CLI installed and authenticated
- Git repository with remote origin
- Push access to create tags
- Write access to create releases
