---
name: xvast-subtitle-capture
version: 0.0.1
description: 在 Claude Code 中抓取 Xvast 已授权视频的全片烧录字幕和 PPT 页面，整理为每页 PPT 配原文字幕的 Markdown（图片平铺 assets/）。采集用附带的 Swift 工具 xvast-capture（macOS 辅助功能读取/控制播放器 + screencapture -l 截取 Xvast 窗口原始帧）。适用于“Xvast 字幕 capture”“Xvast 截图字幕”“PPT 配完整字幕”“课程图文逐字稿”；不用于仅截一张图、字幕总结或绕过 DRM。
---

# Xvast PPT 与完整字幕图文稿（Claude Code 版）

交付一个 Markdown 和同目录的平铺 `assets/`。每个逻辑 PPT 页只放一张视频中的实际页面截图，下接该页相关的字幕原文；所有截图以下方完整保留所选帧的烧录字幕为裁切基线，再优先保留完整 PPT。没有合格帧时回退到仍保留大部分核心内容的原图。代码、网页、独立图表和软件演示不截图，但这些时段的讲解字幕仍须保留。用户只要求创建或修改本 skill 时，不自动播放或采集视频。

本 skill 是 `.agent/skills/xvast-subtitle-capture`（Codex 版）的移植：内容合同、审核规则和 Python 处理链相同，只把 Codex CUA 截图链路换成本地 Swift 工具。`.raw/*/frames.json` 结构兼容，两版采集的批次可以互相使用。

## 采集链路

```text
Xvast 窗口（chrome://playlist）
→ scripts/xvast-capture（Swift）
    ├─ 辅助功能 AX：视频名、进度、剩余时长、倍速、Play/Pause、10 秒步进 seek
    └─ /usr/sbin/screencapture -x -o -l <窗口ID>：只截 Xvast 窗口，不含阴影
→ 项目 .raw/<batch>/frame-NNNNNN.jpg + frames.json
→ 人工审核后裁切到暂存 assets/
```

已实测（Xvast 109.0.5393.0，macOS 27）：窗口截图包含真实视频画面，DRM 未把画面置黑；单帧约 90–110 ms，500 ms 间隔的实测帧距中位数为 502 ms、最大 505 ms；进度条位置与墙钟一致。

### 前置条件

- 调用 Claude Code 的终端须在“系统设置 → 隐私与安全性”中同时获得**辅助功能**和**屏幕录制**权限。`status` 报 `Accessibility permission missing`，或截图全黑/只有桌面时，停止并请用户授权。
- Xvast 已打开 `chrome://playlist`，目标视频已选中；窗口不能最小化，也不能放在其他桌面空间里（`screencapture -l` 只能截当前屏幕上的窗口，被其他窗口遮挡没关系）。
- 首次运行 `scripts/xvast-capture` 时会用 `swiftc -O` 编译到 `~/Library/Caches/xvast-capture/`，源码改动后自动重编。

### xvast-capture 命令

下文的 `X` 指 `.claude/skills/xvast-subtitle-capture/scripts/xvast-capture`（从项目根目录运行）。每个命令都向 stdout 输出一个 JSON 对象；出错时写 stderr 并以退出码 1 结束。

| 命令 | 用途 |
|---|---|
| `X status` | 视频名、`position_ms`、`duration_ms`、`playback_rate`、`playing`、`window_id`、窗口边界 |
| `X play` / `X pause` | 按播放器的 Play / Pause 按钮（已是目标状态时不动作） |
| `X seek --to H:MM:SS` / `X seek --by -10` | 以 AX 的 10 秒步长逐步移动，精度 ±5 秒；默认最多 30 步（5 分钟），超过时报错 |
| `X park-cursor` | 把指针移到标签栏空白处（浏览器顶栏安全区），让播放器控制层自动隐藏 |
| `X screenshot --out /abs/.raw/layout-001/window.png` | 单张原始全窗口布局证据图；拒绝覆盖已有文件 |
| `X capture --video-id <播放列表中的完整文件名> --output-root /abs/<项目>/.raw --batch-dir <名> [--layout-profile layout-001] [--frame-count 20] [--interval-ms 500] [--shortest-subtitle-ms N] [--format jpg\|png] [--resume-if-paused] [--pause-after-capture]` | 短批次连续采集 |

`capture` 的约束与行为：

- `--output-root` 必须是绝对路径，且末级目录名为 `.raw`；`--batch-dir` 只能用 `[A-Za-z0-9_-]`；目标批次目录非空时拒绝运行。每批 1–120 帧，间隔不少于 150 ms。
- 开始前核对播放器正在播放、播放列表中显示 `--video-id`，并锁定窗口 ID。
- 每帧先写隐藏的临时文件，校验 JPEG/PNG 魔数、尺寸和扩展名后再改名。`screencapture` 偶发退出码 15，会自动重试最多 4 次，次数记在 `capture_attempts`。
- 每帧截图后立即读取 AX 进度，记为 `ax_position_ms`（整秒精度）。最终时间轴仍以批次起止锚加墙钟推算（`build_paddleocr_frame_index.py`）；`ax_position_ms` 只用于抽查。
- 结束后写 `frames.json`，状态为 `pending_manual_review`。出现以下任一情况则写 `invalid`，并在 `invalid_reasons` 中列明：进度与墙钟不一致（偏差超过 `max(3000 ms, 5%)`）、最大帧距不小于 `--shortest-subtitle-ms`、批次中途停止播放、截图失败。截图失败时仍写出清单，然后以退出码 1 结束。
- `viewport_review` 的各项边界初始为 `null`，工具**不会**自动证明画面完整，必须人工审核后填写。

### 已知限制

- **seek 只能以 10 秒为步长逐步移动**：Xvast 忽略直接写入的进度值，只有逐步加减有效。一次曾在连发 3 个步进后 Xvast 退出，原因未查明，因此工具每步之间等待 250 ms 并复读进度，默认最多 30 步。远距离跳转请用户手动拖动进度条，再用 `seek` 微调。`seek` 报 `lost the progress bar` 时，先运行 `X status` 确认 Xvast 是否仍在运行。
- 进度只有整秒精度。批次间的“可见重叠”至少按 1 秒计算。
- 按下 Play 会唤起控制层，遮住字幕（已实测：首帧字幕被控制条盖住）。因此探针批和主批都必须采用 [references/capture-protocol.md](references/capture-protocol.md) 中的“回退预热”。
- 指针停在画面上会被截进帧里。截图前一律运行 `X park-cursor`；禁止把鼠标移入或点击播放器下方的空白页面区域（可滚动，会把播放器滚出视口）。
- **临时文件名不得以点开头**：`screencapture` 在部分系统上写不了隐藏文件名（报 `cannot write file to intended destination`），工具已改用 `_<帧名>.part.<ext>`。自行改动时不要改回点开头。
- **失败批次自动让出目录**：第 1 帧起就截图失败、没有任何帧的批次，会把含 `frames.json` 的目录移到 `.raw/_failed/<批次名>-<时间戳>/`，同名批次可直接重采；已有部分帧的无效批次仍留在原处。
- `chrome://playlist` 不能假定支持 DevTools、DOM、CDP、Canvas 或可读字幕轨；本工具只用原生 AX 和窗口截图。

### 目视审核

Claude 用 Read 工具直接查看 `.raw/` 原始帧（2154×1898 级别的 Retina 图），完成布局、PPT 四边、字幕遮挡和裁切边界的人工审核。审核结论写进清单，不得仅凭工具输出的结构字段判定 `valid`。

### 标准采集节奏

```bash
X status                                             # 核对视频、时长、倍速、窗口
X pause && X screenshot --out "$RAW/layout-001/window.png"   # 布局证据图 → Read 审核四边
X seek --to 0:00:00 && X play && X park-cursor       # 从 00:00 开始；等 2–3 秒控制层隐藏
X capture --video-id "$VIDEO" --output-root "$RAW" --batch-dir preflight-001 \
  --frame-count 11 --interval-ms 500 --pause-after-capture   # 5 秒 pre-flight
# Read 审核 pre-flight 帧 → 确认合格后在 frames.json 填写 viewport_review，并把 status 改为 valid
# 每个正式批次：回退预热（seek --by -10 → play → park-cursor → 等控制层隐藏）
#   → 3 帧探针（--frame-count 3 --pause-after-capture）→ 审核
#   → 再回退预热 → 主批（≤120 帧）→ 审核首/中/末帧
```

pre-flight 的控制层问题：00:00 之前没有可回退的已覆盖区间，因此从 00:00 按 Play 后，先运行 `park-cursor`，等控制层隐藏再开始 `capture`。此时批次起点会晚于 00:00 约 2–3 秒，须在清单中如实记录；首批开头这段缺口，在 pre-flight 通过后从 00:00 重新预热补采（预热区间可以与 pre-flight 首帧之前的部分重叠），或者在文档中如实披露。

## Python 环境

凡是需要 Python 的步骤，统一用调用项目当前目录的 `.venv/` 运行，不得向系统 Python 安装依赖，也不得猜测或默认复用其他项目的环境。`.venv/bin/python` 不存在时执行 `python3 -m venv .venv`，再用 `.venv/bin/python -m pip ...` 安装缺失包。若用户或项目明确指出某个已装好相同依赖、且 Python ABI 兼容的本地 Conda 环境，可先逐项核对 Python、PaddleOCR、PaddleX、ONNX Runtime、OpenCV 和 Pillow 的版本，再用该环境的解释器执行 `python -m venv --system-site-packages .venv`。不得把不同 ABI 的原生包复制或软链进 `.venv`。依赖已满足时，不为追求“最新”而重复升级。核心裁切与清单脚本至少需要 Pillow，用 `.venv/bin/python -c 'from PIL import Image; print(Image.__version__)'` 验证。只有项目明确要求直接运行 Conda 环境时，才传 `--conda-env <name>`。

## 默认 OCR 候选生成

使用本地 PaddleOCR/ONNX 生成中文字幕候选。运行前阅读 [references/paddleocr.md](references/paddleocr.md)。处理链：建立媒体时间索引 → 3 帧 OCR smoke → `mobile` 模型最多 5 路并行 → `server` 复核低置信度帧 → 合并候选时间线。

- 模型缓存放在当前目录 `.paddleocr-cache/`。第一次联网安装依赖并下载 `mobile`、`server` 两套模型，之后离线推理，不调用 `paddleocr api` 云服务。
- 正式批量前，先加 `--max-images 3 --keep-crops` 检查裁切带和 `subtitle_texts`。全片并行封装默认使用 `--dedupe-threshold 0.01`；更换布局、字号或采样方式时，须用短样本重新确认，必要时设为 0。
- 全片批量用 [scripts/paddleocr-parallel](scripts/paddleocr-parallel)，`--workers` 硬上限为 5，不得用多个命令绕开这个上限。
- JSONL 中，`texts` 是裁切区域的全部候选，`subtitle_texts` 是排除水印和播放器控件后的候选，两者都不能直接标为人工核验。
- [scripts/vision_ocr.m](scripts/vision_ocr.m) 是 macOS Vision 轻量回退：`clang -fobjc-arc -framework AppKit -framework Vision -framework ImageIO scripts/vision_ocr.m -o <临时目录>/vision_ocr`，再运行 `<临时目录>/vision_ocr <逐行原图绝对路径清单> <新的输出.jsonl>`。输入必须是 `.raw/` 原始帧；输出路径已存在时会被拒绝。

所有 OCR 结果始终标记为 `ocr_only`。OCR 可能产生合并、拆分或同形字误识别，不得据此确认字幕原文、画面归页或 `verified` 状态；只有逐事件对照原始帧人工核验后，才可升级审核级别。

## 内容合同

- 字幕不总结、不改写、不删除口头语。只允许调整连接标点、段末标点和分段；保留视频字幕自身的错字。看不清的字不得用语音、PPT 正文或领域知识猜补，须标为待核验。
- 每次实际字幕事件恰好出现一次。同一条字幕持续显示时的重复观测要合并；讲者后来再次说出的相同文字要保留。不可按全文字符串去重。
- OCR 只是候选生成工具。多轮 OCR 一致不等于人工核验；字幕修正必须按事件记录原文、修正文字和原始画面引用，禁止不限定事件范围的全文替换。
- 同一逻辑 PPT 分步展开时，只留最终完整状态；离开后再返回补充，仍算同一页。网页或软件画面即使与课件相似，也不能当成 PPT。
- 截图去掉浏览器顶栏、playlist 和无关按钮，保留内容区原有水印和所选帧的完整烧录字幕。下方裁切基线是“完整字幕”：字幕文字、底色、描边或阴影均不得被下边界截断。播放器控件可在不损伤字幕时去除，不得为去控件而裁掉字幕。每页必须从该页的原始全窗口图分别确认 `slide_bounds`、`subtitle_bounds` 和 `crop_box`，不能沿用上一页或全局固定的坐标。穷尽同页候选后仍无完整 PPT 时，允许回退使用原图，但须完整保留字幕、大部分 PPT 核心内容可辨认，并明确标注为“原图回退”。
- “时间轴覆盖完整”“字幕文字已目视核对”“逐字人工核对”是三个不同结论，必须分别陈述。不得用结构校验通过代替内容准确性证明。

## 工作流

1. 核对目标视频、时长、输出目录和已有材料；用 `X status` 确认 Xvast 中实际选中的视频。若有已验证覆盖本视频的字幕轨或用户提供的字幕文件，优先使用并抽查。修补既有图文稿时，先运行 [scripts/prepare_retake.py](scripts/prepare_retake.py)，从章节标题和字幕时间块中提取候选时间窗。
2. 按 [references/capture-protocol.md](references/capture-protocol.md) 和上文“标准采集节奏”完成布局证据图、5 秒 pre-flight、每批的 3 帧探针和回退预热，再进行正式连续采集。若只能看到部分视频或 PPT，请用户把 Xvast 页面滚到播放器顶部（或在获准后操作），然后新建 `layout_profile`，重做检查；滚到顶部后仍看不到完整 PPT 四边时，停止正式采集。
3. 运行 [scripts/build_paddleocr_frame_index.py](scripts/build_paddleocr_frame_index.py)，只纳入有效批次并按媒体时间排序。抽查首尾和批次边界，可对照 `ax_position_ms`。
4. 对索引前 3 张执行 PaddleOCR smoke 并查看保留的裁切图，通过后用 `paddleocr-parallel` 处理全片；用 [scripts/select_paddleocr_review.py](scripts/select_paddleocr_review.py) 筛出疑难帧交给 `server` 复核，再用 [scripts/merge_paddleocr_timeline.py](scripts/merge_paddleocr_timeline.py) 生成 `ocr_only` 候选事件。
5. PPT 与字幕分开处理：PPT 采集、补漏或重新裁切时阅读 [references/ppt-review.md](references/ppt-review.md)。用 [scripts/detect_slide_changes.py](scripts/detect_slide_changes.py) 对 `frame-index.jsonl` 做帧间差分（`--region` 取画布内部、避开字幕条）：`changes[].kind` 为 `slide` 是整页切换、`content` 是逐条展开；`flicker` 是两页之间来回闪烁的区段，不要当成换页，也不要因此漏掉其中出现的章节页。
6. 逐事件对照原始帧审核 OCR 候选，建立逻辑页映射后再归属字幕。无法确认归属的放入“未归属字幕（待确认）”。
   - mobile 的置信度常常很高却有形近字错误（「找们」「同字」「回撒」），置信度筛选不会触发 server 复核。先用 [scripts/recheck_events_with_server.py](scripts/recheck_events_with_server.py) 对每个合并事件的代表帧再跑一遍 server，`--output-report` 列出 mobile 与 server 不一致的事件。
   - 再用 [scripts/make_cue_review_sheets.py](scripts/make_cue_review_sheets.py) 把 `--candidates`（上一步的 jsonl）做成带编号的字幕条拼图和 `candidates.txt`，逐条对照原帧；把看到的正确文字按 `{事件 id: 文字}` 写进 `corrections.json`，加 `--corrections ... --output-events ...` 生成带事件级 `correction` 的事件。只有通过 `--mark-verified` 才写 `verified`，默认保持 `ocr_only`。
7. 创建或修改清单时阅读 [references/manifest-schema.md](references/manifest-schema.md)，不得把未经逐事件目视确认的 OCR 候选批量标为 `verified`。
8. 逐页写入前先用 [scripts/measure_bounds.py](scripts/measure_bounds.py) 对所选原始帧测量 `video`、`slide`、`text`、`subtitle` 四组边界（输出是目视审核的证据，不是结论；字幕范围须把输出画到图上确认）。逐页写入 `viewport_review`、`crop_review` 和具体 source 路径；确认 `subtitle_edge: verified_full`。完整无遮挡写 `image_review: complete`，局部遮挡写 `fallback_original` 和具体缺口。
9. 在新的暂存目录运行 [scripts/crop_reviewed.py](scripts/crop_reviewed.py) 生成附件；用 [scripts/build_markdown.py](scripts/build_markdown.py) 生成文稿；用 [scripts/make_crop_audit.py](scripts/make_crop_audit.py) 生成裁切审核联系表，逐页查看。
10. 运行 `.venv/bin/python .claude/skills/xvast-subtitle-capture/scripts/validate_capture.py --require-viewport-review --require-crop-review --require-source-assets --manifest ... --document ... --assets ... [--batch-root .raw [--batch-list batches.txt]]`；`--batch-list` 是每行一个批次目录名的文本文件，只验证本次纳入时间轴的批次（旧的 pending/无关批次不会拦住验证）。通过后先备份旧正式文件，再提升暂存文稿和附件，并重新核对正式路径下的链接。

### 长视频推荐流程：一次连续播放 + 10 分钟分段 + 合并（已实测）

长视频（约 1 小时以上）默认这样做，「凌烟阁2-5-参数遍历」（84 分钟）按此完成：

1. **一次连续播放采集**。`seek` 回退在部分视频上不可用（`AXDecrement did not move the progress bar`，暂停、播放状态都失败），逐批回退预热会反复卡住或让 Xvast 崩溃。因此在布局证据图、5 秒 pre-flight、3 帧探针通过后，用 `capture_series.py --continuous --measure-after --frame-count 120 --interval-ms 500 --warmup-seconds 3 --target-ms <时长>` 从当前位置一次播完全片：只预热一次，批次首尾相接、不 seek、不暂停。凌烟阁2-5 共 83 批（每批 120 帧 ≈ 60 秒）覆盖 0:10–1:24:00，批内最大帧距 547 ms，批间墙钟间隔不超过 690 ms（无重叠，须在覆盖说明中披露）。风火轮3（75 分钟，未加 `--measure-after`）却有 22 处接缝超过 1.5 秒（最长 2.13 秒）；疑因每批之间同步跑 3 次 `measure_bounds` 拉长了间隔（未证实），因此连续模式一律加 `--measure-after`，并看每行的 `seam_ms`。命令放后台跑，输出重定向到 `.raw/series-NNN.jsonl`；跑完再逐批看首、中、末帧（做成拼图看），确认后用 `mark_batches_valid.py` 写 `viewport_review` 并标 `valid`。播到片尾时最后一批会因「批次中途停止播放」被判 `invalid`：要么用 `mark_batches_valid.py --exclude-frames` 去掉停播后的帧，要么回退预热后补采 `tail-001`（风火轮3 做法），并在覆盖说明里写明片尾未采到的秒数。
2. **按 10 分钟切段处理**（段名如 `s000`、`s010`…，每段 `[k×600000, (k+1)×600000)` ms）：`prepare_segment.py`（索引→OCR→合并→过滤→server 复核→字幕条拼图）→ `vision_events.py` 第三路 → `classify_events.py` 分出 OCR 一致与需目视的事件 → `make_cue_review_sheets.py` 出需目视事件的拼图 → 按 `sheets-rev/index.json` 分块读拼图写校对结果 → `join_reader_chunks.py` 合成一份读者结果 → `filler_glyphs.py apply` 校 呃/呢 → `check_reader_reads.py` 标出可疑条目并放大复核 → `merge_cue_review.py` 生成 `review.json` → `detect_slide_changes.py` + `make_page_sheets.py` 分页写 `pages.json`（字幕压住正文的页用 `find_clean_frames.py` 找无字幕帧）→ `segment_coverage.py` 出本段 `coverage` → `make_segment_config.py` → `build_segment_manifest.py` → `crop_reviewed.py` → `make_crop_audit.py` → 本段 `validate_capture.py --batch-list`。每段的暂存目录为 `<视频目录>/.staging-<段>-vN/`，失败就换 `vN+1`，不覆盖。
3. **合并**：`merge_segment_manifests.py`，`parts` 按时间顺序列出各段，`merge` 折叠跨段边界的同一页，`use_image_of` 处理「首次只见标题、最终状态在下一段」的页（先跑 `--suggest` 列出标题相同的候选，逐条对照画面再写进配置：同标题不同正文是不同页）；配置的 `coverage` 不写 `gaps` 时自动拼接各段的缺口；先不带 `--final` 合并给 `build_markdown.py` 复制附件，再用 `--final` 版本对总稿跑 `validate_capture.py`（`--batch-list` 列出全部纳入时间轴的批次）。验证通过后，把暂存目录（`.staging-final-vN/`）的文稿、`assets/` 和 `manifest.json` 提升到视频目录。

覆盖说明必须写明：起点前未采集的区段（pre-flight 之前、回退失败留下的缝隙）、批间无重叠及其最大间隔、末尾未采到的片尾秒数。`build_markdown.py` 会按 `coverage.gaps` 写出缺口处数和总秒数，并按字幕的 `review_basis` 写出「N 条中 X 条目视、Y 条按 OCR 一致接受」；生成后仍要通读这两行，确认与实际审核一致。

### 什么情况用什么脚本

脚本都在 `scripts/`，都有测试，参数见各自 `--help`；一律用项目 `.venv/bin/python` 从项目根运行。输出文件已存在时脚本拒绝覆盖，换新文件名或新暂存目录。

| 阶段 / 情况 | 脚本 | 产出与要点 |
|---|---|---|
| 修补既有图文稿、要找补采时间窗 | `prepare_retake.py` | 从章节标题和字幕时间块提取候选时间窗，不选帧 |
| 采集：单批、布局证据图、状态 | `xvast-capture`（Swift） | 见上文「xvast-capture 命令」 |
| 采集：长视频连续多批 | `capture_series.py`（长视频加 `--continuous`） | `.raw/main-NNN/`，每批一行 JSON；Xvast 退出时退出码 3 并给 `resume_from_ms` |
| 采集后把批次标为 valid（目视首中末帧之后） | `mark_batches_valid.py --range main:1-40 --layout layout-001=117,198,2037,1278 --reviewed-by-eye "…" --batch-list .raw/batches.txt` | 写全 `viewport_review`；实测视频区与布局不符时拒收，除非 `--accept-measure 批次=原因`；批内滚动条平移用 `--layout-segment`；停播的 invalid 批次用 `--exclude-frames` |
| 采集后抽测画面边界 / 选定页后测裁切边界 | `measure_bounds.py` | `video`/`slide`/`text`/`subtitle` 四组框；无字幕时可能把右下水印当字幕（x≥1768），须目视 |
| 一个 10 分钟段的 OCR 全链 | `prepare_segment.py`（内部调用 `build_paddleocr_frame_index.py`、`paddleocr-parallel`、`merge_paddleocr_timeline.py`、`filter_events_in_range.py`、`recheck_events_with_server.py`、`make_cue_review_sheets.py`） | `seg-<段>/ocr/`、`sheets-rev/`；目录已存在时拒绝运行 |
| 短视频或手工逐步跑 OCR | `build_paddleocr_frame_index.py` → `paddleocr-parallel` → `select_paddleocr_review.py` → `merge_paddleocr_timeline.py` → `recheck_events_with_server.py` | 同上，逐步执行 |
| 第三路 OCR（打破 mobile/server 分歧） | `vision_events.py`（调用 `vision_ocr.m`） | `{id, vision}`；纯 CPU，不要在连续采集期间跑 |
| 决定哪些字幕要目视 | `classify_events.py` | `three_model`/`two_model` 记 `ocr_agreement`；含 呃/呢 或字母数字的强制目视 |
| 第四路 OCR（可选，云端，需用户确认额度） | `baidu_ocr_events.py` | 先 `--dry-run`；密钥只经 `--credentials .env` 读取 |
| 出字幕条拼图（只含需目视的事件） | `make_cue_review_sheets.py --candidates ocr/review-candidates.jsonl --output-dir sheets-rev` | 每张条数由 `--per-sheet` 定（默认 16，本项目用 20），编号以 `candidates.txt` 为准，每张拼图的编号范围见 `index.json`，分块按它切，不要自己估算条数；读者按编号写 `{"items":[{n,cand,read}]}` |
| 合并分块的读者结果 | `join_reader_chunks.py --candidates sheets-rev/candidates.txt --chunks c1.json c2.json c2-retry.json --output review-reader-1.json` | 后列的文件按编号覆盖前面的；缺号、重号或编号不在 `candidates.txt` 时整份拒绝 |
| 读者结果里的 呃/呢 | `filler_glyphs.py detect` → `apply` | 模板匹配定字形；个数不一致的进 `mismatch`，放大目视 |
| 读者结果的偏差机检 | `check_reader_reads.py` | 标出与「mobile = Vision」冲突、或照抄 server 独有读法的条目，逐条放大原帧复核；标记不是结论 |
| 合并读者结果 | `merge_cue_review.py` | `review.json`（`corrections`/`drop`/`uncertain`/`auto`）；`cand` 与编号错位时整份拒收 |
| 找换页 | `detect_slide_changes.py`（`--region 330,260,1800,1150 --min-gap-ms 2000`） | `changes`（`slide`/`content`）与 `flicker`；对时间要求精确时再按标题区像素差定位 |
| 看页面、选帧 | `make_page_sheets.py` | 带时间标签的联系表，标签就是 `pages.json` 的 `frame` |
| 字幕压住表格/公式/图表横轴，找同页无字幕帧 | `find_clean_frames.py --frame-index … --range A-B --top 6 --sheet …` | 按字幕宽度从窄到宽列候选（0 = 未测到字幕），标签可直接写进 `pages.json`；须看拼图确认 |
| 一段（或全片）的覆盖缺口 | `segment_coverage.py --frame-index … --start-ms --end-ms [--tail-reason …] [--cue-text-review visual_reviewed]` | `coverage` 块：间隔 >1.5 秒的接缝、片头片尾；`cue_text_review` 默认 `ocr_only`，确实目视后才提高 |
| 页表 → 构建配置 | `make_segment_config.py` | 读 `pages.json`（新页、`same_as` 回访、`fallback`/`gaps`、`video_bounds`、`no_subtitle`） |
| 生成段清单 | `build_segment_manifest.py` | 按 `review.json` 与配置出暂存清单；回退页不带 `verified_full`；`no_subtitle` 页的 `subtitle_bounds` 记 null；配置里的 `crop_evidence` 写进 `crop_review.evidence` |
| 裁切 / 出文稿 / 裁切审核 | `crop_reviewed.py` → `build_markdown.py` → `make_crop_audit.py` | 暂存目录里的 `assets/`、Markdown、审核联系表 |
| 多段合并成总稿 | `merge_segment_manifests.py` | 事件 ID 加段前缀；`merge` 折叠跨段同页，`use_image_of` 换用更好的图；`--suggest` 列出候选 merge；`--final` 供验证；会自动建输出目录 |
| 验证 | `validate_capture.py --batch-list` | 只验证列出的批次 |
| 共享的 OCR 文本过滤 | `ocr_text_filter.py` | 被 `merge_paddleocr_timeline.py`、`recheck_events_with_server.py` 引用，不单独运行 |

各脚本补充说明：

- [scripts/capture_series.py](scripts/capture_series.py)：连续采集多个批次，每批先回退 10 秒预热；批次 `invalid` 或输出读不出就停；Xvast 崩溃/退出（`status` 读不到播放器）时输出 `{"event":"xvast_lost","last_valid_batch","resume_from_ms"}` 并以退出码 3 停止，需人工重启 Xvast、在 playlist 重新选中视频、seek 回 `resume_from_ms` 之前再续采（不自动重启，因为选中视频只能人工做）；每批输出一行 JSON，含首中末帧的视频区边界和是否检测到字幕（`--measure-after` 时改为结束后统一输出 `{"event":"layout"}` 行），连续模式下另有 `seam_ms`。编号默认接着已有的最大批次。须在已授权“辅助功能”和“屏幕录制”的终端里运行。
- [scripts/prepare_segment.py](scripts/prepare_segment.py)：对一个时间段按 `--batch-list` 里的批次做索引（相邻批次重叠帧只由后一批计入）→ OCR → 合并 → 过滤到区间内 → server 复核 → 字幕条拼图。须显式用默认的 `--crop 450,1160,1700,1285`，skill 自带的 auto 裁切会截掉字幕底色。可用 `--stop-after`、`--dry-run`。
- [scripts/build_segment_manifest.py](scripts/build_segment_manifest.py)：由校对结果（`review.json`：`corrections`、`drop`）和逐页配置生成该段的暂存清单；页面几何由 `measure_bounds.py` 实测，回退页不会带 `verified_full`。
- [scripts/merge_segment_manifests.py](scripts/merge_segment_manifests.py)：把几段清单合并成总稿清单；事件 ID 加段前缀，用 `merge` 去掉跨段重复页，`--final` 把图片路径改成 `assets/ppt-NNN.png` 供验证。
- [scripts/vision_events.py](scripts/vision_events.py)：第三路 OCR。对事件代表帧裁字幕条，调用 [scripts/vision_ocr.m](scripts/vision_ocr.m)（macOS Vision，CPU），输出 `{id, vision, vision_all, vision_error}`；`vision` 只留高度不低于最高行 60% 的行并按从左到右拼接。无 `--vision-command` 时在 `--work-dir` 里自动编译 `vision_ocr.m`（最新 SDK 链接失败会改用其他已装 SDK）；输出文件或 `--work-dir` 里已有 `vision-raw.jsonl` 时拒绝覆盖。
- [scripts/filler_glyphs.py](scripts/filler_glyphs.py)：呃/呢 字形判定。同一视频的字幕字体、字号一致，从原帧切出 呃、呢 各一个模板后做模板匹配（本字 ≈0.97–1.0；另一字的得分随字体而变，风火轮2周年 ≈0.88–0.91、风火轮3 ≈0.34；普通字 <0.7，阈值 0.85。每个新视频先让两个模板互相匹配一次，确认阈值能分开）。`detect` 给每个事件输出从左到右的语气词序列；`apply` 把读者结果里的 呃/呢 按检测序列替换（个数一致才替换），个数不一致的列入 `mismatch` 供放大目视。模板坐标先在原帧上放大 3 倍确认字形再记录。
- 读者校对的已知偏差（风火轮2周年实测）：子代理读拼图时会照抄候选文字，包括 server 的形近错字（今大、风灭轮、万式、币值）和 呃/呢 错判。对策：给读者看 mobile/server/Vision 三路读法并声明它们不可靠，要求 呃/呢 一律放大原帧；读者结果再过两道机检——`filler_glyphs.py apply`，以及 `check_reader_reads.py` 标出的条目逐条放大原帧复核。
- 读者子代理的规模：一个子代理一次读完整段（15–20 张拼图）时多次卡死（10 分钟无进展被终止，未写出结果）。按每个子代理 ≤5 张拼图（≤100 条）分块、同时最多约 4 个，每块写 `review-reader-1-cN.json`（重读的块写 `cNb`），用 `join_reader_chunks.py` 按编号合成 `review-reader-1.json`，再过 `filler_glyphs.py apply`、`check_reader_reads.py`，最后交给 `merge_cue_review.py`。
- 连续采集期间不要跑 PaddleOCR：3 个 worker 并行时帧距曾拉长到 2022 ms。OCR 放到采集结束后；采集期间只做索引、换页检测、页面拼图等轻量工作（`nice -n 19`）。写成 `nice -n 19 .venv/bin/python …`，不要把解释器放进带引号的变量（`nice -n 19 "$PY"` 在 zsh 下报 no such file）。
- 页面纵向滚动条出现时视频区左右平移（风火轮3 实测 15 px，`x=102–2022` 对 `117–2037`）。批内切换帧要逐帧找出，用 `mark_batches_valid.py --layout-segment` 记录；深色画面（PowerPoint 编辑窗口、聊天截图）会让 `measure_bounds` 测错视频区，这时在 `pages.json` 给该页写 `video_bounds`，批次审核用 `--accept-measure` 写明原因。
- 原则：同一类手工步骤在一次采集里出现第二次，就做成 `scripts/` 下带测试的脚本，不在会话 scratchpad 里反复写一次性 Python。
- 辅助：[scripts/filter_events_in_range.py](scripts/filter_events_in_range.py)、[scripts/recheck_events_with_server.py](scripts/recheck_events_with_server.py)、[scripts/baidu_ocr_events.py](scripts/baidu_ocr_events.py)、[scripts/make_cue_review_sheets.py](scripts/make_cue_review_sheets.py)、[scripts/detect_slide_changes.py](scripts/detect_slide_changes.py)、[scripts/measure_bounds.py](scripts/measure_bounds.py)。

## 字幕归页

- 逻辑 PPT 页按首次出现顺序编号；每条字幕保存唯一事件 ID、实际时间范围、证据，以及一个 `slide_id` 或 `null`。
- 开始展开某页时的字幕属于该页，即使最终完整截图出现得更晚。
- 同页回访按时间排序并另起时间块，不能把不连续的讲解伪造成连续范围。
- 跨页字幕根据语义和画面切换判断；需要拆句时保存母事件引用，不能把整句重复放到两页。
- 软件演示字幕不能因为画面不是 PPT 就删除，也不能不看语境全部塞给上一页。

## 阅读排版与输出

```text
课程图文稿.md
assets/
  ppt-001.png
  ppt-002.png
```

- 图片使用 `![页面标题](assets/ppt-001.png)`；不用绝对路径、远程地址或 base64，`assets/` 下不嵌套子目录。
- 文档顺序：来源和覆盖说明 → 每页标题 → 一张完整图或原图回退 → 对应字幕 → 未归属字幕和缺口说明。
- 每个连续讲解时间块默认不超过 180 秒，只在块首标一次约略时间；换页、同页回访、明显间隔或新话题时另起时间块。
- 不超过 220 字通常一段，221–480 字通常两段，更长通常三段；优先在完整句子、转折、举例或总结处分段。
- 已有正式文件先就近备份，构建脚本拒绝直接覆盖。最终报告 PPT 页数、字幕事件数、时间覆盖、未归属数、不确定项和具体缺口。

## 完成门槛

只有以下条件全部满足，才可标记 `document_finalized`：

- 5 秒 pre-flight 已完成并记录实测帧数、帧距中位数/最大值、时间锚和倍速；已目视确认播放器和 PPT 四边完整。每个正式长批次的 3 帧探针均先于长采集通过；布局变化后已用新 `layout_profile` 重做检查。无效批次未进入时间轴。
- 每个有效布局都有原始全窗口 `viewport_review` 证据。
- 时间轴区分了有字幕、确实无字幕、无法读取和未采集四种区段，所有可补的缺口都已回看。pre-flight 起点之前的缺口已补采或已披露。
- 每条字幕事件恰好输出一次，事件级修正有证据；未核验的事件仍标为不确定。
- PPT 已完成粗扫、补扫、换页密集复查和逐页裁切边界审核；文档和清单汇总了 `complete` 与 `fallback_original` 的数量。
- Markdown 图片链接全部存在且平铺，时间块不超过 180 秒。
- 每张最终图片都完整保留烧录字幕，`crop_review.subtitle_edge` 为 `verified_full`；每张 source 都通过 `viewport_review.source_slide_complete: true`。
- 覆盖声明与实际审核等级一致；有限采样、OCR 或未逐字听写等限制写进文档，不能只在聊天中说明。

## 脚本测试

脚本改动后在项目根目录运行 `.venv/bin/python -m pytest .claude/skills/xvast-subtitle-capture/tests`。测试一律从命令行入口运行、使用合成夹具，不调用内部函数，也不需要 Xvast；`xvast_capture.swift` 只做 `swiftc -typecheck`，真实采集与失败批次迁移需在 Xvast 上手工验证。
