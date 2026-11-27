---
status: accepted
---
# 用自写的块级分页器，不引入 paged.js

Report 在屏幕上要严格模拟 A4 分页。我们选自写的块级 Paginator：把原始 Block 整块搬进 Sheet，不拆分文本节点，不克隆 DOM，不引入 paged.js。

原因：Annotation 由 recogito 4.3.7 按保存的字符偏移还原，paged.js 会拆分文本节点、插入连字符并重复表头，偏移一变，高亮就会静默落到别的段落上。Paginator 只搬运完整节点，文本流不变，这个不变量可测。

## Considered Options

- **paged.js**：`target-counter()` 填不进外部侧栏目录，要自己读页面盒子；默认包裹整个 `<body>`；表格拆分有上游 issue。被否决。
- **只做纸张外观**：做不到严格 A4，页码不准。被否决。

## Consequences

- 段落、列表整块不拆，页底可能留白；超长表格（Oversized table）由作者自己拆，Paginator 对它报错或告警。
- 只支持报告模板里的 Block 类型，不做通用排版。
- docx 的页码由 Word 自己算，不追求与 HTML 逐页一致。
