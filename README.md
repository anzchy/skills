# jack-cheng-skills

A Claude Code **plugin marketplace** by [@anzchy](https://github.com/anzchy) — productivity skills for AI-assisted coding, plus reading & writing skills distilled from Li Xiaolai's 《写作的真相》.

<p align="center">
  <a href="https://github.com/anzchy/skills/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="https://github.com/anzchy/skills/network/members"><img alt="Forks" src="https://img.shields.io/github/forks/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="https://github.com/anzchy/skills/issues"><img alt="Issues" src="https://img.shields.io/github/issues/anzchy/skills?style=for-the-badge&logo=github" /></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge" /></a>
</p>

**English** | [中文](#中文)

## Plugins

| Plugin | Category | What's inside |
|--------|----------|---------------|
| [anzchy-skills](./anzchy-skills) | productivity | `jack-prompt-master` · `jack-loop-prompt` · `jack-html-preview` |
| [writing-truth](./writing-truth) | writing | `dissect-author-mind` (L1) · `logic-template-lens` (L4) · `rhetoric-lens` (L5) — from 《写作的真相》 |

Plugin skills are namespaced as `/<plugin>:<skill>`, e.g. `/writing-truth:rhetoric-lens`.

## Install

```bash
# add this repo as a marketplace, then install the plugin(s) you want
/plugin marketplace add anzchy/jack-cheng-skills
/plugin install writing-truth
/plugin install anzchy-skills
```

After install, restart your Claude Code session so the new skills are picked up.

## Repository structure

```
.claude-plugin/
  marketplace.json       # marketplace manifest, lists the plugins below
anzchy-skills/           # plugin: productivity
  .claude-plugin/plugin.json
  skills/productivity/
    jack-prompt-master/  (README.md, SKILL.md, references/)
    jack-loop-prompt/    (SKILL.md, reference/)
    jack-html-preview/   (SKILL.md, reference/)
  README.md
writing-truth/           # plugin: reading & writing (《写作的真相》)
  .claude-plugin/plugin.json
  skills/
    dissect-author-mind/ (SKILL.md, README.md)   # 第一课
    logic-template-lens/ (SKILL.md, README.md)   # 第四课
    rhetoric-lens/       (SKILL.md, README.md)    # 第五课
  knowledge/
  README.md
  CLAUDE.md
docs/                    # planning docs (not installed)
```

## Adding a new plugin

1. Create `<plugin-name>/.claude-plugin/plugin.json` and a `skills/` (or `commands/`, `agents/`) directory.
2. Append the plugin to `.claude-plugin/marketplace.json` with its `source` path.
3. Commit and push.

## License

MIT

---

## 中文

[@anzchy](https://github.com/anzchy) 的 Claude Code **插件市场**：AI 辅助编程的生产力技能，外加一组提炼自李笑来《写作的真相》的阅读/写作技能。

### 插件列表

| 插件 | 类别 | 内含 |
|------|------|------|
| [anzchy-skills](./anzchy-skills) | 生产力 | `jack-prompt-master`、`jack-loop-prompt`、`jack-html-preview` |
| [writing-truth](./writing-truth) | 写作 | `dissect-author-mind`（第一课）、`logic-template-lens`（第四课）、`rhetoric-lens`（第五课） |

插件内 skill 以 `/<插件>:<skill>` 命名空间调用，如 `/writing-truth:rhetoric-lens`。

### 安装

```bash
/plugin marketplace add anzchy/jack-cheng-skills
/plugin install writing-truth
/plugin install anzchy-skills
```

安装后重启 Claude Code 会话，新技能即可生效。
