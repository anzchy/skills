---
name: jc-basic-report
description: 'Build a VC 项目基本信息报告 (basic-information due-diligence report) as one self-contained HTML file from a company BP, optionally exported to an editable docx, following the 大纲 V 0.0.2 (投资要点、概念、公司概况与 BP 核验、产品与技术指标、市场与竞品、团队、经营、估值、风险、附录). Kami design with white/black/beige themes, A4 sheet pagination with page header and page numbers, per-report settings, data charts from JSON specs, left sidebar TOC with page numbers, highlight/underline/note annotations, and a browser test suite. Use when asked to 写/做 项目基本信息报告、尽调报告、BP 分析报告, or to rebuild/verify such a report HTML, or to 转成 Word/docx.'
version: 0.1.2
---

# jc-basic-report

把一份 BP（加公开资料）变成一份单文件 HTML 的项目基本信息报告（**Report**）。设计沿用 Kami（墨蓝单一强调色、单一衬线字体），读者可切换白 / 黑 / 米三种 **Theme**；正文排成一张张 A4 **Sheet**，带页眉页码，侧栏目录带页码；附带批注功能和自动化测试。

路径均相对本 skill 目录（下称 `<skill>`）。报告文件放在项目目录，不放进 skill。术语（Report、Sheet、Block、Paginator、Oversized table、Page chrome、Theme、Print palette、Settings、Annotation）以 `CONTEXT.md` 为准；为什么自写分页器而不用 paged.js，见 `docs/adr/0001-block-paginator-not-pagedjs.md`。

## 文件

| 路径 | 作用 |
|---|---|
| `references/outline.md` | 报告大纲与验收标准（V 0.0.2）。动笔前先读 |
| `references/design.md` | 版式规则与组件用法（从 Kami 精简），以及 Theme、Sheet 分页、Page chrome、目录页码、打印的规则 |
| `references/charts.md` | 图表 JSON 规格与各 Theme 的图表色板 |
| `references/docx.md` | 导出 docx：依赖、字体、样式与 CSS 的对应、页眉页码、排错 |
| `CONTEXT.md` | 术语表 |
| `docs/adr/0001-block-paginator-not-pagedjs.md` | ADR 0001：块级 Paginator，不用 paged.js |
| `assets/template.html` | 脱敏后的报告骨架，含全部组件和 `{{占位符}}` |
| `assets/report.css`, `ui.css`, `ui.js`, `theme.css`, `theme.js`, `paginator.css`, `paginator.js`, `chrome.css`, `chrome.js`, `assets/vendor/` | 构建时内联进 HTML，不要手改生成后的文件 |
| `assets/settings.default.json` | 默认 Settings（见下文「Settings」） |
| `scripts/build.py` | 源文件 + 图表规格 + Settings → 单文件 HTML |
| `scripts/settings.py` | Settings 的合并与校验规则（`SCHEMA`），由 build.py 调用 |
| `scripts/chart.py` | Kami 图表生成器（MIT），由 build.py 调用 |
| `scripts/docx/` | 报告 HTML → 可编辑 docx（pandoc + python-docx），含 LibreOffice 渲染与逐页对比工具 |
| `tests/` | 构建与浏览器测试；`tests/fixtures/sample` 是以沐曦股份为例的样例报告 |

## 流程

### 1. 读 BP

- 加密 PDF 先要解密版本。
- `pdftotext -layout BP.pdf bp.txt` 取文字。
- 图表页用 `pdftoppm -r 130 -f N -l N -png` 渲染后看图读数；横版幻灯片需要 `sips -r 90` 旋转。从图上读出的数要标注“读图约值”。

### 2. 查公开资料（并行子代理）

BP 只是一方说法，至少派两个子代理并行查证，要求每个事实附 URL 和日期，查不到写“未找到”：

- **核验**：
  - 工商信息、历次股权变动。上市公司股东或合资方的公告（巨潮、上交所、深交所）是首要来源。
  - 团队履历、前雇主交易、竞业与诉讼。
  - 输出核验表：主张 | 状态（已核验 / 部分核验 / 矛盾 / 无法核验）| 证据。
- **市场与竞品**：
  - 按产品线列全球头部（含海外）、A 股/港股可比公司、创业公司（≥3 家）。注明外售 / 自用角色、最新财务、产品进展。
  - 第三方市场数据要写明口径。
  - 产品技术指标给出行业典型值和测试条件。

子代理的结论是输入，不是事实。关键数字回查，矛盾之处写进报告。

### 3. 写源文件

1. 复制 `assets/template.html` 到项目目录，命名为 `report.src.html`，替换全部 `{{占位符}}`。
2. 组件可以增删行，但保留 `JC:CSS`、`JC:SCRIPTS` 标记、`#side` 侧栏和 `<main id="report">`。
3. 每个数字注明口径：BP 口径 / 一手来源〔Sx〕 / 二手转述 / 本报告计算。
4. 缺失的数据写 `<span class="gap">[DATA NEEDED: 缺什么]</span>`，不得估填。
5. 图表写成 `charts/<名称>.json`（见 `references/charts.md`），正文放 CHART 标记，如 `<!--CHART:holders-->`。
6. **算术自查**：分项是否等于合计，比例和倍数是否算对，股权是否合计 100%。逐条核对，错的数字比缺的数字更伤可信度。
7. **为分页写作**（规则详见 `references/design.md`「Sheet 与分页」）：
   - Block（标题、段落、列表、表格、图、卡片）直接放在 `<main id="report">` 下，不要再包一层 `<section>`/`<div>`，否则整层会被当成一个 Block。
   - Block 永远整块落在一张 Sheet 上，不会被拆开。
   - 高度超过一张 Sheet 的表格（Oversized table）不会续表，**作者必须自己把它拆成多张表**（按产品线、年份或维度拆，每张表各带表头和来源）。
   - 需要强制换页时，放 `<div class="page-break"></div>`。

### 4. 构建

```bash
python3 <skill>/scripts/build.py report.src.html -o <公司>-项目基本信息报告-<YYYYMMDD>.html
```

- 有未填占位符时构建失败并列出它们；`--draft` 只用于预览。
- 构建会读取 Settings（见下文），合并后内联进报告。报告仍是单个自包含 HTML。
- 构建成功后会输出 `GAP n` 和缺口清单，把它们并入附录 A「管理层访谈问题清单」。
- 打开报告时如果页面顶部出现警告框「Oversized table：……已单独成页、未截断；请拆成多张表。」，按提示拆表后重新构建。

#### Settings

默认值在 `assets/settings.default.json`，不写任何配置也能构建出合理的报告。要为某份报告改设置，在 `report.src.html` 旁放一个 `settings.json`，只写要改的键：

```json
{"defaultTheme": "white", "chrome": {"headerTemplate": "{company} · 尽调底稿"}}
```

构建时，`settings.json` 与默认文件深度合并：覆盖文件优先，嵌套对象逐键合并，写 `null` 会删除该键，然后构建失败并报「缺少必填键」。

| 键 | 默认值 | 作用 |
|---|---|---|
| `defaultTheme` | `"beige"` | 读者没选过 Theme 时的起始主题：`white` / `black` / `beige` |
| `pagination.enabled` | `true` | `false` 时不分页，回退到连续滚动：没有 Sheet、Page chrome 和目录页码 |
| `paper.size` | `"A4"` | 目前只支持 `"A4"` |
| `paper.marginMm.{top,right,bottom,left}` | `16 / 18 / 18 / 18` | Sheet 页边距（毫米，非负数），页眉页脚画在这里 |
| `chrome.headerTemplate` | `"{company} · 项目基本信息报告"` | 页眉模板 |
| `chrome.footerTemplate` | `"第 {page} 页 共 {pages} 页"` | 页脚模板，必须含 `{page}`，可含 `{pages}` |
| `toc.pageNumbers` | `true` | 侧栏目录是否显示页码 |
| `print.palette` | `"white"` | Print palette：打印、PDF 和 docx 用哪套配色，与读者当前的 Theme 无关 |
| `themes.<white\|black\|beige>.chart.<键>` | 见默认文件 | 各 Theme 的图表色板（hex 颜色，如 `#1B365D`），键名见 `references/charts.md` |

模板变量：`{company}` 是文档 `<title>` 第一个「·」之前的部分，在打开报告（和导出 docx）时填入，构建时不替换；`{page}`、`{pages}` 是当前 Sheet 序号和 Sheet 总数。

构建时会校验合并结果，有问题就失败（退出码 1），并逐条列出原因，例如：

```
ERROR: Settings 校验失败（4 处）：
  未知键 foo
  非法主题名 defaultTheme = 'blue'（可选：white / black / beige）
  页边距必须是非负数（毫米） paper.marginMm.top = -1
  缺少必填键 toc
```

类型错误、`footerTemplate` 不含 `{page}`、颜色不是 hex、`settings.json` 不是合法 JSON 也会失败。要新增一个键，`scripts/settings.py` 的 `SCHEMA` 和 `assets/settings.default.json` 要同时改，否则构建失败。

### 5. 测试

```bash
uv run --with pytest --with playwright --with python-docx --with pymupdf --with pillow python -m pytest <skill>/tests --report <生成的报告>.html
```

- 用本机 Chrome 跑，无需下载浏览器。不带 `--report` 时测试内置样例。
- 覆盖：构建脚本与 Settings 校验、Theme（切换、记忆、图表色板）、分页（Sheet 数量与 A4 尺寸、Block 不跨 Sheet、Oversized table、关闭分页）、Page chrome、侧栏目录（生成、页码、跳转高亮、折叠及记忆）、批注（高亮、划线、备注、刷新后位置不漂移、「未定位」、删除、列表跳转、导出导入）、打印（白底、每张 Sheet 一页）、docx 导出（样式、内容、页眉页码、渲染）。
- docx 渲染测试在缺 LibreOffice 或今楷字体时自动跳过，见 `references/docx.md`。
- 全部通过才算完成。

### 6. 目视检查

- 用无头 Chrome 截全页图，分段查看。
- 重点检查：页面顶部有没有 Oversized table 警告、Sheet 底部是否有大片留白（可调整段落顺序或拆表）、标题区公司名是否折行（标题用简称）、四个关键数字标签是否溢出（每个 ≤8 字）、两栏图表是否过小（改用 `"size": "compact"`），数字列是否折行，表格列宽是否失衡，标签是否继承了首行缩进。
- 每轮修最明显的三处，最多三轮。

### 7. 导出 docx（可选）

用户要 Word 版时：

```bash
W=$(mktemp -d)
uv run --with playwright python <skill>/scripts/docx/prep.py <报告>.html $W
uv run --with python-docx python <skill>/scripts/docx/build_docx.py $W <报告>.docx
uv run --with playwright --with pymupdf --with pillow python <skill>/scripts/docx/compare.py <报告>.html <报告>.docx <对比目录>
```

- 依赖 pandoc、Chrome、LibreOffice。仓耳今楷 TsangerJinKai02 必须装在 `~/Library/Fonts`，否则 Chrome 和 Word 都会换成别的字体。详见 `references/docx.md`。
- 打开 `compare.py` 生成的逐页并排图，检查图表是否完整、表格是否跨页、页数与 HTML 是否接近。
- docx 带页眉（首页无页眉）和居中的 Word `PAGE`/`NUMPAGES` 页码域，页面底色跟随 Print palette（默认白底），都读报告里内联的 Settings；页数由 Word 自己计算，不与 HTML 的 Sheet 逐页对应。已知差异（页眉只有一行且靠左、页边距固定 2cm）见 `references/docx.md`。

### 8. 交付

在回复里写明：

- 文件路径；
- 测试结果；
- `[DATA NEEDED]` 清单与所做的假设；
- BP 与公开记录不一致的地方。

## 批注功能须知（告诉读者）

- 批注保存在读者本机浏览器（localStorage），按 `<meta name="report-id">` 区分报告。每份报告的 report-id 必须唯一。
- 换电脑或分享前用侧栏的「导出 JSON」备份。
- 打开报告时，已保存或导入的批注会按原文引文（连同前后文）重新定位，所以报告修订、重新分页后，高亮仍落在原来的文字上；同一句话出现多次时，取前后文最吻合、离原位置最近的一处。
- 原文已找不到的批注不会画到别的文字上，也不会悄悄丢掉：它排在侧栏批注列表末尾，带「未定位」标记，点击不跳转；仍会随「导出 JSON」导出，只有「清空」能删除它。
- 批注不会跨 Sheet：Block 整块落在一张 Sheet 上，页眉页码也不属于可批注的文字。
