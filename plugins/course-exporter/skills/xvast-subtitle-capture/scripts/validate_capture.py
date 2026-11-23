#!/usr/bin/env python3
"""Validate a reviewed Xvast manifest, generated Markdown, assets, and optional batch logs."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from PIL import Image


def fail(errors, message):
    errors.append(message)


def validate_manifest(path, errors, require_crop_review=False, require_viewport_review=False):
    data = json.loads(path.read_text(encoding='utf-8'))
    duration = data.get('duration_ms')
    if type(duration) is not int or duration <= 0:
        fail(errors, 'duration_ms must be a positive integer')
        duration = 0
    slides, cues = data.get('slides', []), data.get('cues', [])
    slide_ids = [s.get('id') for s in slides]
    if any(not isinstance(x, str) or not x for x in slide_ids) or len(slide_ids) != len(set(slide_ids)):
        fail(errors, 'slide IDs must be nonempty and unique')
    allowed_slides = set(slide_ids)
    crop_reviews = 0
    fallback_reviews = 0
    for slide in slides:
        if slide.get('image') and require_viewport_review:
            sid = slide.get('id')
            viewport = slide.get('viewport_review')
            if not isinstance(viewport, dict):
                fail(errors, f'slide {sid} missing viewport_review')
            else:
                required_true = ('player_top_visible', 'player_bottom_visible',
                                 'player_left_visible', 'player_right_visible',
                                 'controls_visible', 'source_slide_complete')
                for key in required_true:
                    if viewport.get(key) is not True:
                        fail(errors, f'slide {sid} viewport_review does not confirm {key}')
                for key in ('window_dimensions', 'player_bounds', 'video_content_bounds'):
                    value = viewport.get(key)
                    expected = 2 if key == 'window_dimensions' else 4
                    if (not isinstance(value, list) or len(value) != expected
                            or not all(type(item) is int for item in value)):
                        fail(errors, f'slide {sid} viewport_review has invalid {key}')
                if viewport.get('scroll_state') != 'player_fully_in_view':
                    fail(errors, f'slide {sid} viewport_review has unsafe scroll_state')
                if not str(viewport.get('evidence', '')).strip():
                    fail(errors, f'slide {sid} viewport_review lacks evidence')
        image_review = slide.get('image_review')
        if slide.get('image') and image_review not in ('complete', 'fallback_original'):
            fail(errors, f"slide {slide.get('id')} has an invalid image_review")
        if slide.get('image') and slide.get('candidate_type') not in (None, 'full_slide', 'editor_canvas'):
            fail(errors, f"slide {slide.get('id')} uses a rejected candidate type")
        if slide.get('image') and require_crop_review and image_review == 'fallback_original':
            sid = slide.get('id')
            if not str(slide.get('fallback_reason', '')).strip():
                fail(errors, f'slide {sid} fallback lacks fallback_reason')
            gaps = slide.get('known_crop_gaps')
            if not isinstance(gaps, (str, list)) or not gaps:
                fail(errors, f'slide {sid} fallback lacks known_crop_gaps')
            if slide.get('fallback_preserves_core_content') is not True:
                fail(errors, f'slide {sid} fallback does not confirm preserved core content')
            review = slide.get('crop_review')
            if not isinstance(review, dict) or review.get('subtitle_edge') != 'verified_full':
                fail(errors, f'slide {sid} does not verify complete subtitle edge')
            has_bounds, subtitle_bounds = find_subtitle_bounds(slide, review)
            if not has_bounds:
                fail(errors, f'slide {sid} missing subtitle_bounds')
            if subtitle_bounds is not None and (not isinstance(subtitle_bounds, list)
                                                or len(subtitle_bounds) != 4
                                                or not all(type(value) is int for value in subtitle_bounds)):
                fail(errors, f'slide {sid} has invalid subtitle_bounds')
            crop = slide.get('crop_box')
            if isinstance(subtitle_bounds, list) and isinstance(crop, list) and len(crop) == 4:
                sx0, sy0, sx1, sy1 = subtitle_bounds
                cx0, cy0, cx1, cy1 = crop
                if not (cx0 <= sx0 < sx1 <= cx1 and cy0 <= sy0 < sy1 <= cy1):
                    fail(errors, f'slide {sid} crop_box does not contain subtitle_bounds')
            if isinstance(review, dict) and (review.get('bottom_edge') == 'verified_full'
                                             or review.get('content_edges') == 'verified_full'):
                fail(errors, f'slide {sid} fallback incorrectly claims verified_full')
            fallback_reviews += 1
        elif slide.get('image') and require_crop_review:
            sid = slide.get('id')
            review = slide.get('crop_review')
            if not isinstance(review, dict):
                fail(errors, f'slide {sid} missing crop_review')
                continue
            dimensions = review.get('source_dimensions')
            bounds = review.get('slide_bounds')
            crop = slide.get('crop_box')
            valid_lists = all(isinstance(value, list) and len(value) in (2, 4)
                              for value in (dimensions, bounds, crop))
            if not valid_lists or len(dimensions) != 2 or len(bounds) != 4 or len(crop) != 4:
                fail(errors, f'slide {sid} has invalid crop review geometry')
                continue
            if not all(type(value) is int for value in dimensions + bounds + crop):
                fail(errors, f'slide {sid} crop review geometry must use integers')
                continue
            width, height = dimensions
            sx0, sy0, sx1, sy1 = bounds
            cx0, cy0, cx1, cy1 = crop
            if not (width > 0 and height > 0 and 0 <= cx0 <= sx0 < sx1 <= cx1 <= width
                    and 0 <= cy0 <= sy0 < sy1 <= cy1 <= height):
                fail(errors, f'slide {sid} crop_box does not contain reviewed slide_bounds')
            if review.get('bottom_edge') != 'verified_full' or review.get('content_edges') != 'verified_full':
                fail(errors, f'slide {sid} crop edges are not verified_full')
            if review.get('subtitle_edge') != 'verified_full':
                fail(errors, f'slide {sid} does not verify complete subtitle edge')
            has_bounds, subtitle_bounds = find_subtitle_bounds(slide, review)
            if not has_bounds:
                fail(errors, f'slide {sid} missing subtitle_bounds')
            if subtitle_bounds is not None:
                if (not isinstance(subtitle_bounds, list) or len(subtitle_bounds) != 4
                        or not all(type(value) is int for value in subtitle_bounds)):
                    fail(errors, f'slide {sid} has invalid subtitle_bounds')
                else:
                    tx0, ty0, tx1, ty1 = subtitle_bounds
                    if not (cx0 <= tx0 < tx1 <= cx1 and cy0 <= ty0 < ty1 <= cy1):
                        fail(errors, f'slide {sid} crop_box does not contain subtitle_bounds')
            if not str(review.get('evidence', '')).strip():
                fail(errors, f'slide {sid} crop review lacks evidence')
            crop_reviews += 1
    cue_ids = [c.get('id') for c in cues]
    if any(not isinstance(x, str) or not x for x in cue_ids) or len(cue_ids) != len(set(cue_ids)):
        fail(errors, 'cue IDs must be nonempty and unique')
    uncertain = 0
    for cue in cues:
        cid = cue.get('id')
        start, end = cue.get('start_ms'), cue.get('end_ms')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration:
            fail(errors, f'invalid cue time range: {cid}')
        if cue.get('slide_id') is not None and cue.get('slide_id') not in allowed_slides:
            fail(errors, f'unknown slide_id in cue {cid}')
        if cue.get('review') not in ('verified', 'uncertain') or not str(cue.get('evidence', '')).strip():
            fail(errors, f'missing review/evidence in cue {cid}')
        uncertain += cue.get('review') != 'verified'
    coverage = data.get('coverage', {})
    capture = coverage.get('capture_coverage')
    if capture is None:
        capture = 'complete' if coverage.get('full_timeline_reviewed') is True else 'incomplete'
    review = coverage.get('cue_text_review', 'visual_reviewed' if coverage.get('full_timeline_reviewed') is True else 'ocr_only')
    exact = coverage.get('word_for_word_manual_review', review == 'manual_exact')
    gaps = coverage.get('gaps', [])
    if capture not in ('complete', 'incomplete'):
        fail(errors, 'invalid capture_coverage')
    if review not in ('ocr_only', 'visual_reviewed', 'manual_exact'):
        fail(errors, 'invalid cue_text_review')
    if exact and review != 'manual_exact':
        fail(errors, 'word_for_word_manual_review requires manual_exact')
    if capture == 'complete' and (gaps or not str(coverage.get('evidence', '')).strip()):
        fail(errors, 'complete coverage conflicts with gaps or missing evidence')
    if exact and uncertain:
        fail(errors, 'word-for-word manual review conflicts with uncertain cues')
    return data, {'slides': len(slides), 'cues': len(cues), 'uncertain': uncertain,
                  'capture_coverage': capture, 'cue_text_review': review,
                  'word_for_word_manual_review': exact, 'gaps': len(gaps),
                  'crop_review_required': require_crop_review,
                  'viewport_review_required': require_viewport_review,
                  'crop_reviews': crop_reviews,
                  'fallback_reviews': fallback_reviews}


def validate_source_assets(data, manifest_path, assets, errors):
    """Check physical image evidence; self-reported review booleans are insufficient."""
    checked = 0
    for number, slide in enumerate(data.get('slides', []), 1):
        if not slide.get('image'):
            continue
        sid = slide.get('id', f'slide-{number}')
        value = slide.get('source')
        if not value:
            fail(errors, f'slide {sid} has no source frame')
            continue
        source = Path(value)
        if not source.is_absolute():
            source = manifest_path.parent / source
        if '.raw' not in source.parts:
            fail(errors, f'slide {sid} source is not an original frame under .raw')
            continue
        if not source.is_file():
            fail(errors, f'slide {sid} source frame does not exist: {source}')
            continue
        target = assets / f'ppt-{number:03d}.png'
        if not target.is_file():
            fail(errors, f'slide {sid} final crop does not exist: {target}')
            continue
        box = slide.get('crop_box')
        review = slide.get('crop_review') or {}
        viewport = slide.get('viewport_review') or {}
        try:
            with Image.open(source) as original, Image.open(target) as final:
                width, height = original.size
                if review.get('source_dimensions') != [width, height] or viewport.get('window_dimensions') != [width, height]:
                    fail(errors, f'slide {sid} reviewed dimensions differ from actual source')
                    continue
                if not isinstance(box, list) or len(box) != 4 or not all(type(v) is int for v in box):
                    fail(errors, f'slide {sid} has invalid crop_box')
                    continue
                x0, y0, x1, y1 = box
                if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                    fail(errors, f'slide {sid} crop_box is outside actual source')
                    continue
                if final.size != (x1 - x0, y1 - y0):
                    fail(errors, f'slide {sid} final dimensions do not match crop_box')
                    continue
                if original.crop(tuple(box)).convert('RGB').tobytes() != final.convert('RGB').tobytes():
                    fail(errors, f'slide {sid} final image is not the reviewed source crop')
                    continue
                checked += 1
        except Exception as exc:
            fail(errors, f'slide {sid} cannot inspect source/final image: {exc}')
    return {'source_assets_verified': checked}


def validate_document(data, document, assets, errors):
    text = document.read_text(encoding='utf-8')
    links = re.findall(r'!\[[^]]*\]\((assets/[^)]+)\)', text)
    expected = sum(bool(s.get('image')) for s in data.get('slides', []))
    if len(links) != expected or len(set(links)) != len(links):
        fail(errors, 'Markdown image links do not match unique reviewed slide images')
    if not assets.is_dir() or assets.is_symlink():
        fail(errors, 'assets must be a real local directory')
        return {'images': 0, 'time_blocks': 0, 'max_block_seconds': 0}
    nested = [p for p in assets.rglob('*') if p.is_file() and p.parent != assets]
    if nested:
        fail(errors, 'assets contains nested files')
    files, hashes = [], []
    for link in links:
        path = document.parent / link
        if not path.exists() or path.parent != assets:
            fail(errors, f'missing or non-flat asset: {link}')
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            fail(errors, f'invalid image {link}: {exc}')
            continue
        files.append(path)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    if len(hashes) != len(set(hashes)):
        fail(errors, 'duplicate image contents found in final assets')
    blocks = re.findall(r'\*\*约 (\d+):(\d+)–(\d+):(\d+)\*\*', text)
    durations = [(int(c) * 60 + int(d)) - (int(a) * 60 + int(b)) for a, b, c, d in blocks]
    if any(x < 0 or x > 180 for x in durations):
        fail(errors, 'a time block is negative or exceeds 180 seconds')
    return {'images': len(files), 'time_blocks': len(blocks),
            'max_block_seconds': max(durations, default=0)}


EDGE_KEYS = ('player_top_visible', 'player_bottom_visible', 'player_left_visible', 'player_right_visible')


def four_edges_confirmed(viewport):
    """True when the review says all four player edges are visible, in either accepted spelling."""
    if viewport.get('four_edges_visible') is True:
        return True
    return all(viewport.get(key) is True for key in EDGE_KEYS)


def find_subtitle_bounds(slide, review):
    """Return (present, value). The slide-level key wins; crop_review is accepted for older manifests."""
    if 'subtitle_bounds' in slide:
        return True, slide['subtitle_bounds']
    if isinstance(review, dict) and 'subtitle_bounds' in review:
        return True, review['subtitle_bounds']
    return False, None


def batch_paths(root, batch_list=None):
    if batch_list is None:
        return sorted(set(root.rglob('manifest.json')) | set(root.rglob('frames.json')))
    names = [line.strip() for line in batch_list.read_text(encoding='utf-8').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    return [root / name / 'frames.json' for name in names]


def validate_batches(root, errors, require_viewport_review=False, batch_list=None):
    checked = invalid = 0
    paths = batch_paths(root, batch_list)
    if not paths:
        fail(errors, f'no batch logs found under {root}')
    for path in paths:
        if not path.is_file():
            fail(errors, f'listed batch log not found: {path}')
            continue
        item = json.loads(path.read_text(encoding='utf-8'))
        required = ('video_start_ms', 'video_end_ms', 'wall_start_ms', 'wall_end_ms',
                    'playback_rate', 'frame_count', 'layout_profile', 'status')
        if not all(key in item for key in required):
            fail(errors, f'batch log missing integrity fields: {path}')
            continue
        if item['status'] == 'invalid':
            invalid += 1
            continue
        if item['status'] == 'pending_manual_review':
            fail(errors, f'batch still pending manual review: {path}')
            continue
        if item['status'] != 'valid':
            fail(errors, f'unknown batch status: {path}')
            continue
        if require_viewport_review:
            viewport = item.get('viewport_review')
            if (not isinstance(viewport, dict)
                    or not four_edges_confirmed(viewport)
                    or viewport.get('controls_visible') is not True
                    or viewport.get('scroll_state') != 'player_fully_in_view'
                    or not str(viewport.get('evidence', '')).strip()):
                fail(errors, f'batch lacks valid viewport_review: {path}')
        expected = (item['wall_end_ms'] - item['wall_start_ms']) * item['playback_rate']
        actual = item['video_end_ms'] - item['video_start_ms']
        tolerance = max(3000, expected * .05)
        if expected <= 0 or actual <= 0 or abs(actual - expected) > tolerance:
            fail(errors, f'batch progress mismatch: {path}')
        if type(item['frame_count']) is not int or item['frame_count'] <= 0:
            fail(errors, f'invalid frame_count: {path}')
        checked += 1
    return {'valid_batches_checked': checked, 'invalid_batches_ignored': invalid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--document', type=Path)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--batch-root', type=Path)
    parser.add_argument('--batch-list', type=Path,
                        help='text file of batch directory names under --batch-root; only these are validated')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--require-crop-review', action='store_true',
                        help='require per-slide source geometry and verified crop edges')
    parser.add_argument('--require-viewport-review', action='store_true',
                        help='require proof that the full player and all four PPT edges are visible in each source')
    parser.add_argument('--require-source-assets', action='store_true',
                        help='verify source files, actual dimensions and exact source-to-final crop pixels')
    args = parser.parse_args()
    errors = []
    data, result = validate_manifest(args.manifest.resolve(), errors,
                                     args.require_crop_review, args.require_viewport_review)
    if args.document:
        document = args.document.resolve()
        assets = args.assets.resolve() if args.assets else document.parent / 'assets'
        result.update(validate_document(data, document, assets, errors))
        if args.require_source_assets:
            result.update(validate_source_assets(data, args.manifest.resolve(), assets, errors))
    elif args.require_source_assets:
        fail(errors, '--require-source-assets requires --document')
    if args.batch_root:
        result.update(validate_batches(args.batch_root.resolve(), errors,
                                       args.require_viewport_review, args.batch_list))
    elif args.batch_list:
        fail(errors, '--batch-list requires --batch-root')
    result.update({'status': 'passed' if not errors else 'failed', 'errors': errors})
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.resolve().write_text(payload + '\n', encoding='utf-8')
    print(payload)
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
