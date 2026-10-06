#!/usr/bin/env python3
"""check_font.py -- regenerate the bundled code-page font and verify it.

Run from anywhere:  python tools/check_font.py

Checks, in order:
  1. every code point that any of the three display modes can reach is inside
     a font block and has a non-blank glyph -- this is the regression that
     matters, since gint's default 8x9 face carries nothing above 0x7E;
  2. a handful of glyphs are drawn as ASCII art so a human can eyeball them;
  3. if a built textedit.g3a (or its .elf) is present, the signature bitmaps of
     a few forged glyphs must still be inside it -- i.e. the font really did
     make it into the artifact and was not dropped by the linker.
"""
import io
import os
import re
import sys
import contextlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(HERE)
sys.path.insert(0, HERE)

with contextlib.redirect_stdout(io.StringIO()):
    import gen_font as G        # regenerates src/wcfont.c and src/wcfont.h


def art(rows):
    return [format(r, "08b").replace("0", ".").replace("1", "#") for r in rows]


def covered(cp):
    return any(s <= cp < s + l for s, l in G.blocks)


# A space is a space, and 0x7F / 0xA0 / 0xAD are the defined-but-empty delete,
# no-break-space and soft-hyphen slots: blank is the correct rendering of all
# four, so they must not be reported as missing glyphs.
BLANK_OK = {0x20, 0x7F, 0x00A0, 0x00AD}

MODES = {
    "Standard (Latin-1)": [(b, b) for b in list(range(0x20, 0x7F)) + list(range(0xA0, 0x100))],
    "Windows (ANSI)":     [(b, G.CP1252_UNI[b]) for b in range(0x80, 0x100)],
    "DOS/IBM (OEM)":      [(b, G.CP437_UNI[b]) for b in range(0x80, 0x100) if G.CP437_UNI[b]],
}

bad = 0
for name, pairs in MODES.items():
    miss = ["0x%02X->U+%04X" % (b, cp) for b, cp in pairs if not covered(cp)]
    blank = ["0x%02X->U+%04X" % (b, cp) for b, cp in pairs
             if cp not in BLANK_OK and all(r == 0 for r in G.glyph_for(cp))]
    print("%-18s bytes=%3d uncovered=%d blank=%d" % (name, len(pairs), len(miss), len(blank)))
    for x in (miss + blank)[:8]:
        print("        ", x)
    bad += len(miss) + len(blank)
print("font: blocks=%d glyphs=%d storage=%d bytes/glyph"
      % (len(G.blocks), G.GLYPH_COUNT, G.STORAGE))

CASES = [
    ("ASCII pipes 0x7C and broken bar U+00A6", [0x7C, 0x00A6]),
    ("OEM box frame U+250C U+2500 U+2510", [0x250C, 0x2500, 0x2510]),
    ("OEM box vertical/junction U+2502 U+253C U+2580", [0x2502, 0x253C, 0x2580]),
    ("OEM shades U+2591 U+2592 U+2593 U+2588", [0x2591, 0x2592, 0x2593, 0x2588]),
    ("ANSI accents U+00C9 U+00C0 U+00CD U+00DD", [0x00C9, 0x00C0, 0x00CD, 0x00DD]),
    ("Latin-1 superscripts/times U+00B9 U+00B2 U+00B3 U+00D7",
     [0x00B9, 0x00B2, 0x00B3, 0x00D7]),
    ("typographic U+2013 U+2014 U+2026 U+00AF", [0x2013, 0x2014, 0x2026, 0x00AF]),
    ("diacritics U+00A8 U+00B4 and fractions U+00BC U+00BE",
     [0x00A8, 0x00B4, 0x00BC, 0x00BE]),
    ("section/pilcrow U+00A7 U+00B6", [0x00A7, 0x00B6]),
    ("ANSI quotes U+201C U+201D U+2018 U+2019", [0x201C, 0x201D, 0x2018, 0x2019]),
]
for title, cps in CASES:
    print("--- %s ---" % title)
    rows = [""] * G.H
    for cp in cps:
        g = G.glyph_for(cp)
        for y in range(G.H):
            rows[y] += "".join("#" if (g[y] >> (7 - x)) & 1 else "." for x in range(8))
    for line in rows:
        print("   " + line)

print("SOURCE PROBLEMS:", bad)

# --- 2b. the bundled rasterized faces --------------------------------------
# Lucida Console comes from tools/gen_lucida.py; the five TTF faces come from
# tools/gen_ttf.py. Both write the same shape of C file, so one parser covers
# them all. The check that matters is not the shapes but the invariant: every
# face must cover exactly the code points the code-page face covers, so
# switching faces never blanks a character out. The glyph data is decoded
# straight out of the .c files (no PIL, no TTF needed), so a committed font can
# always be re-verified from a bare checkout.
face_sigs = []          # (label, packed bitmap) -- checked against the artifact

# label, source basename, symbol prefix, macro prefix, sample code points
FACE_SPECS = [
    ("Lucida Console", "lucfont",  "luc", "LUC",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
    ("Consolas",       "con_font", "con", "CON",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
    ("Noto Sans",      "not_font", "not", "NOT",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
    ("Source Sans 3",  "ss3_font", "ss3", "SS3",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
    ("Comic Sans MS",  "cms_font", "cms", "CMS",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
    ("Roboto",         "rob_font", "rob", "ROB",
     [0x41, 0x67, 0x30, 0x250C, 0x253C, 0x00C9]),
]

for label, base, pre, up, samples in FACE_SPECS:
    c_path = os.path.join("src", base + ".c")
    h_path = os.path.join("src", base + ".h")
    if not (os.path.exists(c_path) and os.path.exists(h_path)):
        print("%s: src/%s.{c,h} MISSING" % (label, base))
        bad += 1
        continue

    c = open(c_path, encoding="ascii").read()
    h = open(h_path, encoding="ascii").read()
    W = int(re.search(r"#define %s_W (\d+)" % up, h).group(1))
    H = int(re.search(r"#define %s_H (\d+)" % up, h).group(1))
    blocks = [(int(a, 16), int(b, 16)) for a, b in re.findall(
        r"\(uint32_t\)\(0x([0-9A-Fa-f]+)u << 12\) \| 0x([0-9A-Fa-f]+)u", c)]
    words = [int(x, 16) for x in re.findall(
        r"0x([0-9A-Fa-f]{8})u", c.split("%s_data[] = {" % pre)[1].split("};")[0])]
    count = int(re.search(r"(\d+),\s*/\* glyph_count \*/", c).group(1))
    storage = int(re.search(r"\.storage_size = (\d+)", c).group(1))
    width = int(re.search(r"\.width = (\d+)", c).group(1))
    prop = int(re.search(r"(\d+),\s*/\* prop", c).group(1))
    spacing = int(re.search(r"(\d+),\s*/\* char_spacing", c).group(1))
    height = int(re.search(r"(\d+),\s*/\* line_height \*/", c).group(1))

    covered = set()
    for s, l in blocks:
        covered.update(range(s, s + l))
    missing = sorted(G.NEEDED - covered)
    blank = []
    for cp in sorted(G.NEEDED - set(BLANK_OK)):
        g = None
        i = 0
        for s, l in blocks:
            if s <= cp < s + l:
                gi = i + (cp - s)
                bits = "".join(format(v, "032b") for v in
                               words[gi * storage:(gi + 1) * storage])
                g = bits
                break
            i += l
        if g is None or "1" not in g:
            blank.append(cp)

    print("%s: cell %dx%d blocks=%d glyphs=%d storage=%d"
          % (label, W, H, len(blocks), count, storage))
    print("  needed=%d covered=%d missing=%d blank=%d"
          % (len(G.NEEDED), len(G.NEEDED) - len(missing), len(missing), len(blank)))
    for cp in missing[:8]:
        print("        no block: U+%04X" % cp)
    for cp in blank[:8]:
        print("        blank   : U+%04X" % cp)

    # The grid contract: fixed advance == width, one storage size for all.
    if prop != 0:
        print("  prop=%d -- the editor grids by the cell, this must be 0" % prop)
        bad += 1
    if spacing != 0:
        print("  char_spacing=%d -- advance would not equal the cell width" % spacing)
        bad += 1
    if width != W:
        print("  .width=%d but %s_W=%d" % (width, up, W))
        bad += 1
    if storage != (W * H + 31) // 32:
        print("  storage=%d, expected %d for a %dx%d cell"
              % (storage, (W * H + 31) // 32, W, H))
        bad += 1
    if height != H:
        print("  line_height=%d but %s_H=%d" % (height, up, H))
        bad += 1
    if len(words) != count * storage:
        print("  DATA LENGTH MISMATCH: %d longwords, expected %d"
              % (len(words), count * storage))
        bad += 1
    bad += len(missing) + len(blank)

    # Decode rows so a human can eyeball the face at 1:1.
    def glyph(cp):
        i = 0
        for s, l in blocks:
            if s <= cp < s + l:
                gi = i + (cp - s)
                bits = "".join(format(v, "032b")
                               for v in words[gi * storage:(gi + 1) * storage])
                return [bits[y * W:(y + 1) * W] for y in range(H)]
            i += l
        return None

    print("--- %s samples (A g 0, box light+cross, E-acute) ---" % label)
    rows = [""] * H
    for cp in samples:
        g = glyph(cp)
        for y in range(H):
            rows[y] += (g[y] if g else "." * W).replace("0", ".").replace("1", "#")
    for line in rows:
        print("   " + line)

    # Pack a few glyphs so part 3 can prove the face landed in the artifact
    # rather than being dropped by the linker.
    for cp, what in ((0x41, "A"), (0x253C, "box cross U+253C"),
                     (0x2588, "full block U+2588")):
        g = None
        i = 0
        for s, l in blocks:
            if s <= cp < s + l:
                gi = i + (cp - s)
                g = words[gi * storage:(gi + 1) * storage]
                break
            i += l
        if g:
            face_sigs.append(("%s %s" % (label, what),
                              b"".join(w.to_bytes(4, "big") for w in g)))

# --- 3. artifact spot check ------------------------------------------------
SIGS = {
    "ASCII '|' (solid)":   0x7C,
    "U+00A6 broken bar":   0x00A6,
    "U+2026 ellipsis":     0x2026,
    "U+2588 full block":   0x2588,
}
for cand in ("textedit.g3a", os.path.join("build-cg", "textedit.elf")):
    if not os.path.exists(cand):
        continue
    blob = open(cand, "rb").read()
    print("--- artifact %s (%d bytes) ---" % (cand, len(blob)))
    for label, cp in SIGS.items():
        packed = b"".join(w.to_bytes(4, "big") for w in G.words(G.glyph_for(cp)))
        ok = blob.count(packed) > 0
        print("   %-20s bitmap in artifact: %s" % (label, "yes" if ok else "NO"))
        if not ok:
            bad += 1
    for label, packed in face_sigs:
        ok = blob.count(packed) > 0
        print("   %-34s bitmap in artifact: %s" % (label, "yes" if ok else "NO"))
        if not ok:
            bad += 1
    break

print("TOTAL PROBLEMS:", bad)
sys.exit(1 if bad else 0)
