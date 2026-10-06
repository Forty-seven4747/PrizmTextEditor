#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Generate the fx-CG50 menu icons (92x64 PNG) for the TEXTEDIT add-in:
#
#   assets/icon-uns.png   a blank sheet with a caret   (add-in not selected)
#   assets/icon-sel.png   the same sheet with "PRIZM!" typed and the caret
#                         sitting right after the text  (add-in selected)
#
# The fx-CG header stores each icon as a raw 92x64 RGB565 bitmap and fxgxa
# copies exactly 92*64*2 bytes per icon with no size check, so the images MUST
# be 92x64. The format has no alpha channel either (libpng is asked for
# PNG_FORMAT_RGB): every pixel is opaque, so the artwork is drawn full-bleed on
# an opaque background instead of relying on transparency.
#
# Pure stdlib (zlib + struct) so it runs anywhere. Run: python gen_icon.py
# ---------------------------------------------------------------------------
import os, struct, zlib

W, H = 92, 64

BG     = (26, 35, 50)       # dark navy, same family as the add-in's own UI
SHADOW = (12, 17, 26)       # one step darker than BG, for the sheet's drop
PAPER  = (255, 255, 255)    # the blank sheet
EDGE   = (176, 189, 205)    # 1px outline so the sheet reads on the navy
FOLD   = (223, 230, 239)    # the turned-over corner
INK    = (26, 35, 50)       # text drawn in the background colour
CURSOR = (0, 200, 160)      # teal caret, the add-in's accent colour

# Sheet geometry, in pixels. The dog-ear is cut out of the top-right corner.
PL, PT, PR, PB = 8, 5, 83, 58
FOLDN = 13

# Text: a pixel face drawn at 2x, so the strokes come out 2px thick. Each
# glyph is as wide as its own artwork and gets a 1px gap on top of that.
SCALE = 2
TEXT = "PRIZM!"
CURW, CURH = 3, 14                      # caret, a shade taller than the text

GLYPHS = {
    "P": ("###.", "#..#", "###.", "#...", "#...", "#..."),
    "R": ("###.", "#..#", "###.", "#.#.", "#..#", "#..#"),
    "I": ("###", ".#.", ".#.", ".#.", ".#.", "###"),
    "Z": ("####", "...#", "..#.", ".#..", "#...", "####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#"),
    "!": (".#", ".#", ".#", ".#", "..", ".#"),
}


def glyph_w(ch):
    return len(GLYPHS[ch][0]) * SCALE


def text_width(s):
    """Ink width of s, without the trailing inter-glyph gap."""
    a = [glyph_w(c) + 1 for c in s]
    return sum(a[:-1]) + a[-1] - 1

img = [[BG for _ in range(W)] for _ in range(H)]


def rect(x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        if 0 <= y < H:
            for x in range(x0, x1 + 1):
                if 0 <= x < W:
                    img[y][x] = color


def sheet():
    """The blank sheet: drop shadow, white body, outline and dog-ear."""
    rect(PL + 2, PT + 2, PR + 2, PB + 2, SHADOW)
    rect(PL, PT, PR, PB, PAPER)

    # Outline, stopping where the dog-ear cuts the corner away. The crease and
    # the right edge past the flap are drawn by the loop below.
    rect(PL, PT, PR - FOLDN, PT, EDGE)              # top, up to the fold
    rect(PL, PT, PL, PB, EDGE)                      # left
    rect(PL, PB, PR, PB, EDGE)                      # bottom
    rect(PR, PT + FOLDN, PR, PB, EDGE)              # right, below the fold

    # Dog-ear. The diagonal runs from (PR-FOLDN, PT) to (PR, PT+FOLDN); the
    # triangle up-right of it is cut away, the one below it is the flap.
    for y in range(PT, PT + FOLDN + 1):
        for x in range(PR - FOLDN, PR + 1):
            e = (x - (PR - FOLDN)) - (y - PT)
            if e > 0:
                img[y][x] = BG                      # the missing corner
            elif e == 0:
                img[y][x] = EDGE                    # the crease
            else:
                img[y][x] = FOLD                    # the folded-over corner


def blit_text(x0, y0, s):
    """Draw s at 2x; returns the x of the rightmost ink column."""
    x, right = x0, x0
    for ch in s:
        for ry, row in enumerate(GLYPHS[ch]):
            for rx, c in enumerate(row):
                if c != "#":
                    continue
                rect(x + rx * SCALE, y0 + ry * SCALE,
                     x + rx * SCALE + SCALE - 1, y0 + ry * SCALE + SCALE - 1, INK)
        right = x + glyph_w(ch) - 1
        x = right + 2
    return right


def caret(x, y):
    rect(x, y, x + CURW - 1, y + CURH - 1, CURSOR)


def build(selected):
    sheet()

    tw = text_width(TEXT)
    ink_w = tw + 3 + CURW                        # text, a gap, then the caret
    inner_l, inner_r = PL + 2, PR - 2
    x = inner_l + (inner_r - inner_l + 1 - ink_w) // 2

    # Same line position either way, so the two icons line up: the caret is
    # where the text will start (blank sheet) or just after it (typed).
    y = PT + (PB - PT + 1 - 6 * SCALE) // 2
    caret_y = y - 1

    if not selected:
        caret(x, caret_y)
    else:
        end = blit_text(x, y, TEXT)
        caret(end + 3, caret_y)
    return x, ink_w


# ---------------------------------------------------------------------------
# PNG writer (RGB, no alpha: the .g3a icon format is opaque)
# ---------------------------------------------------------------------------
def write_png(path, rows):
    h = len(rows)
    w = len(rows[0])
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw += bytes(rows[y][x])

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)   # 8-bit truecolour
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))


def preview(rows_list, scale=5, gap=6, bg=(90, 96, 110)):
    """Blow both icons up side by side, so the artwork can be eyeballed without
    loading a 92x64 PNG. Nearest-neighbour, so the pixels stay square."""
    cw, ch = W * scale, H * scale
    out = [[bg for _ in range(cw * len(rows_list) + gap * (len(rows_list) - 1))]
           for _ in range(ch)]
    for i, rows in enumerate(rows_list):
        ox = i * (cw + gap)
        for y in range(H):
            for x in range(W):
                c = rows[y][x]
                for dy in range(scale):
                    for dx in range(scale):
                        out[y * scale + dy][ox + x * scale + dx] = c
    return out


out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(out_dir, exist_ok=True)

made = []
for name, sel in (("icon-uns.png", False), ("icon-sel.png", True)):
    for y in range(H):
        for x in range(W):
            img[y][x] = BG
    x0, ink = build(sel)
    p = os.path.join(out_dir, name)
    write_png(p, img)
    made.append([row[:] for row in img])    # keep a copy for the preview
    print("wrote %s (%d bytes)  sheet %dx%d  ink cols %d..%d"
          % (p, os.path.getsize(p), PR - PL + 1, PB - PT + 1, x0, x0 + ink - 1))

p = os.path.join(out_dir, "icon-preview.png")
write_png(p, preview(made))
print("wrote %s (%d bytes)  both icons at 5x" % (p, os.path.getsize(p)))
