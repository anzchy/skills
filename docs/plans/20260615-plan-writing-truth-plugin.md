# Plan：将三个写作 Skill 集成为 `writing-truth` 插件

**日期**：2026-06-15
**状态**：待执行（已锁定关键决策）
**参考**：[anzchy/analyst-pro-plugins](https://github.com/anzchy/analyst-pro-plugins) 的 marketplace + 自包含插件结构

---

## 1. 目标

把三个源自李笑来《写作的真相》的 Skill 收拢成**一个**主题插件 `writing-truth`，去掉 `jack-` 前缀，命名空间由插件名提供（`/writing-truth:<skill>`）。

| Skill（去 jack- 后）      | 出处          | 作用           |
| --------------------- | ----------- | ------------ |
| `dissect-author-mind` | 第一课 钻进作者的脑子 | 按词性拆解、反推作者认知 |
| `logic-template-lens` | 第四课 逻辑模板    | 并列/递进/转折逻辑骨架 |
| `rhetoric-lens`       | 第五课 修辞正义    | 具象/排比/类比/隐喻  |

---

## 2. 已锁定决策

- **插件名**：`writing-truth`（《写作的真相》直译，与 `analyst-deal` 同构）。
- **落地位置**：并入现有 `jack-cheng-skills` 仓库，把**根目录升级为 marketplace**，托管两个插件——`anzchy-skills`（productivity）与 `writing-truth`（writing）。结构与参考仓库完全一致。
- **形态**：保留 `skills/`（不改写成 `commands/`）。plugin 子目录 skills 同样获得 `/插件名:名` 命名空间，省去改写成本。

---

## 3. 目标目录结构

```
jack-cheng-skills/
  .claude-plugin/marketplace.json        # 新：列出 2 个插件，删掉原 root plugin.json
  anzchy-skills/                          # 原插件整体移入子目录（仅保留 productivity）
    .claude-plugin/plugin.json
    skills/productivity/
      jack-prompt-master/  (README.md, SKILL.md, references/)
      jack-loop-prompt/    (SKILL.md, reference/)
      jack-html-preview/   (SKILL.md, reference/)
    README.md
  writing-truth/                          # 新插件（无 jack- 前缀）
    .claude-plugin/plugin.json
    skills/
      dissect-author-mind/  (SKILL.md, README.md)        # 第一课
      logic-template-lens/  (SKILL.md, README.md)        # 第四课
      rhetoric-lens/        (SKILL.md, README.md)         # 第五课
    knowledge/                            # 可选：三课原文摘录，做共享知识底座
    README.md
    CLAUDE.md
  README.md                               # 根级，改成 marketplace 索引
  docs/plans/20260615-plan-writing-truth-plugin.md   # 本文件
```

调用形态：`/writing-truth:dissect-author-mind`、`/writing-truth:logic-template-lens`、`/writing-truth:rhetoric-lens`。

---

## 4. 执行步骤

### ① 把现有插件移入子目录 `anzchy-skills/`

- `skills/productivity/` 整个移入 `anzchy-skills/skills/productivity/`。
- 现有 `.claude-plugin/plugin.json` 移入 `anzchy-skills/.claude-plugin/plugin.json`；其 `skills` 数组路径改为插件内相对路径，并**移除&#x20;****`jack-dissect-author-mind`****&#x20;那一项**（它迁往 writing-truth）。
- 现有 root `README.md` 中 productivity 内容移入 `anzchy-skills/README.md`。

### ② 新建插件 `writing-truth/`

- 从 `skills/writing/jack-{dissect-author-mind,logic-template-lens,rhetoric-lens}/` 复制三套，落到 `writing-truth/skills/{dissect-author-mind,logic-template-lens,rhetoric-lens}/`，**目录名去 jack-**。
- 改每个 `SKILL.md` frontmatter：
  - `name:` 去 jack-（如 `rhetoric-lens`）。
  - description 里 `/jack-xxx` 触发词 → `/writing-truth:xxx`。
  - 正文"姊妹技能 `jack-xxx`"互引同步去前缀。
  - README.md 内的调用示例同步改 `/writing-truth:xxx`。
- 写 `writing-truth/.claude-plugin/plugin.json`（仿 analyst-deal：name/version/description/author/license/keywords，靠 `skills/` 自动发现，不显式列 skills）。
- 写 `writing-truth/README.md` + `CLAUDE.md`：三 skill ↔ 第一/四/五课对照、调用示例、叠用方式。

### ③ 根目录改造为 marketplace

- 删除 root `.claude-plugin/plugin.json`，新建 `.claude-plugin/marketplace.json`，`plugins[]` 两项：
  - `{ name: "anzchy-skills", source: "./anzchy-skills", ... }`
  - `{ name: "writing-truth", source: "./writing-truth", ... }`
  - 各带 version / description / category / keywords。
- 重写根 `README.md` 为 marketplace 索引（列两个插件 + 安装方式）。

### ④ 去重

- 删除原 `skills/` 顶层目录（productivity 已移走、writing 三个已迁入 writing-truth），避免同名 skill 两处并存触发歧义。

### ⑤ 验证

- `python3 -m json.tool` 校验 `marketplace.json` 与两份 `plugin.json`。
- `/plugin marketplace add <repo路径>` → 重启会话。
- 冒烟：`/writing-truth:rhetoric-lens`、`/writing-truth:logic-template-lens`、`/writing-truth:dissect-author-mind` 各触发一次。
- **收尾**：派一个 subagent 做端到端自检（见 §6）。

---

## 5. 风险 / 待定

1. **跨插件依赖**：`dissect-author-mind` 首选用 `jack-html-preview`（归 `anzchy-skills`）渲染 HTML，移到 `writing-truth` 后成跨插件依赖。SKILL 内已有"回退到直接生成 HTML"兜底 → **功能不受影响**。处理策略：保留兜底、不强绑；如需自包含，可把 html-preview 也复制进 writing-truth。
2. **改动面**：移动 productivity 三个 skill 路径、删 root plugin.json → 已工作的 productivity 插件结构变化（功能不变）。已选"完全一致"方案，接受此改动。
3. **git 历史**：移动用 `git mv` 保留历史；新建的 logic/rhetoric 两个 skill 此前未提交（untracked），dissect 已跟踪。
4. **提交策略**：本轮只在本地操作，**不** commit/push，留给作者 review。`jack-prompt-master/SKILL.md` 等此前已有的未提交改动避开、单独留给作者处理。

---

## 6. 收尾自检（subagent）

执行完成后派一个子代理做端到端验证：

- 两份 `plugin.json` + `marketplace.json` 均为合法 JSON 且字段完整。
- `writing-truth/skills/` 下三个 `SKILL.md` 的 `name:` 已去 jack-、frontmatter 完整、触发词已改 `/writing-truth:`。
- 旧 `skills/` 顶层目录已无残留（无重复 skill）。
- `anzchy-skills` 插件不再含 dissect、productivity 三件齐全、内部路径自洽。
- 互引、README 调用示例全部去 jack- 且指向新命名空间。
- 输出一份 PASS/FAIL 清单与发现的问题。

