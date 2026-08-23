# Intent extraction — 9 dimensions

Used in Phase 2 step 1. Run inline in the main context; no other skill is invoked. Read the draft once and fill every dimension below **from the draft text only**. Do not ask questions here (the interview in step 1c handles that) and do not guess — a dimension the draft does not cover is `unspecified`.

| # | Dimension | What to extract |
|---|---|---|
| 1 | `task` | The specific action. Convert vague verbs ("improve", "fix up") into the precise operation the draft implies. |
| 2 | `target_tool` | Which AI system / CLI will execute the final prompt (Claude Code, Codex, Cursor, …). |
| 3 | `output_format` | Shape of the result: diff, file list, PR, report, answer length, filetype. |
| 4 | `constraints` | MUST / MUST NOT: scope boundaries, files not to touch, dependencies not to add, compatibility. |
| 5 | `input` | What the user supplies alongside the prompt: files, logs, screenshots, a spec. |
| 6 | `context` | Domain, project state, prior decisions the draft references. |
| 7 | `audience` | Who reads the output and their level (only if the output is user-facing). |
| 8 | `success_criteria` | How anyone would know the task is done — binary checks where possible. |
| 9 | `examples` | Desired input/output pairs, if the draft gives or implies any. |

## Output block

```
## Intent
- task: <text> [user-stated]
- target_tool: <text> [user-stated | unspecified]
- output_format: … [user-stated | unspecified]
- constraints: … [user-stated | unspecified]
- input: … [user-stated | unspecified]
- context: … [user-stated | unspecified]
- audience: … [user-stated | unspecified]
- success_criteria: … [user-stated | unspecified]
- examples: … [user-stated | unspecified]
```

Rules:

- `task` is always filled; if the draft has no discernible task, abort with "draft has no actionable task" instead of inventing one.
- A `[user-stated]` value may only paraphrase the draft; keep the draft's own nouns and verbs.
- `[unspecified]` lines stay empty after the tag. They feed the interview (1c) and, if still open, must appear in v1 as labelled assumptions or open questions — see the provenance rule in Phase 3.
