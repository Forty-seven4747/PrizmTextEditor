#!/usr/bin/env python3
"""gen_glyphtest.py -- write glyph-test.txt: one line per character the bundled
code-page face can draw, so the glyphs can be checked on the calculator.

The labels (byte value, U+ code point, Unicode name) are read straight out of
gen_font.py, so the test file cannot drift from the font that gets linked into
the add-in. Each line carries the raw test byte right after its [xx] label, so
the byte is never trailing (a CR at end of line would be eaten on load) and it
always sits at the same column for easy scanning.

Sections are split by character set, because the same byte means different
things on different pages: 0x01 is a smiley on the DOS page and a dot
everywhere else.

Run from anywhere:  python tools/gen_glyphtest.py [outfile]
"""

import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import gen_font as G          # noqa: E402  (authoritative code-page tables)


def cname(cp):
    """Unicode name, shortened so the line stays readable on a 49-col screen."""
    try:
        n = unicodedata.name(chr(cp))
    except ValueError:
        return "?"
    n = n.replace("BOX DRAWINGS ", "").replace(" AND ", " & ")
    return n


def row(b, cp, note=None):
    """[xx] <raw byte> U+xxxx  NAME"""
    label = " U+%04X  %s" % (cp, note or cname(cp))
    return b"[%02X] " % b + bytes([b]) + label.encode("ascii", "replace")


def section(n, title, intro, rows):
    out = [b"", b"", ("SECTION %d - %s" % (n, title)).encode("ascii"), b"-" * 72]
    out += [("  " + s).encode("ascii") for s in intro]
    out.append(b"")
    out += rows
    return out


HEADER = """TEXTEDIT GLYPH TEST -- bundled code-page face
========================================================================

WHAT THIS IS
  Every character the code-page face (wcfont) can draw, one per line, so the
  glyphs can be eyeballed on the calculator. The bytes in this file are raw:
  what a byte looks like depends on the Character set selected, so each
  section says which one to choose (SHIFT+MENU > Character set).

HOW TO READ A LINE
      [01] X U+263A  WHITE SMILING FACE
  [01]  = the byte value in hex (that is what is stored in the file)
  X     = the glyph the font should have drawn for that byte and page
  U+..  = the Unicode code point it is supposed to be
  NAME  = the expected shape, in words

HOW TO USE
  1. Copy this file into the calculator's storage memory, unchanged. Do not
     re-save it with an editor that rewrites text; it contains control bytes.
  2. Open it in TextEdit and turn wrapping ON (Settings > Wrap long lines) so
     the whole of each line stays visible.
  3. For each section set the Character set its header names, then walk the
     lines top to bottom and check the glyph matches its label.
  4. Section 4 lists bytes that are layout, not pictures: they are meant to be
     drawn as a plain dot.

  The cell is 8x9 on every page, so one label plus the glyph is at most about
  45 columns and the name runs on from there.
"""


ROWRE = re.compile(rb"^\[([0-9A-F]{2})\] (.?)( U\+([0-9A-F]{4})  .*)?$", re.S)


def expected(n, b):
    """Code point section n says byte b must draw."""
    if n == 1:
        return G.OEM_LO.get(b)
    if n == 2:
        return G.CP437_UNI[b]
    if n == 3:
        return G.CP1252_UNI[b]
    return 0x002E


def check(path):
    """Parse the generated file back and prove it matches the font tables."""
    with open(path, "rb") as f:
        lines = f.read().split(b"\n")

    sect = 0
    count = {1: 0, 2: 0, 3: 0, 4: 0}
    bad = 0
    for ln in lines:
        m = re.match(rb"^SECTION (\d) - ", ln)
        if m:
            sect = int(m.group(1))
            continue
        m = ROWRE.match(ln)
        if not m:
            continue
        where = "[%s]" % m.group(1).decode()
        raw = m.group(2)
        b = int(m.group(1), 16)
        got = int(m.group(4), 16) if m.group(4) else None
        want = expected(sect, b)
        count[sect] += 1

        # the raw byte, the label and the page table must all agree
        if len(raw) != 1 or raw[0] != b:
            print("BAD byte   %s: label says 0x%02X, file holds %r" % (where, b, raw))
            bad += 1
        # doc_load() eats a CR that sits at the end of a line, so a test byte
        # must never be the last byte of its own line
        if ln.endswith(bytes([b])):
            print("BAD layout %s: the test byte is last on the line and would be"
                  " eaten by doc_load()" % where)
            bad += 1
        if got != want:
            print("BAD cp     %s: label says U+%04X, page wants U+%04X"
                  % (where, got or -1, want or -1))
            bad += 1
        # every code point must have a real bitmap; only the deliberately
        # ink-less ones (NO-BREAK SPACE, SOFT HYPHEN, the dot) may be blank
        if want is not None and want not in ({0x00A0, 0x002E} | set(G.INVISIBLE)):
            if not any((r >> c) & 1 for r in G.glyph_for(want) for c in range(8)):
                print("BLANK      %s: U+%04X has no ink" % (where, want))
                bad += 1

    want_counts = {1: len(G.OEM_LO), 2: 128, 3: 128, 4: 2}
    for n in want_counts:
        if count[n] != want_counts[n]:
            print("BAD count  section %d: %d rows, expected %d"
                  % (n, count[n], want_counts[n]))
            bad += 1

    print("checked %d rows (sections %s)"
          % (sum(count.values()), ", ".join("%d:%d" % (n, count[n])
                                            for n in sorted(count))))
    print("PROBLEMS:", bad)
    return bad


def build():
    out = [HEADER.rstrip("\n").encode("ascii")]

    # 1. DOS page control slots -- the smileys, suits, arrows.
    rows = [b"  byte  glyph   code point   expected shape"]
    for b in sorted(G.OEM_LO):
        rows.append(row(b, G.OEM_LO[b]))
    out += section(
        1, "DOS/IBM-ASCII (OEM) control slots",
        ["Set Character set: DOS/IBM-ASCII (OEM)",
         "The DOS page puts graphics in slots 0x01-0x1F and 0x7F. This is the",
         "set that was just wired up, so it is the one to check first."],
        rows)

    # 2. DOS page upper half.
    rows = [b"  byte  glyph   code point   expected shape"]
    for b in range(0x80, 0x100):
        cp = G.CP437_UNI[b]
        note = "NO-BREAK SPACE (blank)" if cp == 0x00A0 else None
        rows.append(row(b, cp, note))
    out += section(
        2, "DOS/IBM-ASCII (OEM) upper half 0x80-0xFF",
        ["Set Character set: DOS/IBM-ASCII (OEM)",
         "Accents, box drawing, shades, blocks, Greek, math and the money",
         "signs. A run of these should tile into a seamless box frame."],
        rows)

    # 3. ANSI page upper half.
    rows = [b"  byte  glyph   code point   expected shape"]
    for b in range(0x80, 0x100):
        cp = G.CP1252_UNI[b]
        if cp == 0x002E:
            note = "undefined on this page (draws a dot)"
        elif cp == 0x00A0:
            note = "NO-BREAK SPACE (blank)"
        elif cp == 0x00AD:
            note = "SOFT HYPHEN (blank by design)"
        else:
            note = None
        rows.append(row(b, cp, note))
    out += section(
        3, "Windows (ANSI) upper half 0x80-0xFF",
        ["Set Character set: Windows (ANSI)",
         "Same bytes as section 2 but a different page: the accents move, the",
         "box drawing becomes punctuation (quotes, dashes, ellipsis, euro) and",
         "the five undefined slots fall back to a dot.",
         "The built-in 'Prizm standard' page equals this one for 0xA0-0xFF."],
        rows)

    # 4. Layout bytes: no glyph on purpose.
    rows = [
        b"  byte  glyph   code point   expected shape",
        row(0x09, 0x002E, "layout byte TAB -- the font draws a dot"),
        row(0x0D, 0x002E, "layout byte CR  -- the font draws a dot"),
    ]
    out += section(
        4, "layout bytes with no glyph",
        ["Set Character set: any",
         "NUL (0x00), LF (0x0A), TAB (0x09) and CR (0x0D) are layout, not",
         "pictures, so the face deliberately has no glyph for them and the",
         "editor draws a dot. NUL and LF cannot appear in a text file at all,",
         "so only TAB and CR are shown; both must come out as a dot."],
        rows)

    out.append(b"")
    return b"\n".join(out) + b"\n"


SECTION_PAGE = {1: 2, 2: 2, 3: 1, 4: 2}   # which page each section tests
BAND = 24                                  # glyphs per printed band


def enc_cp(b, page):
    """main.c's enc_cp() in Python -- same byte -> code point rule, so the
    preview shows exactly what the add-in will draw."""
    if b < 0x20:
        if page == 2:
            cp = G.OEM_LO.get(b)
            if cp:
                return cp
        return 0x2E
    if b == 0x7F:
        return 0x2302 if page == 2 else 0x2E
    if b < 0x80:
        return b
    if page == 1:
        return G.CP1252_UNI[b]
    if page == 2:
        return G.CP437_UNI[b]
    return b


def preview(path):
    """Print every section's glyphs as ASCII art, drawn from the file's own
    bytes through enc_cp() + glyph_for() -- the same path the add-in uses."""
    with open(path, "rb") as f:
        lines = f.read().split(b"\n")

    bands, sect, rows, title = [], 0, [], ""
    for ln in lines:
        m = re.match(rb"^SECTION (\d) - (.*)$", ln)
        if m:
            if sect:
                bands.append((sect, title, rows))
            sect, title, rows = int(m.group(1)), m.group(2).decode(), []
            continue
        m = ROWRE.match(ln)
        if m:
            rows.append(int(m.group(1), 16))
    if sect:
        bands.append((sect, title, rows))

    for n, ttl, bs in bands:
        glyphs = [G.glyph_for(enc_cp(b, SECTION_PAGE[n])) for b in bs]
        print("\n== SECTION %d - %s  (page %d, %d glyphs) =="
              % (n, ttl, SECTION_PAGE[n], len(bs)))
        for i in range(0, len(glyphs), BAND):
            chunk = glyphs[i:i + BAND]
            print("   " + " ".join("%-8s" % ("%02X" % b) for b in bs[i:i + BAND]))
            for ry in range(G.H):
                print("   " + " ".join(
                    "".join("#" if (g[ry] >> (7 - c)) & 1 else "." for c in range(8))
                    for g in chunk))
            print()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dest = args[0] if args else os.path.join(HERE, "glyph-test.txt")

    if "--check" not in sys.argv:
        data = build()
        with open(dest, "wb") as f:
            f.write(data)
        nlines = data.count(b"\n")
        print("wrote %s (%d bytes, %d lines)" % (dest, len(data), nlines))
        if nlines > 1500:
            print("WARNING: more than MAX_LINES (1500) -- the editor will truncate")

    if "--check" in sys.argv:
        sys.exit(1 if check(dest) else 0)

    if "--preview" in sys.argv:
        preview(dest)


if __name__ == "__main__":
    main()
