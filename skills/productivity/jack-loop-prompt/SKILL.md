---
name: jack-loop-prompt
description: Refine a rough long-running-task prompt into one paste-ready prompt with a binary goal, a project-appropriate self-verification loop, and a final two-subagent adversarial review stage. Use before kicking off a /goal, /loop, or /workflow run. Invoke manually as "/jack-loop-prompt your rough prompt".
version: 0.1.2
disable-model-invocation: true
---

# jack-loop-prompt

Rough prompts like "implement x as per plan-x.md" give Claude no way to check its own work, so quality ends up depending on the user babysitting the session. This skill rewrites the rough prompt into ONE refined, paste-ready prompt that closes the loop: a goal with binary done-criteria, a self-verification method matched to the project type, and an adversarial review stage that runs once everything passes.

The user's rough prompt: $ARGUMENTS

## Workflow

### 1. Derive the goal

- If the rough prompt names a plan file (e.g. `plan-auth.md`), read it and derive the done-criteria from its tasks. If the file doesn't exist yet, keep the reference and derive criteria from the prompt alone.
- If the prompt lists tasks inline, use those as the criteria.
- Every criterion must be binary — checkable as pass/fail ("all 5 plan tasks implemented and their tests pass"), never vague ("auth works well"). Vague criteria let Claude stop at "looks done", which is exactly the failure this skill exists to prevent.
- If the plan or prompt mandates a methodology (TDD, contract-first, etc.), carry it into the criteria — e.g. "each task shows its failing test RED first, then GREEN." Don't let project-type verification silently drop a discipline the plan required.
- Note any isolation requirement (a git worktree, a dedicated branch, a sandbox dir). If the prompt asks to work in a worktree, this becomes the first done-criterion and an explicit early instruction in Section 1 — not a clause buried mid-paragraph.

### 2. Detect the project type

Check the prompt first for explicit signals (framework names, "iOS app", "CLI tool"). If the prompt doesn't say, inspect the repo:

| Repo signal                                                                 | Project type         |
| --------------------------------------------------------------------------- | -------------------- |
| `package.json` with next/vite/react/vue + dev script                        | Web app              |
| Xcode project/workspace with iOS target, or android/ dir, Flutter/RN config | Mobile (iOS/Android) |
| Xcode project with a macOS app target                                       | Mac app              |
| `bin` entry, `main()` + argparse/clap/cobra, no server                      | CLI                  |
| Express/FastAPI/Rails/Go HTTP server, Dockerfile exposing a port            | Backend/service      |

If still ambiguous, pick the most likely type and flag the guess in the closing note so the user can correct it before pasting.

While inspecting the repo, also detect the **environment-activation prefix** — a conda env, `venv`, `nvm`, etc. (check CLAUDE.md, README, `environment.yml`, `requirements.txt`). A bare shell resets between commands, so a verification command that works in your terminal will fail in the loop without it. Capture the exact prefix (e.g. `eval "$(conda shell.bash hook)" && conda activate <env>`) and prepend it to every command in Section 2.

### 3. Assign a model tier per task

Rough prompts run everything on one model — overkill for plumbing, underpowered for the hard work item. Tag each task from step 1 with the right model by complexity:

| Complexity                 | Tier   | Typical work                                                                                                       |
| -------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------- |
| Mechanical / deterministic | Sonnet | renames, config plumbing, boilerplate scaffolding, doc edits, a fully-specified mechanical change                 |
| Standard feature work      | Opus   | a well-specified work item with localized logic and its tests                                                      |
| High-judgment              | Opus   | novel algorithm, cross-cutting or architectural change, subtle correctness / concurrency, ambiguous spec — and ALL review, adversarial, and synthesis steps |

Only pure plumbing drops to Sonnet; anything carrying real logic or judgment runs on Opus. When torn between the two, pick Opus — a wrong cheap result costs more than the model saved. The tags are advisory: an executor that dispatches tasks to subagents (e.g. `/workflow`) routes each to its tagged tier; a single-model `/loop` run uses them to choose which tier to launch.

### 4. Compose the refined prompt

The refined prompt contains exactly these three sections — no extra sections, no modes.

**Section 1 — Goal.** The target state plus the binary done-criteria from step 1, with the plan file referenced by path if one was named. If step 1 found an isolation requirement, lead with it as a standalone instruction ("Create a git worktree off `<branch>` first; all edits, tests, and commits happen inside it, never on the main checkout") so it can't be missed. Annotate each task / work item with its tier from step 3 (e.g. `WI-3 [Sonnet]`, `WI-7 [Opus]`) so a dispatching executor can route it; if the whole run is single-model, note the highest tier any task needs as the recommended launch tier.

**Section 2 — Self-verification loop.** Instruct Claude to verify after **each** task (not once at the end), using the method for the detected project type:

| Project type         | Verification method                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Web app              | Run the dev server, test the UI in a browser (Claude in Chrome / Chrome DevTools MCP), check the console for errors |
| Mobile (iOS/Android) | Build and run in the simulator via the sim MCP, screenshot and verify                                               |
| Mac app              | Build with `xcodebuild`, launch the app, screenshot/interact to verify                                              |
| CLI                  | Run the binary with example invocations, assert on stdout and exit codes                                            |
| Backend/service      | Start the service, hit the endpoints with `curl`, run the test suite                                                |

Always append these lines regardless of type:

- Prefix every shell command with the environment-activation prefix detected in step 2 (the shell resets between commands).
- If working in a worktree or a specific dir, `cd` into it at the start of every command, and include `pwd` + `git branch --show-current` in the evidence — the cwd resets between calls, so a run can silently drift back to the main checkout.
- Maintain a durable progress tracker (a task list, or a checklist file inside the worktree) updated after each task, so an interrupted run resumes cleanly from "continue where you left off" instead of re-deriving state.
- Run existing tests, lint, and typecheck after every change.
- Show evidence (test output, screenshots, exit codes) — never assert success without it.

**Section 3 — Final adversarial review.** Append this block verbatim to every refined prompt:

```text
## Final adversarial review (only after every task passes self-verification)

When all tasks pass self-verification, spawn two subagents in parallel (run both on Opus — review is the highest-leverage judgment step):
1. One runs the /review skill to check the full diff against the plan.
   Report only gaps that affect correctness or the stated requirements — not style.
2. One runs `/cc-suite:audit --full` to audit the implementation against the plan.

Write the merged findings to `.audit/findings.md` (severity + status per item) so
the fix loop survives an interruption. Fix the confirmed gaps, then re-run both
reviews. Repeat until both come back clean.
```

### 5. Output format

Return:

1. The refined prompt in a single copyable code block.
2. One line after the block: `Project type: <type> — verification via <method>.` (note here if the type was guessed).

Nothing else — the user pastes the block straight into their /goal, /loop, or /workflow invocation.

## Reference files (read on demand, don't preload)

- `reference/Claude-best-practices.md` — read when unsure how hard a check should gate the stop (/goal conditions, Stop hooks, subagent second opinions) or how to phrase evidence-over-assertion instructions.
- `reference/Boris-Loop-tweets.md` — read for long-running-task framing: give Claude a tool to see its output, self-verify end to end per domain.
- `reference/Feedback_loops.md` — read for the rationale behind the fresh-context review stage and encoding manual checks.

