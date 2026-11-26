#!/usr/bin/env python3
"""SPIKE (throwaway): overlay the proposed themes / A4 sheets / TOC pages onto a built report.

    python3 apply_spike.py <built.html> <out.html>
Never modifies the input file.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))

# literal colours chart.py bakes into every SVG  ->  chart-palette key
SVG_MAP = {
    "#f5f4ed": "parchment", "#141413": "near_black", "#4d4c48": "charcoal", "#504e49": "olive",
    "#6b6a64": "stone", "#b8b7b0": "light_stone", "#d4d3cd": "mist", "#1b365d": "brand",
    "#eef2f7": "brand_tint", "#e8e7e1": "grid", "#30302e": "text_strong", "#e4ecf5": "tag", "#faf9f5": "ivory",
}


def tokens(t: dict) -> str:
    rows = [f"--parchment:{t['parchment']}", f"--ivory:{t['ivory']}", f"--near-black:{t['near_black']}",
            f"--dark-warm:{t['dark_warm']}", f"--olive:{t['olive']}", f"--stone:{t['stone']}",
            f"--brand:{t['brand']}", f"--border:{t['border']}", f"--border-soft:{t['border']}",
            f"--tag-bg:{t['tag_bg']}", f"--positive:{t['brand']}", f"--negative:{t['stone']}",
            f"--desk:{t['desk']}"]
    rows += [f"--c-{k.replace('_', '-')}:{v}" for k, v in t["chart"].items()]
    return ";".join(rows)


def css() -> str:
    out = []
    for name, t in S["themes"].items():
        out.append(f'html[data-theme="{name}"]{{{tokens(t)}}}')
    # SVG: presentation attributes lose to CSS, so remap the baked-in hex to variables.
    for hexv, key in SVG_MAP.items():
        v = f"var(--c-{key.replace('_', '-')})"
        for up in {hexv, hexv.upper(), "#" + hexv[1:].upper()}:
            out.append(f'svg [fill="{up}"]{{fill:{v}}} svg [stroke="{up}"]{{stroke:{v}}}')
    pal = S["themes"][{"white": "white"}.get(S["print"]["palette"], "white")]
    out.append(f"@media print{{html[data-theme]{{{tokens(pal)}}}}}")
    out.append("""
html, body { background: var(--desk, var(--parchment)); }
@media screen { body { max-width: none; padding: 14px 0 40px; } }
#report .sheet { position: relative; box-sizing: border-box; background: var(--parchment); margin: 0 auto 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.18), 0 6px 22px rgba(0,0,0,.10); overflow: hidden; }
.sheet-body { display: flow-root; height: 100%; position: relative; }
.sheet-head, .sheet-foot { position: absolute; left: 18mm; right: 18mm; font-size: 8.5pt; color: var(--stone); letter-spacing: .5pt; }
.sheet-head { top: 8mm; border-bottom: .5pt solid var(--border); padding-bottom: 2mm; }
.sheet-head:empty { border: 0; }
.sheet-foot { bottom: 7mm; text-align: center; }
.sheet-body > .oversized { outline: 1.5pt dashed #c0392b; }
.theme-bar { display: flex; align-items: center; gap: 6px; padding: 8px 12px 0 16px; font-size: 12px; color: var(--stone); }
.theme-bar span { margin-right: 4px; }
.theme-bar button { flex: 1; border: .6pt solid var(--border); background: transparent; color: var(--olive); font: inherit; font-size: 12px; padding: 3px 0; border-radius: 4px; cursor: pointer; }
.theme-bar button[aria-pressed="true"] { background: var(--brand); color: var(--parchment); border-color: var(--brand); }
.js-toc a.toc-link { display: flex !important; justify-content: space-between; gap: 8px; }
.toc-pg { color: var(--stone); font-variant-numeric: tabular-nums; flex: none; }
.gap { background: color-mix(in srgb, var(--near-black) 9%, var(--parchment)); }
html[data-theme="black"] .side { background: var(--ivory); }
html[data-theme="black"] .js-toc a.toc-link:hover { background: #26262c; }
html[data-theme="black"] .hl { color: var(--brand); }
html[data-theme="black"] table.compact td, html[data-theme="black"] table.compact th { border-color: var(--border); }
@page { size: A4; margin: 0; background: #fff; @bottom-center { content: none; } }
@media print {
  html, body { background: #fff !important; }
  body { padding: 0 !important; margin: 0 !important; }
  #report .sheet { margin: 0; box-shadow: none; height: 296.4mm !important; }
  #report .sheet + .sheet { break-before: page; }   /* not :last-child: recogito appends a layer div into #report */
  .theme-bar { display: none !important; }
}
""")
    return "\n".join(out)


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    h = src.read_text(encoding="utf-8")
    settings = json.dumps(S, ensure_ascii=False)
    assert "</main>" in h and "</head>" in h and "</body>" in h
    h = h.replace("</head>", f"<style id=\"jc-spike-css\">\n{css()}\n</style>\n</head>", 1)
    inject = (f'<script type="application/json" id="jc-settings">{settings}</script>\n'
              f'<script id="jc-spike">\n{(HERE / "spike.js").read_text(encoding="utf-8")}\n</script>\n')
    h = h.replace("</main>", "</main>\n" + inject, 1)   # runs before ui.js (tocbot / recogito)
    dst.write_text(h, encoding="utf-8")
    print("wrote", dst, len(h))


if __name__ == "__main__":
    main()
