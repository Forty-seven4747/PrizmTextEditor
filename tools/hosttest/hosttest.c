/* ==========================================================================
 * hosttest.c -- PC-side test harness for TextEdit's document model.
 *
 * The add-in targets the fx-CG50, where every candidate build has to be
 * carried to the calculator by hand. That makes the *logic* worth testing off
 * target: this file includes src/main.c directly (so the static functions are
 * reachable), stubs the gint API under stubs/, and drives the line model,
 * the range operations (copy / delete / paste), the undo stack and
 * find/replace from a normal command line.
 *
 * Build and run:
 *     cd tools/hosttest && ./run.sh
 *
 * What it covers:
 *   - load / save round trip, including the trailing-newline rule
 *   - range deletion on one line and across lines
 *   - CLIP + DEL of a range, and its undo
 *   - PASTE and its undo (a single recorded range)
 *   - undo history is dropped when another document is loaded
 *   - single replace and replace-all, with undo where it is offered
 *   - the caret lands on the join seam after a backspace-join
 *   - no two document lines ever share a buffer (the shift-down aliasing trap)
 *   - the SHIFT+AC/ON poweroff shortcut (and that AC/ON alone is ignored)
 *   - a randomised soak run that re-checks all of the above invariants
 *
 * It is a development tool: nothing here is linked into textedit.g3a.
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* main.c's own main() must not collide with the test's. */
#define main textedit_main
#include "../../src/main.c"
#undef main

/* ------------------------------ test scaffolding ------------------------- */
static int g_fail = 0;
static long g_checks = 0;

#define CHECK(cond, ...) do {                                            \
        g_checks++;                                                      \
        if(!(cond)) {                                                    \
            g_fail++;                                                    \
            fprintf(stderr, "FAIL %s:%d  ", __FILE__, __LINE__);         \
            fprintf(stderr, __VA_ARGS__);                                \
            fprintf(stderr, "\n");                                       \
        }                                                                \
    } while(0)

#define TEST(name) fprintf(stderr, "  - %s\n", name)

/* ------------------------------- gint stubs ------------------------------ */
uint16_t *gint_vram = NULL;

void dclear(int c) { (void)c; }
void drect(int a, int b, int c, int d, int e) { (void)a;(void)b;(void)c;(void)d;(void)e; }
void drect_border(int a, int b, int c, int d, int e, int f, int g)
{ (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g; }
font_t const *dfont(font_t const *f) { return f; }
void dtext(int x, int y, int fg, char const *s) { (void)x;(void)y;(void)fg;(void)s; }
void dtext_opt(int x, int y, int fg, int bg, dtext_align_t ha,
               dtext_valign_t va, char const *s, int n)
{ (void)x;(void)y;(void)fg;(void)bg;(void)ha;(void)va;(void)s;(void)n; }
void dprint(int x, int y, int fg, char const *fmt, ...) { (void)x;(void)y;(void)fg;(void)fmt; }
void dupdate(void) {}

/* Text metrics: a fixed 8x9 cell is enough for the layout arithmetic. */
int dsize(char const *s, font_t const *f, int *w, int *h)
{ (void)f; if(w) *w = s ? (int)strlen(s) * 8 : 0; if(h) *h = 9; return 0; }
int dnsize(char const *s, int n, font_t const *f, int *w, int *h)
{ (void)f; if(w) *w = n * 8; if(h) *h = 9; return 0; }
char const *drsize(char const *s, font_t const *f, int maxw, int *w)
{
    (void)f;
    int n = (maxw > 0) ? maxw / 8 : 0;
    int l = (int)strlen(s);
    if(l > n) l = n;
    if(w) *w = l * 8;
    return s + l;
}

/* A tiny injectable event queue for the key-driven tests. When it is empty,
 * pollevent() falls back to alternating "nothing" and "EXE pressed", so the
 * modal helpers (notice(), ask_confirm()) always come straight back instead of
 * hanging. */
static key_event_t g_feed[16];
static int g_feedN = 0, g_feedI = 0;
static void feed(uint8_t type, uint8_t key) {
    if(g_feedN < (int)(sizeof g_feed / sizeof g_feed[0])) {
        memset(&g_feed[g_feedN], 0, sizeof g_feed[0]);
        g_feed[g_feedN].type = type;
        g_feed[g_feedN].key = key;
        g_feedN++;
    }
}

key_event_t pollevent(void) {
    static int tick = 0;
    key_event_t e;
    memset(&e, 0, sizeof e);
    if(g_feedI < g_feedN) return g_feed[g_feedI++];
    if((tick++ & 1) == 0) { e.type = KEYEV_NONE; return e; }
    e.type = KEYEV_DOWN; e.key = KEY_EXE; e.mod = 1;
    return e;
}
key_event_t getkey(void) { return pollevent(); }
void sleep_us(int us) { (void)us; }

int gint_world_switch(int rc) { return rc; }   /* GINT_CALL already called it */
void gint_osmenu(void) {}
/* gint_poweroff() would world-switch and show the CASIO logo screen; off target
 * it just records that it was reached, so the SHIFT+AC/ON test can assert it. */
int hosttest_poweroff_calls = 0;
void gint_poweroff(bool show_logo) { (void)show_logo; hosttest_poweroff_calls++; }
void gint_exc_catch(gint_exc_catcher_t c) { (void)c; }
void gint_panic_set(void (*h)(uint32_t)) { (void)h; }

/* The bundled faces are not compiled here; the code only needs them to exist. */
static font_t g_stub_face = { NULL, 0 };
font_t const *wc_font_get(void)  { return &g_stub_face; }
font_t const *luc_font_get(void) { return &g_stub_face; }
font_t const *con_font_get(void) { return &g_stub_face; }
font_t const *not_font_get(void) { return &g_stub_face; }
font_t const *ss3_font_get(void) { return &g_stub_face; }
font_t const *cms_font_get(void) { return &g_stub_face; }
font_t const *rob_font_get(void) { return &g_stub_face; }

uint16_t const wc_cp437[128]  = { 0 };
uint16_t const wc_cp1252[128] = { 0 };
uint16_t const wc_cp437_lo[32] = { 0 };

/* ---------------------------- document helpers --------------------------- */
#define SCRATCH "hst_doc.tmp"

/* Put [text] in the model, exactly as opening a file would. */
static void set_doc(const char *text) {
    FILE *f = fopen(SCRATCH, "wb");
    if(!f) { fprintf(stderr, "cannot write %s\n", SCRATCH); exit(2); }
    size_t n = strlen(text);
    fwrite(text, 1, n, f);
    fclose(f);
    int rc = doc_load(SCRATCH);
    CHECK(doc_loaded(rc), "doc_load(%s) rc=%d", SCRATCH, rc);
}

/* The whole document as one string, lines joined with '\n'. */
static char *dump_doc(void) {
    int total = 1;
    for(int i = 0; i < g_nLines; i++) total += g_lines[i].len + 1;
    char *out = malloc((size_t)total);
    int p = 0;
    for(int i = 0; i < g_nLines; i++) {
        memcpy(out + p, g_lines[i].d, (size_t)g_lines[i].len);
        p += g_lines[i].len;
        if(i < g_nLines - 1) out[p++] = '\n';
    }
    out[p] = 0;
    return out;
}

static void expect_doc(const char *want, const char *what) {
    char *got = dump_doc();
    CHECK(strcmp(got, want) == 0, "%s: got \"%s\" want \"%s\"", what, got, want);
    free(got);
}

/* Every line must be well formed, and no two lines may share a buffer -- the
 * latter is what catches a shift-down leaving a duplicate pointer behind. */
static void check_invariants(const char *what) {
    CHECK(g_nLines >= 1, "%s: g_nLines=%d", what, g_nLines);
    CHECK(g_nLines <= MAX_LINES, "%s: g_nLines=%d > MAX", what, g_nLines);
    CHECK(g_curLine >= 0 && g_curLine < g_nLines, "%s: curLine=%d", what, g_curLine);
    for(int i = 0; i < g_nLines; i++) {
        TedLine *L = &g_lines[i];
        CHECK(L->d != NULL, "%s: line %d has no buffer", what, i);
        if(!L->d) continue;
        CHECK(L->len >= 0, "%s: line %d len=%d", what, i, L->len);
        CHECK(L->len < L->cap, "%s: line %d len=%d cap=%d", what, i, L->len, L->cap);
        CHECK(L->d[L->len] == 0, "%s: line %d not terminated", what, i);
        for(int j = 0; j < i; j++)
            CHECK(L->d != g_lines[j].d, "%s: lines %d and %d share a buffer", what, i, j);
    }
    if(g_curLine < g_nLines)
        CHECK(g_curCol >= 0 && g_curCol <= g_lines[g_curLine].len,
              "%s: curCol=%d on line of len %d", what, g_curCol, g_lines[g_curLine].len);
}

static void goto_rc(int line, int col) { g_curLine = line; g_curCol = col; }

/* -------------------------------- the tests ----------------------------- */
static void t_load_roundtrip(void) {
    TEST("load: line splitting and the trailing-newline rule");
    set_doc("one\ntwo\nthree");
    CHECK(g_nLines == 3, "nLines=%d", g_nLines);
    expect_doc("one\ntwo\nthree", "no trailing newline");
    CHECK(g_modified == 0, "a fresh load is not dirty");

    /* A trailing newline is a real (empty) final line, and saving puts the
     * file back byte for byte -- that round trip is what the loader and
     * writer were written around. */
    set_doc("one\ntwo\n");
    CHECK(g_nLines == 3, "trailing newline -> nLines=%d", g_nLines);
    CHECK(g_lines[2].len == 0, "last line should be empty");
    expect_doc("one\ntwo\n", "trailing newline preserved");
    check_invariants("load");
}

static void t_load_clears_undo(void) {
    TEST("load: undo history does not survive into another document");
    set_doc("aaa\nbbb");
    goto_rc(0, 3);
    doc_insert_char('!');
    CHECK(g_undoTop > 0, "an edit should record undo");
    set_doc("short");
    CHECK(g_undoTop == 0, "history must be empty after a load, got %d", g_undoTop);
}

static void t_range_delete_same_line(void) {
    TEST("range delete: inside one line");
    set_doc("hello world!");
    int rc = range_delete_raw(0, 5, 0, 11);          /* remove " world" */
    CHECK(rc == 0, "rc=%d", rc);
    expect_doc("hello!", "delete inside a line");
    check_invariants("range same line");
}

static void t_range_delete_across_lines(void) {
    TEST("range delete: across lines joins the survivors");
    set_doc("aaa\nbbb\nccc");
    int rc = range_delete_raw(0, 1, 2, 2);           /* keep "a", drop "bbb", keep "c" */
    CHECK(rc == 0, "rc=%d", rc);
    CHECK(g_nLines == 1, "nLines=%d", g_nLines);
    expect_doc("ac", "cross-line delete");
    check_invariants("range cross line");
}

static void t_sel_del_and_undo(void) {
    TEST("DEL on a CLIP range: deletes, and UNDO puts it back");
    set_doc("0123456789");
    g_selMode = 1; g_selAnchorLine = 0; g_selAnchorCol = 2;
    goto_rc(0, 6);                                   /* range = "2345" */
    CHECK(!sel_range_empty(), "range should not be empty");
    editor_delete_range();
    expect_doc("016789", "range deleted");
    CHECK(g_selMode == 0, "selection mode must end after the cut");

    editor_undo();
    expect_doc("0123456789", "range restored by undo");
    check_invariants("sel del undo");
}

static void t_sel_del_multiline_undo(void) {
    TEST("DEL on a multi-line range: undo restores every line");
    set_doc("alpha\nbravo\ncharlie");
    g_selMode = 1; g_selAnchorLine = 0; g_selAnchorCol = 3;
    goto_rc(2, 4);                                   /* "ha" + bravo + "char" */
    editor_delete_range();
    expect_doc("alplie", "cross-line cut");
    check_invariants("multiline cut");

    editor_undo();
    expect_doc("alpha\nbravo\ncharlie", "cross-line cut undone");
    check_invariants("multiline cut undo");
}

static void t_paste_and_undo(void) {
    TEST("PASTE: multi-line insert, and its single-step undo");
    set_doc("start\nend");
    free(g_clip);
    g_clip = malloc(16);
    memcpy(g_clip, "A\nBB\nCCC", 8);
    g_clipLen = 8;
    goto_rc(0, 5);                                   /* after "start" */
    editor_paste();
    expect_doc("startA\nBB\nCCC\nend", "paste result");

    editor_undo();
    expect_doc("start\nend", "paste undone");
    CHECK(g_curLine == 0 && g_curCol == 5, "caret back at %d:%d", g_curLine, g_curCol);
    check_invariants("paste undo");
}

static void t_slot_hygiene_after_shrink(void) {
    TEST("slots: appending lines after a shrink cannot alias a live buffer");
    set_doc("l0\nl1\nl2\nl3\nl4\nl5");
    /* Shrink with a cross-line range delete, then rebuild the document to the
     * same size -- the old code left duplicate pointers above g_nLines and the
     * next append wrote straight into a live line's buffer. */
    int rc = range_delete_raw(0, 0, 4, 0);
    CHECK(rc == 0, "rc=%d", rc);
    check_invariants("after shrink");

    set_doc("x");
    for(int i = 0; i < 40; i++) {
        goto_rc(g_nLines - 1, g_lines[g_nLines - 1].len);
        doc_newline();
        doc_insert_char((char)('a' + (i % 26)));
    }
    check_invariants("after regrow");
    CHECK(g_lines[0].len == 1 && g_lines[0].d[0] == 'x', "first line corrupted");
}

static void t_join_caret_at_seam(void) {
    TEST("backspace-join: caret lands on the seam, not past it");
    set_doc("abcd\nefgh");
    goto_rc(1, 0);
    doc_backspace();
    CHECK(g_nLines == 1, "nLines=%d", g_nLines);
    expect_doc("abcdefgh", "join");
    CHECK(g_curLine == 0 && g_curCol == 4, "caret at %d:%d, want 0:4", g_curLine, g_curCol);
    check_invariants("join");

    editor_undo();
    expect_doc("abcd\nefgh", "join undone");
    check_invariants("join undo");
}

static void t_replace_one(void) {
    TEST("replace: one match at a time, one undo per replace");
    set_doc("cat dog cat");
    strcpy(g_findStr, "cat"); g_findLen = 3; g_findOn = 1;
    strcpy(g_replStr, "COW"); g_replLen = 3; g_replMode = 1;

    CHECK(find_from(0, 0), "first match");
    CHECK(g_findLine == 0 && g_findCol == 0, "at %d:%d", g_findLine, g_findCol);
    doc_replace_at(g_findLine, g_findCol, g_replStr, g_replLen, 1);
    expect_doc("COW dog cat", "first replaced");

    CHECK(find_from(0, 3), "second match");
    CHECK(g_findCol == 8, "second at col %d", g_findCol);
    doc_replace_at(g_findLine, g_findCol, g_replStr, g_replLen, 1);
    expect_doc("COW dog COW", "second replaced");

    /* A replace is ONE undo step, whichever way the lengths differ. */
    editor_undo();
    expect_doc("COW dog cat", "undo one replace");
    editor_undo();
    expect_doc("cat dog cat", "undo the other replace");
    check_invariants("replace undo");

    /* Growing and shrinking replacements also reverse in one step. */
    set_doc("x AB x");
    strcpy(g_findStr, "AB"); g_findLen = 2;
    strcpy(g_replStr, "WXYZ"); g_replLen = 4;
    doc_replace_at(0, 2, g_replStr, g_replLen, 1);
    expect_doc("x WXYZ x", "grow");
    editor_undo();
    expect_doc("x AB x", "grow undone");

    strcpy(g_replStr, ""); g_replLen = 0;
    doc_replace_at(0, 2, g_replStr, g_replLen, 1);
    expect_doc("x  x", "shrink to nothing");
    editor_undo();
    expect_doc("x AB x", "shrink undone");
    check_invariants("replace sizes");
}

static void t_replace_all(void) {
    TEST("replace all: counts matches and rewrites the whole file");
    set_doc("aXbXc\nXX\nplain");
    strcpy(g_findStr, "X"); g_findLen = 1;
    strcpy(g_replStr, "yy"); g_replLen = 2;
    int n = doc_replace_all();
    CHECK(n == 4, "replaced %d, want 4", n);
    expect_doc("ayybyyc\nyyyy\nplain", "replace all");

    /* An empty replacement deletes the matches, and must still terminate. */
    set_doc("aaaa");
    strcpy(g_findStr, "aa"); g_findLen = 2;
    g_replStr[0] = 0; g_replLen = 0;
    n = doc_replace_all();
    CHECK(n == 2, "delete-all replaced %d, want 2", n);
    expect_doc("", "delete all matches");
    check_invariants("replace all");
}

static void t_line_full_refuses(void) {
    TEST("line limit: typing past LINE_MAXLEN is refused, not silently lost");
    set_doc("tiny");
    /* Fill the line to the brim, then make sure one more char is rejected. */
    goto_rc(0, g_lines[0].len);
    while(g_lines[0].len < LINE_MAXLEN) doc_insert_char('z');
    CHECK(g_lines[0].len == LINE_MAXLEN, "len=%d", g_lines[0].len);
    doc_insert_char('!');
    CHECK(g_lines[0].len == LINE_MAXLEN, "overflow was not refused");
    check_invariants("line full");
}

/* Deterministic soak: random edits, with the invariants re-checked each step.
 * This is the part that would have caught the aliasing regression. */
static void t_soak(void) {
    TEST("soak: 4000 random edits keep every invariant");
    set_doc("seed");
    uint32_t rng = 12345;
    for(int step = 0; step < 4000; step++) {
        rng = rng * 1103515245u + 12345u;
        int op = (int)((rng >> 16) % 9);
        switch(op) {
        case 0: doc_insert_char((char)('a' + (rng % 26))); break;
        case 1: doc_backspace(); break;
        case 2: doc_newline(); break;
        case 3: doc_move_left(); break;
        case 4: doc_move_right(); break;
        case 5: doc_move_up(); break;
        case 6: doc_move_down(); break;
        case 7: {
            int l2 = (int)((rng >> 8) % g_nLines);
            int c2 = (int)((rng >> 4) % (g_lines[l2].len + 1));
            range_delete_raw(g_curLine, g_curCol, l2, c2);
            break;
        }
        case 8: {
            goto_rc(0, 0);
            int l2 = (int)((rng >> 8) % g_nLines);
            int c2 = (int)((rng >> 4) % (g_lines[l2].len + 1));
            char *buf = range_extract(g_curLine, g_curCol, l2, c2, &g_clipLen);
            if(buf) { free(g_clip); g_clip = buf; goto_rc(l2, c2); editor_paste(); }
            break;
        }
        }
        if(g_curLine < 0) g_curLine = 0;
        if(g_curLine >= g_nLines) g_curLine = g_nLines - 1;
        if(g_curCol < 0) g_curCol = 0;
        if(g_curCol > g_lines[g_curLine].len) g_curCol = g_lines[g_curLine].len;
        check_invariants("soak");
        if(g_fail > 20) { fprintf(stderr, "  (stopping: too many failures)\n"); return; }
    }
    /* Unwind whatever the soak left behind and make sure UNDO stays sane. */
    int guard = 0;
    while(g_undoTop > 0 && guard++ < 5000) editor_undo();
    check_invariants("soak unwind");
}

static void t_save_roundtrip(void) {
    TEST("save: writes the document back byte for byte");
    set_doc("alpha\nbeta");
    g_saveCrlf = 0; g_finalNewline = 0;
    int rc = doc_save(SCRATCH);
    CHECK(rc == 0, "doc_save rc=%d", rc);
    CHECK(!g_modified, "saving clears the dirty flag");
    FILE *f = fopen(SCRATCH, "rb");
    CHECK(f != NULL, "cannot reopen the saved file");
    if(f) {
        char buf[64];
        size_t n = fread(buf, 1, sizeof(buf) - 1, f);
        fclose(f);
        buf[n] = 0;
        CHECK(strcmp(buf, "alpha\nbeta") == 0, "saved \"%s\"", buf);
    }
    /* The temp file must not be left lying around after a good save. */
    f = fopen(SCRATCH ".tmp", "rb");
    CHECK(f == NULL, "a stale .tmp file was left behind");
    if(f) fclose(f);

    /* CRLF and the final newline are still honoured. */
    g_saveCrlf = 1; g_finalNewline = 1;
    set_doc("a\nb");
    CHECK(doc_save(SCRATCH) == 0, "crlf save failed");
    f = fopen(SCRATCH, "rb");
    if(f) {
        char buf[64];
        size_t n = fread(buf, 1, sizeof(buf) - 1, f);
        fclose(f);
        buf[n] = 0;
        CHECK(strcmp(buf, "a\r\nb\r\n") == 0, "crlf+final saved \"%s\"", buf);
    }
    g_saveCrlf = 0; g_finalNewline = 0;
    remove(SCRATCH);
}

/* SHIFT+AC/ON must reach gint_poweroff(). It is the one global shortcut the
 * custom reader still owes getkey() (its GETKEY_POWEROFF bit), and the easiest
 * to lose because AC/ON (0x07) is not an ordinary matrix key. AC/ON alone must
 * do nothing -- that key also powers the calculator back on. */
static void t_poweroff_combo(void) {
    TEST("SHIFT+AC/ON powers off; AC/ON alone does nothing");

    /* AC/ON with no SHIFT latched: must be ignored. */
    g_shiftOn = 0; g_alphaMode = 0;
    hosttest_poweroff_calls = 0;
    g_feedI = g_feedN = 0;
    feed(KEYEV_DOWN, KEY_ACON);
    feed(KEYEV_NONE, 0);
    getkey_poll();
    CHECK(hosttest_poweroff_calls == 0, "AC/ON alone powered off (%d calls)",
          hosttest_poweroff_calls);

    /* SHIFT latches on its press, then AC/ON powers the calculator off. */
    g_shiftOn = 0; g_alphaMode = 0;
    hosttest_poweroff_calls = 0;
    g_feedI = g_feedN = 0;
    feed(KEYEV_DOWN, KEY_SHIFT);
    feed(KEYEV_DOWN, KEY_ACON);
    feed(KEYEV_NONE, 0);
    getkey_poll();
    CHECK(hosttest_poweroff_calls == 1,
          "SHIFT+AC/ON did not power off (%d calls)", hosttest_poweroff_calls);

    g_shiftOn = 0; g_alphaMode = 0;
    g_feedI = g_feedN = 0;
}

int main(void) {
    /* Pin the metrics the drawing helpers would otherwise measure. */
    g_FH = 9; g_FW = 8; g_LH = 12; g_lineGap = 3;
    g_contentW = WC_W; g_glyphStep = 0; g_contentFace = g_stub_face;

    fprintf(stderr, "TextEdit document-model tests\n");
    t_load_roundtrip();
    t_load_clears_undo();
    t_range_delete_same_line();
    t_range_delete_across_lines();
    t_sel_del_and_undo();
    t_sel_del_multiline_undo();
    t_paste_and_undo();
    t_slot_hygiene_after_shrink();
    t_join_caret_at_seam();
    t_replace_one();
    t_replace_all();
    t_line_full_refuses();
    t_save_roundtrip();
    t_poweroff_combo();
    t_soak();

    remove(SCRATCH);
    fprintf(stderr, "\n%ld checks, %d failure(s)\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
