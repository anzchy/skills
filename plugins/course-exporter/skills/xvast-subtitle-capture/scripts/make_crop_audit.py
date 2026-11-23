#!/usr/bin/env python3
"""Build crop-context and final-bottom contact sheets for manual PPT edge review."""
import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


def resolve(path, base):
    value = Path(path)
    return value if value.is_absolute() else base / value


def contact_sheets(tiles, output, prefix, tile_height):
    paths = []
    for page, start in enumerate(range(0, len(tiles), 20), 1):
        sheet = Image.new('RGB', (1600, tile_height * 5), '#dddddd')
        for index, tile in enumerate(tiles[start:start + 20]):
            sheet.paste(tile, ((index % 4) * 400, (index // 4) * tile_height))
        path = output / f'{prefix}-{page:02d}.jpg'
        sheet.save(path, quality=92)
        paths.append(str(path))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--document', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--buffer', type=int, default=24)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    document = args.document.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    links = re.findall(r'!\[[^]]*\]\((assets/[^)]+)\)', document.read_text(encoding='utf-8'))
    slides = [slide for slide in data.get('slides', []) if slide.get('image')]
    errors, records, sources, contexts, bottoms = [], [], [], [], []
    if len(links) != len(slides):
        errors.append('Markdown image count does not match imaged slides')
    for index, slide in enumerate(slides):
        sid = slide.get('id', f'slide-{index + 1}')
        source_value, crop = slide.get('source'), slide.get('crop_box')
        subtitle_bounds = slide.get('subtitle_bounds', (slide.get('crop_review') or {}).get('subtitle_bounds'))
        if not source_value or not isinstance(crop, list) or len(crop) != 4:
            errors.append(f'{sid}: missing source or four-value crop_box')
            continue
        source = resolve(source_value, manifest.parent)
        if not source.exists():
            errors.append(f'{sid}: missing source {source}')
            continue
        try:
            with Image.open(source) as image:
                image = image.convert('RGB')
                width, height = image.size
                x0, y0, x1, y1 = map(int, crop)
                if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                    errors.append(f'{sid}: crop_box outside source dimensions')
                    continue
                bx0, by0 = max(0, x0 - args.buffer), max(0, y0 - args.buffer)
                bx1, by1 = min(width, x1 + args.buffer), min(height, y1 + args.buffer)
                context = image.crop((bx0, by0, bx1, by1))
                draw = ImageDraw.Draw(context)
                draw.rectangle((x0 - bx0, y0 - by0, x1 - bx0 - 1, y1 - by0 - 1), outline='#ff2020', width=3)
                if subtitle_bounds is not None:
                    if (not isinstance(subtitle_bounds, list) or len(subtitle_bounds) != 4
                            or not all(type(value) is int for value in subtitle_bounds)):
                        errors.append(f'{sid}: invalid subtitle_bounds')
                        continue
                    tx0, ty0, tx1, ty1 = subtitle_bounds
                    if not (0 <= tx0 < tx1 <= width and 0 <= ty0 < ty1 <= height):
                        errors.append(f'{sid}: subtitle_bounds outside source dimensions')
                        continue
                    draw.rectangle((tx0 - bx0, ty0 - by0, tx1 - bx0 - 1, ty1 - by0 - 1),
                                   outline='#2070ff', width=3)
                context_path = output / f'context-{sid}.jpg'
                context.save(context_path, quality=94)
                source_preview = image.copy()
                source_draw = ImageDraw.Draw(source_preview)
                for key, color in (("player_bounds", "#00a000"),
                                   ("video_content_bounds", "#0070ff")):
                    bounds = (slide.get("viewport_review") or {}).get(key)
                    if isinstance(bounds, list) and len(bounds) == 4:
                        source_draw.rectangle(tuple(bounds), outline=color, width=4)
                slide_bounds = (slide.get("crop_review") or {}).get("slide_bounds")
                if isinstance(slide_bounds, list) and len(slide_bounds) == 4:
                    source_draw.rectangle(tuple(slide_bounds), outline="#ff8c00", width=4)
                source_draw.rectangle(tuple(crop), outline="#ff2020", width=4)
                source_preview.thumbnail((384, 216))
                source_tile = Image.new('RGB', (400, 248), 'white')
                source_tile.paste(source_preview, ((400 - source_preview.width) // 2, 22))
                ImageDraw.Draw(source_tile).text((6, 3), f'{sid} full source: player green, video blue, slide orange, crop red', fill='black')
                sources.append(source_tile)
                thumb = context.copy(); thumb.thumbnail((384, 216))
                tile = Image.new('RGB', (400, 248), 'white')
                tile.paste(thumb, ((400 - thumb.width) // 2, 22))
                ImageDraw.Draw(tile).text((6, 3),
                                          f'{sid} source {width}x{height} crop {crop} subtitle {subtitle_bounds}',
                                          fill='black')
                contexts.append(tile)
        except Exception as exc:
            errors.append(f'{sid}: cannot open source: {exc}')
            continue
        final_path = document.parent / links[index] if index < len(links) else None
        if not final_path or not final_path.exists():
            errors.append(f'{sid}: missing final asset')
            continue
        with Image.open(final_path) as final:
            final = final.convert('RGB')
            strip_height = max(40, round(final.height * .18))
            bottom = final.crop((0, final.height - strip_height, final.width, final.height))
            bottom = bottom.resize((384, 180))
            tile = Image.new('RGB', (400, 214), 'white')
            tile.paste(bottom, (8, 24))
            ImageDraw.Draw(tile).text((6, 3), f'{sid} final bottom 18%', fill='black')
            bottoms.append(tile)
            records.append({'id': sid, 'source': str(source), 'source_dimensions': [width, height],
                            'crop_box': crop, 'final_asset': str(final_path),
                            'subtitle_bounds': subtitle_bounds,
                            'final_dimensions': list(final.size), 'context': str(context_path)})
    result = {'slides_checked': len(records), 'errors': errors,
              'source_sheets': contact_sheets(sources, output, 'full-source', 248),
              'context_sheets': contact_sheets(contexts, output, 'crop-context', 248),
              'bottom_sheets': contact_sheets(bottoms, output, 'final-bottom', 214)}
    (output / 'crop-audit.json').write_text(json.dumps({'result': result, 'slides': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
