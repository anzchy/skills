# 版式规则（从 Kami 精简，MIT）

## 不变量

1. 米色主题的页面底色为羊皮纸 `#f5f4ed`（白色、黑色主题见下文「Theme」）；只有一个强调色：墨蓝 `#1B365D`，面积不超过 5%。
2. 灰色一律用暖灰（带黄褐底色），不用冷蓝灰。
3. 整页只用一种衬线字体：仓耳今楷 TsangerJinKai02，回退为思源宋体或宋体。
4. 字重只有两档：正文 400、标题 500。不用粗体 700，也不用斜体。
5. 行高：标题 1.1–1.3，密排 1.4–1.45，正文 1.5–1.55。
6. 标签底色用实色 hex，不用 rgba。
7. 不做装饰性的短线、边条或色块。每条线都要表达分隔、状态或关系。
8. 屏幕正文字号不小于 12px。

## Theme

读者在侧栏顶部三选一切换 **Theme**：白色、黑色、米色（Kami 羊皮纸）。

- 选择存在读者本机（localStorage 键 `jc-report-theme`），对所有报告生效（全局，不按报告），刷新或打开别的报告后仍保留。读者没选过时，用 Settings 的 `defaultTheme`（默认 `beige`）。
- 上面「不变量」里的色值是米色主题的取值。CSS 里一律引用 token（`var(--parchment)`、`var(--brand)`、`var(--wash)` 等），不要写死 hex，否则黑色主题下会出现低对比度的色块。米色 token 是 `assets/report.css` 的 `:root`（加上 `theme.css` 的 `:root`），白色、黑色的覆盖在 `assets/theme.css` 的 `html[data-theme="…"]` 块里。新增颜色时三种主题各配一份。
- 图表和手写示意图也随 Theme 换色（见下文「示意图」和 `references/charts.md`），批注高亮在黑色主题下改用深色高亮。
- Theme 只作用于屏幕。打印、PDF 和 docx 走 **Print palette**（见下文「打印」），与当前 Theme 无关。
- 切换 Theme 或收起侧栏不会重新分页。

## Sheet 与分页

打开报告时，**Paginator**（`assets/paginator.js`，构建时内联）把 `<main id="report">` 的直接子节点按顺序整块搬进一张张 A4 **Sheet**，不拆分、不复制。理由与取舍见 ADR 0001（`docs/adr/0001-block-paginator-not-pagedjs.md`），术语见 `CONTEXT.md`。

- Sheet 是严格 A4（210 × 297 mm），页边距取 Settings 的 `paper.marginMm`（默认上 16、右 18、下 18、左 18 毫米）。
- Paginator 等字体和图片加载完再测量高度，最多等 8 秒。页码依赖字体：今楷没装、CDN 字体又加载不到时，换用的字体字宽不同，分页位置会变。
- **Block**（标题、段落、列表、表格、图、卡片）永远整块落在一张 Sheet 上。段落和列表不按行拆，所以 Sheet 底部可能留白。
- 标题不会单独留在 Sheet 底部，会和它后面的 Block 一起换到下一张。
- `<div class="page-break"></div>`（或任何带 `break-before: page` 的 Block）强制从新 Sheet 开始。

写作约束：

- Block 必须是 `#report` 的直接子元素。把一整节包进 `<section>` 或 `<div>`，整节会被当作一个 Block。
- **Oversized table**：高度超过一张 Sheet 可用高度的表格。Paginator 不做续表，只把它单独放一张 Sheet，按内容长高，不截断。同时在页面顶部（`#report` 之前）显示警告框、在控制台输出 `console.warn`，警告里写明它在哪个标题下、有多高。**作者必须自己把它拆成多张表**（按产品线、年份或维度拆，每张各带表头和来源），然后重新构建。其他超高的 Block 也照此处理，提示是「Oversized block」。
- 警告框不会打印出来。但 Oversized Sheet 打印时会占好几页纸，而页脚的「共 Y 页」只数 Sheet，会少算。所以交付前要消除所有警告。
- 不想分页时，在 `settings.json` 写 `{"pagination": {"enabled": false}}`，报告回到连续滚动：没有 Sheet、Page chrome 和目录页码，打印走 `report.css` 的默认 `@page`（固定 16/18 mm 页边距，底部居中「页码 · 项目基本信息报告」）。

## Page chrome

每张 Sheet 的页边距里画着页眉和页码，由 `assets/chrome.js` 在分页完成后添加，只在分页开启时出现。

- **页眉**：按 Settings 的 `chrome.headerTemplate`（默认 `{company} · 项目基本信息报告`）生成。`{company}` 是文档 `<title>` 第一个「·」之前的部分，所以 `<title>` 要保持模板里的「{{公司简称}} · 项目基本信息报告」格式。模板在第一个「·」处分成两段：左段靠左（公司简称），右段靠右（报告名）。
- **页脚**：按 `chrome.footerTemplate`（默认 `第 {page} 页 共 {pages} 页`）居中显示「第 X 页 共 Y 页」。Y 是 Sheet 总数。
- 第一张 Sheet（标题区）没有页眉，但计入页码，页脚为「第 1 页 共 Y 页」。
- 页眉页脚用 CSS 生成内容绘制，不属于正文文字，不能选中或批注，也不会被导出到 docx 正文里。
- 颜色用 `var(--stone)`，随 Theme 变化。

## 目录页码

侧栏目录（tocbot）在分页完成后生成，每一项右侧显示该标题所在 Sheet 的序号，点击跳到对应 Sheet 上的标题，滚动时仍高亮当前小节。`toc.pageNumbers` 设为 `false`，或关闭分页时，不显示页码。侧栏收起时页码随目录一起隐藏。

## 打印（Print palette）

打印和「另存为 PDF」使用 Settings 的 `print.palette`（默认 `white`，即白底），与读者屏幕上的 Theme 无关；页面 token 和图表色板都换成该主题的取值。

- 想打印成羊皮纸底色：`settings.json` 写 `{"print": {"palette": "beige"}}`。也可以设为 `black`，但 docx 导出不适合黑色（见 `references/docx.md`）。
- 分页开启时，每张 Sheet 正好打印成一页 A4：纸张本身没有页边距（Sheet 自带页边距），页码只有 Page chrome 画的那一个，不再叠加 `report.css` 的底部页码。Oversized Sheet 例外，会跨几页纸。
- 打印时会隐藏侧栏、批注工具条和分页警告。

## 层级与强调

- 层级靠字号、间距、墨蓝，不靠粗体或装饰线。
- 强调某个数字或结论：用 `<span class="hl">`（墨蓝），不加粗。
- 正文段落首行缩进 2 字（已在 CSS 中设定）。注释、标签、表格内文字不缩进。

## 组件（均已在 template.html 中给出示例）

| 组件 | 用法 |
|---|---|
| `.report-header` + `.metrics` | 标题区与 4 个关键数字。4 个数字讲不出故事，说明选错了数字 |
| `h2.with-rating` | 投资要点标题，右侧放建议 |
| `ul.thesis` | 3–5 条论点，每条以 `<strong>标题。</strong>` 开头，并有数字和来源 |
| `table.compact` | 默认表格：细线分隔，首尾列贴齐正文边缘，无竖线、无底色表头 |
| `table.financial` | 数字列右对齐、等宽数字；文字列加 `style="text-align:left"` |
| `table.nums` | 前 4 列不折行（适合时间、金额列） |
| `table.spec` | 技术指标表：指标、通俗解释、方向、典型值、公司值 |
| `.dir.up / .down / .mid` | 方向标签：↑ 越大越好 / ↓ 越小越好 / ◎ 越接近目标越好 |
| `.gap` | `[DATA NEEDED: …]` 缺口标记；build.py 会统计 |
| `p.note` | 表、图下方的来源和口径说明 |
| `.two-col` | 两图并排（图表规格必须用 `"size": "compact"`） |
| `.risk-grid` | 风险两列网格，每项“标签 + 量化描述” |
| `.verdict` | 结尾总结：一句结论 + 看多 / 看空 / 决策条件 / 条款建议 |
| `ol.qa`、`ol.sources` | 附录问题清单与编号来源（正文以〔S1〕引用） |

## 示意图

“产品在下游的位置”这类示意图需要手写 SVG。颜色一律写成 CSS 变量加 Kami 字面量回退值，切换 **Theme**（白 / 黑 / 米）时示意图与数据图表一起换色；不要写裸的十六进制色，否则黑色主题下会变成一块亮框。只用下面这些：
- 底色 `var(--chart-parchment, #f5f4ed)`，文字 `var(--chart-near-black, #141413)`，次要文字 `var(--chart-stone, #6b6a64)`；
- 墨蓝 `var(--chart-brand, #1B365D)`，用于目标公司的产品；浅墨蓝 `var(--brand-mid, #2D5A8A)`、标签底 `var(--chart-brand-tint, #EEF2F7)`；
- 象牙块 `var(--ivory, #faf9f5)`、边线 `var(--chart-grid, #e8e7e1)` / `var(--chart-mist, #d4d3cd)`；
- 深色块 `var(--chart-charcoal, #4d4c48)`，块上文字用 `var(--chart-parchment, #f5f4ed)`（黑色主题下二者自动反转，仍可读）。

`--chart-*` 是图表色板，每个 Theme 的取值来自 Settings 的 `themes.<主题>.chart`（键名 `near_black` 对应变量 `--chart-near-black`）；`--ivory`、`--brand-mid` 是页面 token。示例：`<rect fill="var(--chart-brand, #1B365D)"/>`。

文字用 `font-family="TsangerJinKai02, 'Source Han Serif SC', 'Songti SC', serif"`，图注写明“示意图，本报告绘制”。

## 写作要求

- 每个结论有数字或来源支撑，不写无法量化的形容词。
- 先承认反方观点，再给判断。
- 用“我们估计”“我们的判断”这类语气，不用夸张表述。
- 术语第一次出现时加注；全文同一术语只用一种写法。
