# jc-basic-report

把一份 BP 变成单文件 HTML 的项目基本信息报告，并可导出 docx。本文件只记录这个 skill 的专有术语。

## Language

**Report**:
构建出的单文件 HTML，含正文、侧栏、批注功能。
_Avoid_: 页面、文档（泛指时）

**Sheet**:
屏幕上模拟的一张 A4 纸，是分页的单位，自带页眉、页码和页边距。
_Avoid_: Page（易与浏览器页面混淆）、页面

**Block**:
分页时不可再拆的最小内容单元：标题、段落、列表、表格、图、卡片。
_Avoid_: 元素、节点（泛指 DOM 时）

**Paginator**:
把 Report 的 Block 依次装进 Sheet 的构建后运行时脚本。
_Avoid_: 分页器库、paged.js（本项目不使用）

**Oversized table**:
高度超过一张 Sheet 可用高度的表格，由作者自行拆成多张表。
_Avoid_: 长表、续表（本项目不做续表）

**Page chrome**:
每张 Sheet 上的页眉和居中页码，docx 导出时带同样的页眉和页码。
_Avoid_: 页眉页脚（泛指时）

**Theme**:
一套可切换的配色，共三种：白色、黑色、米色（Kami 羊皮纸，现有风格）。
_Avoid_: 皮肤、模式

**Print palette**:
打印和导出时使用的配色，默认强制白底，与当前 Theme 无关。
_Avoid_: 打印主题

**Settings**:
集中存放默认 Theme、纸张与页边距、Page chrome、Print palette、图表色板的独立配置。
_Avoid_: 配置项散落在 CSS 或脚本里

**Annotation**:
读者在正文上做的高亮、划线或备注，存于读者本机浏览器。
_Avoid_: 评论、标注

## Relationships

- 一份 **Report** 由多张 **Sheet** 组成，每张 **Sheet** 装若干个 **Block**
- **Block** 永远整块落在某一张 **Sheet** 上，不跨页，所以 **Annotation** 不会跨 **Sheet**
- **Paginator** 只搬运原始 **Block**，不改文本流
- **Theme** 影响屏幕显示；**Print palette** 影响打印，二者独立
- **Settings** 决定默认 **Theme**、**Page chrome** 内容和各 **Theme** 的图表色板

## Flagged ambiguities

- "页" 既可指浏览器页面，也可指 A4 纸 — 已解决：A4 纸统一叫 **Sheet**。
- "超长表格" — 已解决：只有高度超过一张 **Sheet** 的才是 **Oversized table**，策略是作者自己拆。
