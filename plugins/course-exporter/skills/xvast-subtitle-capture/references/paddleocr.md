# 本地 PaddleOCR 字幕候选

PaddleOCR 是本 Skill 的默认本地字幕候选生成器。它使用 PP-OCRv5 中文检测/识别模型和 ONNX Runtime CPU；模型下载后可断网推理，输入帧不上传到云端。全片批量默认使用 `mobile`，仅对低置信度或疑难帧使用 `server` 复核。

## 环境准备

默认在调用项目的当前目录使用 `.venv/`，不向系统 Python 安装：

```bash
.claude/skills/xvast-subtitle-capture/scripts/setup_paddleocr.sh
```

安装脚本会：

1. 当前目录没有 `.venv/bin/python` 时创建 `.venv/`。
2. 安装 `scripts/paddleocr-requirements.txt` 中固定的依赖。
3. 把 `mobile` 主模型和 `server` 复核模型都下载到当前目录 `.paddleocr-cache/`。
4. 运行 `pip check`。

访问 PyPI 不稳定时可指定镜像：

```bash
.../scripts/setup_paddleocr.sh \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

若项目明确要求已有 Conda 环境，跳过 `.venv`，显式传环境名：

```bash
.../scripts/setup_paddleocr.sh \
  --conda-env web-scrape \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

不要仅因机器存在某个 Conda 环境就自动使用；默认入口仍是当前目录 `.venv/`。若用户或项目明确指定一个已具备相同版本依赖且 Python ABI 兼容的 Conda 环境，可用该环境的 Python 创建带 `--system-site-packages` 的薄 `.venv`，经逐包路径与版本验证后复用；不得把不同 Python ABI 的 ONNX Runtime 等原生包直接复制或软链。依赖已满足时跳过重复安装。

## 优化后的全片流程

### 1. 建立帧时间索引

先从每批 `frames.json` 生成按媒体时间排序的输入清单。默认只纳入 `status: valid` 的批次：

```bash
python .claude/skills/xvast-subtitle-capture/scripts/build_paddleocr_frame_index.py \
  --batch-root 课程目录/.raw \
  --output-list 课程目录/.raw/paddleocr/frames.txt \
  --output-index 课程目录/.raw/paddleocr/frame-index.jsonl
```

时间索引优先使用每帧墙钟和批次实际倍速换算；缺少逐帧墙钟时才在批次媒体时间锚之间插值。生成后抽查首尾与批次边界。

正在排查旧材料时可临时加 `--include-pending`，但这些帧在进入正式时间线前仍须完成布局和批次有效性审核。`--include-invalid` 只用于诊断，不得用于正式稿。

### 2. 三帧 OCR smoke

正式批量前必须检查 3 张原图的裁切图和 `subtitle_texts`：

默认 `.venv`：

```bash
.claude/skills/xvast-subtitle-capture/scripts/paddleocr-subtitles \
  课程目录/.raw/paddleocr/frames.txt \
  -o 课程目录/.raw/paddleocr/smoke.jsonl \
  --max-images 3 --keep-crops
```

显式 Conda 环境仍使用同一命令前缀：

```bash
.../scripts/paddleocr-subtitles --conda-env web-scrape \
  课程目录/.raw/paddleocr/frames.txt \
  -o 课程目录/.raw/paddleocr/smoke.jsonl \
  --max-images 3 --keep-crops
```

三张裁切图必须只覆盖字幕附近，不应大量包含 IDE、PowerPoint 工具栏、播放器控件或图表正文。任一张不合格时显式传 `--crop x1,y1,x2,y2` 重做；不能直接开始全片。

### 3. 最多五路并行批量 OCR

使用封装脚本运行全片，默认并且最多 5 个进程：

```bash
.../scripts/paddleocr-parallel --conda-env web-scrape \
  课程目录/.raw/paddleocr/frames.txt \
  -o 课程目录/.raw/paddleocr/mobile \
  --workers 5 --dedupe-threshold 0.01
```

`--workers` 只允许 1–5；不得绕开上限同时启动更多 part。内存紧张时降为 2–4。脚本按时间连续分片，保证每个进程内部的相似帧去重仍按相邻时间工作，并为每个 part 保留结果、meta 和日志。

`0.01` 是已验证的密集采样候选阈值；更换布局、字号或截图方式后须重新用短样本确认。去重只用于 OCR 候选计算，跳过帧仍保留在结果中并由合并器延长上一事件，不能证明时间轴完整。

### 4. server 复核低置信度帧

先自动筛出 `subtitle_scores` 最低值小于 `0.70` 或执行失败的帧：

```bash
python .claude/skills/xvast-subtitle-capture/scripts/select_paddleocr_review.py \
  --ocr-results 课程目录/.raw/paddleocr/mobile-part-*.jsonl \
  --output-list 课程目录/.raw/paddleocr/server-review.txt
```

若人工查看时间线后发现异常空档，再加 `--include-empty` 生成专项清单；不要默认把所有无字幕帧交给 server。随后用单进程或少量进程运行：

```bash
.../scripts/paddleocr-subtitles --conda-env web-scrape \
  课程目录/.raw/paddleocr/server-review.txt \
  -o 课程目录/.raw/paddleocr/server-review.jsonl \
  --model-size server --dedupe-threshold 0
```

server 结果只有在候选非空且平均置信度达到合并阈值时自动替换 mobile 候选；其余事件继续标记 `needs_review`，不得静默删除。

### 5. 合并候选时间线

```bash
python .claude/skills/xvast-subtitle-capture/scripts/merge_paddleocr_timeline.py \
  --frame-index 课程目录/.raw/paddleocr/frame-index.jsonl \
  --ocr-results 课程目录/.raw/paddleocr/mobile-part-*.jsonl \
  --server-review 课程目录/.raw/paddleocr/server-review.jsonl \
  --output-jsonl 课程目录/.raw/paddleocr/subtitle-events.jsonl \
  --output-markdown 课程目录/.raw/paddleocr/subtitle-candidates.md
```

合并器按媒体时间排序、延长被去重帧、合并连续相同字幕，并过滤明确的应用控件文字。输出仍统一为 `ocr_only`；之后才进行事件级人工复核和 PPT 归页。

## 路径与输出

- 默认模型缓存：调用项目当前目录 `.paddleocr-cache/`。
- 可通过 `PADDLE_PDX_CACHE_HOME` 或 `--cache-dir` 覆盖。
- `--crop auto` 对已验证的 2154×1898 Xvast 布局裁取中央字幕带 `(500,1120)–(1650,1260)`；其他尺寸按底部区域裁切。坐标不是跨布局真理，每个新 `layout_profile` 都必须重做三帧 smoke，必要时显式覆盖。
- JSONL 的 `texts` 保留裁切区域全部 OCR；`subtitle_texts` 根据字幕纵向区域排除水印和播放器控件候选。
- 每条记录还包含 `ocr_model`、置信度、文本框、裁切坐标、差异分数和耗时；同目录 `.meta.json` 汇总批次状态。

OCR 结果一律为 `ocr_only`。必须结合原始帧、视频时间锚和人工目视审核后，才能升级字幕事件状态。
