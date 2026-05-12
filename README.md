# jack-cheng-skills

Personal Claude Code skill hub by [@anzchy](https://github.com/anzchy).

## Install

```bash
npx skills@latest add anzchy/skills
```

After install, restart your Claude Code session so the new skills are picked up.

## Skills

### Productivity

- **[jack-prompt-master](./skills/productivity/jack-prompt-master)** — Tournament-based meta-prompting. Iteratively refines a prompt across multiple rounds using parallel Claude + Codex candidate generation, an LLM-as-judge with a 7-criterion rubric, and a synthesizer. Invoke with `/jack-prompt-master <draft>` for high-stakes coding prompts.

## Repository structure

```
.claude-plugin/
  plugin.json          # manifest read by the `skills` installer
skills/
  productivity/
    jack-prompt-master/
      SKILL.md         # skill entrypoint (frontmatter + body)
      README.md
      references/      # supporting prompts / scripts
docs/                  # planning docs (not installed)
```

## Adding a new skill

1. Create `skills/<category>/<skill-name>/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: <skill-name>
   description: <one-line trigger description>
   version: 0.1.0
   ---
   ```
2. Append the skill path to `.claude-plugin/plugin.json`.
3. Commit and push — `npx skills add` pulls the latest `main`.

## License

MIT
