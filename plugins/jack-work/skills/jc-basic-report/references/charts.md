# 图表规格（摘自 Kami diagrams.md §9，MIT）

图表一律由数据生成，不手画柱子、点或扇区。每张图写一个 `charts/<名称>.json`，正文放 `<!--CHART:名称-->`，`build.py` 会调用 `scripts/chart.py` 生成内联 SVG。要改数字就改 JSON 再构建。

图表颜色不写在 JSON 里：生成的 SVG 每个颜色都是 `var(--chart-<名称>, <Kami 色>)`，切换 Theme 即换色；要改某个主题的色板，在报告旁的 `settings.json` 里覆盖 `themes.<white|black|beige>.chart.<键>`（如 `{"themes": {"black": {"chart": {"brand": "#8fb4e8"}}}}`）。构建后可用 `python3 scripts/chart.py --check-charts report.html` 核对每张图仍与其规格一致。

```json
{"type": "bar", "categories": ["2023", "2024", "2025"],
 "series": [{"name": "营收", "values": [0.53, 7.43, 16.44]},
            {"name": "归母净利润", "values": [-8.71, -14.09, -7.89]}],
 "unit": "亿元", "decimals": 2, "source": "公司年报", "lang": "cn"}
```

| type | 数据字段 | 上限 |
|---|---|---|
| `bar` | `categories`, `series[].name`, `series[].values` | 8 个类别、3 个系列 |
| `line` | 同 bar；`"zero": false` 允许纵轴不从 0 开始 | 12 个点、3 条线 |
| `hbar` | `items[].label`, `items[].value`；`focus` 为墨蓝高亮的行号（默认 0，`null` 为不高亮） | 12 行 |
| `donut` | `items[].label`, `items[].value`（原始值，占比自动计算）；`center_label` | 6 段 |
| `waterfall` | `items[].label`, `items[].value`；`"total": true` 标记期初或期末合计 | 8 根 |
| `candlestick` | `points[].label`, `open`, `high`, `low`, `close` | 30 个点 |

所有类型可选：
- `size`：`full`，或 `compact`（两图并排时必须用 compact，否则字太小）；
- `unit`：坐标轴单位；
- `prefix` / `suffix`：数值标签前后缀，如 `"%"`；
- `decimals`：小数位数；
- `source`：图下脚注，写明口径；
- `lang`：`cn`；
- `title`：仅用于无障碍读屏，图上不显示。

选图规则：
- 合计约 100% 的占比，6 项以内用 donut，7 项及以上用 hbar（如股权结构）。
- 绝对值随时间变化用 bar，不用 line。
- 图注（figcaption）写结论，不写数据范围。例如写“2025 年营收翻倍但仍亏损”，而不是“2023–2025 年营收”。
- 从 BP 图上读出的数，在 `source` 里写明“读图约值”。

生成器会拒绝无法如实绘制的数据（超出上限、瀑布图合计不符等）。遇到报错应修正数据或补问，不要放宽规格。
