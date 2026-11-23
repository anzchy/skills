"""Pick the subtitle pieces out of one paddleocr-subtitles row, optionally dropping short (small-font) text boxes.

`subtitle_texts` is the band-filtered subset of `texts`, in the same order; `boxes` belong to `texts`. With a minimum
height, each subtitle piece is matched back to its box and kept only when the box is at least that tall, which drops
interface text (status bars, taskbar search boxes) that sits behind a burned-in subtitle in a screen share.
"""


def subtitle_pieces(row, min_height=None):
    pieces = list(zip(row.get("subtitle_texts", []), row.get("subtitle_scores", [])))
    if not min_height:
        return pieces
    texts, boxes = row.get("texts", []), row.get("boxes", [])
    kept, cursor = [], 0
    for text, score in pieces:
        while cursor < len(texts) and texts[cursor] != text and str(texts[cursor]).strip() != str(text).strip():
            cursor += 1
        if cursor >= len(texts) or cursor >= len(boxes):
            continue
        box = boxes[cursor]
        cursor += 1
        if box[3] - box[1] >= min_height:
            kept.append((text, score))
    return kept
