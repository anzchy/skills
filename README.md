# jack-cheng-skills

Personal Claude Code skill hub by [@anzchy](https://github.com/anzchy) — productivity skills for high-quality AI-assisted coding.

<p align="center">
  <a href="https://github.com/anzchy/skills/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="https://github.com/anzchy/skills/network/members"><img alt="Forks" src="https://img.shields.io/github/forks/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="https://github.com/anzchy/skills/issues"><img alt="Issues" src="https://img.shields.io/github/issues/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="https://github.com/anzchy/skills/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/anzchy/skills?style=for-the-badge&logo=git" /></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge" /></a>
</p>

**English** | [中文](#中文)

## Install

```bash
npx skills@latest add anzchy/skills
```

After install, restart your Claude Code session so the new skills are picked up.

To list available skills without installing:

```bash
npx skills@latest add anzchy/skills --list
```

## Skills

### Productivity

| Skill | Invoke | Description |
|-------|--------|-------------|
| [jack-prompt-master](./skills/productivity/jack-prompt-master) | `/jack-prompt-master <draft>` | Tournament-based meta-prompting. Iteratively refines a prompt across multiple rounds using parallel Claude + Codex candidate generation, an LLM-as-judge with a 7-criterion rubric, and a synthesizer. Best for high-stakes coding prompts. |
| [jack-loop-prompt](./skills/productivity/jack-loop-prompt) | `/jack-loop-prompt <rough prompt>` | Rewrites a rough long-running-task prompt into a paste-ready prompt with binary done-criteria, a project-type–matched self-verification loop, and a final adversarial review stage. Use before a `/goal`, `/loop`, or `/workflow` run. |

## When to use which skill

```
Rough idea → /jack-loop-prompt  → polished /goal prompt  → paste into agent
Weak prompt → /jack-prompt-master → tournament-refined prompt → paste into agent
```

- Use `/jack-loop-prompt` when you have a rough task description and want Claude to self-verify as it works.
- Use `/jack-prompt-master` when you have a draft prompt and want maximum quality through multi-round competition.

## Repository structure

```
.claude-plugin/
  plugin.json          # manifest read by the `skills` CLI
skills/
  productivity/
    jack-prompt-master/
      SKILL.md         # skill entrypoint (frontmatter + body)
      README.md
      references/      # supporting prompts / scripts
    jack-loop-prompt/
      SKILL.md
      reference/       # supporting reference docs
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
3. Commit and push — `npx skills add anzchy/skills` pulls the latest `main`.

## License

MIT

---

## 中文

个人 Claude Code 技能集，作者 [@anzchy](https://github.com/anzchy)，专注于提升 AI 辅助编程质量的生产力技能。

### 安装

```bash
npx skills@latest add anzchy/skills
```

安装后重启 Claude Code 会话，新技能即可生效。

### 技能列表

| 技能 | 调用方式 | 描述 |
|------|---------|------|
| [jack-prompt-master](./skills/productivity/jack-prompt-master) | `/jack-prompt-master <草稿>` | 基于锦标赛的元提示词优化。通过多轮 Claude + Codex 并行候选生成、7 条标准的 LLM 裁判评分、合成器综合最优版本，迭代精炼提示词。适合对质量要求极高的编程提示词。 |
| [jack-loop-prompt](./skills/productivity/jack-loop-prompt) | `/jack-loop-prompt <粗糙描述>` | 将粗糙的长任务描述改写为可直接粘贴的精炼提示词，包含二元完成标准、与项目类型匹配的自我验证循环，以及最终的对抗性审查阶段。在启动 `/goal`、`/loop` 或 `/workflow` 前使用。 |

### 使用场景

```
粗糙想法 → /jack-loop-prompt  → 精炼 /goal 提示词  → 粘贴到 agent
弱提示词 → /jack-prompt-master → 锦标赛精炼提示词 → 粘贴到 agent
```
