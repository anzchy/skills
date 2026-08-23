# 提问思路对照：和菜头修机经验 vs Claude Code 官方 Prompt 最佳实践

整理日期：2026-08-23

来源：

- 和菜头《怎样让 AI 指导维修设备》（2026-06-28，本目录 `和菜头-怎样让_AI_指导维修设备.md`）
- Claude Code 官方文档 [best-practices](https://code.claude.com/docs/en/best-practices.md)、[common-workflows](https://code.claude.com/docs/en/common-workflows.md)（2026-08-23 抓取）

核心论点（和菜头）：**这和 AI 无关，只和"正确提问"有关**。向 AI 提问的技巧与向医生、工程师求助完全相同，前 AI 时代就存在。

---

## 一、和菜头的提问思路

**反面教材：**"我的 CD 机坏了，你告诉我怎么修" —— 信息量几乎为零，作者称之为"索取情绪价值"/"撒娇"。

**他实际用的那段话：**

> 我的索尼 D-NE800 便携式 CD 播放器现在无法通电。这是一台日本原产 CD 机，我使用两节口香糖电池供电。昨天工作一切正常，但是今天无法开机，屏幕不亮，按键无任何反应，一直处于不通电状态。我把电池换到其它 CD 机上，工作正常。请帮我分析故障原因，然后提出维修建议。

**拆解：**

| 步骤 | 做法 | 例子 | 目的 |
|---|---|---|---|
| 1. 精确标识对象 | 型号 + 品类 + 产地/批次 | 索尼 D-NE800 / 便携式 CD 播放器 / 日本原产 | 同型号有共性故障；品类做双保险防型号撞车；产地缩小范围 |
| 2. 交代运行条件 | 能源/环境 | 两节口香糖电池供电 | 故障是"无反应"，所以先说清能源 |
| 3. **按时序描述变化** | 之前 → 之后 | 昨天正常，今天无法开机 | "故障是一种变化，变化和时间密切相关"；三个月没开 vs 隔天开是两回事 |
| 4. 把抽象词展开成动作 + 结果 | 用动词名词，不用形容词 | 不说"坏了"，说"屏幕不亮、按键无反应、不通电" | "全用抽象概念那是为了抒情……肯定不是为了维修" |
| 5. **主动排除可能性** | 说明已做的交叉验证 | 电池换到另一台机器正常 | 压缩 AI 的搜索空间，让它聚焦其他方向 |
| 6. 补充原始材料 | 拍照片 | 机器照片 | 防止自己遗漏细节（AI 从图里看出了非原装电池、电池仓状态） |
| 7. 明确要什么 | 分析原因 + 维修建议 | — | 给出期望的输出 |

**多轮迭代方式：**

- 每执行一轮建议，**把结果反馈回去**（电源供电正常 → AI 判定主板没问题，把范围收敛到电池回路，并给出按概率排序的假设）。
- 不灵也要回来说"都试过了，仍无反应"，AI 再升级手段（万用表测电压 / 物理刮除氧化层）。
- 成功后**把真实解法告诉 AI**，当作案例沉淀。

**元结论：**

- 提问不好的根因是**头脑里没有"事物如何运行"的框架**，所以无法按框架整理信息。
- **"有框架的人聚焦在变化上，没框架的人聚焦在状态或者结果上"** —— 差别像微积分和四则运算。
- AI 的最大优点是耐心：哪怕小白，只要老实按建议执行、老实反馈，多轮之后也能锁定问题。
- 未来需要两种人：能帮 AI 减少交互回合的（提供好信息），以及不折不扣执行反馈的（AI 的手脚）。"不高不低反倒是个麻烦。"

---

## 二、Claude Code 官方 Prompt 最佳实践

### 1. 在 prompt 里给具体上下文

来源：[best-practices.md#provide-specific-context-in-your-prompts](https://code.claude.com/docs/en/best-practices.md#provide-specific-context-in-your-prompts)

| 策略 | Before | After |
|---|---|---|
| 限定范围 | "add tests for foo.py" | "write a test for foo.py covering the edge case where the user is logged out. avoid mocks." |
| 指向来源 | "why does ExecutionFactory have such a weird api?" | "look through ExecutionFactory's git history and summarize how its api came to be" |
| 引用现有模式 | "add a calendar widget" | "look at how existing widgets are implemented on the home page to understand the patterns. HotDogWidget.php is a good example. follow the pattern to implement a new calendar widget that lets the user select a month and paginate forwards/backwards to pick a year. build from scratch without libraries other than the ones already used in the codebase." |
| 描述症状 | "fix the login bug" | "users report that login fails after session timeout. check the auth flow in src/auth/, especially token refresh. write a failing test that reproduces the issue, then fix it" |

模糊 prompt 并非不可用——探索阶段、能随时纠偏时可以用 "what would you improve in this file?"。

### 2. 给 Claude 一个能自己验证的办法

来源：[best-practices.md#give-claude-a-way-to-verify-its-work](https://code.claude.com/docs/en/best-practices.md#give-claude-a-way-to-verify-its-work)

> Give Claude a check it can run: tests, a build, a screenshot to compare. It's the difference between a session you watch and one you walk away from.

| 策略 | Before | After |
|---|---|---|
| 给验证标准 | "implement a function that validates email addresses" | "write a validateEmail function. example test cases: user@example.com is true, invalid is false, user@.com is false. run the tests after implementing" |
| 视觉验证 | "make the dashboard look better" | "[paste screenshot] implement this design. take a screenshot of the result and compare it to the original. list differences and fix them" |
| 修根因不压症状 | "the build is failing" | "the build fails with this error: [paste error]. fix it and verify the build succeeds. address the root cause, don't suppress the error" |

- 要求**证据而非断言**：测试输出、实际运行的命令及返回、截图。
- 检查的形式：测试套件、build 退出码、linter、对比 fixture 的脚本、浏览器截图对比设计稿。
- 失败模式 "trust-then-verify gap"（代码看起来合理但漏边界）的解法："Always provide verification (tests, scripts, screenshots). If you can't verify it, don't ship it."

### 3. 提供丰富素材

来源：[best-practices.md#provide-rich-content](https://code.claude.com/docs/en/best-practices.md#provide-rich-content)、[common-workflows.md#work-with-images](https://code.claude.com/docs/en/common-workflows.md#work-with-images)

- 用 `@` 引用文件，而不是描述代码在哪（Claude 先读再答；`@` 还会带入该目录及父目录的 CLAUDE.md）。
- 直接贴图片（拖拽 / `Ctrl+V` / 给路径）：错误截图、UI 设计稿、架构图。
- 给文档 / API 的 URL；`/permissions` 加白名单域名。
- 管道喂数据：`cat error.log | claude`。
- 或告诉 Claude 自己用 Bash / MCP / 读文件去取。

### 4. 先探索、再计划、再写代码

来源：[best-practices.md#explore-first-then-plan-then-code](https://code.claude.com/docs/en/best-practices.md#explore-first-then-plan-then-code)

- 用 plan mode（`Shift+Tab` / `claude --permission-mode plan`）把调研和实现分开：Explore → Plan → Implement → Commit。
- 一句话能说清的小改动直接跳过计划；计划最有用的场景是：不确定方案、跨多文件、不熟的代码。

### 5. 让 Claude 反过来采访你

来源：[best-practices.md#let-claude-interview-you](https://code.claude.com/docs/en/best-practices.md#let-claude-interview-you)

- 大功能先让它用 `AskUserQuestion` 问清实现、UI/UX、边界情况、取舍，写成 SPEC.md，再开新会话实现。
- 好的 spec：点名涉及的文件 / 接口、说明什么不做、以端到端验证步骤收尾。

### 6. 及早纠偏、管理上下文

来源：[#course-correct-early-and-often](https://code.claude.com/docs/en/best-practices.md#course-correct-early-and-often)、[#manage-context-aggressively](https://code.claude.com/docs/en/best-practices.md#manage-context-aggressively)

- 一跑偏就纠（`Esc`、`Esc+Esc` / `/rewind`、"Undo that"、`/clear`）。
- 同一问题纠两次还不对，就 `/clear`，用学到的东西写一个更锐利的 prompt 重来。
- 不相关任务之间 `/clear`；`/compact <instructions>` 定向压缩；`/btw` 问旁支问题不进上下文。

### 7. 加一个对抗性审查步骤

来源：[best-practices.md#add-an-adversarial-review-step](https://code.claude.com/docs/en/best-practices.md#add-an-adversarial-review-step)

- 把工作当作完成之前，让一个**全新上下文**的子代理按明确标准（例如 plan 文件）审 diff。
- 只报影响正确性 / 需求的缺口，不报风格偏好——否则"总能挑出点什么"的审查者会导致过度工程。

### 8. 其他

- **CLAUDE.md**（[#write-an-effective-claude-md](https://code.claude.com/docs/en/best-practices.md#write-an-effective-claude-md)）：`/init` 生成；保持短；每一行问"删掉会不会出错"；写 Claude 猜不到的命令、非默认代码风格、测试方式、仓库礼仪、架构决策、环境坑；不写能从代码推出的、标准惯例、详细 API 文档、常变的信息。强调词 `IMPORTANT` 只给一处。
- **子代理做调查**（[#use-subagents-for-investigation](https://code.claude.com/docs/en/best-practices.md#use-subagents-for-investigation)）："use subagents to investigate X"，探索在独立上下文里进行，只回来摘要；无范围的 "investigate X" 会读几百个文件撑爆上下文，要收窄。
- **修 bug**（[common-workflows.md#fix-bugs-efficiently](https://code.claude.com/docs/en/common-workflows.md#fix-bugs-efficiently)）：给复现命令、复现步骤、说明是间歇还是稳定复现。
- **写测试**（[#work-with-tests](https://code.claude.com/docs/en/common-workflows.md#work-with-tests)）：明说要验证什么行为；Claude 会跟随已有测试文件的风格 / 框架。
- **定时 / 无人值守任务**（[#run-claude-on-a-schedule](https://code.claude.com/docs/en/common-workflows.md#run-claude-on-a-schedule)）：不能反问，所以要明写成功标准和结果去向。

---

## 三、两者对照

| 和菜头（修机） | Claude Code 官方 |
|---|---|
| 型号 / 品类 / 产地精确标识 | 指向具体文件（`@`）、引用现有模式（HotDogWidget.php） |
| 按时序描述变化；把"坏了"展开成动作 + 结果 | "描述症状"：谁在什么场景下出了什么错；贴错误原文；复现步骤、是否间歇 |
| 主动排除电池（交叉验证），压缩搜索空间 | "address the root cause, don't suppress the error"；限定范围（"avoid mocks"、"without libraries other than…"） |
| 拍照片给 AI 防遗漏 | 贴图片 / `@` 文件 / `cat error.log \| claude` / 让 Claude 自己去取 |
| 明确要"分析原因 + 维修建议" | 明确输出形态和成功标准（"run the tests after implementing"） |
| 每轮执行后把结果反馈回去，不灵也说 | 给可运行的检查 + 要证据不要断言 + 及早纠偏 |
| 纠几轮不灵就换手段（万用表 / 物理刮触点） | 同一问题纠两次失败 → `/clear` 重写更锐利的 prompt |
| "有框架的人聚焦变化，没框架的人聚焦状态" | Explore → Plan → Code；大功能先让 Claude 采访你写 spec |
| AI 按概率给假设排序 | 对抗性审查：新上下文、只报正确性缺口 |
| 成功后把真实解法告诉 AI 沉淀为案例 | 写进 CLAUDE.md 的 gotchas / 环境坑 |

**共同的底层结构：** 对象是什么 → 运行条件 → 之前 / 之后的变化 → 已排除什么 → 原始证据 → 我要什么输出 → 怎么算成功 → 多轮反馈并沉淀。

**两边侧重的差异：**

- 和菜头更强调**"变化"而非"状态"**这一思维框架，以及提问者自身的知识结构；官方文档默认你有框架，直接给模板。
- 官方文档额外强调**让 AI 能自己闭环验证**（测试 / 截图 / build）与**上下文管理**——这是工具层面的能力，修机场景下对应的是"人是 AI 的手脚，亲自去试并回报"。
- 和菜头的"成功后把解法告诉 AI"在官方体系里没有直接对应的单次对话动作，最接近的是把经验写入 CLAUDE.md。

**与本仓库的关系：** `plugins/jack-prompting/skills/jack-prompt-master` 的 7 条 rubric（role / context / task / output / constraint / failure-mode / verifiability）与上表几乎一一对应；其 Round 2 的"Grill yourself"隔离审查即官方第 7 条的实践。
