# xvast-subtitle-capture 用户指南

把 Xvast 播放器里的课程视频，整理成「每页 PPT 配原文字幕」的 Markdown 图文稿。本指南按实际操作顺序写：每一步给命令、验收标准、常见问题。规则细节以 `SKILL.md`、`AGENTS.md`、`references/` 为准，本文是操作手册。

约定：以下命令都在**项目根目录**运行；`S=.claude/skills/xvast-subtitle-capture/scripts`，`X=$S/xvast-capture`；`V="视频在播放列表里的完整文件名.mp4"`；`D=视频目录`（如 `凌烟阁2合集`）；`RAW=$PWD/$D/.raw`。Python 一律 `.venv/bin/python`。

---

## 0. 全流程总览

```text
① 环境准备 → ② 窗口与布局 → ③ pre-flight → ④ 连续采集 → ⑤ 批次审核(valid)
→ ⑥ 分段 OCR(prepare_segment) → ⑦ 字幕校对(review.json) → ⑧ 换页检测与逐页选帧
→ ⑨ 生成分段清单/裁图/Markdown → ⑩ 验证 → ⑪ 合并总稿 → ⑫ 清理与交付
```

| 阶段 | 做什么 | 主要工具 | 产出 |
|---|---|---|---|
| 采集 | 窗口截图 + 播放控制 | `xvast-capture`、`capture_series.py` | `.raw/main-NNN/frame-*.jpg` + `frames.json` |
| 字幕 | OCR 候选 → 目视校对 | `prepare_segment.py`、`baidu_ocr_events.py`、`vision_ocr.m` | `seg-*/ocr/*`、`review.json` |
| PPT | 换页检测 → 选帧 → 裁图 | `detect_slide_changes.py`、`measure_bounds.py`、`crop_reviewed.py` | `assets/ppt-NNN.png` |
| 出稿 | 清单 → Markdown → 验证 → 合并 | `build_segment_manifest.py`、`build_markdown.py`、`validate_capture.py`、`merge_segment_manifests.py` | `*.md`、`manifest*.json` |

核心原则：**字幕原文不改写、不删口头语；「时间轴覆盖完整」「字幕目视核对」「逐字人工核对」是三个不同结论，文稿里分别如实陈述。**

---

## 1. 环境准备（一次性）

### 1.1 macOS 权限
运行命令的终端（Terminal / Warp / iTerm）在「系统设置 → 隐私与安全性」里必须同时有：
- **辅助功能**（读 Xvast 进度、按 Play/Pause、seek）
- **屏幕录制**（`screencapture -l` 截窗口）

症状与处理：

| 症状 | 原因 | 处理 |
|---|---|---|
| `status` 报 `Accessibility permission missing` | 缺辅助功能权限 | 授权后**重启终端** |
| 截图全黑或只有桌面 | 缺屏幕录制权限，或窗口最小化/在其他桌面空间 | 授权；把 Xvast 窗口放回当前桌面 |
| 采集中弹出录屏授权框 | 首次授权弹窗（Warp 常见） | 没造成丢帧，但建议改用已授权的 Terminal 运行；采集期间不要碰 Xvast |

### 1.2 Python 与 PaddleOCR
```bash
python3 -m venv .venv                       # 没有 .venv 时
$S/setup_paddleocr.sh                       # 装固定版本依赖，下载 mobile + server 模型到 .paddleocr-cache/
# PyPI 慢时：$S/setup_paddleocr.sh --index-url https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/python -c 'from PIL import Image; print(Image.__version__)'   # 验证 Pillow
```
不要装到系统 Python。模型下载后可离线推理。

### 1.3 Swift 采集工具
首次运行 `$X` 会自动 `swiftc -O` 编译到 `~/Library/Caches/xvast-capture/`。编译失败（例如 `unknown architecture arm64e.x1`）见 §9 排错表。

### 1.4 跑一遍测试（改过脚本时）
```bash
.venv/bin/python -m pytest .claude/skills/xvast-subtitle-capture/tests
```

### 1.5 百度 OCR 密钥（只有用百度时）
项目根 `.env`，权限 600：`BAIDU_OCR_API_KEY=…`、`BAIDU_OCR_SECRET_KEY=…`。**不要用工具读取/打印/复制 `.env`**，只让 `baidu_ocr_events.py --credentials .env` 读。

---

## 2. 窗口与布局（最容易出事的一步）

### 2.1 为什么窗口尺寸重要
- 截图是 `screencapture -l <窗口ID>`，**只截 Xvast 窗口本身，与它在桌面上的位置无关**，被别的窗口遮挡也没关系；但窗口最小化或在别的桌面空间就截不到。
- 但窗口**大小**决定画面布局：OCR 裁切框（如 `400,1160,1700,1285`）、`measure_bounds.py` 的边距、`slide_bounds`/`crop_box` 全是按标定布局算的。窗口尺寸一变，旧坐标全部失效。
- 本项目标定布局：窗口 **1077×949 pt、位置 (0,33)** → 截图 **2154×1898**（Retina 2×），视频区 1920×1080，位于 `[102,198,2022,1278]` 或 `[117,198,2037,1278]`（页面纵向滚动条时隐时现，视频区左右平移约 14 px，y 不变）。

### 2.2 检查当前窗口
```bash
$X status
```
看输出中的 `window_bounds_pt`：应为 `{"x":0,"y":33,"width":1077,"height":949}`，并确认 `video`、`position_ms`、`duration_ms`、`playback_rate`、`playing`、`window_id`。

### 2.3 窗口被拖动/缩放后怎么恢复
**先暂停采集**（正在跑 `capture_series.py` 就 Ctrl-C），再用 AppleScript 复位（用 bundle id 找进程，避免进程名猜错）：

```bash
osascript <<'EOF'
tell application "System Events"
  set p to first process whose bundle identifier is "com.haihaisoft.xvast"
  tell p
    set w to window 1
    set position of w to {0, 33}
    set size of w to {1077, 949}
  end tell
end tell
EOF
$X status    # 再确认 window_bounds_pt
```
注意：
- `set position` 与 `set size` 要分行写在 `tell` 块里。曾把两句用 `&` 连成一行表达式，会语法错误。
- 复位后截一张证据图并目视确认（见 2.4），再继续采集。
- 若窗口恢复不到 1077×949（屏幕太小、Xvast 有最小宽度），**不要硬凑**：接受新尺寸，按 2.5 建新 layout。

### 2.4 布局证据图（每个 layout 必做）
```bash
mkdir -p "$RAW/layout-001"
$X pause
$X screenshot --out "$RAW/layout-001/window.png"      # 拒绝覆盖已有文件
```
用 Read 看这张图，必须同时看见：播放器内容区四边、控制条、PPT 画布四边。只见局部 → 把 Xvast 页面滚到播放器顶部再拍；滚到顶仍不全 → **停止采集**。

### 2.5 窗口尺寸变了怎么办（实战经验）
| 情况 | 判定 | 处理 |
|---|---|---|
| 视频区仍 1920×1080、四边完整，只是窗口宽高变了（例：被拖窄到 1988×1898，视频区变 `[19,198,1939,1278]`） | 画面可用 | **新建 `layout-NNN`**，证据图放 `.raw/layout-NNN/window.*`；该布局的批次在 `frames.json` 写 `layout_profile`；之后 OCR 裁切框、`measure_bounds` 边距要按新布局核对 |
| 窗口被拖宽（如 3024×1898），控制层压到字幕 | 不可用 | 整批 `invalid`，不入时间轴；复位窗口后回退到上一有效批次末尾之前重采 |
| 窗口被拖小（约 770×680），视频缩小 | 不可用 | 这些帧写入 `manual_review.excluded_frames`；复位窗口后补采 |
| 只有少数帧异常（批尾/批首几帧） | 局部不可用 | 在该批 `frames.json` 的 `manual_review.excluded_frames` 里列出帧号，OCR 与选帧时排除；该时段必须被相邻批次覆盖，否则记入 `coverage.gaps` |

用 `scan_bounds` 思路批量排查：对每批的首/中/末帧（或全部帧）跑 `measure_bounds.py`，只要视频区不在已知取值（`[102,198,2022,1278]`、`[117,198,2037,1278]` 或新 layout 的取值）、或截图尺寸变了，就逐批目视确认。

### 2.6 采集期间的纪律
- 不要点击/拖动 Xvast 窗口，不要把鼠标移进播放器区域（指针会被截进帧里）。
- 要隐藏控制层只能 `$X park-cursor`（把指针放到浏览器顶栏空白处）。**禁止**点击播放器下方空白页面区域——那里可滚动，会把播放器滚出视口。
- 采集期间不要切走桌面空间、不要让窗口最小化。

---

## 3. 采集命令速查（xvast-capture）

每条命令向 stdout 输出一个 JSON；出错写 stderr、退出码 1。

| 命令 | 作用 / 注意 |
|---|---|
| `$X status` | 视频名、进度、时长、倍速、播放状态、窗口 ID 与边界 |
| `$X play` / `$X pause` | 已在目标状态时不动作 |
| `$X seek --to H:MM:SS` / `--by -10` | 按 10 秒步长逐步移动，精度 ±5 秒。**默认最多 30 步（5 分钟）**，更远要加 `--max-steps N`；Xvast 忽略直接写进度，只认步进 |
| `$X park-cursor` | 指针移到顶栏安全区，让控制层自动隐藏 |
| `$X screenshot --out /abs/path.png` | 单张窗口证据图，不覆盖 |
| `$X capture --video-id "$V" --output-root "$RAW" --batch-dir NAME [--layout-profile layout-001] [--frame-count N] [--interval-ms 500] [--pause-after-capture]` | 连续采集；1–120 帧，间隔 ≥150 ms；批次目录非空则拒绝；`--batch-dir` 仅限 `[A-Za-z0-9_-]` |

`capture` 结束后写 `frames.json`，状态 `pending_manual_review`，出现以下情况直接标 `invalid`：进度与墙钟偏差超过 `max(3000 ms, 5%)`、最大帧距 ≥ `--shortest-subtitle-ms`、中途停止播放、截图失败。工具**不会**自动证明画面完整——`viewport_review` 初始为 null，必须你目视后填。

---

## 4. 采集流程

### 4.1 核对
```bash
$X status      # 视频、时长、倍速、窗口
```

### 4.2 5 秒 pre-flight（从 00:00 起，仅首次）
```bash
$X pause && $X screenshot --out "$RAW/layout-001/window.png"   # Read 目视
$X seek --to 0:00:00 && $X play && $X park-cursor              # 等 2–3 秒控制层隐藏
$X capture --video-id "$V" --output-root "$RAW" --batch-dir preflight-001 \
  --layout-profile layout-001 --frame-count 11 --interval-ms 500 --pause-after-capture
```
目视首/中/末帧：字幕完整可读、PPT 四边完整 → 在 `frames.json` 填 `viewport_review` 并改 `status: valid`。00:00–00:03 因控制层遮挡通常采不到，要在清单 `coverage.gaps` 如实记录。

### 4.3 每批的 3 帧探针 + 主批（手动逐批）
协议要点（`references/capture-protocol.md`）：

```bash
$X seek --by -10 && $X play && $X park-cursor && sleep 7      # 回退 10 秒预热，等控制层隐藏
$X capture --video-id "$V" --output-root "$RAW" --batch-dir probe-001 \
  --layout-profile layout-001 --frame-count 3 --interval-ms 500 --pause-after-capture
# Read 目视 3 帧通过后
$X seek --by -10 && $X play && $X park-cursor && sleep 7
$X capture --video-id "$V" --output-root "$RAW" --batch-dir main-001 \
  --layout-profile layout-001 --frame-count 120 --interval-ms 500 --pause-after-capture
```
为什么要「回退预热」：按 Play 会唤出控制层盖住字幕；回退到已覆盖区间再播，等控制层隐藏后才开拍，才不会丢字幕。新批次起点必须 ≤ 上一批终点（至少约 1 秒重叠），否则是缺口，回退重采。

### 4.4 长视频自动连采（推荐）
```bash
.venv/bin/python $S/capture_series.py --raw-root "$RAW" --video-id "$V" \
  --target-ms 6040000 --layout-profile layout-003
```
- 每批：`seek --by -10` → `play` → `park-cursor` → 等 7 秒 → 采 120 帧 / 500 ms → 暂停。批间重叠约 10 秒。
- 批次编号自动接着已有最大批次；批次 `invalid` 或输出读不出就停。
- 每批一行 JSON，含首/中/末帧测得的视频区边界和是否检测到字幕——**这是自动提示，不是审核**。
- 必须在已授权的终端运行；运行期间不要碰 Xvast。
- 中断后重启前，先 `$X status` 确认窗口尺寸和进度，再续采（会从当前位置回退 10 秒）。
- `--layout-profile` 要和当前真实布局一致；窗口变了就停下换 profile。

### 4.5 批次审核（决定能否标 valid）
对每个批次用 Read 看首、中、末三帧：
- 视频区四边与 PPT 画布四边完整、控制条可见（`controls_visible`）。
- 首帧**没有**控制层遮挡字幕（遮挡 → 整批 `invalid`）。
- 尺寸、视频区边界属于已登记的 layout。
然后在 `frames.json` 写：
```json
"status": "valid",
"layout_profile": "layout-003",
"viewport_review": {"four_edges_visible": true, "controls_visible": true,
                    "scroll_state": "player_fully_in_view", "evidence": "首/中/末帧目视，视频区 [102,198,2022,1278]"},
"manual_review": {"excluded_frames": [92,93,94], "note": "控制层压底部"}
```
批量检查辅助：`measure_bounds.py <帧>` 输出视频区/画布/字幕边界（证据，非结论）。

### 4.6 批次清单
验证和索引只用批次名清单，**不递归扫全部批次**（旧 pending/invalid 批次会让验证失败）：
```bash
printf '%s\n' main-001 main-002 … > "$RAW/batches.txt"   # 一行一个批次目录名，只含 valid
```
无效批次（如被拖动窗口污染的 `main-046`）不进清单，目录保留不删。

### 4.7 检查时间缺口
逐批比较 `video_end_ms` 与下一批 `video_start_ms`，下一批起点必须 ≤ 上一批终点。曾出现的真实缺口（41:40–41:43 共 3 秒）必须写入 `coverage.gaps`，不能说「完整覆盖」。

---

## 5. 字幕 OCR：流程与选项

### 5.1 总流程（`prepare_segment.py` 一键做前半段）
按每 10 分钟一段：
```bash
.venv/bin/python $S/prepare_segment.py --video-dir "$D" --name s40 \
  --batch-list "$RAW/batches.txt" --start-ms 2400000 --end-ms 3000000 \
  --crop 400,1160,1700,1285 --strip-crop 400,1175,1700,1285
```
内部阶段：`index`（建时间索引，相邻批次重叠帧只由后一批计入）→ `ocr`（PaddleOCR mobile，≤5 路并行）→ `merge`（合并成字幕事件）→ `range`（过滤到区间内）→ `recheck`（server 模型复核）→ `sheets`（带编号字幕条拼图 + `candidates.txt`）。可用 `--stop-after`、`--dry-run`。输出在 `$D/.raw/seg-s40/`。

关键约束：
- **必须显式传 `--crop`**。skill 自带的 auto 裁切会截掉字幕底色。1077×949 布局用 `400,1160,1700,1285`；窗口布局变了要重新量。
- 正式批量前先 `--max-images 3 --keep-crops` 做 3 帧 smoke，看裁切图和 `subtitle_texts`。
- 事件 ID（`ocr-000001…`）**每段重新编号，跨段会重名**，做集合运算要带段标签；合并总稿时会加前缀。
- 所有 OCR 结果都是 `ocr_only`，不等于已核对。

### 5.2 OCR 引擎怎么选

| 选项 | 位置 | 优点 | 缺点 / 限制 | 本项目用法 |
|---|---|---|---|---|
| PaddleOCR **mobile** | 本地 CPU | 快，免费，离线，可 5 路并行 | 置信度虚高；形近字错误多（「找们」「同字」「回撒」「小币值」） | 全量第一遍 |
| PaddleOCR **server** | 本地 CPU | 比 mobile 准，`recheck_events_with_server.py` 每个事件代表帧重跑 | 慢；仍会错（实测出过「牛币」「官万」「左石」） | 全量第二遍；与 mobile 不一致的事件优先看（实测约 46% 事件不一致） |
| **百度 OCR**（accurate_basic） | 云端（上传字幕条裁切图） | 独立的第三方引擎 | **有每日请求上限**（实测约 330 次后报 `17: Open api daily request limit reached`）；上传图片到云端；用量超免费额度需用户在控制台确认 | 可选；先 `--dry-run` 看张数；额度用完就停，不要依赖它做全量 |
| **Apple Vision**（`vision_ocr.m`） | 本地 macOS | 免费，离线，333 条约 20 秒；与 mobile/server 错误模式不同，适合作第三方 | 只能系统决定 CPU/GPU；会混入状态栏词（China、Notes、Comments）、日期轴刻度等杂字，需清洗 | 推荐的第三方，六段全跑 |
| **目视校对** | 人 / Claude Read | 唯一能确认原文的方式 | 慢 | 不一致、含「呃/呢」、含字母数字的事件必须做 |

**推荐组合：mobile + server + Apple Vision，三路比较；百度仅当额度够且用户同意时补充。**

### 5.3 Apple Vision 用法
```bash
mkdir -p "$TMP/vision"
clang -fobjc-arc -framework AppKit -framework Vision -framework ImageIO \
  $S/vision_ocr.m -o "$TMP/vision/vision_ocr"
# 默认 SDK 链接报 "unknown architecture arm64e.x1" 时，加：
#   -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk   （按本机实际 SDK 路径）
"$TMP/vision/vision_ocr" 图片清单.txt 输出.jsonl      # 输入：逐行绝对路径；输出文件已存在会被拒绝
```
- 输入用字幕条裁切图（`strip-crop`），不要喂整窗口图。
- 输出每张图是多行 `rows`（含文字、`x`、`h`）。取字幕行：保留高度 ≥ 0.6×最大高度 的行，按 `x` 排序拼接，滤掉小号杂字。
- 清洗：去 `United States/China/Simplified, Mainland China`、`Notes/Comments/Accessibility: Unavailable`、日期轴刻度（出现 ≥2 个 `\d{1,2}日|\d月` 时整体去除及尾随两位数字）。
- `usesCPUOnly = YES`（现状）与系统自选算力，准确率与耗时无可测差别，不必折腾 GPU。

### 5.4 百度 OCR 用法（可选）
```bash
.venv/bin/python $S/baidu_ocr_events.py --candidates "$D/.raw/seg-s40/ocr/event-server.jsonl" \
  --credentials .env --dry-run                    # 先看会上传多少张
.venv/bin/python $S/baidu_ocr_events.py --candidates … --credentials .env --pause 0.25 \
  --output-jsonl "$D/.raw/seg-s40/ocr/event-baidu.jsonl" \
  --output-report "$D/.raw/seg-s40/ocr/baidu-report.json"
```
- 超出免费额度由用户确认；遇到 `17` 或其他 `error` 行立即停，不要重试刷额度。
- 输出里有 `error` 的行不算有效，`classified` 时按缺失处理。

### 5.5 一致性分级规则
对每个事件比较三路文本（去标点、空白后比较）：
- **three_model**：mobile = server = 第三方 → 可按 OCR 一致接受。
- **two_model**：server = 第三方 → 可接受。
- **needs_review**：其余全部目视读图。
- **强制目视**：含「呃/呢」（OCR 最易混）、含字母/数字/年份/`6日` 等图表文字的事件，即使三路一致也要看。
- 接受的事件在清单里标 `review_basis: ocr_agreement`，文稿开头写明有多少条未目视。

### 5.6 目视校对怎么做
```bash
# 拼图在 $D/.raw/seg-s40/sheets/sheet-NN.jpg，每张 16 条带编号字幕条
# 编号 → 事件 id → 候选文字在 $D/.raw/seg-s40/sheets/candidates.txt
```
用 Read 看拼图，逐条对照候选文字。拼图看不清（尤其「呃/呢」「的/地」「0/O」）→ 回到原帧放大裁切再看，**不凭语感改**。结果写 `$D/.raw/seg-s40/review.json`：
```json
{"corrections": {"ocr-000012": "那我们来看一下", "ocr-000047": "呃我也改不了PPT啊"},
 "drop": ["ocr-000203"]}
```
- `corrections`：事件 id → 从帧上读到的原文（只改有错的；没写的沿用 server 文本）。
- `drop`：不是字幕的事件（画面杂字、水印、空条）。
- 保留视频字幕自身的错字和口头语（「斯拉水」「回回车」「呃」「那个那个」不要改）。
- 看不清的字不得靠语音/PPT 正文/领域知识猜补，标待核验。

### 5.7 常见 OCR 错误速查
`找们→我们`、`同字→同学`、`回撒→回撤`、`小币值→小市值`、`趋势/超势`、`呃/呢` 混淆；日期轴数字、状态栏英文混进字幕；字幕被图表遮挡时底部几行丢字。

### 5.8 OCR 排错
| 现象 | 处理 |
|---|---|
| OCR 突然大面积为空，但画面在变 | 先查原始帧布局/`layout_profile`/裁切框是否漂移，再用 3 张原图做 smoke；确认裁切对了再查 OCR 环境。空结果不能据此判定无字幕 |
| 字幕底部被截掉 | 用默认 `--crop`，不要 auto 裁切 |
| 多进程脚本报 spawn/pickle 错 | 把脚本写成文件再运行，不要从 stdin 跑 |
| `candidates.txt` 某行只有两列 | 解析时补空：`(l.split(None,2)+[''])[:3]` |
| Vision 输出混入 `China`/`Notes`/日期刻度 | 按 §5.3 清洗 |
| Baidu 报 `17` | 当日额度用尽，停止，改用 Vision |
| 同一批帧被重复 OCR | 相邻批次重叠帧只由后一批计入（`prepare_segment` 已处理），自己做索引时注意 |

---

## 6. PPT：换页检测与选帧

### 6.1 换页检测
```bash
.venv/bin/python $S/detect_slide_changes.py \
  --frame-index "$D/.raw/seg-s40/ocr/frame-index.jsonl" --region 120,210,2000,1160
```
`--region` 取画布内部、避开字幕条和控件。`changes[].kind`：`slide`=整页切换，`content`=逐条展开，`flicker`=两页间来回闪烁（不是换页，也别因此漏掉其中的章节页）。

### 6.2 页面划分规则
- 以**版式和正文**分页，不只看标题；同标题不同正文是不同页。
- PPT 逐条展开只取最终完整状态；离开后再回来仍算同一页。
- 放大镜局部画面并入对应页，不单独成页。
- 软件界面、PowerPoint 编辑窗口不是 PPT：只能作为「原图回退」，裁整窗并写明原因。
- 代码、网页、独立图表、软件演示不截图，但这些时段的字幕仍要保留。

### 6.3 逐页选帧
- 优先选「字幕条没压住内容」的帧。
- 字幕压住图表横轴/页底、且同页没有无字幕的帧 → `fallback_original`，**不要靠上移裁切框造成「完整」**。
- 每页对所选帧实测：`.venv/bin/python $S/measure_bounds.py <帧路径>`，得到 `video`/`slide`/`text`/`subtitle` 边界，写入 `slide_bounds`、`subtitle_bounds`、`crop_box`。默认边距按 2154×1898 标定，换布局要重新核对。
- 被标 `excluded_frames` 的帧不能选。
- 目视确认字幕条文字、底色、描边完整（`subtitle_edge: verified_full`）。

---

## 7. 生成分段清单、裁图、Markdown

### 7.1 分段清单
写配置 JSON（字段见 `build_segment_manifest.py --help`）：`seg_dir`、`out_dir`、`title`、`end_ms`、`coverage`、`ranges`（`[[start_ms, slide_id], …]`）、`merge_keys`、`slides`（`id`/`title`/`frame`/`first_seen`/可选 `type`/`crop_box`/`slide_bounds`/`fallback`/`gaps`）。
```bash
.venv/bin/python $S/build_segment_manifest.py --config cfg-s40.json --project-root .
```
输入需要 `seg_dir/ocr/event-server.jsonl` 和 `seg_dir/review.json`。输出 `<out_dir>/manifest.json`；空文本事件跳过；超过 `end_ms` 的事件截断；1500 ms 内相同文字合并为一条。

### 7.2 裁图与 Markdown（先到暂存目录）
```bash
.venv/bin/python $S/crop_reviewed.py --manifest "$D/.staging-s40/manifest.json" --output-dir "$D/.staging-s40/assets"
.venv/bin/python $S/build_markdown.py --manifest "$D/.staging-s40/manifest.json" --output "$D/.staging-s40/文稿.md"
.venv/bin/python $S/make_crop_audit.py …      # 裁切审核联系表，逐页看一遍
```
`assets/` 必须和 Markdown 同级且平铺；输出路径已存在时脚本拒绝覆盖，换新的 `.staging-*`。时间块不超过 180 秒。

---

## 8. 验证与合并

### 8.1 验证（分段与总稿都要）
```bash
.venv/bin/python $S/validate_capture.py --require-viewport-review --require-crop-review \
  --require-source-assets --manifest "$D/…manifest.json" --document "$D/….md" --assets "$D/assets" \
  --batch-root "$D/.raw" --batch-list "$D/.raw/batches.txt"
```
一定要带 `--batch-list`，只验证纳入时间轴的批次。

### 8.2 合并总稿
写 merge 配置：`title`、`duration_ms`、`coverage`、`parts: [{"tag":"p1","manifest":"…"}, …]`、`merge: {被丢弃的重复页id: 保留页id}`、`use_image_of`。
```bash
.venv/bin/python $S/merge_segment_manifests.py --config merge.json --output merged.manifest.json          # 先出绝对路径版供 build_markdown 复制资源
.venv/bin/python $S/merge_segment_manifests.py --config merge.json --output final.manifest.json --final    # 路径改成 assets/ppt-NNN.png 供验证
```
事件 ID 自动加段前缀；跨段重复页（章节页、同页延续）只保留一个。合并后必须**重新用 `--batch-list` 验证**。已有正式文件先备份，再把暂存提升为正式。

---

## 9. 总排错表

| 现象 | 原因 | 处理 |
|---|---|---|
| `Accessibility permission missing` | 终端缺权限 | §1.1 |
| 截图全黑 | 缺屏幕录制权限/窗口最小化 | §1.1 |
| 截图尺寸不是 2154×1898 | 窗口被拖动/缩放 | §2.3 复位或 §2.5 建新 layout |
| 视频区边界不在已知值 | 滚动条出现/窗口变了 | `measure_bounds.py` 抽测，建新 layout_profile |
| 帧里有鼠标指针 | 采集前没 `park-cursor` | 重采该批 |
| 首帧字幕被控制条盖住 | 没有回退预热 | 整批 `invalid`，回退重采 |
| 批次 `invalid`：进度偏差 | 中途暂停/卡顿 | 回退到上一有效批次末尾之前重采 |
| `seek` 提示超步数 | 默认 30 步（5 分钟） | 加 `--max-steps N`，或手动拖进度条再微调 |
| `AXDecrement did not move the progress bar` | 播放器进度条卡住 | 不要连续重试（曾疑似导致 Xvast 退出）；手动拖动，必要时重启 Xvast 并确认视频选中 |
| `lost the progress bar` | Xvast 退出/页面变了 | `$X status` 确认是否仍在运行 |
| `cannot write file to intended destination` | 临时文件名以点开头 | 工具已改 `_<帧名>.part.<ext>`，别改回 |
| 第 1 帧起截图失败 | 权限/窗口问题 | 批次自动移到 `.raw/_failed/…`，修好后同名重采 |
| Swift 编译 `unknown architecture arm64e.x1` | 默认 SDK 不匹配 | `swiftc/clang` 加 `-isysroot <SDK>` |
| 批次间有缺口 | 起点晚于上一批终点 | 回退重采；不补采则写入 `coverage.gaps` |
| 验证因旧 pending 批次失败 | 递归扫了全部批次 | 用 `--batch-list` |
| 构建脚本拒绝覆盖 | 路径已存在 | 换新 `.staging-*` |
| shell 里 `diff/cat/ls` 行为异常 | 被别名替换 | 用 `/bin/ls`、`/usr/bin/cmp`；比较文件用 `cmp` |
| `pkill -f baidu` 杀到别的 App | 名字撞 BaiduNetdisk | 用 `pgrep -f "baidu_ocr_events"` 精确匹配 |

---

## 10. 覆盖说明怎么写（文稿开头必须有）

分别陈述，不得混用：
1. **时间轴覆盖**：采集范围、`coverage.gaps`（如 00:00–00:03、41:40–41:43）、`excluded_frames` 及其是否被相邻批次覆盖。
2. **字幕目视核对**：多少条看过原帧，多少条是 `ocr_agreement` 未目视。
3. **逐字人工核对**：只有真的逐条对照原帧才可声明；否则明确写「未逐字人工核对」。
4. 未解决项：待核验的「呃/呢」、看不清的字、`fallback_original` 页数及原因。

---

## 11. 清理与交接
- 不要删除文件或暂存目录；列出可清理清单（空 `.staging-*`、`*-manifest-build.json`、失败/部分批次目录）让用户处理。
- 临时脚本放会话 scratchpad；通用的、可复用的写进 `scripts/` 并配测试。
- 长任务中断时更新 `handoff/` 下交接文档：已完成批次范围、无效批次、缺口、layout 列表、窗口状态、下一步命令。
