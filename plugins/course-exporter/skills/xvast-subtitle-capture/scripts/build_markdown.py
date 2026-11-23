#!/usr/bin/env python3
"""Assemble reviewed slides and verbatim cues; does not capture or OCR anything."""
import argparse
import html
import itertools
import json
import re
from pathlib import Path
from PIL import Image


def timecode(ms):
    seconds, millis = divmod(ms, 1000)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}'
    return f'{minutes:02d}:{seconds:02d}.{millis:03d}'


def inline(s):
    return re.sub(r'([\\`*_\[\]<>#!|])', r'\\\1', str(s).replace('\n', ' '))


def display_time(ms):
    seconds = ms // 1000
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def prose(text):
    value = html.escape(text, quote=False)
    value = re.sub(r'([\\`*_\[\]#!|])', r'\\\1', value)
    return re.sub(r'^(\d+)\.', r'\1\\.', value)


def join_cues(cues):
    parts = []
    for cue in cues:
        text = re.sub(r'\s*\n\s*', ' ', cue['text']).strip()
        if parts and not re.search(r'[，。！？；：,.!?;:]$', parts[-1]):
            parts[-1] += '，'
        parts.append(text)
    text = ''.join(parts)
    if text and not re.search(r'[。！？.!?]$', text):
        text += '。'
    return text


def short_paragraphs(text):
    """Keep accepted 1/2/3-paragraph defaults; prefer balanced transition cuts."""
    n = 1 if len(text) <= 220 else 2 if len(text) <= 480 else 3
    if n == 1:
        return [text]
    candidates, depth = [], 0
    for i, char in enumerate(text):
        if char in '（([{':
            depth += 1
        elif char in '）)]}':
            depth = max(0, depth - 1)
        if char in '，。！？；' and depth == 0 and 60 < i < len(text) - 60:
            candidates.append(i + 1)
    if len(candidates) < n - 1:
        return [text]  # Do not cut words to force a paragraph count.
    target = len(text) / n
    pools = []
    for k in range(1, n):
        pool = [x for x in candidates if abs(x - target * k) <= target * .55]
        pools.append(pool or sorted(candidates, key=lambda x: abs(x - target * k))[:5])
    transitions = ('接下来', '那么', '但是', '所以', '因此', '比如说', '比如', '也就是说',
                   '换句话说', '首先', '其次', '最后', '另一方面', '我们今天', '然后呢')
    best = None
    for cuts in itertools.product(*pools):
        if tuple(sorted(set(cuts))) != cuts:
            continue
        positions = (0,) + cuts + (len(text),)
        lengths = [b - a for a, b in zip(positions, positions[1:])]
        if min(lengths) < 65:
            continue
        score = sum(((length - target) / target) ** 2 for length in lengths)
        for x in cuts:
            after = text[x:].lstrip()
            if text[x - 1] in '。！？':
                score -= .25
            if after.startswith(transitions):
                score -= .28
            elif after.startswith(('然后', '另外', '对吧', '好', '那我们')):
                score -= .10
        if best is None or score < best[0]:
            best = (score, positions)
    if best is None:
        return [text]
    parts = [text[a:b].strip() for a, b in zip(best[1], best[1][1:])]
    for i in range(len(parts) - 1):
        if parts[i].endswith('，'):
            parts[i] = parts[i][:-1] + '。'
    return parts


def time_blocks(cues, visits):
    blocks, current = [], []
    for cue in sorted(cues, key=lambda c: (c['start_ms'], c['end_ms'])):
        if current and (
            max(cue['end_ms'], max(c['end_ms'] for c in current)) - current[0]['start_ms'] > 180000
            or cue['start_ms'] - max(c['end_ms'] for c in current) > 12000
            or visits[cue['id']] != visits[current[-1]['id']]
            or cue.get('visit_id') != current[-1].get('visit_id')
            or cue.get('break_before') is True
        ):
            blocks.append(current)
            current = []
        current.append(cue)
    if current:
        blocks.append(current)
    return blocks


def build(manifest, output, prefix='ppt'):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', prefix):
        raise ValueError('Asset prefix must be a flat filename prefix')
    if output.suffix.lower() != '.md':
        raise ValueError('Output must be .md')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    duration = data['duration_ms']
    if type(duration) is not int or duration <= 0:
        raise ValueError('Positive integer duration_ms required')
    slides, cues = data['slides'], data['cues']
    if not cues:
        raise ValueError('No captured subtitles; do not fabricate a document')
    by_slide = {}
    images = []
    assets = output.parent / 'assets'
    if assets.is_symlink():
        raise ValueError('assets must be a real local directory')
    for i, slide in enumerate(slides, 1):
        sid = slide['id']
        if not isinstance(sid, str) or not sid or sid in by_slide:
            raise ValueError('Nonempty unique slide IDs required')
        by_slide[sid] = []
        source = slide.get('image')
        if source:
            image_review = slide.get('image_review')
            if image_review not in ('complete', 'fallback_original'):
                raise ValueError('Slide image must be complete or fallback_original')
            if slide.get('candidate_type') not in (None, 'full_slide', 'editor_canvas'):
                raise ValueError(f'Invalid PPT candidate type for complete image: {sid}')
            source = Path(source)
            if not source.is_absolute():
                source = manifest.parent / source
            with Image.open(source) as im:
                im.verify()
            images.append((sid, source, assets / f'{prefix}-{i:03d}.png', image_review))
    ids = set()
    uncertain = []
    unassigned = []
    for cue in cues:
        cid = cue['id']
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ValueError('Nonempty unique cue IDs required')
        ids.add(cid)
        start, end = cue['start_ms'], cue['end_ms']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration:
            raise ValueError(f'Invalid times: {cid}')
        if not isinstance(cue.get('text'), str) or not cue['text'].strip():
            raise ValueError(f'Empty subtitle: {cid}')
        if cue.get('review') not in ('verified', 'uncertain') or not str(cue.get('evidence', '')).strip():
            raise ValueError(f'Review and evidence required: {cid}')
        if cue['review'] != 'verified':
            uncertain.append(cid)
        sid = cue.get('slide_id')
        if sid is not None and sid not in by_slide:
            raise ValueError(f'Unknown slide: {sid}')
        (unassigned if sid is None else by_slide[sid]).append(cue)
    coverage = data['coverage']
    gaps = coverage.get('gaps', [])
    for gap in gaps:
        start, end = gap['start_ms'], gap['end_ms']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration or not str(gap.get('reason', '')).strip():
            raise ValueError('Invalid coverage gap')
    capture_coverage = coverage.get('capture_coverage')
    if capture_coverage is None:
        capture_coverage = 'complete' if coverage.get('full_timeline_reviewed') is True else 'incomplete'
    if capture_coverage not in ('complete', 'incomplete'):
        raise ValueError('coverage.capture_coverage must be complete or incomplete')
    cue_text_review = coverage.get('cue_text_review', 'visual_reviewed' if coverage.get('full_timeline_reviewed') is True else 'ocr_only')
    if cue_text_review not in ('ocr_only', 'visual_reviewed', 'manual_exact'):
        raise ValueError('Invalid coverage.cue_text_review')
    word_exact = coverage.get('word_for_word_manual_review', cue_text_review == 'manual_exact')
    if type(word_exact) is not bool or (word_exact and cue_text_review != 'manual_exact'):
        raise ValueError('word_for_word_manual_review requires cue_text_review=manual_exact')
    capture_complete = capture_coverage == 'complete' and bool(str(coverage.get('evidence', '')).strip()) and not gaps
    targets = [output] + [item[2] for item in images]
    if any(p.exists() for p in targets):
        raise FileExistsError('Refusing to overwrite document or attachments')
    review_labels = {
        'ocr_only': '仅完成 OCR 候选生成，文字尚未逐事件目视核对。',
        'visual_reviewed': '已对照字幕画面目视核对；非逐字人工听写，仍可能保留个别识别错误。',
        'manual_exact': '已逐事件进行逐字人工核对。',
    }
    complete_images = sum(item[3] == 'complete' for item in images)
    fallback_images = sum(item[3] == 'fallback_original' for item in images)
    agreed = sum(c.get('review_basis') == 'ocr_agreement' for c in cues)
    review_text = review_labels[cue_text_review]
    if agreed and cue_text_review == 'visual_reviewed':
        review_text = (f'{len(cues)} 条中 {len(cues) - agreed} 条已对照字幕画面目视核对，{agreed} 条按 OCR 一致接受、未逐条目视；'
                       '非逐字人工听写，仍可能保留个别识别错误。')
    if capture_complete:
        timeline_text = '已完成全时段复核。'
    elif gaps:
        total = sum(g['end_ms'] - g['start_ms'] for g in gaps) / 1000
        timeline_text = f'共 {len(gaps)} 处未采集区段，合计 {total:g} 秒（见文末「字幕缺口」），不能认定为全片时间轴完整。'
    else:
        timeline_text = '待补全/核验，不能认定为全片时间轴完整。'
    lines = [f'# {inline(data["title"])}', '',
             f'视频时长：{timecode(duration)}；字幕事件：{len(cues)} 条；PPT 图片：{len(images)} 张（完整无遮挡 {complete_images} 张，原图回退 {fallback_images} 张）。', '',
             '字幕时间轴覆盖：' + timeline_text, '',
             '字幕文字校核：' + review_text +
             (f'；其中 {len(uncertain)} 条事件仍待核验。' if uncertain else ''), '',
             '覆盖依据：' + inline(coverage.get('evidence', '未提供全时段复核依据。')), '']
    lines.extend(['排版说明：约 3 分钟为一个时间块，只在块首标注时间范围；长块内按话题转折拆为 2–3 个短段，短内容不强拆。保留字幕原词和顺序，仅调整连接标点和段末标点。', ''])
    image_map = {sid: dest.name for sid, source, dest, review in images}
    image_reviews = {sid: review for sid, source, dest, review in images}
    rendered = []
    visits, visit, previous_slide = {}, 0, object()
    for cue in sorted(cues, key=lambda c: (c['start_ms'], c['end_ms'])):
        if cue.get('slide_id') != previous_slide:
            visit += 1
        visits[cue['id']] = visit
        previous_slide = cue.get('slide_id')
    layout_counts = {'time_blocks': 0, 'paragraphs': 0}
    def render_cues(group):
        for block in time_blocks(group, visits):
            start = block[0]['start_ms']
            end = max(c['end_ms'] for c in block)
            uncertain_block = any(c['review'] != 'verified' for c in block)
            lines.extend([f'**约 {display_time(start)}–{display_time(end)}**' +
                          ('（本时间块含待核验字幕）' if uncertain_block else ''), ''])
            paragraphs = short_paragraphs(join_cues(block))
            for paragraph in paragraphs:
                lines.extend([prose(paragraph), ''])
            rendered.extend(c['id'] for c in block)
            layout_counts['time_blocks'] += 1
            layout_counts['paragraphs'] += len(paragraphs)
    for i, slide in enumerate(slides, 1):
        lines.extend([f'## {i:02d} {inline(slide["title"])}', ''])
        if slide['id'] in image_map:
            lines.extend([f'![{inline(slide["title"])}](assets/{image_map[slide["id"]]})', ''])
            if image_reviews[slide['id']] == 'fallback_original':
                reason = inline(slide.get('fallback_reason', '未找到完整无遮挡的替代帧，保留原图片。'))
                lines.extend([f'> 图片说明：原图回退。{reason}', ''])
        else:
            lines.extend(['未获得完整 PPT 截图。', ''])
        lines.extend(['### 对应字幕', ''])
        render_cues(by_slide[slide['id']])
        if not by_slide[slide['id']]:
            lines.extend(['没有已归属到本页的字幕记录。', ''])
    if unassigned:
        lines.extend(['## 未归属字幕（待确认）', ''])
        render_cues(unassigned)
    if gaps:
        lines.extend(['## 字幕缺口', ''])
        for gap in gaps:
            lines.extend([f'- {timecode(gap["start_ms"])}–{timecode(gap["end_ms"])}：{inline(gap["reason"])}'])
    if len(rendered) != len(cues) or set(rendered) != ids:
        raise AssertionError('Cue loss or duplication')
    output.parent.mkdir(parents=True, exist_ok=True)
    assets.mkdir(exist_ok=True)
    for sid, source, dest, review in images:
        with Image.open(source) as im:
            im.convert('RGB').save(dest)
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'document': str(output), 'images': len(images), 'cues': len(cues),
            'capture_coverage_complete': capture_complete, 'cue_text_review': cue_text_review,
            'word_for_word_manual_review': word_exact, 'unassigned': len(unassigned), **layout_counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path, help='Reviewed capture JSON; image paths relative to this file')
    parser.add_argument('--output', required=True, type=Path, help='Markdown output file; attachments go directly in sibling assets/')
    parser.add_argument('--asset-prefix', default='ppt', help='Flat PNG filename prefix; default ppt')
    args = parser.parse_args()
    print(json.dumps(build(args.manifest.resolve(), args.output.resolve(), args.asset_prefix), ensure_ascii=False))
