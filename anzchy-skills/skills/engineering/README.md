# Engineering

Skills for code work: reviewing it, auditing it, and getting it shipped.

## Model-invoked

- **[jack-audit-fable](./jack-audit-fable/SKILL.md)**: Claude-native code auditor. Full 9-dimension or fast 5-dimension audit of uncommitted changes, staged changes, recent commits, specific paths, or the whole codebase, run by a single read-only subagent.
- **[jack-review-plan-fable](./jack-review-plan-fable/SKILL.md)**: Send an implementation plan, design doc, or spec to a fresh Fable 5 subagent for an independent buildability review across five dimensions: internal consistency, completeness, feasibility, ambiguity, risk and sequencing.
- **[jack-auto-fix](./jack-auto-fix/SKILL.md)**: Find the oldest open GitHub issue and fix it end to end: fix, PR, review, merge.
- **[jack-audit-branches](./jack-audit-branches/SKILL.md)**: Audit every remote `fix/audit` branch, merge the clean ones to master with `--no-ff` and a closing reference, run the full gates, push, and close what remains.
- **[gh-commit](./gh-commit/SKILL.md)**: Atomic commits following Conventional Commits. Analyzes staged and unstaged changes, groups them into logical commits, and generates the messages.
- **[gh-pr](./gh-pr/SKILL.md)**: Push the current branch and open a Pull Request against a target branch (default `main`) with the `gh` CLI.
- **[gh-release](./gh-release/SKILL.md)**: Tag and publish a GitHub Release, generating notes from the commits since the previous tag.
