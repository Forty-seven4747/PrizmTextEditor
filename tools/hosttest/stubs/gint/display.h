/* Host-test stub for <gint/display.h>.
 *
 * The PC build exists to exercise the DOCUMENT MODEL (lines, ranges, undo,
 * find/replace), so the drawing calls are no-ops. font_t keeps the shape
 * main.c actually touches -- the char_spacing field it patches into its RAM
 * copy -- and nothing else. */
#ifndef HOSTTEST_GINT_DISPLAY_H
#define HOSTTEST_GINT_DISPLAY_H

#include <stdint.h>

/* ---- font_t (only the fields main.c reads/writes) ---- */
typedef struct {
    void const *data;
    uint8_t char_spacing;
} font_t;

/* ---- colours (R5G6B5, same values the real header uses) ---- */
enum {
    C_NONE  = -1,
    C_BLACK = 0x0000,
    C_WHITE = 0xffff,
    C_RED   = 0xf800,
    C_GREEN = 0x07e0,
    C_BLUE  = 0x001f,
    C_DARK  = 0x528a,
    C_LIGHT = 0xc618,
};

typedef enum {
    DTEXT_LEFT = 0,
    DTEXT_RIGHT,
    DTEXT_CENTER,
} dtext_align_t;

typedef enum {
    DTEXT_TOP = 0,
    DTEXT_MIDDLE,
    DTEXT_BOTTOM,
} dtext_valign_t;

extern uint16_t *gint_vram;

void dclear(int color);
void drect(int x1, int y1, int x2, int y2, int color);
void drect_border(int x1, int y1, int x2, int y2, int fill, int bw, int border);
font_t const *dfont(font_t const *font);
void dtext(int x, int y, int fg, char const *s);
void dtext_opt(int x, int y, int fg, int bg, dtext_align_t halign,
               dtext_valign_t valign, char const *s, int n);
void dprint(int x, int y, int fg, char const *fmt, ...);
void dupdate(void);

int dsize(char const *s, font_t const *font, int *w, int *h);
int dnsize(char const *s, int n, font_t const *font, int *w, int *h);
char const *drsize(char const *s, font_t const *font, int maxw, int *w);

#endif
