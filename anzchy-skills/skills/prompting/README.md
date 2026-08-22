# Prompting

Skills that work on the prompt itself, before any code gets written.

They form a chain: `jack-meta-think` fixes **what** you are asking, `jack-prompt-master` fixes **how** you word it, `jack-loop-prompt` shapes it for a long autonomous run. Nothing auto-chains; each hands you a copy-paste block and you decide where it goes. `jack-ask` is the front door if you don't know which one you want.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`).

- **[jack-ask](./jack-ask/SKILL.md)**: Router for this plugin. Give it a raw ask, get back the one skill that fits and the exact command to run. Routes only — never does the downstream work.
- **[jack-loop-prompt](./jack-loop-prompt/SKILL.md)**: Refine a rough long-running-task prompt into one paste-ready prompt with a binary goal, a project-appropriate self-verification loop, and a final two-subagent adversarial review stage. Use before kicking off a `/goal`, `/loop`, or `/workflow` run.

## Model-invoked

- **[jack-meta-think](./jack-meta-think/SKILL.md)**: Diagnose the question before the prompt. Scans a raw ask for embedded conclusions, evaluative language, missing timeline and missing ruled-out factors, then interviews you for what only you can answer, and rewrites the ask as a neutral open question. Domain-general.
- **[jack-prompt-master](./jack-prompt-master/SKILL.md)**: Tournament-based meta-prompting. Multiple rounds of parallel Claude + Codex candidates, judged on a binary 7-criterion rubric with quoted evidence, synthesized between rounds. For high-stakes coding prompts.
