#!/usr/bin/env python3
"""gen_faces_preview.py -- draw a mock 396x224 editor screen for every bundled
face, straight out of the generated src/*.c files, into font-faces-preview.png.

The point is to be able to judge a face without flashing the calculator: the
bitmaps are decoded from the same C arrays that get linked in, so what you see
is what the screen draws -- same cell, same 1-bit cut, same line pitch.

Faces are read from:
    src/wcfont.c    the code-page bitmap face        (gen_font.py)
    src/lucfont.c   Lucida Console                   (tools/gen_lucida.py)
    src/*_font.c    Consolas, Noto Sans, Source Sans 3, Comic Sans MS, Roboto
                                                     (tools/gen_ttf.py)

Run from anywhere:  python tools/gen_faces_preview.py [scale]
"""

import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(HERE)

DWIDTH, DHEIGHT = 396, 224
BAR = 15                  # status bar / soft-key bar height, as in main.c
TEXT_GAP = 3              # main.c's default line spacing
LINE_GAP = 10             # blank rows between the panels of the sheet

# label, source basename, symbol prefix, macro prefix. Order matches the Font
# option's list so the sheet reads like the menu. ("Default" is gint's own
# proportional 8x9, which lives in libgint-cg and cannot be decoded offline.)
FACES = [
    ("Code page",     "wcfont",   "wc",  "WC"),
    ("Lucida Console", "lucfont", "luc", "LUC"),
    ("Consolas",      "con_font", "con", "CON"),
    ("Noto Sans",     "not_font", "not", "NOT"),
    ("Source Sans 3", "ss3_font", "ss3", "SS3"),
    ("Comic Sans MS", "cms_font", "cms", "CMS"),
    ("Roboto",        "rob_font", "rob", "ROB"),
]

# The same shape of content the editor has to cope with: code (ASCII only),
# Latin-1 accents, the CP437 box/shade set and the ANSI punctuation.
#
# Every character here must be inside the app's repertoire, which is exactly
# "anything CP437 or Windows-1252 can name". CP437 carries only 14 Greek
# letters, so beta and gamma are NOT available in any face -- main() warns if a
# character below is out of repertoire, rather than quietly drawing a gap.
CONTENT = [
    "static int parse_int(const char *s) {",
    "    int neg = 0, v = 0;",
    "    if(*s == '-') { neg = 1; s++; }",
    "    while(*s >= '0' && *s <= '9')",
    "        v = v * 10 + *s++ - '0';",
    "    return neg ? -v : v;",
    "}",
    "",
    "Accents: \u00c9\u00c0\u00cd\u00dd\u00e9\u00e8\u00fc\u00f1\u00c7\u00df  Greek: \u03b1\u03c3\u03a3\u03a9\u0398\u03a6",
    "Quotes: \u201c\u201d \u2018\u2019 \u2013 \u2014 \u2026  Math: \u00b1\u00d7\u00f7\u2248\u2261\u221a\u207f\u00b2",
    "Box: \u250c\u2500\u252c\u2500\u2510 \u251c\u2500\u253c\u2500\u2524",
    "     \u2514\u2500\u2534\u2500\u2518 \u2502 \u2591\u2592\u2593\u2588",
]
STATUS = "TEXTEDIT.C *"
POS = "Ln 12, Col 20"
SOFTKEYS = "F1 Save  F5 Browser  F2 Menu  F6 More"


def load_face(base, prefix, upper):
    """Return (W, H, glyph, blocks) for a generated font_t, glyph(cp) -> list
    of rows as '0'/'1' strings, or None when the code point has no block."""
    c = open(os.path.join("src", base + ".c"), encoding="ascii").read()
    h = open(os.path.join("src", base + ".h"), encoding="ascii").read()
    w = int(re.search(r"#define %s_W (\d+)" % upper, h).group(1))
    hh = int(re.search(r"#define %s_H (\d+)" % upper, h).group(1))
    blocks = [(int(a, 16), int(b, 16)) for a, b in re.findall(
        r"\(uint32_t\)\(0x([0-9A-Fa-f]+)u << 12\) \| 0x([0-9A-Fa-f]+)u", c)]
    words = [int(x, 16) for x in re.findall(
        r"0x([0-9A-Fa-f]{8})u", c.split("%s_data[] = {" % prefix)[1].split("};")[0])]
    storage = int(re.search(r"\.storage_size = (\d+)", c).group(1))

    def glyph(cp):
        i = 0
        for s, l in blocks:
            if s <= cp < s + l:
                gi = i + (cp - s)
                bits = "".join(format(v, "032b")
                               for v in words[gi * storage:(gi + 1) * storage])
                return [bits[y * w:(y + 1) * w] for y in range(hh)]
            i += l
        return None

    return w, hh, glyph, blocks


def panel(w, h, glyph, cellw, cellh, cglyph, gap=0, caret_col=None):
    """One mock editor screen in this face: ink 0, paper 255.

    `gap` is the extra column spacing the app's Char spacing option adds; the
    column pitch becomes w + gap, exactly like gint's advance = width +
    char_spacing. `caret_col` draws the editor's caret block on one line so the
    grid can be checked by eye: the block must sit exactly on the character."""
    img = Image.new("L", (DWIDTH, DHEIGHT), 255)
    px = img.load()

    # status bar (top) and soft-key bar (bottom), both inverted like main.c
    for y in list(range(BAR)) + list(range(DHEIGHT - BAR, DHEIGHT)):
        for x in range(DWIDTH):
            px[x, y] = 0

    cpitch = w + gap               # column pitch
    rpitch = h + TEXT_GAP          # row pitch

    def put(text, cx, cy, ink, face, pitch):
        for ch_ in text:
            g = face(ord(ch_))
            if g:
                for ry, row in enumerate(g):
                    for rx, bit in enumerate(row):
                        if bit == "1":
                            X, Y = cx + rx, cy + ry
                            if 0 <= X < DWIDTH and 0 <= Y < DHEIGHT:
                                px[X, Y] = ink
            cx += pitch
        return cx

    for i, line in enumerate(CONTENT):
        y = BAR + 2 + i * rpitch
        if y + h > DHEIGHT - BAR:
            break
        put(line, 2, y, 0, glyph, cpitch)

    if caret_col is not None:
        ci = 1                                     # "    int neg = 0, v = 0;"
        y = BAR + 2 + ci * rpitch
        x = 2 + caret_col * cpitch
        if x + cpitch <= DWIDTH and y + h <= DHEIGHT - BAR:
            for yy in range(y, y + h):
                for xx in range(x, x + cpitch):
                    px[xx, yy] = 0
            if caret_col < len(CONTENT[ci]):
                g = glyph(ord(CONTENT[ci][caret_col]))
                if g:
                    for ry, row in enumerate(g):
                        for rx, bit in enumerate(row):
                            if bit == "1" and y + ry < DHEIGHT - BAR:
                                px[x + rx, y + ry] = 255

    # Chrome is drawn with the code-page face, exactly as the app keeps its
    # bars in a small face whatever the content face is.  The bars always use
    # the face's own pitch (cellw) with no added spacing, like main.c's
    # bar_text()/bar_width() helpers.
    put(STATUS, 2, 2, 255, cglyph, cellw)
    put(SOFTKEYS, 2, DHEIGHT - BAR + 3, 255, cglyph, cellw)
    put(POS, DWIDTH - 2 - len(POS) * cellw, 2, 255, cglyph, cellw)
    return img


def main():
    scale = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    lw, lh, lglyph, lblocks = load_face("wcfont", "wc", "WC")

    # The code-page face covers exactly the app's repertoire, so it is the
    # reference for "can any face draw this?". Warn rather than draw a gap.
    covered = set()
    for s, l in lblocks:
        covered.update(range(s, s + l))
    for line in CONTENT:
        for ch in line:
            if ord(ch) not in covered:
                print("WARNING sample U+%04X '%s' is outside the repertoire"
                      % (ord(ch), ch))

    panels = []
    for label, base, prefix, upper in FACES:
        w, h, glyph, _ = load_face(base, prefix, upper)
        panels.append((label, "%dx%d" % (w, h), panel(w, h, glyph, lw, lh, lglyph)))
        print("%-16s cell %dx%d   %d columns x %d rows of content"
              % (label, w, h, (DWIDTH - 4) // w,
                 (DHEIGHT - 2 * BAR - 4) // (h + TEXT_GAP)))

    # One extra panel that demonstrates the "Character spacing" (char_gap)
    # option: the code-page face with the same +2px the setting can add, caret
    # drawn on line 1 so the widened column pitch is obvious by eye.  The bars
    # deliberately stay at 0 gap, exactly as main.c's bar_text() keeps them.
    panels.append(("Code page +2 gap", "%dx%d +2" % (lw, lh),
                   panel(lw, lh, lglyph, lw, lh, lglyph, gap=2, caret_col=4)))

    cols = 2
    rows = (len(panels) + cols - 1) // cols
    head = lh + 5
    cw_, ch_ = DWIDTH + 16, head + DHEIGHT + LINE_GAP
    sheet = Image.new("L", (cols * cw_ + 16, rows * ch_ + 16), 230)
    spx = sheet.load()

    def title(text, x, y):
        for ch in text:
            g = lglyph(ord(ch))
            if g:
                for ry, row in enumerate(g):
                    for rx, bit in enumerate(row):
                        if bit == "1":
                            spx[x + rx, y + ry] = 0
            x += lw

    for i, (label, cell, img) in enumerate(panels):
        cx = 16 + (i % cols) * cw_
        cy = 16 + (i // cols) * ch_
        title("%s  %s" % (label, cell), cx, cy)
        sheet.paste(img, (cx, cy + head))

    out = "font-faces-preview.png"
    big = sheet.resize((sheet.width * scale, sheet.height * scale),
                       Image.NEAREST)
    big.save(out)
    print("wrote %s (%dx%d, scale %d)" % (out, big.width, big.height, scale))


if __name__ == "__main__":
    main()
