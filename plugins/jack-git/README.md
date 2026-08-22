# jack-git

Install: `/plugin install jack-git@jack-cheng-marketplace` · invoke as `/jack-git:<skill>`.

Ship with the `gh` CLI: commit → PR → release.

## Model-invoked

- **[gh-commit](./skills/gh-commit/SKILL.md)**: Atomic commits following Conventional Commits. Analyzes staged and unstaged changes, groups them into logical commits, and generates the messages.
- **[gh-pr](./skills/gh-pr/SKILL.md)**: Push the current branch and open a Pull Request against a target branch (default `main`) with the `gh` CLI.
- **[gh-release](./skills/gh-release/SKILL.md)**: Tag and publish a GitHub Release, generating notes from the commits since the previous tag.
