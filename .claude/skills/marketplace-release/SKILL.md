---
name: marketplace-release
description: >-
  Project-scoped release skill for the jack-cheng-skills hub repo
  (anzchy/skills). Analyzes both committed (since last tag) AND uncommitted
  skill changes, then adaptively proposes per-artifact version bumps (repo
  tag/CHANGELOG, and each affected skill's SKILL.md `version:` frontmatter)
  for confirmation. Default (full) mode updates CHANGELOG, tags, pushes, and
  publishes the GitHub release. `--bump-only` mode stops after applying +
  committing the version bumps and a local annotated tag — no push, no GitHub
  release. Use this (not the global /gh-release) when cutting a versioned
  release of THIS repo so the repo tag and each skill's frontmatter version
  stay in sync.
---

# marketplace-release

Project-scoped variant of `gh-release` for **this repo only** (the
`jack-cheng-skills` / `anzchy/skills` hub). Same release flow, plus a
model-driven **Step 0** that proposes per-artifact version bumps (the repo
tag/`CHANGELOG.md`, and each affected skill's `SKILL.md` `version:`
frontmatter) from **both** the commits since the last release **and** any
uncommitted working-tree changes. The global `/gh-release` skill is
intentionally left without Step 0; this project-local skill owns that
behavior. Has two modes: **full** (default — bump → CHANGELOG → tag → push →
GitHub release) and **`--bump-only`** (bump + local tag, then stop — no push,
no release).

> **This repo's distribution model — two channels:**
> 1. `npx skills@latest add anzchy/skills` pulls the latest `main`; tags are
>    history only.
> 2. `/plugin marketplace add anzchy/skills` + `/plugin install
>    <plugin>@jack-cheng-marketplace` reads `.claude-plugin/marketplace.json`
>    on `main`. Per the official docs, the plugin **`version` in
>    `<plugin>/.claude-plugin/plugin.json` wins** (then the marketplace entry,
>    then git tag) and **users only receive updates when that version is
>    bumped**. So every release that touches a plugin's skills MUST bump that
>    plugin's `plugin.json` `version` and the matching `marketplace.json`
>    entry; the repo tag equals the marketplace-level `version`.
>
> Releasing here means: bump affected `SKILL.md` versions, bump the affected
> plugin's `plugin.json` + `marketplace.json` version, record the CHANGELOG,
> tag, and publish notes.

## Usage

```
/marketplace-release              # full release: bump + CHANGELOG + tag + push + gh release
/marketplace-release v1.2.3       # repo tag pre-supplied; Step 0 still bumps the rest
/marketplace-release --bump-only  # bump skill frontmatter + local tag only; no push, no gh release
/marketplace-release v1.2.3 --bump-only   # both: fixed tag, local-only
```

## Invocation modes

This skill has two modes. Parse the argument string before Step 0:

| Mode | Trigger | Stops after |
|---|---|---|
| **full** (default) | no `--bump-only` flag | Step 7 (pushed + GitHub release published) |
| **bump-only** | `--bump-only` anywhere in args | Step 6a (skill versions + CHANGELOG committed, **local** annotated tag created) — **no `git push`, no `gh release create`** |

- A bare version token (e.g. `v1.2.3`) is still the **repo release tag** and
  pre-answers Step 2, in either mode.
- `--bump-only` is the adaptive "sync the versions, don't ship yet" entry
  point: it runs the same Step 0 analysis, applies + commits the bumps,
  writes the CHANGELOG, and lays down a local annotated tag, then **stops** so
  you can review and push manually later. The full mode is the only one that
  touches the remote or GitHub.
- Set `MODE=full` or `MODE=bump-only` from this parse and carry it forward;
  Step 6 branches on it.

## Workflow

When this skill is invoked, follow these steps.

> If invoked with a version argument (`/marketplace-release v1.2.3`), that is
> the **repo release tag** — Step 2 is pre-answered, but Step 0 still runs (it
> bumps the *skills* that changed and sanity-checks the supplied tag against
> the commit history). The `--bump-only` flag is a mode switch, not a tag.

### Step 0: Version bump analysis (model-driven, propose + confirm)

Goal: from the committed **and** uncommitted changes, decide which
version-bearing artifacts changed and propose a semver bump for each. **The
model makes the semver judgment; the user confirms before anything is
written.** This step runs identically in both `full` and `--bump-only` mode.

**0.1 — Range + changed files.** The trigger model is adaptive: it folds in
**both** committed changes since the last tag **and** anything still
uncommitted in the working tree (staged or not). This makes the skill work
whether you already committed your skill edits or are calling it straight off
a dirty tree.

```bash
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
RANGE=$([ -n "$PREV_TAG" ] && echo "${PREV_TAG}..HEAD" || echo "")

# (a) committed since last tag — commit subjects drive the semver class
git log ${RANGE} --no-merges --pretty='%h %s'

# (b) changed paths = committed ∪ uncommitted (staged + unstaged + untracked)
{
  git diff ${PREV_TAG}..HEAD --name-only 2>/dev/null || git ls-files
  git diff --name-only            # unstaged tracked edits
  git diff --name-only --cached    # staged
  git ls-files --others --exclude-standard   # new untracked files
} | sort -u
```

- The **union** of (a) and (b) is the changed-path set Step 0.3 maps to
  owning artifacts.
- For paths that appear **only** in the uncommitted set (no commit yet),
  there is no Conventional-Commit type to read. Infer the change class from
  the nature of the edit and **state the inference explicitly** in the Step
  0.5 proposal (e.g. "jack-prompt-master/SKILL.md edited, uncommitted —
  treating as `feat` → minor; confirm or correct"). When in doubt, propose the
  smaller bump and let the user escalate in the Edit branch.
- Untracked files under `.claude/` (session/editor config), `.DS_Store`,
  `docs/` planning notes, and other paths unrelated to a versioned skill are
  noise — exclude them from the artifact mapping, don't let them force a bump.

**0.2 — Discover version-bearing artifacts** (skip any that don't exist):

| Artifact | Version source | "Owns" these paths |
|---|---|---|
| Repo / release | git tag + `CHANGELOG.md` heading | everything (the tag always bumps) |
| Each plugin | `plugins/<plugin>/.claude-plugin/plugin.json` `version` **and** the matching entry in `.claude-plugin/marketplace.json` (keep them equal) | everything under `plugins/<plugin>/` |
| Each skill | `plugins/<plugin>/skills/<name>/SKILL.md` (or a single-skill plugin's root `SKILL.md`) `version:` frontmatter | that skill's directory — `SKILL.md`, its `README.md`, and its `reference/` or `references/` dir |

> Layout: every plugin lives under `plugins/<name>/` (`marketplace.json`
> `metadata.pluginRoot` = `./plugins`); skills are auto-discovered from each
> plugin's `skills/` (single-skill plugins keep `SKILL.md` at the root).
> Three version layers, bumped independently by what changed:
>
> - **Skill** `version:` frontmatter — bump only the skills that changed;
>   respect each skill's own cadence, don't force-sync to each other.
> - **Plugin** `plugin.json` `version` + the same plugin's `marketplace.json`
>   entry — bump by the highest change class among that plugin's skills.
>   This is the field that gates `/plugin` updates, so never skip it when a
>   skill inside the plugin changed. Also append a new skill's path to the
>   `skills` array (auto-discovery would find it, but keep the list complete).
> - **Marketplace `version` in `marketplace.json` = repo tag / CHANGELOG** —
>   bump by the highest change class across all plugins; the tag is that
>   number with a `v` prefix.
>
> There is no `package.json` — nothing else to track. Validate after editing:
> `claude plugin validate . && for p in plugins/*/; do claude plugin validate $p; done`.

**0.3 — Map commits → owning artifact.** For each changed path, attribute it to
the narrowest owning artifact above. A commit can touch several skills. Any
edit under `plugins/<plugin>/skills/<name>/` → that skill and its plugin. A
**new** plugin directory also means appending an entry to
`.claude-plugin/marketplace.json` (structural, same Step 0.6 commit) — flag it.

**0.4 — Classify per artifact and propose a bump** (Conventional Commits):

- `BREAKING CHANGE:` / `!:` → **major** (or, for `0.y.z` pre-1.0 skills,
  **minor** — pre-1.0 has no stability guarantee; state this explicitly).
- `feat:` → **minor** (pre-1.0: minor, or patch if the skill is barely past
  0.0.x — use judgment and explain).
- `fix:` / `perf:` → **patch**.
- `docs:` / `refactor:` / `chore:` / `test:` only → **no bump** for that
  skill (but the **repo tag still bumps** — a release always tags).
- A brand-new skill starts at `0.1.0` (per the README "Adding a new skill"
  convention) — propose that as its initial version, not a bump.
- The repo tag/CHANGELOG version: bump by the **highest** change class across
  all skills, unless the user passed an explicit tag argument.

Respect existing per-skill cadence — if a skill has deliberately lagged, say
so and propose the in-line next number, don't silently leap it.

**0.5 — Present the plan via `AskUserQuestion`** (one question, the proposed
table in the question body; options: Approve / Edit / Cancel). Format:

```
Proposed version bumps — since <PREV_TAG | "(no tags yet)"> (<N> commits + <M> uncommitted paths)
Mode: <full | bump-only>

  <skill name>          <cur> -> <new>   (<why: commit type, or "uncommitted edit — inferred <class>">)
  ...
  repo tag / CHANGELOG  <prev> -> <new>  (highest class: <feat|fix|...>)

  <plugin> plugin.json + marketplace.json  <cur> -> <new>  (highest class within the plugin) | (unchanged — no skill in it changed)
```

State the mode in the proposal so the user knows whether approving will
publish (full) or stop locally (`--bump-only`).

- **Approve** → apply as proposed.
- **Edit** → ask which line(s) to change, collect new numbers, re-confirm.
- **Cancel** → stop the whole skill, write nothing.

**0.6 — Apply** (only after Approve):

- Edit each affected `SKILL.md`'s `version:` frontmatter line with `Edit`
  (exact string — match `version: <cur>` exactly; never reformat the
  frontmatter). This is the only version write per skill — there are no JSON
  version fields to touch.
- If a **new** skill was added, append its path to the `skills` array in
  `<plugin>/.claude-plugin/plugin.json` with `Edit`.
- Bump each affected plugin's `version` in `<plugin>/.claude-plugin/plugin.json`
  **and** in its `.claude-plugin/marketplace.json` entry (same number), then
  run `claude plugin validate .` and `claude plugin validate ./<plugin>`.
- Do **not** touch `CHANGELOG.md` here — Step 5.5 owns it (it will use the
  repo version confirmed in this step; it creates the file if absent).
- Commit the bumps as their own commit:

```bash
git add <each edited SKILL.md> <each bumped plugin.json> .claude-plugin/marketplace.json
git commit -m "chore(release): bump skill versions for <repo-tag>

<one line per bumped skill: name cur -> new>

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Carry the confirmed **repo tag** forward — Step 2 must use it, not re-ask.

> Skip Step 0 entirely only if the user explicitly says "don't bump versions".
> If no version-bearing skills changed at all, Step 0 reduces to: confirm the
> repo tag (Step 2) and let Step 5.5 record the CHANGELOG — nothing else.

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

### Step 2: Version Tag

**If Step 0 already ran**, the repo tag was proposed and confirmed there (or
passed as the `/marketplace-release <tag>` argument) — **use that, do not
re-ask**. Only fall through to the prompt below if Step 0 was skipped and no
argument was supplied.

Use `AskUserQuestion` to ask the user for the version tag:

```
Question: "What version tag should this release have?"
Options:
- Suggest next version based on latest tag (e.g., if latest is v1.2.0, suggest v1.2.1, v1.3.0, v2.0.0)
- Custom (let user type their own)
```

> **No tags exist yet?** If `git tag` is empty, this is the **first** release.
> Suggest `v0.1.0` as the default repo tag (it matches the skills' current
> pre-1.0 cadence), and let the user override.

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
## jack-cheng-skills <Version>

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

### Skill versions in this release
- <skill name> <version>
- ...

### Contributors
Thanks to all contributors: @user1, @user2, ...

### Full Changelog
https://github.com/anzchy/skills/compare/<prev-tag>...<new-tag>
```

### Step 5.5: Update CHANGELOG.md (before tagging)

This step runs **before** creating the git tag so the CHANGELOG commit is included in
the release. If `CHANGELOG.md` does not exist in the repo root (it does **not** today),
create it with the standard Keep a Changelog header and `## [Unreleased]` section
before proceeding.

**Rules (non-negotiable):**
- Once it exists, always use `Edit` with exact `old_string` — never `Write` on CHANGELOG.md.
- Never delete, reorder, or replace existing entries. Insert only.
- Preserve any existing `## [Unreleased]` section exactly as found.

**1. Read the file to find the insertion point.**

```bash
head -80 CHANGELOG.md 2>/dev/null || echo "CHANGELOG.md does not exist — create it"
```

If creating it fresh, use this header skeleton, then add the new version section under it:

```markdown
# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

```

If the file already exists, find the first line that matches `^## \[` followed by a
version number (not `Unreleased`). That line is the `<first-versioned-section>` anchor
used in the Edit below. If no versioned section exists yet (only `[Unreleased]`), insert
after the last line of the `[Unreleased]` block.

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
- It helps to name which skill changed (e.g. "jack-loop-prompt: …").
- End the block with `---` and a blank line so it visually separates from the next entry.

**3. Insert using Edit** (when the file already had a versioned section):

```
old_string: "<first-versioned-section>"   ← exact text of that ## [...] line
new_string:  "<new entry>\n\n<first-versioned-section>"
```

**4. Update the link references** at the bottom of CHANGELOG.md:

- Update `[Unreleased]` to compare against the new tag: `compare/vX.Y.Z...HEAD`
- Add a new link for the version: `[X.Y.Z]: https://github.com/anzchy/skills/compare/v<prev>...vX.Y.Z`
- For the **first** release (no prev tag), link to the tag itself:
  `[X.Y.Z]: https://github.com/anzchy/skills/releases/tag/vX.Y.Z`

**5. Commit the CHANGELOG update:**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG entry for vX.Y.Z

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Do **not** push yet — the tag creation in Step 6 will be a separate push.

---

### Step 6: Create Tag and Release

**Step 6a — Local annotated tag (BOTH modes).**

```bash
git tag -a <version> -m "Release <version>"
```

**Step 6b — Push + GitHub release (FULL mode only).**

> **Gate:** run Step 6b *only* if `MODE=full`. If `MODE=bump-only`, **skip
> all of 6b** — do not `git push`, do not `gh release create`. The bump-only
> run ends here with the skill versions + CHANGELOG committed and a local-only
> annotated tag, exactly as requested. Jump straight to Step 7 and report the
> local-only result.

```bash
# Push branch + tag together so CHANGELOG commit and tag land atomically
git push origin HEAD <version>

# Create GitHub release
gh release create <version> \
  --title "jack-cheng-skills <version>" \
  --notes "$(cat <<'EOF'
<generated release notes>
EOF
)"
```

> Even in `full` mode, treat `git push` / `gh release create` as
> remote-visible actions: state that you are about to push and publish before
> running 6b. (`--bump-only` sidesteps this entirely by never reaching 6b.)

### Step 7: Report Result

**Full mode** — after publishing, display:
- Release URL
- Tag name
- Number of commits included
- Previous version (if any)
- Per-skill version bumps applied in Step 0
- Whether CHANGELOG.md was created/updated

**Bump-only mode** — display instead:
- Per-skill version bumps applied in Step 0 (cur → new, with the driving change)
- The local annotated tag created (`<version>`) — **not pushed**
- Commits created (version bump commit + CHANGELOG commit)
- Whether CHANGELOG.md was created/updated
- The exact follow-up command to ship later, e.g.:
  `git push origin HEAD <version> && gh release create <version> ...`
  (or "re-run `/marketplace-release <version>` in full mode")
- Reminder that nothing was pushed and no GitHub release exists yet

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
User: /marketplace-release
Claude: Step 0 — proposes per-skill SKILL.md version bumps from commits since
        last tag, confirms via AskUserQuestion, applies + commits frontmatter
        edits. Then: checks state, generates notes, tags, publishes release
```

### Repo tag pre-supplied
```
User: /marketplace-release v0.2.0
Claude: Step 0 — repo tag fixed to v0.2.0, still proposes per-skill
        frontmatter bumps; rest of the flow proceeds
```

### Bump-only (sync versions, don't ship)
```
User: /marketplace-release --bump-only
Claude: Step 0 — folds in committed + uncommitted edits, proposes per-skill
        bumps, confirms, applies + commits SKILL.md frontmatter, writes
        CHANGELOG, creates a LOCAL annotated tag, then STOPS. No push, no
        GitHub release. Reports the follow-up push command for later.
```

## Error Handling

- If uncommitted changes exist: this is **expected input**, not an error —
  Step 0.1 folds them into the bump analysis. Only warn if they look
  unrelated to a versioned skill (and never let `.claude/` session config,
  `.DS_Store`, or `docs/` notes block the run).
- If no tags exist yet, treat it as the first release (suggest `v0.1.0`).
- If tag already exists, offer to use a different tag.
- In **full mode**, if `gh` CLI not authenticated, provide `gh auth login`
  instructions. In **bump-only mode**, `gh` is never invoked — don't gate on it.
- If no commits **and** no uncommitted changes since last tag, warn user.

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

- Git repository (local) — sufficient for `--bump-only`
- **Full mode only:** `gh` CLI installed and authenticated, the `origin`
  remote (`github.com/anzchy/skills`), push access for tags, and write access
  to create releases. `--bump-only` needs none of these — it never touches
  the remote.
