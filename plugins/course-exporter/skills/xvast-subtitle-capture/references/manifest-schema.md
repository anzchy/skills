# 审核清单契约

创建或修改最终 JSON 清单时读取。原始观测、OCR 草稿和毫秒时间继续保存在 `.raw/`，正文不承担证据存储功能。

## PaddleOCR 侧文件

PaddleOCR 处理链应在 `.raw/paddleocr/` 或同等原始证据目录保留：

- 按媒体时间排序的 `frame-index.jsonl` 和对应 UTF-8 图片路径清单；
- 每个并行 part 的 JSONL、`.meta.json`、进度日志和并行汇总；
- 合并后的候选事件 JSONL，至少包含 `start_ms`、`end_ms`、`text`、`review: ocr_only`、`ocr_models`、置信度和原始帧证据；
- 用于阅读的候选 Markdown，它不能代替事件清单或人工复核记录。

并行进程数、模型置信度和多帧 OCR 一致都不构成文字已核验。最多 5 个进程只用于控制本机资源；将候选写入正式 `cues` 时仍须保留实际审核等级。

## 覆盖状态

推荐结构：

```json
{
  "coverage": {
    "capture_coverage": "complete",
    "cue_text_review": "visual_reviewed",
    "word_for_word_manual_review": false,
    "evidence": "逐批连续采集并回查异常间隔；逐事件目视检查字幕候选。",
    "gaps": []
  }
}
```

- `capture_coverage`: `complete` 或 `incomplete`，只表示时间轴是否覆盖。
- `cue_text_review`: `ocr_only`、`visual_reviewed` 或 `manual_exact`。
- `word_for_word_manual_review`: 只有逐事件精确人工核对才可为 `true`。
- `gaps`: 未采集或无法读取的区段。正常无字幕不写入 gaps。

为兼容旧清单，`full_timeline_reviewed: true` 仍可读取，但新清单优先使用上述三字段。文档必须按真实级别描述，不能把 `visual_reviewed` 写成逐字人工听写。

## 页面记录

```json
{
  "id": "p01",
  "title": "页面标题",
  "image": "已裁切完整页.png",
  "image_review": "complete",
  "candidate_type": "full_slide",
  "first_seen_ms": 12000,
  "source": "原始全窗口截图.png",
  "crop_box": [47, 80, 825, 480]
}
```

`image_review` 使用两级状态：`complete` 表示原图和最终附件均确认完整无遮挡；`fallback_original` 表示未找到合格替代帧，按用户偏好保留原图，允许裁切不完整但应保留大部分核心 PPT 内容。只有核心内容也无法辨认时才使用 `image: null`。

## 批次级与页面级 viewport_review

两处都叫 `viewport_review`，但要求不同。

批次级（`.raw/<batch>/frames.json`，`validate_capture.py --batch-root ... --require-viewport-review` 检查，批次 `status: valid` 时才查）：

- `four_edges_visible: true`，或 `player_top_visible`、`player_bottom_visible`、`player_left_visible`、`player_right_visible` 四项都为 `true`（两种写法等价，采集工具默认写出这两组、初始为 `null`）；
- `controls_visible: true`；
- `scroll_state: "player_fully_in_view"`；
- `evidence`：非空，指向布局证据图或帧文件。

页面级（manifest 的每个有图 slide，`--require-viewport-review` 检查）：

- 上述四个单边字段和 `controls_visible` 必须逐项为 `true`（页面级不接受只写 `four_edges_visible`）；
- `source_slide_complete: true`；
- `window_dimensions`（2 个整数）、`player_bounds`、`video_content_bounds`（各 4 个整数）；
- `scroll_state: "player_fully_in_view"` 和非空 `evidence`。

## subtitle_bounds 的位置

每个有图页面的 `subtitle_bounds` 写在 slide 顶层（与 `crop_box` 并列）；该帧确实无字幕时写 `null`。为兼容旧清单，写在 `crop_review` 下也被 `validate_capture.py` 和 `make_crop_audit.py` 接受；两处都有时顶层优先。`crop_reviewed.py` 不读取该字段。

## 源画面完整性记录

每个有图页面必须在裁切审核前记录 `viewport_review`：

- `window_dimensions`：原始全窗口截图尺寸；
- `player_bounds`：播放器在窗口中的完整边界；
- `video_content_bounds`：实际视频内容区边界；
- `player_top_visible`、`player_bottom_visible`、`player_left_visible`、`player_right_visible`：四边是否在 source 中真实可见；
- `controls_visible`：播放器控制条是否可见，用于证明视频下缘没有被页面滚动裁掉；
- `source_slide_complete`：PPT 画布四边均可见时才为 `true`；
- `scroll_state`：例如 `player_fully_in_view`；
- `evidence`：原始全窗口 source 或带播放器边界标注的审核图。

`source_slide_complete` 必须人工判断，不能由 OCR、图片尺寸一致或裁切框数学包含关系自动推断。该值为 `false` 或缺失时，页面不得进入正式 `assets/`，应按文稿字幕时间回到 Xvast 重新定位和截图。

修补既有文稿时另记 `capture_time_ms` 和该章的字幕时间窗，并在审核证据中写明画面标题或独有正文如何与章节匹配、是否为最终展开状态。章节时间只用于搜索；不可按章首时间自动判定图片内容正确。

## 裁切审核记录

新建或重新裁切 PPT 时，每个有图的页面还需记录 crop_review，包含：

- source_dimensions：原始 source 的宽高。
- slide_bounds：在原图上逐页目视确认的真实幻灯片边界。
- subtitle_bounds：所选帧中烧录字幕文字及其底色、描边或阴影的完整外接边界；该帧确实无字幕时为 `null`，并在 evidence 中说明。推荐写在 slide 顶层（见上节），写在本记录里也兼容。
- subtitle_edge：必须为 `verified_full`，表示最终附件完整包含所选帧字幕及下缘安全余量；不得由 OCR 自动判定。
- bottom_edge：只有表格底行、横轴、流程图底部、最后一条 bullet 和页面底边都完整时才写 verified_full。
- content_edges：四边正文均完整时才写 verified_full。
- evidence：原图裁切缓冲区联系表与最终附件原尺寸检查的证据路径或记录。

## 回退图片记录

回退页必须保留 `source`、`crop_box` 和原始图片，并记录：

- `image_review: fallback_original`；
- `fallback_reason`：为什么没有使用完整无遮挡页；
- `known_crop_gaps`：已知被裁掉或遮挡的边缘、表格行、坐标轴、文字等；
- `fallback_preserves_core_content: true`：人工确认大部分核心内容仍可辨认。

回退页不得填写 `bottom_edge: verified_full` 或 `content_edges: verified_full`。文档开头分别报告完整无遮挡页数与原图回退页数。

所有有图页面的 crop_box 都必须完整包含 subtitle_bounds，且不得超出 source_dimensions。对于 `complete`，crop_box 还必须完整包含 slide_bounds。字幕或播放控件遮住真实页底时，不得通过上移 crop_box 或裁掉字幕获得 `verified_full`；应先换用字幕完整且遮挡更少的同页帧，仍无合格帧时改记为 `fallback_original`。只有完整字幕的回退图也无法保留大部分核心内容时，才将 image 设为 null。

使用 `scripts/crop_reviewed.py --manifest <manifest> --output-dir <empty-assets-dir>` 将审核过的 source 裁切到空暂存目录。该脚本拒绝缺少 source 完整性确认、字幕下缘审核、真实尺寸不符或坐标越界的页面。完成后用 `validate_capture.py --require-source-assets` 检查最终图片像素是否与对应 source 的裁切一致；两者都不能替代内容匹配的目视审核。

## 字幕事件

```json
{
  "id": "c00001",
  "start_ms": 12000,
  "end_ms": 14500,
  "slide_id": "p01",
  "text": "字幕原文",
  "review": "verified",
  "evidence": "原始观测图片",
  "correction": {
    "before": "OCR 原文字",
    "after": "目视确认文字",
    "evidence": "原始观测图片"
  }
}
```

- `verified` 表示该事件文字已对照可读画面目视确认；OCR 一致、置信度高或批量联系表生成成功都不自动构成 verified。
- `uncertain` 表示仍有看不清或无法确定的字词；文档需显示待核验。
- 同一事件的多张观察图放进 evidence 或辅助索引，不拆成多个事件。
- 任何文字修正按事件记录 `before`、`after`、`evidence`。禁止对整个字幕清单做无事件范围的全局替换。
- 拆分跨页事件时保存 `parent_event_id`，子事件文字不得重叠或遗漏。
- 可选 `visit_id` 区分同页回访，`break_before: true` 强制新时间块。

## 完整示例

```json
{
  "title": "课程标题",
  "duration_ms": 120000,
  "coverage": {
    "capture_coverage": "complete",
    "cue_text_review": "visual_reviewed",
    "word_for_word_manual_review": false,
    "evidence": "连续采集全片并补采异常区段。",
    "gaps": []
  },
  "slides": [
    {"id": "p01", "title": "第一节", "image": "已裁切完整页.png", "image_review": "complete", "candidate_type": "full_slide"}
  ],
  "cues": [
    {"id": "c00001", "start_ms": 0, "end_ms": 2500, "slide_id": "p01", "text": "字幕原文", "review": "verified", "evidence": "原始观测 c00001"},
    {"id": "c00002", "start_ms": 2500, "end_ms": 5000, "slide_id": null, "text": "暂未明确归页的字幕", "review": "verified", "evidence": "原始观测 c00002"}
  ]
}
```
