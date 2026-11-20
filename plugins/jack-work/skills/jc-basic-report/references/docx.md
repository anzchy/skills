# 导出 docx

`scripts/docx/` 把构建好的报告 HTML 转成可编辑的 docx，版式尽量贴近 HTML。它依赖本模板的 DOM 结构和 `assets/report.css`，不是通用的 HTML→docx 转换器。

## 流程

| 脚本 | 作用 |
|---|---|
| `prep.py <报告.html> <工作目录>` | Playwright 打开报告：SVG 图表截成 PNG；标题区、关键数字、风险卡片、结论清单、来源列表、评级标签、`.two-col` 改写成 pandoc 能处理的结构；记录每张表的类型和列宽、文档标题，写入 `meta.json` |
| `build_docx.py <工作目录> <输出.docx>` | pandoc 转 docx，再用 python-docx 按 report.css 设置样式 |
| `render.py <docx> <输出目录>` | LibreOffice 把 docx 渲染成 PDF（使用 `fonts.conf`） |
| `compare.py <报告.html> <docx> <输出目录>` | Chrome 打印 HTML（A4、2cm 边距）与 LibreOffice 渲染的 docx 逐页并排，输出 `pages_NN-MM.png` |

## 依赖

- pandoc、Google Chrome（Playwright 用 `channel="chrome"`）、LibreOffice（`brew install --cask libreoffice`）。
- **字体**：仓耳今楷 TsangerJinKai02 W04/W05 要放在 `~/Library/Fonts`。kami 默认装到 `~/.local/share/fonts/kami/`，macOS 的 Chrome、Word 都看不到，会回退到别的宋体（常见的是只装了 Heavy 字重的思源宋体，整篇显得特粗）。用 `pdffonts` 检查 Chrome 打印出的 PDF 就能确认实际用的字体。
- **fonts.conf**：headless LibreOffice 在 macOS 上只认自带字体，中文会全部消失（PDF 里有文字，但没有字形）。`render.py` 通过 `FONTCONFIG_FILE` 指向它，并把"宋体 / SimSun"映射到 STSong。
- 收件人电脑没装今楷时，Word 会用本机宋体显示，版式不变，字形不同。

## 样式与 CSS 的对应

| 项目 | report.css | docx |
|---|---|---|
| 正文 | `--serif`，10pt，`line-height: 1.5` | 东亚字体 TsangerJinKai02、西文 Georgia；固定行高 15pt |
| 数据表 | `table.compact`：8pt，`line-height: 1.4`，`padding: 2.5pt 6pt`，`break-inside: avoid` | 固定行高 11.2pt；单元格边距 50/120 twips；除末行外"与下段同页"；标题行跨页重复 |
| 图注 | `figcaption`：9pt，stone，居中 | `Image Caption` 样式 |
| 评级标签 | `.h2-rating` 9pt stone + `b` 15pt brand，`space-between` | `RatingLead` / `RatingWord` 字符样式，无底色；17cm 右对齐制表位 |
| 双栏 | `.two-col` | 无边框两栏表格，图宽 ≤300px |
| 页面 | 羊皮纸底色 | A4、2cm 边距、页面背景色 |

## 排错

- **图表只剩图注**：图片段落用了固定行高，被裁掉了。`build_docx.py` 会把所有含图片的段落（包括表格单元格里的）设为单倍行距，`test_no_chart_is_clipped_by_a_fixed_line_box` 守着这一点。
- **中文全部空白**：LibreOffice 没加载 `fonts.conf`，请用 `render.py`，不要直接调用 `soffice`。
- **docx 比 HTML 少很多页**：多半是表格被允许跨页拆开，或单元格边距被改小了。
