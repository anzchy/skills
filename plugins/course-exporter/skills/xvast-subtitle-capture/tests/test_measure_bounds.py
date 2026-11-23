from PIL import Image, ImageDraw

PAGE = (221, 221, 221)
BROWN = (150, 100, 90)
CARD = (252, 252, 252)
BOX = (70, 70, 70)
WHITE = (255, 255, 255)


def synthetic_frame(path, dx=0, subtitle=True, icons=False, title=False, axis_label=False):
    """400x300 window. Video (black) x20..380 y20..260; slide x60..340 y40..230; white card above the subtitle."""
    image = Image.new("RGB", (400, 300), PAGE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20 + dx, 20, 379 + dx, 259), fill=(0, 0, 0))
    draw.rectangle((60 + dx, 40, 339 + dx, 229), fill=BROWN)
    draw.rectangle((70 + dx, 50, 329 + dx, 188), fill=CARD)
    if title:  # large white title on a dark band inside the slide: dense text-like pixels far from the subtitle
        draw.rectangle((80, 60, 320, 100), fill=(60, 40, 40))
        for x in range(90, 300, 10):
            draw.rectangle((x + dx, 64, x + 7 + dx, 96), fill=WHITE)
    if subtitle:  # as in real frames the text straddles the slide's bottom edge (y=230)
        draw.rectangle((110 + dx, 190, 290 + dx, 243), fill=BOX)
        for x in range(130, 270, 8):  # glyph-like strokes: 4 px wide, 4 px apart
            draw.rectangle((x + dx, 197, x + 3 + dx, 236), fill=WHITE)
    if axis_label:  # a few light pixels (chart tick label) touching the top of the subtitle text rows
        draw.rectangle((135 + dx, 188, 137 + dx, 196), fill=WHITE)
    if icons:
        for x in range(64, 80, 8):
            draw.rectangle((x + dx, 205, x + 3 + dx, 222), fill=WHITE)
    image.save(path)
    return path


def measure(run, tmp_path, **kw):
    frame = synthetic_frame(tmp_path / "f.png", **kw)
    return run("measure_bounds.py", frame)


def test_measures_video_slide_and_subtitle_bounds(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path)

    assert code == 0, out + err
    assert payload["video"] == [20, 20, 380, 260]
    assert payload["slide"] == [60, 40, 340, 230]
    assert payload["text"] == [130, 197, 270, 237]


def test_subtitle_bounds_pad_the_text_and_stay_inside_the_video(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path)

    x0, y0, x1, y1 = payload["subtitle"]
    tx0, ty0, tx1, ty1 = payload["text"]
    assert x0 < tx0 and y0 < ty0 and x1 > tx1 and y1 > ty1
    vx0, vy0, vx1, vy1 = payload["video"]
    assert vx0 <= x0 and vy0 <= y0 and x1 <= vx1 and y1 <= vy1


def test_a_horizontally_shifted_layout_shifts_every_measurement(run, tmp_path):
    base = measure(run, tmp_path)[1]
    (tmp_path / "s").mkdir()
    shifted = measure(run, tmp_path / "s", dx=14)[1]

    for key in ("video", "slide", "text"):
        assert shifted[key] == [base[key][0] + 14, base[key][1], base[key][2] + 14, base[key][3]]


def test_a_frame_without_subtitle_reports_none(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path, subtitle=False)

    assert code == 0, out + err
    assert payload["text"] is None and payload["subtitle"] is None


def test_player_control_icons_are_not_mistaken_for_subtitle_text(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path, icons=True)

    assert payload["text"] == [130, 197, 270, 237]


def test_an_image_without_a_video_area_is_an_error(run, tmp_path):
    path = tmp_path / "blank.png"
    Image.new("RGB", (400, 300), PAGE).save(path)

    code, payload, out, err = run("measure_bounds.py", path)

    assert code != 0
    assert "video" in (err + out).lower()


def test_large_white_text_inside_the_slide_is_not_the_subtitle(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path, title=True)

    assert payload["text"] == [130, 197, 270, 237]


def test_title_does_not_create_a_subtitle_in_a_frame_without_one(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path, title=True, subtitle=False)

    assert payload["text"] is None


def test_stray_pixels_touching_the_text_do_not_extend_its_top_edge(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path, axis_label=True)

    assert payload["text"] == [130, 197, 270, 237]


def test_subtitle_bounds_cover_the_whole_translucent_box(run, tmp_path):
    code, payload, out, err = measure(run, tmp_path)

    x0, y0, x1, y1 = payload["subtitle"]
    assert x0 <= 110 and y0 <= 190 and x1 >= 291 and y1 >= 244  # box drawn at (110,190)-(290,243) inclusive


def test_a_few_light_pixels_in_the_bottom_band_are_not_a_subtitle(run, tmp_path):
    frame = synthetic_frame(tmp_path / "f.png", subtitle=False)
    image = Image.open(frame)
    draw = ImageDraw.Draw(image)
    draw.rectangle((300, 232, 330, 233), fill=WHITE)   # a thin watermark-like sliver, 2 px tall
    draw.rectangle((300, 234, 302, 236), fill=(0, 0, 0))
    image.save(frame)

    code, payload, out, err = run("measure_bounds.py", frame)

    assert payload["text"] is None and payload["subtitle"] is None


def test_a_video_without_black_letterbox_is_found_against_the_page_background(run, tmp_path):
    """Older captures: the video fills its area edge to edge, so there are no black bars to find. The area is
    then the region that differs from the light page, 16:9, anchored at its top-left."""
    image = Image.new("RGB", (400, 400), PAGE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 40, 379, 241), fill=BROWN)  # 360 x 202 (16:9)
    draw.rectangle((20, 242, 379, 399), fill=(51, 51, 51))  # dark player panel under the video
    draw.rectangle((70, 90, 329, 200), fill=CARD)
    frame = tmp_path / "noblack.png"
    image.save(frame)

    code, payload, out, err = run("measure_bounds.py", frame)

    assert code == 0, out + err
    assert payload["video"] == [20, 40, 380, 40 + 202]


def test_a_few_black_pixels_inside_a_letterboxless_video_do_not_pass_for_the_video_area(run, tmp_path):
    image = Image.new("RGB", (400, 400), PAGE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 40, 379, 241), fill=BROWN)
    draw.rectangle((20, 242, 379, 399), fill=(51, 51, 51))
    draw.rectangle((200, 100, 260, 160), fill=(0, 0, 0))  # a black sticker on the slide
    frame = tmp_path / "sticker.png"
    image.save(frame)

    code, payload, out, err = run("measure_bounds.py", frame)

    assert code == 0, out + err
    assert payload["video"] == [20, 40, 380, 40 + 202]


def test_a_given_video_area_overrides_detection(run, tmp_path):
    frame = synthetic_frame(tmp_path / "f.png")
    code, payload, out, err = run("measure_bounds.py", frame, "--video", "20,20,380,260")
    assert code == 0, out + err
    assert payload["video"] == [20, 20, 380, 260]
    assert payload["slide"] == [60, 40, 340, 230] and payload["text"] == [130, 197, 270, 237]


def test_a_given_video_area_is_used_even_when_detection_would_pick_something_else(run, tmp_path):
    frame = synthetic_frame(tmp_path / "f.png")
    code, payload, out, err = run("measure_bounds.py", frame, "--video", "10,10,390,270")
    assert code == 0, out + err
    assert payload["video"] == [10, 10, 390, 270]
