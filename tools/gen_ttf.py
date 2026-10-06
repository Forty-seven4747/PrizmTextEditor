#!/usr/bin/env python3
"""
gen_ttf.py -- rasterize TrueType/OpenType faces into gint `font_t`s for the
TEXTEDIT add-in, one C file per face.

WHY A FIXED CELL
    The editor and the hex view address a text column n as x = n * CW, so every
    glyph of a selectable face must occupy exactly the same advance. gint gives
    that for a font marked `prop = 0` (monospaced), where

        advance = width + char_spacing        (see src/render-cg/topti.c)

    A proportional face is therefore CELL-FITTED: every glyph is drawn into one
    CW x CH box, CW being wide enough for the widest ink in the repertoire and
    tall enough for the deepest ascender/descender, and char_spacing = 0 keeps
    advance == CW. The face reads as a monospaced version of itself, which is
    what a column-oriented editor needs; narrow letters simply carry the slack
    on the right.

CODEPOINT COVERAGE
    The code point set is gen_font.NEEDED -- ASCII plus everything CP437 or
    Windows-1252 can name (Latin-1 accents, box drawing, blocks, shading, the
    CP437 Greek/maths symbols, the 1252 punctuation). Latin text faces carry
    only part of that. Any code point the face cannot name falls back to the
    bundled CP437 bitmap from gen_font.glyph_for(), nearest-neighbour scaled to
    the cell, so box drawing and shading never go blank when a text face is
    selected.

Run:
    python tools/gen_ttf.py --probe            # measure every spec, no writes
    python tools/gen_ttf.py                    # build every spec
    python tools/gen_ttf.py --only ss3 --em 14 # one spec, forced point size
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import gen_font  # noqa: E402  -- reuse NEEDED, glyph_for and the tables

THRESH = 100      # of 255: biased low so thin stems survive the 1-bit cut
METRIC = 200      # of 255: used only to measure, so AA bleed does not inflate
PROBE = 96        # working box for the ink measurement, in pixels

# ---------------------------------------------------------------------------
# Face table. `em` is the point size handed to PIL, tuned per face by
# `--probe` and checked by pixel dump: too small and the 1-bit cut eats parts
# of a glyph (Comic Sans' capital A loses a leg at em=8 and a full stop
# rasterizes to nothing), too large and the content area drops below ~39
# columns. The rule of thumb is a cell 8-10 px wide and 11-15 px tall, which
# keeps every face within about one column of the bundled Lucida Console's
# 8x13 instead of letting one wide face shrink the editor.
#
# The status/soft-key strips are deliberately NOT part of this: they carry
# fixed legends and are drawn in the small code-page face (see bar_text() in
# main.c), so a wide content face cannot push a legend off the right edge.
# ---------------------------------------------------------------------------
SPECS = [
    dict(prefix="con", name="Consolas",
         path=r"C:\Windows\Fonts\consola.ttf", em=14),      # ->  8x15
    dict(prefix="not", name="Noto Sans",
         path=r"C:\Windows\Fonts\NotoSansSC-VF.ttf", em=10),  # -> 10x14
    dict(prefix="ss3", name="Source Sans 3",
         path=os.path.join(ROOT, "assets", "fonts", "SourceSans3.ttf"),
         em=11),                                            # ->  9x14
    dict(prefix="cms", name="Comic Sans MS",
         path=r"C:\Windows\Fonts\comic.ttf", em=9),          # -> 10x13
    dict(prefix="rob", name="Roboto",
         path=os.path.join(ROOT, "assets", "fonts", "Roboto.ttf"), em=10),
]                                                           # ->  9x12

LUCIDA = r"C:\Windows\Fonts\lucon.ttf"   # fallback for faces PIL cannot open

# Pure line/block geometry (box drawing, block elements, shading, the integral
# pieces). Two reasons to always draw these from the bundled CP437 bitmaps
# rather than from the face:
#   * they must be exactly full-cell to connect, and the CP437 shapes are;
#   * text faces often draw them at a different scale than their em box --
#     Consolas' U+2591-U+2593, for instance, are line-box sized and would both
#     blow the measured cell height up and then be clipped by it.
# Excluding them from the measurement keeps the cell sized by real letterforms.
GEOM = set(range(0x2500, 0x25A0)) | {0x2320, 0x2321, 0x25A0}

# The cell WIDTH is decided by the printable ASCII range only. Letting the
# width be driven by the widest thing in the whole repertoire means the em dash,
# per-mille sign, AE ligature and infinity all count, and since an em dash is by
# definition one em wide the cell ends up ~1 em wide -- at which point a
# proportional face renders about 6 px of letterform in a 10 px cell. ASCII has
# the advance the code actually cares about; anything wider than the cell it
# produces (a few rare symbols) is simply clipped by 1-2 px, which is invisible
# on an em dash and acceptable on the rest.
CORE = set(range(0x21, 0x7F))

# Code points whose correct rendering is nothing at all. Every other code point
# in the repertoire must carry ink, so a face that names one but draws it blank
# (Source Sans 3 maps U+00A8 to an empty glyph) is treated as not covering it
# and falls back to CP437 instead of silently dropping the character.
BLANK_OK = {0x00A0, 0x00AD}   # no-break space, soft hyphen


def load(path, em):
    f = ImageFont.truetype(path, em)
    # Variable faces land on their default instance, which is Regular for every
    # one of our fonts; ask for it explicitly when the API is available.
    try:
        f.set_variation_by_name("Regular")
    except Exception:
        pass
    return f


def font_meta(path):
    """upem, widest printable-ASCII advance (in font units) and the cmap.

    The advance comes from the font's own hmtx table, not PIL: for the variable
    faces (Noto Sans SC, Roboto, Source Sans 3) PIL's getlength reports an
    advance up to 40% too wide, which would silently inflate the cell.
    Returns (upem, adv_units, cmap_set) with any of them None if unreadable."""
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, fontNumber=0, lazy=True)
        upem = t["head"].unitsPerEm
        hmtx, cmap = t["hmtx"], t.getBestCmap()
        adv = max(hmtx[cmap[c]][0] for c in sorted(CORE) if c in cmap)
        return upem, adv, set(cmap.keys())
    except Exception as e:
        print("  (fontTools could not read the metrics: %s)" % e)
        return None, None, None


def per_cp_boxes(f, cps, thresh=METRIC):
    """{code point: (left, right, top, bot)} relative to pen origin / baseline.

    Measured at METRIC, not at the rasterization threshold: anti-aliasing puts
    a partial-coverage skirt ~1 px wide around every outline, and a low cut
    would count that skirt as ink and inflate the cell by 2 px in each axis.
    Code points the face draws nothing for are simply absent."""
    w2, h2 = PROBE * 4, PROBE * 4
    ox, base = PROBE * 2, PROBE * 3
    out = {}
    for cp in cps:
        img = Image.new("L", (w2, h2), 0)
        ImageDraw.Draw(img).text((ox, base), chr(cp), font=f, fill=255,
                                 anchor="ls")
        bb = img.point(lambda v: 255 if v >= thresh else 0).getbbox()
        if bb is None:
            continue
        out[cp] = (bb[0] - ox, bb[2] - ox, bb[1] - base, bb[3] - base)
    return out


def union(boxes):
    """Merge per_cp_boxes() into one (left, right, top, bot), or None."""
    if not boxes:
        return None
    return (min(b[0] for b in boxes.values()),
            max(b[1] for b in boxes.values()),
            min(b[2] for b in boxes.values()),
            max(b[3] for b in boxes.values()))


def plan(spec, em=None):
    """Measure a face and decide its cell. Returns a dict."""
    em = em or spec["em"]
    path = spec["path"]
    f = load(path, em)
    cps = sorted(gen_font.NEEDED)
    draw_cps = [c for c in cps if c != 0x20]

    boxes = per_cp_boxes(f, draw_cps)
    core_boxes = {c: b for c, b in boxes.items() if c in CORE}
    metric_boxes = {c: b for c, b in boxes.items() if c not in GEOM}

    box = union(metric_boxes)
    if box is None:
        raise SystemExit("%s: nothing rasterized" % spec["name"])
    left, right, top, bot = box
    core_box = union(core_boxes)
    upem, adv_units, present = font_meta(path)
    if upem:
        adv = adv_units * em / upem
    else:
        adv = max(f.getlength(chr(c)) for c in sorted(CORE))
    ink_w = core_box[1] - core_box[0]

    cw = int(math.ceil(max(ink_w, adv)))
    ch = int(math.ceil(-top) + math.ceil(bot))
    up = int(math.ceil(-top))            # baseline row inside the cell
    xoff = int(math.ceil(-core_box[0]))  # pen x inside the cell
    clip = sorted(c for c, b in metric_boxes.items()
                  if b[0] + xoff < 0 or b[1] + xoff > cw)

    if present is None:
        # cmap unreadable: a code point counts as covered only if the face
        # actually draws something for it.
        missing = [c for c in draw_cps if c not in boxes]
    else:
        missing = [c for c in draw_cps if c not in present]
    # A code point the face names but draws as an empty cell would blank out on
    # screen, so it counts as missing too -- that is a real case, not a
    # hypothetical: Source Sans 3 maps U+00A8 to an empty outline. Only code
    # points the face actually names are tested, since anything outside `named`
    # is already counted missing above and would otherwise be reported twice.
    # The test uses the rasterization threshold, so it predicts the bitmap that
    # actually ships rather than "the outline exists somewhere".
    named = [c for c in draw_cps if c not in missing]
    inked = per_cp_boxes(f, named, THRESH)
    blank = [c for c in named
             if c not in inked and c not in BLANK_OK and c not in GEOM]
    if blank:
        print("%s: %d named-but-blank code points fall back to CP437: %s"
              % (spec["name"], len(blank),
                 " ".join("U+%04X" % c for c in blank)))
    missing = sorted(set(missing) | set(blank) | (set(draw_cps) & GEOM))
    return dict(spec=spec, em=em, font=f, cw=cw, ch=ch, up=up, xoff=xoff,
                cps=cps, draw_cps=draw_cps, missing=missing, clip=clip,
                adv=adv, ink_w=ink_w, top=top, bot=bot)


def bits_from_ttf(p, cp):
    """1-bit cw x ch grid for one code point, drawn from the TTF."""
    img = Image.new("L", (p["cw"], p["ch"]), 0)
    img = Image.new("L", (p["cw"], p["ch"]), 0)
    if cp != 0x20:
        ImageDraw.Draw(img).text((p["xoff"], p["up"]), chr(cp), font=p["font"],
                                 fill=255, anchor="ls")
    px = img.load()
    return [[1 if px[x, y] >= THRESH else 0 for x in range(p["cw"])]
            for y in range(p["ch"])]


def bits_from_cp437(cp, cw, ch):
    """Nearest-neighbour scale of the 8x9 CP437 bitmap into a cw x ch cell."""
    src = gen_font.glyph_for(cp)
    if len(src) < 9:
        src = list(src) + [0] * (9 - len(src))
    out = []
    for y in range(ch):
        sy = min(y * 9 // ch, 8)
        row = src[sy]
        out.append([(row >> (7 - min(x * 8 // cw, 7))) & 1 for x in range(cw)])
    return out


def words(bits, cw, ch):
    """Pack a cw x ch 0/1 grid into ceil(cw*ch/32) big-endian longwords."""
    flat = []
    for y in range(ch):
        flat.extend(bits[y])
    while len(flat) % 32:
        flat.append(0)
    out = []
    for i in range(0, len(flat), 32):
        v = 0
        for bit in flat[i:i + 32]:
            v = (v << 1) | bit
        out.append(v)
    return out


def build(spec, em=None):
    p = plan(spec, em)
    pre, NAME = spec["prefix"], spec["name"]
    cw, ch = p["cw"], p["ch"]
    up, xoff = p["up"], p["xoff"]
    storage = (cw * ch + 31) >> 5

    print("== %s (em=%d)" % (NAME, p["em"]))
    print("   ink above=%d below=%d  ascii max advance=%.2f  ascii ink width=%d"
          % (-p["top"], p["bot"], p["adv"], p["ink_w"]))
    print("   cell %dx%d  baseline row=%d  pen x=%d  storage=%d longwords"
          % (cw, ch, up, xoff, storage))
    print("   code points: %d needed, %d from the face, %d from CP437"
          % (len(p["cps"]), len(p["draw_cps"]) - len(p["missing"]),
             len(p["missing"])))
    if p["clip"]:
        print("   clipped to the cell by 1-2 px: %s"
              % " ".join("U+%04X" % c for c in p["clip"]))

    p["missing_set"] = set(p["missing"])

    def bits(cp):
        if cp == 0x20 or cp in p["missing_set"]:
            return bits_from_cp437(cp, cw, ch)
        return bits_from_ttf(p, cp)

    # --- blocks over the sorted code point set ---------------------------
    blocks = []
    for cp in p["cps"]:
        if blocks and cp == blocks[-1][0] + blocks[-1][1]:
            blocks[-1][1] += 1
        else:
            blocks.append([cp, 1])
    assert len(blocks) < 256, "too many blocks"

    glyphs = []
    for start, length in blocks:
        for cp in range(start, start + length):
            glyphs.append(bits(cp) if cp in gen_font.NEEDED else
                          [[0] * cw for _ in range(ch)])

    data_lines = []
    for g in glyphs:
        data_lines.append("    " + ",".join("0x%08Xu" % v
                                            for v in words(g, cw, ch)) + ",")
    data_lines[-1] = data_lines[-1].rstrip(",")

    block_lines = []
    for start, length in blocks:
        block_lines.append("    (uint32_t)(0x%Xu << 12) | 0x%Xu,"
                           % (start, length))
    block_lines[-1] = block_lines[-1].rstrip(",")

    U = pre.upper()
    src = []
    w = src.append
    w("/* GENERATED by tools/gen_ttf.py -- do not edit by hand. */")
    w("")
    w("#include <gint/display.h>")
    w("#include <gint/defs/types.h>")
    w('#include "%s_font.h"' % pre)
    w("")
    w("/* Unicode blocks: pairs of (first code point, length) packed into one")
    w(" * word as (start << 12) | length. */")
    w("static uint32_t const %s_blocks[] = {" % pre)
    src.extend(block_lines)
    w("};")
    w("")
    w("/* Glyph bitmaps: %d glyphs x %d longwords, MSB = leftmost pixel. */"
      % (len(glyphs), storage))
    w("static uint32_t const %s_data[] = {" % pre)
    src.extend(data_lines)
    w("};")
    w("")
    w("/* Declared with gint's own font_t so the compiler lays the bitfield")
    w(" * byte, the pointers and the trailing metrics out exactly the way")
    w(" * gint's renderer reads them. */")
    w("static font_t const %s_font = {" % pre)
    w('    "%s",' % NAME)
    w("    0, 0, 0, 0,              /* bold, italic, serif, mono */")
    w("    0,                       /* prop: fixed-width cell */")
    w("    %d,                      /* line_height */" % ch)
    w("    %d,                      /* data_height */" % ch)
    w("    %d,                      /* block_count */" % len(blocks))
    w("    %d,                      /* glyph_count */" % len(glyphs))
    w("    0,                       /* char_spacing: advance == %d px */" % cw)
    w("    (void *)%s_blocks," % pre)
    w("    (void *)%s_data," % pre)
    w("    { .width = %d, .storage_size = %d }" % (cw, storage))
    w("};")
    w("")
    w("font_t const *%s_font_get(void) { return &%s_font; }" % (pre, pre))
    w("")

    hdr = """/* GENERATED by tools/gen_ttf.py -- do not edit by hand. */
#ifndef %s_FONT_H
#define %s_FONT_H

#include <gint/display.h>
#include <gint/defs/types.h>

/* Cell size of the bundled "%s" face, cell-fitted to a fixed advance so a
 * text column n sits at x = n * %s_W. */
#define %s_W %d
#define %s_H %d

font_t const *%s_font_get(void);

#endif
""" % (U, U, NAME, U, U, cw, U, ch, pre)

    with open(os.path.join(ROOT, "src", "%s_font.c" % pre), "w",
              encoding="ascii") as fh:
        fh.write("\n".join(src))
    with open(os.path.join(ROOT, "src", "%s_font.h" % pre), "w",
              encoding="ascii") as fh:
        fh.write(hdr)

    print("   blocks=%d glyphs=%d font data=%d bytes  -> src/%s_font.{c,h}"
          % (len(blocks), len(glyphs), len(glyphs) * storage * 4, pre))
    if p["missing"]:
        print("   CP437 fallback for: %s"
              % " ".join("U+%04X" % c for c in p["missing"]))
    return p


def probe():
    for spec in SPECS:
        print("== %s  (%s)" % (spec["name"], spec["path"]))
        if not os.path.exists(spec["path"]):
            print("   MISSING FILE")
            continue
        for em in range(6, 21):
            try:
                p = plan(spec, em)
            except SystemExit as e:
                print("   em=%2d  %s" % (em, e))
                continue
            mark = "  <-- default" if em == spec["em"] else ""
            print("   em=%2d  cell %2dx%2d  adv=%5.2f  missing=%3d/%d  clip=%d%s"
                  % (em, p["cw"], p["ch"], p["adv"], len(p["missing"]),
                     len(p["cps"]), len(p["clip"]), mark))


def main():
    argv = sys.argv[1:]
    if "--probe" in argv:
        probe()
        return
    only = None
    em = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    if "--em" in argv:
        em = int(argv[argv.index("--em") + 1])
    for spec in SPECS:
        if only and spec["prefix"] != only:
            continue
        if not os.path.exists(spec["path"]):
            print("SKIP %s: %s not found" % (spec["name"], spec["path"]))
            continue
        build(spec, em)


if __name__ == "__main__":
    main()
