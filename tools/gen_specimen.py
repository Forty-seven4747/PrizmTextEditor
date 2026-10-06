#!/usr/bin/env python3
"""gen_specimen.py -- write font-specimen.html.

A pixel-accurate picture of every glyph the bundled code-page font carries,
laid out per display mode, straight from gen_font.py (so it can never drift
from the font that actually gets compiled).

Run from anywhere:  python tools/gen_specimen.py     ->  font-specimen.html
"""
import io
import os
import sys
import contextlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(HERE)
sys.path.insert(0, HERE)

with contextlib.redirect_stdout(io.StringIO()):
    import gen_font as G

SCALE = 5
W, H = G.W, G.H

SECTIONS = [
    ("ASCII / base", [(b, b) for b in range(0x20, 0x7F)]),
    ("Standard - Latin-1, 0xA0-0xFF", [(b, b) for b in range(0xA0, 0x100)]),
    ("Windows (ANSI) - CP1252, 0x80-0xFF", [(b, G.CP1252_UNI[b]) for b in range(0x80, 0x100)]),
    ("DOS/IBM (OEM) - CP437, 0x80-0xFF",
     [(b, G.CP437_UNI[b]) for b in range(0x80, 0x100) if G.CP437_UNI[b]]),
]

# One <g> per distinct bitmap, referenced by <use> from every cell that needs it.
ids, order = {}, []


def gid(rows):
    if rows not in ids:
        ids[rows] = len(order)
        order.append(rows)
    return ids[rows]


def cells(pairs):
    out = []
    for b, cp in pairs:
        out.append((b, cp, gid(tuple(G.glyph_for(cp)))))
    return out


sections = [(t, cells(p)) for t, p in SECTIONS]

defs = []
for i, rows in enumerate(order):
    r = []
    for y, rb in enumerate(rows):
        for x in range(W):
            if (rb >> (7 - x)) & 1:
                r.append('<rect x="%d" y="%d"/>' % (x, y))
    defs.append('<g id="g%d">%s</g>' % (i, "".join(r)))

p = []
p.append('<!DOCTYPE html>')
p.append('<html lang="en"><head><meta charset="utf-8">')
p.append('<title>TEXTEDIT bundled font - specimen</title>')
p.append("""<style>
:root { --bg:#f6f7f9; --panel:#fff; --ink:#1b1f24; --dim:#6b7280; --line:#e3e6ea; --px:#1b1f24; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#14171a; --panel:#1c2024; --ink:#e6e9ec; --dim:#98a2ad; --line:#2b3138; --px:#e6e9ec; }
}
* { box-sizing:border-box; }
body { margin:0; padding:28px 22px 60px; background:var(--bg); color:var(--ink);
       font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
h1 { font-size:19px; margin:0 0 4px; }
h2 { font-size:14px; margin:30px 0 10px; color:var(--ink);
     border-bottom:1px solid var(--line); padding-bottom:6px; }
.meta { color:var(--dim); font-size:12.5px; margin:0 0 18px; }
.meta code { background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:1px 5px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(46px,1fr)); gap:6px; }
.c { background:var(--panel); border:1px solid var(--line); border-radius:6px;
     padding:5px 2px 4px; text-align:center; }
.c svg { display:block; margin:0 auto; shape-rendering:crispEdges; }
.c svg rect { fill:var(--px); }
.b { font:11px/1.4 ui-monospace,Consolas,monospace; color:var(--ink); }
.u { font:10px/1.3 ui-monospace,Consolas,monospace; color:var(--dim); }
.note { color:var(--dim); font-size:12.5px; margin:0 0 6px; }
</style></head><body>""")
p.append('<h1>TEXTEDIT &mdash; bundled code-page font specimen</h1>')
p.append('<p class="meta">monospaced %d&times;%d &middot; %d blocks &middot; %d glyphs &middot; '
         '%d longwords/glyph &middot; <code>char_spacing=0</code> (advance == %dpx, '
         'column <i>n</i> sits at <i>x = n*%d</i>) &middot; font named <code>%s</code></p>'
         % (W, H, len(G.blocks), G.GLYPH_COUNT, G.STORAGE, W, W, G.NAME))
p.append('<p class="note">Every cell is drawn from the exact bitmap that '
         '<code>src/wcfont.c</code> compiles. gint decodes UTF-8 before looking a glyph up, '
         'so the font is indexed by Unicode code point and the editor re-encodes each file '
         'byte to UTF-8; the small grey number is that code point. Cells with no bitmap '
         '(space, soft hyphen) are intentionally empty.</p>')

p.append('<svg width="0" height="0" aria-hidden="true" style="position:absolute">')
p.append('<defs>' + "".join(defs) + '</defs></svg>')

for title, cs in sections:
    p.append('<h2>%s <span class="u">(%d)</span></h2>' % (title, len(cs)))
    p.append('<div class="grid">')
    for b, cp, g in cs:
        p.append('<div class="c"><svg viewBox="0 0 %d %d" width="%d" height="%d">'
                 '<use href="#g%d"/></svg><div class="b">%02X</div>'
                 '<div class="u">%04X</div></div>'
                 % (W, H, W * SCALE, H * SCALE, g, b, cp))
    p.append('</div>')

p.append('</body></html>')

out = "font-specimen.html"
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(p))
print("wrote %s (%d bytes): %d sections, %d distinct bitmaps"
      % (out, os.path.getsize(out), len(sections), len(order)))
