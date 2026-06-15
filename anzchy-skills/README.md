# anzchy-skills

Productivity skills for high-quality AI-assisted coding by [@anzchy](https://github.com/anzchy). Part of the `jack-cheng-marketplace`.

**Status:** v0.1.0 — Claude Code plugin.

## Skills

| Skill | Invoke | Description |
|-------|--------|-------------|
| [jack-prompt-master](./skills/productivity/jack-prompt-master) | `/anzchy-skills:jack-prompt-master <draft>` | Tournament-based meta-prompting. Iteratively refines a prompt across multiple rounds using parallel Claude + Codex candidate generation, an LLM-as-judge with a 7-criterion rubric, and a synthesizer. Best for high-stakes coding prompts. |
| [jack-loop-prompt](./skills/productivity/jack-loop-prompt) | `/anzchy-skills:jack-loop-prompt <rough prompt>` | Rewrites a rough long-running-task prompt into a paste-ready prompt with binary done-criteria, a project-type–matched self-verification loop, and a final adversarial review stage. Use before a `/goal`, `/loop`, or `/workflow` run. |
| [jack-html-preview](./skills/productivity/jack-html-preview) | `/anzchy-skills:jack-html-preview <path-or-url>` | Turns a folder, repo, or Markdown file into ONE self-contained interactive HTML that explains it end-to-end (collapsible tree, click-to-explain nodes, flow diagram), styled in the Claude/Anthropic design language. |

## When to use which

```
Rough idea  → /anzchy-skills:jack-loop-prompt   → polished /goal prompt        → paste into agent
Weak prompt → /anzchy-skills:jack-prompt-master → tournament-refined prompt     → paste into agent
A repo/dir  → /anzchy-skills:jack-html-preview  → one-file interactive explainer
```

## Note

The writing skills (dissect-author-mind, logic-template-lens, rhetoric-lens) moved to the sibling **`writing-truth`** plugin in the same marketplace.

## License

MIT
