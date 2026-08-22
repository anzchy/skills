# jack-engineering

Install: `/plugin install jack-engineering@jack-cheng-marketplace` · invoke as `/jack-engineering:<skill>`.

Skills for code work: reviewing and auditing it. Shipping (commit / PR / release) lives in the sibling `jack-git` plugin.

## Model-invoked

- **[jack-audit-fable](./skills/jack-audit-fable/SKILL.md)**: Claude-native code auditor. Full 9-dimension or fast 5-dimension audit of uncommitted changes, staged changes, recent commits, specific paths, or the whole codebase, run by a single read-only subagent.
- **[jack-review-plan-fable](./skills/jack-review-plan-fable/SKILL.md)**: Send an implementation plan, design doc, or spec to a fresh Fable 5 subagent for an independent buildability review across five dimensions: internal consistency, completeness, feasibility, ambiguity, risk and sequencing.
- **[jack-auto-fix](./skills/jack-auto-fix/SKILL.md)**: Find the oldest open GitHub issue and fix it end to end: fix, PR, review, merge.
- **[jack-audit-branches](./skills/jack-audit-branches/SKILL.md)**: Audit every remote `fix/audit` branch, merge the clean ones to master with `--no-ff` and a closing reference, run the full gates, push, and close what remains.
