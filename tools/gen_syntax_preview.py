#!/usr/bin/env python3
"""gen_syntax_preview.py -- mock 396x224 editor screens showing the "Syntax"
colouring, soft wrap, line-break markers and the find highlight, into
syntax-preview.png.

The glyphs are decoded from the same src/wcfont.c that gets linked in, so the
cells and the 1-bit cut match the device, and the keyword tables are read
straight out of src/main.c so they cannot drift. The tokeniser itself is a
Python mirror of syn_scan() in src/main.c; that C version is separately checked
against the same samples by a host harness, so treat this as a faithful mock of
the shipped code rather than the shipped code.

Run from anywhere:  python tools/gen_syntax_preview.py [scale]
"""

import os
import re
import sys

from PIL import Image

from gen_faces_preview import load_face      # same decoder the font sheet uses

DWIDTH, DHEIGHT = 396, 224
BAR = 15
TEXT_GAP = 3


# gint CG50 palette, R5G6B5 -> RGB888
def rgb(c):
    return (((c >> 11) & 31) * 255 // 31,
            ((c >> 5) & 63) * 255 // 63,
            (c & 31) * 255 // 31)


# class -> colour, matching syn_color() / the C_BLUE bar in main.c
NORM, KW, STR, COM, NUM, PRE = range(6)
COLOR = {
    NORM: rgb(0x0000),   # black
    KW:   rgb(0x001f),   # C_BLUE
    STR:  rgb(0x0600),   # dark green
    COM:  rgb(0x528a),   # C_DARK
    NUM:  rgb(0xA014),   # violet
    PRE:  rgb(0xFC00),   # orange
}
BLUE = rgb(0x001f)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def read_kw_lists():
    """Read the keyword tables straight out of src/main.c so this preview can
    never drift from the shipped tokeniser."""
    src = open(os.path.join("src", "main.c"), encoding="ascii").read()

    def grab(macro):
        m = re.search(r"static const char %s\[\] =\s*((?:\s*\"[^\"]*\")+);" % macro, src)
        return set("".join(re.findall(r'"([^"]*)"', m.group(1))).split())

    return grab("SYN_KW_CPP"), grab("SYN_KW_JAVA"), grab("SYN_KW_PY")


CPP_KW, JAVA_KW, PY_KW = read_kw_lists()


def isword(c):
    return c.isalnum() or c == "_"


def scan(s, lang):
    """Mirror of syn_scan(): one class per column, line-local and stateless."""
    n = len(s)
    cls = [NORM] * n
    py = (lang == "py")
    kw = PY_KW if py else (JAVA_KW if lang == "java" else CPP_KW)
    i = 0
    while i < n:
        c = s[i]
        if c == "#":
            if py or s[:i].strip() == "":
                cls[i:] = [(COM if py else PRE)] * (n - i)
                return cls
        if not py and c == "/" and i + 1 < n and s[i + 1] == "/":
            cls[i:] = [COM] * (n - i)
            return cls
        if not py and c == "/" and i + 1 < n and s[i + 1] == "*":
            j = i + 2
            while j + 1 < n and not (s[j] == "*" and s[j + 1] == "/"):
                j += 1
            end = j + 2 if j + 1 < n else n
            cls[i:end] = [COM] * (end - i)
            i = end
            continue
        if c in "\"'":
            if py and i + 2 < n and s[i + 1] == c and s[i + 2] == c:
                j = i + 3
                while j + 2 < n and not (s[j] == c and s[j + 1] == c and s[j + 2] == c):
                    j += 1
                end = j + 3 if j + 2 < n else n
                cls[i:end] = [STR] * (end - i)
                i = end
                continue
            j = i + 1
            while j < n and s[j] != c:
                if s[j] == "\\" and j + 1 < n:
                    j += 1
                j += 1
            end = j + 1 if j < n else n
            cls[i:end] = [STR] * (end - i)
            i = end
            continue
        if c.isdigit():
            j = i
            while j < n and (isword(s[j]) or s[j] == "."):
                j += 1
            cls[i:j] = [NUM] * (j - i)
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and isword(s[j]):
                j += 1
            if s[i:j] in kw:
                cls[i:j] = [KW] * (j - i)
            i = j
            continue
        i += 1
    return cls


def bar(px, glyph, line, c0, n, start, cols, w, h, y, bg, fg):
    """Filled block over columns [c0, c0+n) clipped to this row's slice."""
    a = max(c0, start)
    b = min(c0 + n, start + cols)
    if b <= a:
        return
    x1 = 2 + (a - start) * w
    x2 = 2 + (b - start) * w
    for yy in range(y, min(y + h, DHEIGHT)):
        for xx in range(x1, x2):
            px[xx, yy] = bg
    for c in range(a, b):
        g = glyph(ord(line[c]))
        if not g:
            continue
        x0 = 2 + (c - start) * w
        for ry, row in enumerate(g):
            for rx, bit in enumerate(row):
                if bit == "1" and y + ry < DHEIGHT:
                    px[x0 + rx, y + ry] = fg


def panel(w, h, glyph, lang, lines, wrap=False, eol=False, gap=0,
          find=None, caret=None):
    """One mock editor screen. find=(line, col, len) -> blue match bar;
    caret=(line, col) -> black cursor block; eol=True -> a pilcrow at every
    real line end (the "Show line breaks" option); gap = "Character spacing"
    in px (negative overlaps glyphs, mirroring draw_disp on the device)."""
    img = Image.new("RGB", (DWIDTH, DHEIGHT), WHITE)
    px = img.load()
    for y in list(range(BAR)) + list(range(DHEIGHT - BAR, DHEIGHT)):
        for x in range(DWIDTH):
            px[x, y] = BLACK
    rpitch = h + TEXT_GAP
    pitch = w + gap           # column pitch, mirrors g_contentW
    if pitch < 1:
        pitch = 1
    cols = max(1, (DWIDTH - 4) // pitch)
    r = 0
    for li, line in enumerate(lines):
        cls = scan(line, lang)
        starts = list(range(0, max(len(line), 1), cols)) if wrap else [0]
        for start in starts:
            y = BAR + 2 + r * rpitch
            if y + h > DHEIGHT - BAR:
                return img
            for j, ch in enumerate(line[start:start + cols]):
                g = glyph(ord(ch))
                if not g:
                    continue
                ink = COLOR[cls[start + j]]
                x0 = 2 + j * pitch
                for ry, row in enumerate(g):
                    for rx, bit in enumerate(row):
                        if bit == "1" and 0 <= y + ry < DHEIGHT:
                            px[x0 + rx, y + ry] = ink
            # "Show line breaks": a pilcrow at the true end of the line. A
            # non-final wrap slice ends exactly on the column pitch, so this
            # only fires on the last slice -- same rule as the C code.
            if eol:
                ec = len(line) - start
                if 0 <= ec < cols and 2 + (ec + 1) * pitch <= DWIDTH:
                    mg = glyph(0xB6)
                    if mg:
                        x0 = 2 + ec * pitch
                        for ry, row in enumerate(mg):
                            for rx, bit in enumerate(row):
                                if bit == "1" and 0 <= y + ry < DHEIGHT:
                                    px[x0 + rx, y + ry] = COLOR[COM]
            if find and find[0] == li:
                bar(px, glyph, line, find[1], find[2], start, cols, pitch, h, y, BLUE, WHITE)
            if caret and caret[0] == li:
                bar(px, glyph, line, caret[1], 1, start, cols, pitch, h, y, BLACK, WHITE)
            r += 1
    return img


LONG = ('    printf("%s: %d bytes, %d files\\n", name, (int)total, count);'
        '   /* wrapped by the device */')

SAMPLES = [
    ("Python", "py", {}, [
        "# Fibonacci",
        "def fib(n):",
        '    """Return the n-th."""',
        "    if n < 2:",
        "        return n",
        "    return fib(n-1) + fib(n-2)",
        "print(fib(10))",
    ]),
    ("C++", "cxx", {}, [
        "#include <stdio.h>",
        "// entry point",
        "int main(void) {",
        "    size_t n = strlen(s);",
        "    printf(\"%zu\\n\", n);",
        "    char *p = malloc(n + 1);",
        "    return 0;",
        "}",
    ]),
    ("Java", "java", {}, [
        "public class A {",
        "    static String fmt(int a) {",
        "        return \"x=\" + a;   // sum",
        "    }",
        "    public static void main(String[] a) {",
        "        String s = fmt(42);",
        "        System.out.println(s);",
        "    }",
        "}",
    ]),
    ("Wrap on", "cxx", {"wrap": True}, [
        LONG,
        "int done = 1;",
    ]),
    ("Show line breaks", "cxx", {"eol": True}, [
        "int main(void) {",
        "    return 0;",
        "",
        "}",
    ]),
    ("Char spacing -3", "cxx", {"gap": -3}, [
        "int  main(void) {",
        "    size_t n = strlen(s);",
        "    return n;",
        "}",
    ]),
    ("Find (blue match)", "py", {"find": (0, 3, 3), "caret": (0, 6)}, [
        "def fib(n):",
        "    return n",
    ]),
    ("Legend", "cxx", {}, [
        "int    keyword",
        '"str"  string',
        "//     comment",
        "#line  preprocessor",
        "42     number",
        "match  find bar (blue)",
        "\xB6   line-break mark",
    ]),
]


def put(sheet, spx, text, x, y, glyph, w, ink=BLACK):
    for ch in text:
        g = glyph(ord(ch))
        if g:
            for ry, row in enumerate(g):
                for rx, bit in enumerate(row):
                    if bit == "1":
                        spx[x + rx, y + ry] = ink
        x += w
    return x


def main():
    scale = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    w, h, glyph, _ = load_face("wcfont", "wc", "WC")

    panels = []
    for name, lang, kw, lines in SAMPLES:
        panels.append((name, panel(w, h, glyph, lang, lines, **kw)))

    cols = 2
    rows = (len(panels) + cols - 1) // cols
    head = h + 5
    cw, ch = DWIDTH + 16, head + DHEIGHT + 10
    sheet = Image.new("RGB", (cols * cw + 16, rows * ch + 16), (230, 230, 230))
    spx = sheet.load()
    for i, (name, img) in enumerate(panels):
        cx = 16 + (i % cols) * cw
        cy = 16 + (i // cols) * ch
        put(sheet, spx, name, cx, cy, glyph, w)
        sheet.paste(img, (cx, cy + head))

    out = "syntax-preview.png"
    big = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    big.save(out)
    print("wrote %s (%dx%d, scale %d)" % (out, big.width, big.height, scale))


if __name__ == "__main__":
    main()
