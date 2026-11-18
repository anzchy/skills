---
name: expense-reimbursement
description: >-
  投资机构的费用报销助手，覆盖三类：①市内交通 ②出差 ③招待客人。从票据
  （网约车行程报销单/电子发票、高铁机票、住宿发票、餐饮发票、支付截图）自动抽取
  可推导字段，按公司标准计算餐补/税抵扣/大写金额，填入官方空白模板产出报销单。
  触发词：报销、市内交通报销、出差报销、招待/接待报销、发给财务前检查、填报销单、
  交通费清单、出差费用报销单、业务招待备案表。处理前先做附件预检，附件不足不开工。
version: 0.1.0
---

# 费用报销 Skill（expense-reimbursement）

帮公司员工完成三类报销的票据整理与表单填写，并按公司规则
（《报销检查清单》）做校验。**所有金额/标准均有出处，禁止编造。**

## 0. 总流程（先预检 → 先自动后补全 → 写出 → 验收）

```
用户给出报销材料目录
   │
   ▼  ① 附件预检（preflight.py）—— 不足则停，列出缺什么
   ▼  ② 抽取：行程报销单走脚本；机票/酒店/餐饮发票由你(Claude)读；两路金额交叉核对
   ▼  ③ 计算：合计 / 大写(rmb_capitalize) / 餐补(meal_subsidy) / 税抵扣(tax_deduction)
   ▼  ④ 补全：生成「待补全清单」，向用户索取 B 类（事由/预算/报告要点/审批金额）
   ▼  ⑤ 写出：fill_forms.py 填官方空白模板（保留公式/打印区），用 resolve_out_path() 直接输出到材料所在目录，不建「输出/」子文件夹
   ▼  ⑥ 自查：对照 checklists/发给财务前检查清单.md 过一遍
```

## 1. 附件预检（必须先做，闸门）

不同报销类型所需附件不同。**处理前先运行预检，缺关键附件就停下来要材料，不要硬填。**

```bash
python3 scripts/preflight.py <transport|travel|entertainment|auto> <材料目录>
# 退出码 0=齐全可处理；2=缺关键附件（按提示补齐再来）
```

各类必需附件（详见 `references/` 与 `checklists/`）：

| 类别 | 必需附件 | 条件附件 |
|---|---|---|
| ① 市内交通 transport | 网约车**行程报销单**PDF + 对应**电子发票**PDF（按平台配对） | 行程单.docx（如有） |
| ② 出差 travel | **城市间交通票**（高铁/机票行程单）+ **出差报告**(本人签字) + **出差申请单**(经批准) | 含住宿→**住宿发票**；含市内接驳→行程报销单+电子发票 |
| ③ 招待 entertainment | **餐饮发票**PDF + **支付截图/付款记录** + **业务招待备案表**(经批准) | — |

预检通过后，再进入对应 SOP。

## 2. 三类 SOP

### ① 市内交通 SOP
1. `preflight.py transport <dir>` 预检。
2. 对每个 `*行程报销单.pdf` 运行 `parse_trip_report.py` → 得到行程（日期/起止/金额/平台）。
   - 交叉核对：`parsed_total` 与行程单自报「合计」一致才放行；不一致说明有行程被排除/漏读，**向用户确认要计入哪些行程**。
3. 与用户确认：每条行程的**事由**（票据没有，必填）、**行程地点的规范写法**（清理「张江|」「-西北门」等）、以及**哪些行程计入报销**。
4. 发票张数：**同一发票多次行程只记 1 张**；按平台分组，每组首行记 1，合计=平台数（电子发票张数）。
5. 税抵扣（如需填报销测算）：`tax_deduction.py` 仅滴滴快车计入抵扣；曹操/T3/出租车不计。
6. 写出：`fill_transport_list()` 填交通费报销清单 → `fill_reimbursement()` 填费用报销单（C4 报销内容、F4 金额合计、C7 大写）。
7. 打印：费用报销单 **A5 纸张、横向**。

### ② 出差 SOP
1. `preflight.py travel <dir>` 预检。
2. **事前**（出差申请单，须早于报销日 ≥2 天、经领导批）：用户提供出差时间/地点/人员/事由/交通工具/住宿/**预算**（交通费/住宿费/餐贴/会议费/其他）。`fill_travel_application()`。
   - 餐贴预算与报销均用 `meal_subsidy.py` 算：北上广深 300、省会/直辖市/计划单列市 200、其他城市 150（元/人/天），半天按全天。
3. **票据抽取**：
   - 城市间交通费：你读高铁/机票 PDF 取**票价**（如 ¥662.00），按人数计（如 `=662*2`）。
   - 住宿费：你读住宿发票取**价税合计**（如 737.44），核对起止时间/单价。
   - 市内接驳：`parse_trip_report.py` 解析曹操/滴滴，或你读电子发票取合计。
   - 两路金额交叉核对，不一致报警。
4. **餐食补贴**：`meal_subsidy(city, days, people)`（北京样例 = 300×2人×1天 = 600）。天数由用户确认（半天按全天）。
5. **出差报告**：正文（目的/讨论/结果）由用户提供；模板 `templates/07.2出差报告模板.docx`；提醒**本人签字**。
6. 写出：`fill_travel_reimbursement()`（按日期分行：城市间交通费/住宿费/餐食补贴/会议费/其他；C12 大写）。
7. 附：经批准的出差申请单、出差报告、各票据。出差参会另附 `08.2参会申请单`。

### ③ 招待 SOP
1. `preflight.py entertainment <dir>` 预检。**招待项目方应尽量避免；如招待须提前向王博申请。**
2. **事前**（业务招待备案表）：用户提供客人单位/人数、接待事由、**申请金额**、**申请标准**（样例 250 元/人，按当次审批填，不写死）、参与接待人数、具体方式。`fill_entertainment_record()`。
3. **票据抽取**：你读每张餐饮发票取**价税合计（小写）**（如川菜 317、咖啡 125）；金额合计 = 各发票之和（报销单 F4 可写 `=125+317`）。
4. 留存支付截图/付款记录。
5. 写出：`fill_reimbursement()`（C4 报销内容=接待事由描述、F4 金额合计、C7 大写）。

## 3. 计算 helper（确定性，禁止手算）

| 脚本 | 用途 |
|---|---|
| `scripts/rmb_capitalize.py` | 金额→中文大写（零/角/分/整边界），所有「大写」必须用它 |
| `scripts/meal_subsidy.py` | 餐补 = 职级×城市×人数×天数（半天按全天） |
| `scripts/tax_deduction.py` | 税抵扣判定：仅滴滴快车可抵扣 |
| `scripts/parse_trip_report.py` | 解析滴滴/曹操行程报销单 + 金额交叉核对 |
| `scripts/fill_forms.py` | 填官方空白模板（保留公式/打印区） |
| `scripts/preflight.py` | 附件预检闸门 |
| `scripts/verify.py` | 与黄金样例比对验收 |
| `scripts/aggregate_travel_rows.py` | 出差票据按(路线+方向,日期)分组汇总，供 `fill_travel_reimbursement()` 使用 |
| `scripts/fill_forms.py: resolve_out_path()` | 报销单输出路径 = 材料所在目录 + 文件名，**不建「输出/」子文件夹** |
| `scripts/insert_payment_screenshot.py` | 把支付截图贴进「支付截图.docx」：页面设为 A5 纵向，按原始长宽比缩放居中插入，替换旧内容 |

跑全部单测：`python3 tests/test_rmb_capitalize.py && python3 tests/test_helpers.py && python3 tests/test_aggregate_travel_rows.py && python3 tests/test_fill_travel_reimbursement.py && python3 tests/test_resolve_out_path.py && python3 tests/test_insert_payment_screenshot.py`（除第一、二个外均需要 openpyxl/python-docx/Pillow，用 装有这些依赖的 Python 3.11+ 跑，例如 `uv run --with openpyxl --with python-docx --with Pillow python …`）

## 4. 字段可推导性（决定能否「一模一样」）

- **A 类（票据可自动推导，必须 100% 准确）**：日期、金额、合计、大写、发票张数、城市间交通费/住宿费合计、餐补（给定城市×天数×人数）。
- **B 类（票据中没有，必须问用户）**：所有**事由/业务事由/接待事由**、出差**申请单预算**、出差**报告正文**、招待**申请金额/标准**、行程地点的**规范写法**、**哪些行程计入**、出差**天数**。

> 一定要先用 A 类自动填，再生成「待补全清单」逐项问用户补 B 类。不要替用户编造事由或金额。

## 5. 规则出处
- 通用附注/打印/发票：`references/rules-common.md`
- 交通税抵扣：`references/rules-transport.md`
- 出差标准（职级×城市表、餐补、时序）：`references/rules-travel.md`
- 招待审批/备案：`references/rules-entertainment.md`

所有数值的唯一出处是《报销检查清单-发给财务之前过一遍.md》，references 已据此整理并标注。

## 6. 模板清单（对照 SOP 附件，`公司报销操作SOP_V202607.docx`）

每格已逐字段核对与 SOP 一致。标 ⚠️ 的仅有模板文件、`fill_forms.py` 尚无对应
`fill_*()` 自动填写函数（③②①三类现有 SOP 未覆盖到会务/培训/超支/付款审批场景，
遇到时手工填写这些模板或先扩展对应 SOP 小节，不要跳过预检硬填）。

| SOP 附件 | 模板文件 | 自动填写 |
|---|---|---|
| 附件1-1 组织会议申请单 | `08.1组织会议申请单模板.xlsx` | ⚠️ 无 |
| 附件1-2 参会申请单 | `08.2参会申请单模板.xlsx` | ⚠️ 无（出差 SOP 提示需附，未提供 fill 函数） |
| 附件2 出差申请单 | `07.1出差申请单模板.xlsx` | `fill_travel_application()` |
| 附件3 业务招待备案表 | `05业务招待备案表模板.xlsx` | `fill_entertainment_record()` |
| 附件4 员工培训申请单 | `06员工培训申请单模板.xlsx` | ⚠️ 无 |
| 附件5 费用超支申请表 | `02费用超支申请表模板.xlsx` | ⚠️ 无（实际支出超申请金额时应使用，见规则出处 P: 差旅/招待费超标须填） |
| 附件6 费用报销单 | `01费用报销单模板.xlsx` | `fill_reimbursement()`（当前仅填 C4/F4 一行，模板本身支持 3 行报销内容） |
| 附件7 出差费用报销单 | `03出差费用报销单模板.xlsx` | `fill_travel_reimbursement()` |
| 附件8 付款审批单 | `09付款审批单模板.xlsx` | ⚠️ 无 |
| 附件9 国内差旅费开支标准 | 无模板（标准表，见 `references/rules-travel.md`） | — |
| 附件10 业务招待费开支标准 | 无模板（标准表，见 `references/rules-entertainment.md`） | — |
| 附件11 费用支出报销需准备的单据 | 无模板（清单，见 `checklists/发给财务前检查清单.md`） | — |
| 附件12 市内交通费清单 | `04市内交通费清单模板.xlsx`（官方版，10 列） | ⚠️ 未使用——`fill_transport_list()` 按既定约定改用非官方的`市内交通费报销清单模板.xlsx`（7 列，见 `fill_forms.py:31` 注释），04 仅作官方版本参考 |
| 附件13 出差报告 | `07.2出差报告模板.docx` | 由你(Claude)按用户提供的正文手写，`insert_payment_screenshot.py` 不适用于此文件 |

`08.1`/`06`/`02`/`09` 四个模板为本次新建（原 skill 缺失），字段/签字栏逐格对
照 SOP 附件1-1/4/5/8 建成，尚无对应 `fill_*()` 函数与 preflight 类别——遇到
会务/培训/超支/付款审批相关报销时先如实告知用户当前仅能提供空白模板。
