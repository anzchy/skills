

What's the best way to create quality validation loops? Or to learn how to create them? I know that's a nuanced question "it depends" but I'm more interested in learning how to think about building them, if that makes sense. 

Boris: It’s really simple actually, I think people sometimes over-complicate it.

1. Give Claude a tool to see the output of the code: if server code, a way to start the server/service; if web code, a way to see and interact with the UI; etc.
2. Tell Claude about the tool: this is just tuning the tool descriptions so Claude understands when it should use the tool

That’s literally it. Claude will figure out the rest.



---

 For very long-running tasks, I will either (a) prompt Claude to verify its work with a background agent when it's done.



---

13/ A final tip: probably the most important thing to get great results out of Claude Code -- give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality of the final result.

Claude tests every single change I land to claude.ai/code using the Claude Chrome extension. It opens a browser, tests the UI, and iterates until the code works and the UX feels good.

Verification looks different for each domain. It might be as simple as running a bash command, or running a test suite, or testing the app in a browser or phone simulator. Make sure to invest in making this rock-solid.



---

Most important thing I’ve found is self-verification + dynamic workflows prompted with something like “use a workflow to test the result e2e in a browser using claude in chrome mcp. Especially look for edge cases and ui issues”



---

Seeing a number of benchmarks showing Opus is the best model for long-running work.

Five tips for running Opus autonomously for hours/days:

1. Use auto mode for permissions, so Claude doesn’t ask for approval
2. Use dynamic workflows, to have Claude orchestrate hundreds/thousands of agents to get a task done
3. Use /goal or /loop, to nudge Claude to keep going until it’s done
4. Use Claude Code in the cloud, so you can close your laptop (easiest way is the desktop or mobile app)
5. Make sure Claude has a way to self-verify its work end to end: Claude in Chrome browser extension for web, iOS/Android sim MCP for mobile, a way to start the full web server or service for backend work



A few things I’ve used very long running sessions for:

- Building complex features
- Migrating code from language X to Y
- Migrating code from framework X to Y
- Repeatedly profiling and optimizing code to hit a specific memory or CPU target
- Finding and fixing flaky tests in CI
- Profiling CI to make it faster

