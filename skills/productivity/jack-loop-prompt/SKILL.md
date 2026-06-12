---
name: jack-loop-prompt
description: Refine a rough long-running-task prompt into one paste-ready prompt with a binary goal, a project-appropriate self-verification loop, and a final two-subagent adversarial review stage. Use before kicking off a /goal, /loop, or /workflow run. Invoke manually as "/jack-loop-prompt your rough prompt".
version: 0.1.0
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

### 3. Compose the refined prompt

The refined prompt contains exactly these three sections — no extra sections, no modes.

**Section 1 — Goal.** The target state plus the binary done-criteria from step 1, with the plan file referenced by path if one was named.

**Section 2 — Self-verification loop.** Instruct Claude to verify after **each** task (not once at the end), using the method for the detected project type:

| Project type         | Verification method                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Web app              | Run the dev server, test the UI in a browser (Claude in Chrome / Chrome DevTools MCP), check the console for errors |
| Mobile (iOS/Android) | Build and run in the simulator via the sim MCP, screenshot and verify                                               |
| Mac app              | Build with `xcodebuild`, launch the app, screenshot/interact to verify                                              |
| CLI                  | Run the binary with example invocations, assert on stdout and exit codes                                            |
| Backend/service      | Start the service, hit the endpoints with `curl`, run the test suite                                                |

Always append these two lines regardless of type:

- Run existing tests, lint, and typecheck after every change.
- Show evidence (test output, screenshots, exit codes) — never assert success without it.

**Section 3 — Final adversarial review.** Append this block verbatim to every refined prompt:

```text
## Final adversarial review (only after every task passes self-verification)

When all tasks pass self-verification, spawn two subagents in parallel:
1. One runs the /review skill to check the full diff against the plan.
   Report only gaps that affect correctness or the stated requirements — not style.
2. One runs `/cc-suite:audit --full` to audit the implementation against the plan.

Both subagents return their complete findings to the main agent. Fix the
confirmed gaps, then re-run both reviews. Repeat until both come back clean.
```

### 4. Output format

Return:

1. The refined prompt in a single copyable code block.
2. One line after the block: `Project type: <type> — verification via <method>.` (note here if the type was guessed).

Nothing else — the user pastes the block straight into their /goal, /loop, or /workflow invocation.

## Reference files (read on demand, don't preload)

- `reference/Claude-best-practices.md` — read when unsure how hard a check should gate the stop (/goal conditions, Stop hooks, subagent second opinions) or how to phrase evidence-over-assertion instructions.
- `reference/Boris-Loop-tweets.md` — read for long-running-task framing: give Claude a tool to see its output, self-verify end to end per domain.
- `reference/Feedback_loops.md` — read for the rationale behind the fresh-context review stage and encoding manual checks.

