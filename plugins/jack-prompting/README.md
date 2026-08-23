# jack-prompting

Install: `/plugin install jack-prompting@jack-cheng-marketplace` · invoke as `/jack-prompting:<skill>`.

Skills that work on the prompt itself, before any code gets written.

They form a chain: `jack-meta-think` fixes **what** you are asking, `jack-prompt-master` fixes **how** you word it, `jack-loop-prompt` shapes it for a long autonomous run. Nothing auto-chains; each hands you a copy-paste block and you decide where it goes. `jack-ask` is the front door if you don't know which one you want.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`).

- **[jack-ask](./skills/jack-ask/SKILL.md)**: Router across the jack-* plugins. Give it a raw ask, get back the one skill that fits and the exact command to run. Routes only — never does the downstream work.
- **[jack-loop-prompt](./skills/jack-loop-prompt/SKILL.md)**: Refine a rough long-running-task prompt into one paste-ready prompt with a binary goal, a project-appropriate self-verification loop, and a final two-subagent adversarial review stage. Use before kicking off a `/goal`, `/loop`, or `/workflow` run.

## Model-invoked

- **[jack-meta-think](./skills/jack-meta-think/SKILL.md)**: Diagnose the question before the prompt. Scans a raw ask for embedded conclusions, evaluative language, missing timeline and missing ruled-out factors, then interviews you for what only you can answer, and rewrites the ask as a neutral open question. Domain-general.
- **[jack-prompt-master](./skills/jack-prompt-master/SKILL.md)**: Two-round self-refinement meta-prompting. Round 1 rewrites the draft inline against a 9-dimension intent block and a binary 7-criterion rubric; Round 2 grills it in an isolated Fable subagent that quotes evidence per criterion and rewrites to v2; an optional, user-gated Round 3 adds a Codex critique plus synthesis. For high-stakes coding prompts.
