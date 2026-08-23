## 第一轮用自带 prompt-master优化提示词的提示词

```rust

/prompt-master read all md files in @skills/productivity/jack-loop-prompt/ I want to create a loop prompt skill using /skill-creator
  ,skill name `jack-loop-prompt`, backgrounds are this: the common claude code users are not good at prompting about the self-verification
  task for long-running tasks using `/goal` or `/loop` or `/workflow`, so based on the
  @skills/productivity/jack-loop-prompt/reference/Claude-best-practices.md and
  @skills/productivity/jack-loop-prompt/reference/Boris-Loop-tweets.md and
  @skills/productivity/jack-loop-prompt/reference/Feedback_loops.md , so skill `jack-loop-prompt` is to polish the user's initial
  prompt(e.g., implement x as per plan-x.md, or simply implement the following tasks: 1.xxx, 2.xxx), return the refined prompt with clear
  goal, apppropriate self-verification method for diffrent projects( mobile, mac app, web app, cli applications, backend etc.) , and also
  explicitly spawn a subagent to use /review skill to check the diff against the plan, another subagent to use `/cc-suite:audit --full` to
  audit against the plan, return all the response of the subagents to the main agent. return the refined prompt.
```

### Fable 5 results

```python

  Use /skill-creator to build a new skill named `jack-loop-prompt` at skills/productivity/jack-loop-prompt/SKILL.md.

  ## Starting state
  The directory skills/productivity/jack-loop-prompt/ already exists and contains only reference/ with three files. Read all three before
  writing anything:
  - reference/Claude-best-practices.md — verification strategies (/goal conditions, Stop hooks, subagent second opinions, evidence over assertion)
  - reference/Boris-Loop-tweets.md — long-running-task tips (give Claude a tool to see output, self-verify end to end, /goal//loop//workflow usage)
  - reference/Feedback_loops.md — encoding manual checks as skills, fresh-context review before merge

  ## What the skill must do
  Problem it solves: Claude Code users running long tasks via /goal, /loop, or /workflow write weak prompts ("implement x as per plan-x.md",
  "implement: 1.xxx 2.xxx") with no self-verification, so quality depends on the user babysitting.

  The skill takes the user's rough prompt as $ARGUMENTS and returns ONE refined, paste-ready prompt containing exactly these sections:

  1. **Goal** — a clear target state with binary done-criteria derived from the user's input (and the referenced plan file if one is named).
  2. **Self-verification loop** — instructions for Claude to verify its own work after each task, with the method chosen by project type.
  The skill must detect project type from the prompt/repo and include a lookup the skill applies:
     - Web app: run dev server, test UI in browser (Claude in Chrome / Chrome DevTools MCP), check console errors
     - Mobile (iOS/Android): build and run in simulator via sim MCP, screenshot and verify
     - Mac app: build with xcodebuild, launch, screenshot/interact to verify
     - CLI: run the binary with example invocations, assert on stdout/exit codes
     - Backend/service: start the service, hit endpoints with curl, run the test suite
     - All types: run existing tests/lint/typecheck after every change; show evidence (test output, screenshots, exit codes), never assert
  success without it
  3. **Final adversarial review stage** — appended verbatim to every refined prompt: when all tasks pass self-verification, spawn two
  subagents in parallel — one runs the /review skill to check the full diff against the plan (report gaps affecting correctness or stated
  requirements, not style), and one runs `/cc-suite:audit --full` to audit the implementation against the plan. Both subagents return their
  complete findings to the main agent, which fixes confirmed gaps and re-runs the review until clean.

  Output format of the skill: the refined prompt in a single copyable code block, followed by one line noting which project type and
  verification method were chosen.

  ## Constraints
  - Keep SKILL.md lean: the rationale stays in reference/ files loaded on demand; do NOT copy the reference file contents into SKILL.md
  - Set disable-model-invocation: true — this skill is invoked manually as /jack-loop-prompt <rough prompt>
  - Only create/edit files inside skills/productivity/jack-loop-prompt/
  - Do not add features beyond this spec (no extra modes, no config files)

  ## Verify before finishing
  1. Run skill-creator's validation on the finished skill
  2. Test it: simulate invoking the skill with the input "implement the tasks in plan-auth.md" for a web app project, and show me the
  refined prompt it would produce
  3. Confirm the test output contains all three sections (goal, self-verification, two-subagent review stage)

  Done when: SKILL.md exists, validation passes, and the simulated test output includes all three required sections. Stop and show me the
  result — do not commit.

  🎯 Target: Claude Code, 💡 Converted a run-on idea into an agentic spec with starting state, exact skill behavior contract (3 required
  output sections), per-platform verification table, scope lock, and a testable done-condition so the skill is verified before the session
  ends.

```

