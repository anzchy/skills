"""Shared fixtures for jc-basic-report tests.

Run from anywhere:
    uv run --with pytest --with playwright python -m pytest <skill>/tests
    uv run --with pytest --with playwright python -m pytest <skill>/tests --report path/to/report.html

Without --report, the browser tests run against the bundled fake-company fixture,
built through scripts/build.py. Browser tests use the locally installed Chrome
(Playwright channel "chrome"), so no browser download is needed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent
BUILD = SKILL / "scripts" / "build.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample"


def pytest_addoption(parser):
    parser.addoption("--report", action="store", default=None,
                     help="Built report HTML to test instead of the bundled fixture.")


def run_build(src: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    """Invoke the build script the way a user would."""
    return subprocess.run(
        [sys.executable, str(BUILD), str(src), "-o", str(out), *extra],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="session")
def report_path(request, tmp_path_factory) -> Path:
    given = request.config.getoption("--report")
    if given:
        path = Path(given).expanduser().resolve()
        assert path.is_file(), f"--report not found: {path}"
        return path
    out = tmp_path_factory.mktemp("built") / "report.html"
    res = run_build(FIXTURE / "report.src.html", out)
    assert res.returncode == 0, f"fixture build failed:\n{res.stdout}\n{res.stderr}"
    return out


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        yield b
        b.close()


@pytest.fixture()
def context(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    # The CDN web font is not under test; fail it fast so pages render offline.
    ctx.route("**/*.ttf", lambda route: route.abort())
    yield ctx
    ctx.close()


class Reader:
    """A person reading the report in a browser: only public, user-visible actions."""

    def __init__(self, page, url: str):
        self.page = page
        self.url = url
        self.errors: list[str] = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())          # import shows a confirmation alert
        # Script errors only: resource failures are expected (the web font is blocked in tests).
        page.on("console", lambda m: self.errors.append(m.text)
                if m.type == "error" and not m.text.startswith("Failed to load resource") else None)

    def open(self):
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.page.wait_for_selector(".js-toc a", state="attached", timeout=5000)
        return self

    def reopen(self):
        return self.open()

    # --- sidebar ---
    def toc_labels(self) -> list[str]:
        return [t.strip() for t in self.page.locator(".js-toc a").all_inner_texts()]

    def click_toc(self, label: str):
        self.page.locator(".js-toc a", has_text=label).first.click()
        self.page.wait_for_timeout(900)

    def active_toc(self) -> str:
        return self.page.locator(".js-toc a.is-active-link").first.inner_text().strip()

    def toggle_sidebar(self):
        self.page.click("#side-toggle")
        self.page.wait_for_timeout(350)

    def sidebar_width(self) -> float:
        return self.page.locator("#side").bounding_box()["width"]

    def open_notes_tab(self):
        self.page.click('.side-tab[data-tab="ann"]')
        self.page.wait_for_timeout(200)

    # --- annotation ---
    def select_text(self, selector: str, nth: int = 0, frac=(0.1, 0.45)):
        el = self.page.locator(selector).nth(nth)
        el.scroll_into_view_if_needed()
        box = el.bounding_box()
        y = box["y"] + 10
        self.page.mouse.move(box["x"] + box["width"] * frac[0], y)
        self.page.mouse.down()
        self.page.mouse.move(box["x"] + box["width"] * frac[1], y, steps=8)
        self.page.mouse.up()
        self.page.wait_for_timeout(400)

    def toolbar_open(self) -> bool:
        return self.page.locator(".ann-pop.open").count() == 1

    def toolbar(self, what: str):
        sel = {"yellow": '[data-kind="hl-yellow"]', "green": '[data-kind="hl-green"]',
               "blue": '[data-kind="hl-blue"]', "underline": '[data-kind="underline"]',
               "note": '[data-act="note"]', "save": '[data-act="save"]', "delete": '[data-act="delete"]'}[what]
        self.page.click(".ann-pop " + sel)
        self.page.wait_for_timeout(300)

    def write_note(self, text: str):
        self.toolbar("note")
        self.page.fill(".ann-pop textarea", text)
        self.toolbar("save")

    def dismiss(self):
        self.page.mouse.click(1380, 880)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    def export_notes(self, dest) -> dict:
        self.open_notes_tab()
        with self.page.expect_download() as dl:
            self.page.click("#ann-export")
        dl.value.save_as(dest)
        return json.loads(open(dest, encoding="utf-8").read())

    def import_notes(self, path):
        self.open_notes_tab()
        self.page.set_input_files("#ann-file", str(path))
        self.page.wait_for_timeout(500)

    def open_note_from_list(self, nth: int = 0):
        self.open_notes_tab()
        self.page.locator(".ann-item").nth(nth).click()
        self.page.wait_for_timeout(900)

    def marks_on_page(self) -> int:
        """Highlight / underline marks drawn over the text."""
        self.page.wait_for_timeout(200)
        return self.page.locator(".r6o-span-highlight-layer .r6o-annotation").count()

    def note_items(self) -> list[dict]:
        self.open_notes_tab()
        items = []
        for el in self.page.locator(".ann-item").all():
            note = el.locator(".ann-note")
            items.append({
                "quote": el.locator(".ann-quote").inner_text().strip(),
                "note": note.inner_text().strip() if note.count() else "",
            })
        return items


@pytest.fixture()
def reader(context, report_path):
    page = context.new_page()
    return Reader(page, report_path.as_uri()).open()


# ---------- docx export (scripts/docx) ----------
DOCX = SKILL / "scripts" / "docx"


@pytest.fixture(scope="session")
def source_html(report_path) -> str:
    """The report HTML as a reader opens it; expected counts in the docx tests are read from it."""
    return report_path.read_text(encoding="utf-8")


def export_docx(report: Path, wd: Path) -> Path:
    """Convert a built report the way a user would: prep.py, then build_docx.py."""
    out = wd / "report.docx"
    for cmd in ([sys.executable, str(DOCX / "prep.py"), str(report), str(wd)],
                [sys.executable, str(DOCX / "build_docx.py"), str(wd), str(out)]):
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"{cmd[1]} failed:\n{res.stdout}\n{res.stderr}"
    return out


def build_fixture_with_settings(tmp: Path, override: dict) -> Path:
    """The bundled fixture, rebuilt with an author's settings.json override next to report.src.html."""
    import shutil
    src_dir = tmp / "src"
    shutil.copytree(FIXTURE, src_dir)
    (src_dir / "settings.json").write_text(json.dumps(override, ensure_ascii=False), encoding="utf-8")
    out = tmp / "report.html"
    res = run_build(src_dir / "report.src.html", out)
    assert res.returncode == 0, f"fixture build failed:\n{res.stdout}\n{res.stderr}"
    return out


@pytest.fixture(scope="session")
def docx_path(report_path, tmp_path_factory) -> Path:
    return export_docx(report_path, tmp_path_factory.mktemp("docx"))


@pytest.fixture(scope="session")
def doc(docx_path):
    from docx import Document
    return Document(str(docx_path))
