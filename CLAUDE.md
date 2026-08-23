# jack-cheng-skills — project instructions

## Versioning

**When bumping any version in this repo, only ever add `0.0.1` (patch).**

This applies to every version-bearing artifact, without exception:

- each skill's `version:` frontmatter in `plugins/<plugin>/skills/<name>/SKILL.md`
- each plugin's `version` in `plugins/<plugin>/.claude-plugin/plugin.json`
- each plugin's entry `version` in `.claude-plugin/marketplace.json`
- the marketplace-level `version` in `.claude-plugin/marketplace.json`, and the
  matching git tag / `CHANGELOG.md` heading

Do **not** propose minor or major bumps based on Conventional Commit type — a
`feat:`, a `BREAKING CHANGE:`, and a `fix:` all move the number by `0.0.1`.
`/marketplace-release`'s Step 0 semver classification is overridden by this rule:
still classify the change (it drives the CHANGELOG wording), but always propose
`+0.0.1` for the number itself.

A brand-new skill or plugin still starts at `0.1.0`.
