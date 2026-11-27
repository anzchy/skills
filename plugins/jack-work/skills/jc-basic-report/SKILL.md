---
name: jc-basic-report
description: 'Build a VC 项目基本信息报告 (basic-information due-diligence report) as one self-contained HTML file from a company BP, optionally exported to an editable docx, following the 大纲 V 0.0.2 (投资要点、概念、公司概况与 BP 核验、产品与技术指标、市场与竞品、团队、经营、估值、风险、附录). Kami parchment design, data charts from JSON specs, left sidebar TOC, highlight/underline/note annotations, and a browser test suite. Use when asked to 写/做 项目基本信息报告、尽调报告、BP 分析报告, or to rebuild/verify such a report HTML, or to 转成 Word/docx.'
version: 0.1.2
---

# jc-basic-report

把一份 BP（加公开资料）变成一份单文件 HTML 的项目基本信息报告。设计沿用 Kami（羊皮纸底色、墨蓝单一强调色、单一衬线字体），附带侧栏目录、批注功能和自动化测试。

路径均相对本 skill 目录（下称 `<skill>`）。报告文件放在项目目录，不放进 skill。

## 文件

| 路径 | 作用 |
|---|---|
| `references/outline.md` | 报告大纲与验收标准（V 0.0.2）。动笔前先读 |
| `references/design.md` | 版式规则与组件用法（从 Kami 精简） |
| `references/charts.md` | 图表 JSON 规格 |
| `references/docx.md` | 导出 docx：依赖、字体、样式与 CSS 的对应、排错 |
| `assets/template.html` | 脱敏后的报告骨架，含全部组件和 `{{占位符}}` |
| `assets/report.css`, `assets/ui.css`, `assets/ui.js`, `assets/paginator.js`, `assets/paginator.css`, `assets/vendor/` | 构建时内联进 HTML，不要手改生成后的文件 |
| `assets/settings.default.json` | 默认 Settings：默认主题、纸张与页边距、页眉页码模板、目录页码、Print palette、各主题图表色板、分页开关 |
| `scripts/build.py` | 源文件 + 图表规格 + Settings → 单文件 HTML |
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

### 4. 构建

```bash
python3 <skill>/scripts/build.py report.src.html -o <公司>-项目基本信息报告-<YYYYMMDD>.html
```

- 有未填占位符时构建失败并列出它们；`--draft` 只用于预览。
- 需要改默认 Settings 时，在 `report.src.html` 旁放 `settings.json`，只写要改的键（如 `{"defaultTheme": "white", "chrome": {"headerTemplate": "{company} · 尽调底稿"}}`）。构建时与 `assets/settings.default.json` 深度合并，覆盖优先；未知键、非法主题名、负页边距、缺失必填键等都会让构建失败并逐条列出。合并结果内联进报告，报告仍是单个文件。
- 打开报告时，Paginator 把正文整块排进 A4 Sheet：段落、列表、表格、图不跨 Sheet，标题与其后的 Block 同页，`<div class="page-break"></div>` 强制换页。高度超过一张 Sheet 的表格（Oversized table）单独成页且不截断，页面顶部和控制台会给出警告，请把它拆成多张表。`settings.json` 里 `{"pagination": {"enabled": false}}` 回退到连续滚动。
- 构建成功后会输出 `GAP n` 和缺口清单，把它们并入附录 A「管理层访谈问题清单」。

### 5. 测试

```bash
uv run --with pytest --with playwright --with python-docx --with pymupdf python -m pytest <skill>/tests --report <生成的报告>.html
```

- 用本机 Chrome 跑，无需下载浏览器。不带 `--report` 时测试内置样例。
- 覆盖：构建脚本行为、侧栏目录（生成、跳转高亮、折叠及记忆）、批注（高亮、划线、备注、刷新后保留、删除、列表跳转、导出导入）、docx 导出（样式、内容、渲染）。
- docx 渲染测试在缺 LibreOffice 或今楷字体时自动跳过，见 `references/docx.md`。
- 全部通过才算完成。

### 6. 目视检查

- 用无头 Chrome 截全页图，分段查看。
- 重点检查：标题区公司名是否折行（标题用简称）、四个关键数字标签是否溢出（每个 ≤8 字）、两栏图表是否过小（改用 `"size": "compact"`），数字列是否折行，表格列宽是否失衡，标签是否继承了首行缩进。
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

### 8. 交付

在回复里写明：

- 文件路径；
- 测试结果；
- `[DATA NEEDED]` 清单与所做的假设；
- BP 与公开记录不一致的地方。

## 批注功能须知（告诉读者）

- 批注保存在读者本机浏览器（localStorage），按 `<meta name="report-id">` 区分报告。每份报告的 report-id 必须唯一。
- 换电脑或分享前用侧栏的「导出 JSON」备份。
- 报告正文改动后，改动段落附近的批注可能需要重新定位。
