# 版式规则（从 Kami 精简，MIT）

## 不变量

1. 页面底色为羊皮纸 `#f5f4ed`，只有一个强调色：墨蓝 `#1B365D`，面积不超过 5%。
2. 灰色一律用暖灰（带黄褐底色），不用冷蓝灰。
3. 整页只用一种衬线字体：仓耳今楷 TsangerJinKai02，回退为思源宋体或宋体。
4. 字重只有两档：正文 400、标题 500。不用粗体 700，也不用斜体。
5. 行高：标题 1.1–1.3，密排 1.4–1.45，正文 1.5–1.55。
6. 标签底色用实色 hex，不用 rgba。
7. 不做装饰性的短线、边条或色块。每条线都要表达分隔、状态或关系。
8. 屏幕正文字号不小于 12px。

## 主题（Theme）

读者可在侧栏顶部切换白色、黑色、米色三种主题（选择全局保存在本机，默认值取 Settings 的 `defaultTheme`）。上面的色值是米色主题的取值；CSS 里一律引用 token（`var(--parchment)`、`var(--brand)`、`var(--wash)` 等），不要写死 hex，否则黑色主题下会出现低对比度的色块。三套 token 定义在 `assets/theme.css`，新增颜色时三种主题各配一份。白色、黑色只作用于屏幕，打印走 Print palette。

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
