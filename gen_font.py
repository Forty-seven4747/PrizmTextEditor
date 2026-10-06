#!/usr/bin/env python3
"""
gen_font.py -- build src/wcfont.c / src/wcfont.h for the TEXTEDIT add-in.

Why this exists: gint's default fx-CG50 font (gint_font8x9) only carries
0x20-0x7E, so bytes >= 0x80 have no glyph at all and any code-page text
shows up as blanks. This script turns the classic IBM VGA CP437 bitmap
face (public domain -- bitmap typefaces are non-copyrightable data) into a
gint `font_t` that covers the whole CP437 repertoire plus the extra Latin-1
and punctuation code points that Windows-1252 needs.

Output font properties
    monospaced, 8 px wide, 9 px line height (matches gint's 8x9 default)
    256-code-point-spread over tight Unicode blocks
    char_spacing 0  ->  advance == width == 8, so content column n sits at
                        x = n*8 exactly; no kerning maths anywhere.

The font is indexed by UNICODE CODE POINT, because gint decodes UTF-8 before
looking a glyph up. Two tables (CP437 / CP1252 byte -> code point) are emitted
alongside so main.c can turn raw file bytes into the right code points.

Run:  python3 gen_font.py          (writes src/wcfont.{c,h})
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from cp437_data import CP437 as _CP437_COLS  # noqa: E402

W, H = 8, 9            # cell width / line height
NAME = "CP437"

# ---------------------------------------------------------------------------
# 1. CP437 columns -> rows
# ---------------------------------------------------------------------------
# The luma/max7219 table stores one byte per COLUMN with bit 0 = top row.
# gint (like every 8x8 bitmap font) wants one byte per ROW with bit 7 = the
# leftmost pixel, so transpose and flip.

def _cols_to_rows(cols):
    rows = []
    for r in range(8):
        b = 0
        for c in range(8):
            if (cols[c] >> r) & 1:
                b |= 1 << (7 - c)
        rows.append(b)
    return rows

GLYPH = [_cols_to_rows(c) for c in _CP437_COLS]      # GLYPH[byte] -> 8 row bytes
assert len(GLYPH) == 256

# The source face draws ASCII '|' with a gap in the middle (rows 0-2 and 4-6
# only), which is really the shape of the "broken bar" U+00A6. A plain-text
# editor has to show a solid stem, so rebuild it here; U+00A6 picks up the
# broken pattern further down in DRAWN.
GLYPH[0x7C] = [0x18] * 8

# ---------------------------------------------------------------------------
# 2. code page tables
# ---------------------------------------------------------------------------

# CP437 byte -> Unicode. The 0x80-0xFF half is the classic DOS page; the
# 0x01-0x1F control slots are listed too, because that is where the DOS
# graphics live (smileys, card suits, arrows...) and the OEM character set is
# supposed to be able to show them. Deliberately absent: NUL, TAB, LF and CR --
# they are layout, not pictures, so main.c keeps folding them to '.'.
CP437_UNI = [None] * 256
for i in range(0x20, 0x7F):
    CP437_UNI[i] = i
OEM_LO = {
    0x01: 0x263A, 0x02: 0x263B, 0x03: 0x2665, 0x04: 0x2666,
    0x05: 0x2663, 0x06: 0x2660, 0x07: 0x2022, 0x08: 0x25D8,
    0x0B: 0x2642, 0x0C: 0x2640, 0x0E: 0x266B, 0x0F: 0x263C,
    0x10: 0x25BA, 0x11: 0x25C4, 0x12: 0x2195, 0x13: 0x203C,
    0x14: 0x00B6, 0x15: 0x00A7, 0x16: 0x25AC, 0x17: 0x21A8,
    0x18: 0x2191, 0x19: 0x2193, 0x1A: 0x2192, 0x1B: 0x2190,
    0x1C: 0x221F, 0x1D: 0x2194, 0x1E: 0x25B2, 0x1F: 0x25BC,
    0x7F: 0x2302,
}
_DOS = {
    0x07: 0x2022, 0x7F: 0x2302,
    0x80: 0x00C7, 0x81: 0x00FC, 0x82: 0x00E9, 0x83: 0x00E2, 0x84: 0x00E4,
    0x85: 0x00E0, 0x86: 0x00E5, 0x87: 0x00E7, 0x88: 0x00EA, 0x89: 0x00EB,
    0x8A: 0x00E8, 0x8B: 0x00EF, 0x8C: 0x00EE, 0x8D: 0x00EC, 0x8E: 0x00C4,
    0x8F: 0x00C5, 0x90: 0x00C9, 0x91: 0x00E6, 0x92: 0x00C6, 0x93: 0x00F4,
    0x94: 0x00F6, 0x95: 0x00F2, 0x96: 0x00FB, 0x97: 0x00F9, 0x98: 0x00FF,
    0x99: 0x00D6, 0x9A: 0x00DC, 0x9B: 0x00A2, 0x9C: 0x00A3, 0x9D: 0x00A5,
    0x9E: 0x20A7, 0x9F: 0x0192,
    0xA0: 0x00E1, 0xA1: 0x00ED, 0xA2: 0x00F3, 0xA3: 0x00FA, 0xA4: 0x00F1,
    0xA5: 0x00D1, 0xA6: 0x00AA, 0xA7: 0x00BA, 0xA8: 0x00BF, 0xA9: 0x2310,
    0xAA: 0x00AC, 0xAB: 0x00BD, 0xAC: 0x00BC, 0xAD: 0x00A1, 0xAE: 0x00AB,
    0xAF: 0x00BB,
    0xB0: 0x2591, 0xB1: 0x2592, 0xB2: 0x2593, 0xB3: 0x2502, 0xB4: 0x2524,
    0xB5: 0x2561, 0xB6: 0x2562, 0xB7: 0x2556, 0xB8: 0x2555, 0xB9: 0x2563,
    0xBA: 0x2551, 0xBB: 0x2557, 0xBC: 0x255D, 0xBD: 0x255C, 0xBE: 0x255B,
    0xBF: 0x2510,
    0xC0: 0x2514, 0xC1: 0x2534, 0xC2: 0x252C, 0xC3: 0x251C, 0xC4: 0x2500,
    0xC5: 0x253C, 0xC6: 0x255E, 0xC7: 0x255F, 0xC8: 0x255A, 0xC9: 0x2554,
    0xCA: 0x2569, 0xCB: 0x2566, 0xCC: 0x2560, 0xCD: 0x2550, 0xCE: 0x256C,
    0xCF: 0x2567,
    0xD0: 0x2568, 0xD1: 0x2564, 0xD2: 0x2565, 0xD3: 0x2559, 0xD4: 0x2558,
    0xD5: 0x2552, 0xD6: 0x2553, 0xD7: 0x256B, 0xD8: 0x256A, 0xD9: 0x2518,
    0xDA: 0x250C, 0xDB: 0x2588, 0xDC: 0x2584, 0xDD: 0x258C, 0xDE: 0x2590,
    0xDF: 0x2580,
    0xE0: 0x03B1, 0xE1: 0x00DF, 0xE2: 0x0393, 0xE3: 0x03C0, 0xE4: 0x03A3,
    0xE5: 0x03C3, 0xE6: 0x00B5, 0xE7: 0x03C4, 0xE8: 0x03A6, 0xE9: 0x0398,
    0xEA: 0x03A9, 0xEB: 0x03B4, 0xEC: 0x221E, 0xED: 0x03C6, 0xEE: 0x03B5,
    0xEF: 0x2229,
    0xF0: 0x2261, 0xF1: 0x00B1, 0xF2: 0x2265, 0xF3: 0x2264, 0xF4: 0x2320,
    0xF5: 0x2321, 0xF6: 0x00F7, 0xF7: 0x2248, 0xF8: 0x00B0, 0xF9: 0x2219,
    0xFA: 0x00B7, 0xFB: 0x221A, 0xFC: 0x207F, 0xFD: 0x00B2, 0xFE: 0x25A0,
    0xFF: 0x00A0,
}
for _b, _u in OEM_LO.items():
    CP437_UNI[_b] = _u
for k, v in _DOS.items():
    CP437_UNI[k] = v

# Windows-1252 byte -> Unicode (0x80-0xFF). The five undefined slots render
# as a plain dot rather than silently dropping a column.
CP1252_UNI = [0x002E] * 256
for i in range(0x20, 0x7F):
    CP1252_UNI[i] = i
for i in range(0xA0, 0x100):
    CP1252_UNI[i] = i
for _b, _u in {
    0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E, 0x85: 0x2026,
    0x86: 0x2020, 0x87: 0x2021, 0x88: 0x02C6, 0x89: 0x2030, 0x8A: 0x0160,
    0x8B: 0x2039, 0x8C: 0x0152, 0x8E: 0x017D,
    0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201C, 0x94: 0x201D, 0x95: 0x2022,
    0x96: 0x2013, 0x97: 0x2014, 0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161,
    0x9B: 0x203A, 0x9C: 0x0153, 0x9E: 0x017E, 0x9F: 0x0178,
}.items():
    CP1252_UNI[_b] = _u

# ---------------------------------------------------------------------------
# 3. glyphs for code points CP437 has no bitmap for
# ---------------------------------------------------------------------------
# 3a. Letters that only Windows-1252 uses. CP437 has the accented LOWERCASE
# letters and a few capitals, but none of the uppercase grave/acute/circumflex/
# tilde/diaeresis forms. Those are built by shifting the plain letter down two
# rows and stamping a small accent into the freed space at the top.
ACC = {
    "grave":  (0x20, 0x10),      # \  shape, two rows
    "acute":  (0x10, 0x20),      # /  shape
    "circ":   (0x10, 0x28),      # ^
    "caron":  (0x28, 0x10),      # v  (circ flipped)
    "tilde":  (0x0C, 0x30),      # ~
    "diaer":  (0x28, 0x00),      # ..
}
COMPOSE = {
    0x00C0: ("A", "grave"), 0x00C1: ("A", "acute"), 0x00C2: ("A", "circ"),
    0x00C3: ("A", "tilde"),
    0x00C8: ("E", "grave"), 0x00CA: ("E", "circ"), 0x00CB: ("E", "diaer"),
    0x00CC: ("I", "grave"), 0x00CD: ("I", "acute"), 0x00CE: ("I", "circ"),
    0x00CF: ("I", "diaer"),
    0x00D2: ("O", "grave"), 0x00D3: ("O", "acute"), 0x00D4: ("O", "circ"),
    0x00D5: ("O", "tilde"),
    0x00D9: ("U", "grave"), 0x00DA: ("U", "acute"), 0x00DB: ("U", "circ"),
    0x00DD: ("Y", "acute"), 0x00FD: ("y", "acute"),
    0x00E3: ("a", "tilde"), 0x00F5: ("o", "tilde"),
    0x0160: ("S", "caron"), 0x0161: ("s", "caron"),
    0x0178: ("Y", "diaer"),
    0x017D: ("Z", "caron"), 0x017E: ("z", "caron"),
}


def _rows(*spec):
    """ASCII-art rows ('#' = ink, bit 7 = leftmost) -> row bytes."""
    out = []
    for s in spec:
        b = 0
        for i, ch in enumerate(s):
            if ch == '#':
                b |= 1 << (7 - i)
        out.append(b)
    return out


# Letters Windows-1252 needs and CP437 has no shape for at all. Drawn in the
# same 8-row cell and the same weight as the transcribed CP437 glyphs, so they
# sit in a line of text without standing out: '#..' strokes are as wide as the
# page face's own (see 'P', 'o', 'D' above).
HAND = {
    # O with a stroke: the diagonal runs (0,6)..(6,0) through the letter.
    0x00D8: _rows("..###.#.", ".##.##..", "##..###.", "##.#.##.",
                  "###..##.", ".##.##..", "#.####..", "........"),
    # o with the same stroke, lengthened past both corners.
    0x00F8: _rows(".......#", "......#.", ".####.#.", "##..##..",
                  "##.#.##.", "###..##.", ".####...", "#......."),
    # ETH: D with a bar leaving the stem to the left.
    0x00D0: _rows("#####...", ".##.##..", ".##..##.", "###..##.",
                  ".##..##.", ".##.##..", "#####...", "........"),
    # eth: an o body with the diagonal stroke coming down into it.
    0x00F0: _rows("....#...", "...#....", "..##....", ".####...",
                  "##..##..", "##..##..", ".####...", "........"),
    # THORN: the P bowl on a stem that runs the full height.
    0x00DE: _rows("#####...", ".##.##..", ".##..##.", ".##..##.",
                  ".#####..", ".##.....", ".##.....", "........"),
    # thorn: the p bowl on a stem that rises above it, foot at the baseline.
    0x00FE: _rows(".##.....", ".##.....", ".##.###.", ".##..##.",
                  ".##..##.", ".#####..", ".##.....", "####...."),
    # OE: a 4-wide O butted against a 3-wide E.
    0x0152: _rows(".##..###", "#..#.#..", "#..#.#..", "#..#.##.",
                  "#..#.#..", "#..#.#..", ".##..###", "........"),
    # oe: the same pair at x-height.
    0x0153: _rows("........", "........", ".##..##.", "#..#.#..",
                  "#..#.##.", "#..#.#..", ".##..##.", "........"),
    # CURRENCY: a small ring with four ticks.
    0x00A4: _rows("........", "..#..#..", "..####..", ".##..##.",
                  ".##..##.", "..####..", "..#..#..", "........"),
    # COPYRIGHT: 8-tall ring around a lower-case c.
    0x00A9: _rows("..####..", ".#....#.", "#..##..#", "#.#....#",
                  "#.#....#", "#..##..#", ".#....#.", "..####.."),
    # REGISTERED: the same ring around an R.
    0x00AE: _rows("..####..", ".#....#.", "#.##...#", "#.#.#..#",
                  "#.##...#", "#.#.#..#", ".#....#.", "..####.."),
    # CEDILLA: the hook, sitting below the baseline.
    0x00B8: _rows("........", "........", "........", "........",
                  "........", "..####..", "....##..", ".####..."),
    # THREE QUARTERS: 3 top-left, slash, 4 bottom-right (the 1/2 and 1/4
    # glyphs are transcribed CP437, so only this third one has to be drawn).
    0x00BE: _rows(".##.....", "..#...#.", ".##..#..", "..#.#...",
                  ".##.###.", "..#.#.#.", ".##..###", "......#."),
    # DAGGER.
    0x2020: _rows("...##...", "...##...", ".######.", "...##...",
                  "...##...", "...##...", "...##...", "...##..."),
    # DOUBLE DAGGER.
    0x2021: _rows("...##...", ".######.", "...##...", ".######.",
                  "...##...", "...##...", "...##...", "...##..."),
    # PER MILLE: one ring, slash, two rings.
    0x2030: _rows("........", "##....#.", "##...#..", "....#...",
                  "...#....", "..###.##", "..###.##", "........"),
    # SINGLE ANGLE QUOTES: '<' / '>' shrunk to the x-height.
    0x2039: _rows("........", "........", "..##....", ".##.....",
                  "##......", ".##.....", "..##....", "........"),
    0x203A: _rows("........", "........", ".##.....", "..##....",
                  "...##...", "..##....", ".##.....", "........"),
    # EURO: the C with two bars through it.
    0x20AC: _rows("..####..", ".##..##.", "######..", "##......",
                  "######..", ".##..##.", "..####..", "........"),
    # TRADE MARK: a tiny T and M.
    0x2122: _rows("###.####", ".#..#..#", ".#..#..#", "........",
                  "........", "........", "........", "........"),
    # MODIFIER CIRCUMFLEX / SMALL TILDE: the accent shapes as spacing marks.
    0x02C6: _rows("...#....", "..#.#...", ".##.##..", "........",
                  "........", "........", "........", "........"),
    0x02DC: _rows(".###.##.", "##.###..", "........", "........",
                  "........", "........", "........", "........"),
    # Typographic quotes. The two single marks differ only in which way the
    # tail leans, which is all an 8x8 cell can say about them.
    0x2018: _rows("..##....", "..##....", "...##...", "........",
                  "........", "........", "........", "........"),
    0x2019: _rows("..##....", "..##....", ".##.....", "........",
                  "........", "........", "........", "........"),
    0x201A: _rows("........", "........", "........", "........",
                  "........", "..##....", "..##....", ".##....."),
    0x201C: _rows("..##.##.", "..##.##.", "...##.##", "........",
                  "........", "........", "........", "........"),
    0x201D: _rows(".##.##..", ".##.##..", "##..##..", "........",
                  "........", "........", "........", "........"),
    0x201E: _rows("........", "........", "........", "........",
                  "........", ".##.##..", ".##.##..", "##..##.."),
}

# 3b. Hand-drawn glyphs. CP437 has no 1/3 superscripts and no multiplication
# sign (its superscript 2 lives at 0xFD, but 1, 3 and the times sign do not
# exist anywhere in the page). The diacritics, dashes and ellipsis below have
# no CP437 source at all, and the ASCII stand-ins CP437 does offer (" , ' - .)
# sit on the wrong rows to read as accents, dashes or an ellipsis.
DRAWN = {
    0x00B9: [0x20, 0x60, 0x20, 0x20, 0x70, 0x00, 0x00, 0x00],   # superscript 1
    0x00B3: [0x78, 0x08, 0x38, 0x08, 0x78, 0x00, 0x00, 0x00],   # superscript 3
    0x00D7: [0x00, 0x00, 0x44, 0x28, 0x10, 0x28, 0x44, 0x00],   # multiplication
    0x00A6: [0x18, 0x18, 0x18, 0x00, 0x18, 0x18, 0x18, 0x00],   # broken bar
    0x00A8: [0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],   # diaeresis
    0x00AF: [0x00, 0x7E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],   # macron
    0x00B4: [0x10, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],   # acute accent
    0x2013: [0x00, 0x00, 0x00, 0xFE, 0x00, 0x00, 0x00, 0x00],   # en dash
    0x2014: [0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00],   # em dash
    0x2026: [0x00, 0x00, 0x00, 0x00, 0x00, 0xDB, 0xDB, 0x00],   # ellipsis
}

# 3d. Fallback safety net. Every code point the two pages can name now has a
# real bitmap (transcribed, composed, hand-drawn), which the assert above
# enforces -- so nothing reaches this table. It is kept so that a future page
# can degrade to a close ASCII stand-in instead of a blank column.
FALLBACK = {
    0x00A4: "o", 0x00A9: "c", 0x00AE: "R",
    0x00B8: ",", 0x00BE: "3",
    0x00D0: "D", 0x00D8: "O", 0x00DE: "P",
    0x00F0: "o", 0x00F8: "o", 0x00FE: "p",
    0x0152: "O", 0x0153: "o", 0x0160: "S", 0x0161: "s",
    0x0178: "Y", 0x017D: "Z", 0x017E: "z",
    0x02C6: "^", 0x02DC: "~",
    0x2018: "'", 0x2019: "'", 0x201A: ",",
    0x201C: '"', 0x201D: '"', 0x201E: '"',
    0x2020: "+", 0x2021: "+", 0x2030: "%",
    0x2039: "<", 0x203A: ">", 0x20AC: "E", 0x2122: "T",
}

UNI2BYTE = {}
for _b, _u in enumerate(CP437_UNI):
    if _u is not None and _u not in UNI2BYTE:
        UNI2BYTE[_u] = _b


def glyph_for(cp):
    """Return H row bytes (bit 7 = leftmost) for code point cp."""
    if cp in UNI2BYTE:
        return list(GLYPH[UNI2BYTE[cp]]) + [0] * (H - 8)
    if cp in DRAWN:
        return list(DRAWN[cp]) + [0] * (H - len(DRAWN[cp]))
    if cp in COMPOSE:
        base, acc = COMPOSE[cp]
        src = GLYPH[ord(base)]
        out = [0] * H
        a0, a1 = ACC[acc]
        out[0] = a0
        out[1] = a1
        for i in range(7):                       # base rows 0..6 -> out 2..8
            out[2 + i] = src[i]
        return out
    if cp in HAND:
        return list(HAND[cp]) + [0] * (H - len(HAND[cp]))
    ch = FALLBACK.get(cp)
    if ch is not None:
        return list(GLYPH[ord(ch)]) + [0] * (H - 8)
    return [0] * H


# ---------------------------------------------------------------------------
# 4. code point set -> blocks
# ---------------------------------------------------------------------------
NEEDED = set(range(0x20, 0x7F))
NEEDED |= {u for u in CP437_UNI if u}     # includes the OEM control slots
NEEDED |= {u for b, u in enumerate(CP1252_UNI) if b >= 0x80 and u}

# Every code point in the repertoire must resolve to a REAL bitmap. The ASCII
# stand-ins in FALLBACK are a net that must now go unused: a silent stand-in is
# exactly the kind of thing that ships without anyone noticing, so this is a
# hard check rather than a warning. Soft hyphen is the one code point that is
# blank on purpose -- it is invisible unless it happens to break a line.
INVISIBLE = {0x00AD}
STANDINS = sorted(cp for cp in NEEDED if cp not in INVISIBLE
                  and cp not in UNI2BYTE and cp not in DRAWN
                  and cp not in COMPOSE and cp not in HAND)
assert not STANDINS, "still drawn as an ASCII stand-in: %s" % [
    "U+%04X" % c for c in STANDINS]

CPS = sorted(NEEDED)
blocks = []
for cp in CPS:
    if blocks and cp == blocks[-1][0] + blocks[-1][1]:
        blocks[-1][1] += 1
    else:
        blocks.append([cp, 1])
assert len(blocks) < 256, "too many blocks"

GLYPHS = []
for start, length in blocks:
    for cp in range(start, start + length):
        GLYPHS.append(glyph_for(cp) if cp in NEEDED else [0] * H)
GLYPH_COUNT = len(GLYPHS)
assert GLYPH_COUNT == sum(l for _, l in blocks)


# ---------------------------------------------------------------------------
# 5. emit
# ---------------------------------------------------------------------------
def words(rows):
    """Pack H row bytes into ceil(W*H/32) big-endian longwords."""
    bits = []
    for r in rows:
        for x in range(8):
            bits.append((r >> (7 - x)) & 1)
    while len(bits) % 32:
        bits.append(0)
    out = []
    for i in range(0, len(bits), 32):
        v = 0
        for bit in bits[i:i + 32]:
            v = (v << 1) | bit
        out.append(v)
    return out


STORAGE = (W * H + 31) >> 5
assert STORAGE == 3

data_lines = []
for g in GLYPHS:
    ws = words(g)
    data_lines.append("    " + ",".join("0x%08Xu" % v for v in ws) + ",")
data_lines[-1] = data_lines[-1].rstrip(",")

block_lines = []
for start, length in blocks:
    block_lines.append("    (uint32_t)(0x%Xu << 12) | 0x%Xu," % (start, length))
block_lines[-1] = block_lines[-1].rstrip(",")

cp437_lines = ["    0x%04X," % CP437_UNI[0x80 + i] for i in range(128)]
cp1252_lines = ["    0x%04X," % CP1252_UNI[0x80 + i] for i in range(128)]
oem_lo_lines = ["    0x%04X," % (OEM_LO.get(i) or 0) for i in range(0x20)]
oem_lo_lines[-1] = oem_lo_lines[-1].rstrip(",")

src = []
w = src.append
w("/* GENERATED by gen_font.py -- do not edit by hand. */")
w("")
w("#include <gint/display.h>")
w("#include <gint/defs/types.h>")
w("#include \"wcfont.h\"")
w("")
w("/* Unicode blocks: pairs of (first code point, length) packed into one")
w(" * word as (start << 12) | length. */")
w("static uint32_t const wc_blocks[] = {")
src.extend(block_lines)
w("};")
w("")
w("/* Glyph bitmaps: %d glyphs x %d longwords, each row one byte, MSB first. */"
  % (GLYPH_COUNT, STORAGE))
w("static uint32_t const wc_data[] = {")
src.extend(data_lines)
w("};")
w("")
w("/* The font itself, declared with gint's own font_t so the compiler lays the")
w(" * bitfield byte, the pointers and the trailing metrics out exactly the way")
w(" * gint's renderer reads them. The unnamed :24 filler is skipped by the")
w(" * initializer, which is what C requires for unnamed bitfields. */")
w("static font_t const wc_font = {")
w("    \"%s\"," % NAME)
w("    0,                       /* bold */")
w("    0,                       /* italic */")
w("    0,                       /* serif */")
w("    0,                       /* mono */")
w("    0,                       /* prop: fixed-width, not proportional */")
w("    %d,                      /* line_height */" % H)
w("    %d,                      /* data_height */" % H)
w("    %d,                      /* block_count */" % len(blocks))
w("    %d,                      /* glyph_count */" % GLYPH_COUNT)
w("    0,                       /* char_spacing: advance == width == %d px */" % W)
w("    (void *)wc_blocks,")
w("    (void *)wc_data,")
w("    { .width = %d, .storage_size = %d }" % (W, STORAGE))
w("};")
w("")
w("font_t const *wc_font_get(void) { return &wc_font; }")
w("")
w("/* Byte -> code point for the two Windows/DOS pages main.c can select. */")
w("uint16_t const wc_cp437[128] = {")
src.extend(cp437_lines)
w("};")
w("")
w("uint16_t const wc_cp1252[128] = {")
src.extend(cp1252_lines)
w("};")
w("")
w("/* OEM control slots 0x00-0x1F -> code point, 0 where the slot holds no")
w(" * graphic (NUL/TAB/LF/CR). Index with the raw byte. DEL (0x7F) is the house")
w(" * U+2302; main.c substitutes it directly when the OEM set is selected. */")
w("uint16_t const wc_cp437_lo[32] = {")
src.extend(oem_lo_lines)
w("};")
w("")

hdr = """/* GENERATED by gen_font.py -- do not edit by hand. */
#ifndef WCFONT_H
#define WCFONT_H

#include <gint/display.h>
#include <gint/defs/types.h>

/* Cell size of the bundled code-page font. Monospaced: every character is
 * exactly WC_W pixels wide, so a text column n starts at x = n * WC_W. */
#define WC_W 8
#define WC_H 9

/* The font, covering ASCII, Latin-1, CP437 box drawing / blocks / symbols,
 * Greek and the Windows-1252 punctuation range. */
font_t const *wc_font_get(void);

/* High-half byte -> Unicode code point, for the DOS/IBM (OEM) and
 * Windows (ANSI) character sets. Index with (byte - 0x80). */
extern uint16_t const wc_cp437[128];
extern uint16_t const wc_cp1252[128];

/* OEM control slots: raw byte 0x00-0x1F -> code point, 0 when the slot has no
 * graphic. The DOS page puts its smileys, card suits and arrows here; the
 * other two pages leave control bytes as '.' and never look at this table.
 * DEL (0x7F) is the house U+2302, which main.c substitutes for the OEM set. */
extern uint16_t const wc_cp437_lo[32];

#endif
"""

def main():
    """Write the generated sources. Kept out of import time so that other
    scripts (tools/gen_lucida.py) can reuse the tables above without rewriting
    these files as a side effect of importing this module."""
    out_c = os.path.join(HERE, "src", "wcfont.c")
    out_h = os.path.join(HERE, "src", "wcfont.h")
    with open(out_c, "w", encoding="ascii") as f:
        f.write("\n".join(src))
    with open(out_h, "w", encoding="ascii") as f:
        f.write(hdr)

    print("blocks=%d glyphs=%d storage=%d" % (len(blocks), GLYPH_COUNT, STORAGE))
    print("wrote %s and %s" % (out_c, out_h))

    # -----------------------------------------------------------------------
    # 6. ASCII-art self check
    # -----------------------------------------------------------------------
    if "--check" in sys.argv:
        for cp in (0x41, 0x30, 0xE9, 0xC4, 0xB0, 0xDB, 0x03, 0x263A, 0x00C0):
            print("--- U+%04X ---" % cp)
            for r in glyph_for(cp):
                print("   " + format(r, "08b").replace("0", ".").replace("1", "#"))


if __name__ == "__main__":
    main()
