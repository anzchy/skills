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
| [jack-prompting](./plugins/jack-prompting) | productivity | `jack-ask` (router) · `jack-meta-think` · `jack-prompt-master` · `jack-loop-prompt` — work on the prompt before any code |
| [jack-engineering](./plugins/jack-engineering) | productivity | `jack-audit-fable` · `jack-review-plan-fable` · `jack-auto-fix` · `jack-audit-branches` — review and audit code and plans |
| [jack-git](./plugins/jack-git) | productivity | `gh-commit` · `gh-pr` · `gh-release` — ship with the `gh` CLI |
| [jack-html-preview](./plugins/jack-html-preview) | productivity | one-file interactive HTML explainer for a folder, repo, or Markdown file |
| [songy-course-exporter](./plugins/songy-course-exporter) | utility | export a Songy course (personal tool, installed disabled by default) |
| [writing-truth](./plugins/writing-truth) | writing | `dissect-author-mind` (L1) · `logic-template-lens` (L4) · `rhetoric-lens` (L5) — from 《写作的真相》 |

Plugins are small on purpose — install only the ones you want. Skills are namespaced as `/<plugin>:<skill>`, e.g. `/jack-prompting:jack-meta-think`, `/writing-truth:rhetoric-lens`. Not sure which skill? `/jack-prompting:jack-ask <your ask>` routes across all of them.

## Install

```bash
# add this repo as a marketplace, then install the plugin(s) you want
/plugin marketplace add anzchy/skills
/plugin install jack-prompting@jack-cheng-marketplace
/plugin install jack-engineering@jack-cheng-marketplace
/plugin install jack-git@jack-cheng-marketplace
/plugin install jack-html-preview@jack-cheng-marketplace
/plugin install writing-truth@jack-cheng-marketplace
```

Or, without the plugin system: `npx skills@latest add anzchy/skills` installs every skill as plain skills.

After install, restart your Claude Code session so the new skills are picked up.

## Repository structure

```
.claude-plugin/
  marketplace.json       # marketplace manifest; metadata.pluginRoot = ./plugins
plugins/
  jack-prompting/        # .claude-plugin/plugin.json + skills/{jack-ask,jack-meta-think,jack-prompt-master,jack-loop-prompt}
  jack-engineering/      # skills/{jack-audit-fable,jack-review-plan-fable,jack-auto-fix,jack-audit-branches}
  jack-git/              # skills/{gh-commit,gh-pr,gh-release}
  jack-html-preview/     # single-skill plugin: SKILL.md at the plugin root
  songy-course-exporter/ # skills/songy-course-exporter (defaultEnabled: false)
  writing-truth/         # skills/{dissect-author-mind,logic-template-lens,rhetoric-lens} + knowledge/
docs/                    # planning docs and reference texts (not installed)
CHANGELOG.md
```

## Design

- **One plugin per install intent.** A plugin is the smallest unit a user can enable, so each plugin groups skills someone would want together and nothing else. A personal tool (`songy-course-exporter`) ships as its own plugin, disabled by default.
- **Skills are auto-discovered** from each plugin's `skills/` directory (recursively); `plugin.json` carries `name`, `version` and metadata only.
- **Three version layers**, bumped independently: each skill's `version:` frontmatter, each plugin's `plugin.json` `version` (mirrored in `marketplace.json` — this is what gates `/plugin` updates), and the marketplace `version` / repo tag.

## Adding a new plugin

1. Create `plugins/<plugin-name>/.claude-plugin/plugin.json` (`name`, `version: 0.1.0`, `description`) and a `skills/<skill>/SKILL.md` (or put a single `SKILL.md` at the plugin root).
2. Append the plugin to `.claude-plugin/marketplace.json` with `source: ./plugins/<plugin-name>` and the same `version`.
3. `claude plugin validate . && claude plugin validate ./plugins/<plugin-name>`, then release with `/marketplace-release`.

## License

MIT

---

## 中文

[@anzchy](https://github.com/anzchy) 的 Claude Code **插件市场**：AI 辅助编程的生产力技能，外加一组提炼自李笑来《写作的真相》的阅读/写作技能。

### 插件列表

| 插件 | 类别 | 内含 |
|------|------|------|
| [jack-prompting](./plugins/jack-prompting) | 生产力 | `jack-ask`（路由）、`jack-meta-think`、`jack-prompt-master`、`jack-loop-prompt` —— 写代码之前先把提示词做对 |
| [jack-engineering](./plugins/jack-engineering) | 生产力 | `jack-audit-fable`、`jack-review-plan-fable`、`jack-auto-fix`、`jack-audit-branches` —— 审代码、审计划 |
| [jack-git](./plugins/jack-git) | 生产力 | `gh-commit`、`gh-pr`、`gh-release` —— 用 `gh` CLI 提交 / PR / 发布 |
| [jack-html-preview](./plugins/jack-html-preview) | 生产力 | 把目录、仓库或 Markdown 变成单文件交互式 HTML 讲解页 |
| [songy-course-exporter](./plugins/songy-course-exporter) | 工具 | 导出 Songy 课程（个人工具，默认不启用） |
| [writing-truth](./plugins/writing-truth) | 写作 | `dissect-author-mind`（第一课）、`logic-template-lens`（第四课）、`rhetoric-lens`（第五课） |

插件刻意拆得很小，只装你需要的。skill 以 `/<插件>:<skill>` 调用，如 `/jack-prompting:jack-meta-think`、`/writing-truth:rhetoric-lens`。不知道该用哪个？`/jack-prompting:jack-ask <你的需求>` 会跨插件路由。

### 安装

```bash
/plugin marketplace add anzchy/skills
/plugin install jack-prompting@jack-cheng-marketplace
/plugin install jack-engineering@jack-cheng-marketplace
/plugin install jack-git@jack-cheng-marketplace
/plugin install jack-html-preview@jack-cheng-marketplace
/plugin install writing-truth@jack-cheng-marketplace
```

不用插件系统也可以：`npx skills@latest add anzchy/skills` 会把所有 skill 作为普通 skill 安装。

安装后重启 Claude Code 会话，新技能即可生效。
