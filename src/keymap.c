/* keymap.c -- Casio fx-CG key matrix -> character translation.
 * Adapted from PythonExtra (TheRainbowPhoenix), MIT licensed.
 * Maps the raw gint keycode (Casio key-matrix position) plus the
 * shift/alpha modifier state to an ASCII character for text input. */
#include "keymap.h"
#include <gint/keyboard.h>

/* Decode a Casio key-matrix code into a linear 0..47 index.
 * keycode layout: high nibble = row (1..9), low nibble = col (1..6). */
	static int key_id(int keycode)
{
	unsigned int col = (keycode & 0x0f) - 1;
	unsigned int row = 9 - ((keycode & 0xf0) >> 4);

	if(col > 5 || row > 8) return -1;
	return 6 * row + col;
}

/* Unmodified / shifted number-and-symbol layer (bottom 2 rows of the pad). */
static uint8_t map_flat[30] = {
	 0,    0,   '(',  ')',  ',',  '=',
	'7',  '8',  '9',   0,    0,    0,
	'4',  '5',  '6',  '*',  '/',   0,
	'1',  '2',  '3',  '+',  '-',   0,
	'0',  '.',  'e',  '_',   0,    0,
};
/* Alpha layer (letters + a few punctuation). */
static uint8_t map_alpha[36] = {
	'a',  'b',  'c',  'd',  'e',  'f',
	'g',  'h',  'i',  'j',  'k',  'l',
	'm',  'n',  'o',   0,    0,    0,
	'p',  'q',  'r',  's',  't',   0,
	'u',  'v',  'w',  'x',  'y',   0,
	'z',  ' ',  '"',  ':',   0,    0,
};

uint32_t keymap_translate(int key, bool shift, bool alpha)
{
	int id = key_id(key);
	if(id < 0) return 0;

	if(!shift && !alpha) {
		/* The first 4 rows have no useful characters */
		return (id < 24) ? 0 : map_flat[id - 24];
	}
	if(shift && !alpha) {
		/* SHIFT layer = the legends printed in YELLOW on the fx-CG50 case.
		 * The six symbols the case actually prints sit on exactly their
		 * physical keys:
		 *   x        -> {          /        -> }
		 *   +        -> [          -        -> ]
		 *   . (dot)  -> =          x10^x    -> SPACE
		 * Every other yellow legend on the number/operator block is a math
		 * function or a command (CAPTURE, CLIP, PASTE, INS/UNDO, CATALOG,
		 * FORMAT, List, Mat, Ans, ...) which a plain-text editor cannot use,
		 * so those keys carry the remaining ASCII punctuation instead.
		 * (The yellow commands themselves are handled in main.c: the editor
		 * maps SHIFT+7/8/9/DEL to CAPTURE/CLIP/PASTE/UNDO.) */
		switch(key) {
		/* symbols exactly as printed in yellow on the case */
		case KEY_MUL:    return '{';
		case KEY_DIV:    return '}';
		case KEY_ADD:    return '[';
		case KEY_SUB:    return ']';
		case KEY_DOT:    return '=';
		case KEY_EXP:    return ' ';   /* the case prints SPACE here */
		/* remaining ASCII punctuation on the other keys */
		case KEY_0:      return ':';
		case KEY_1:      return ';';
		case KEY_2:      return '\'';
		case KEY_3:      return '"';
		case KEY_4:      return '!';
		case KEY_5:      return '?';
		case KEY_6:      return '^';
		case KEY_NEG:    return '~';
		case KEY_LEFTP:  return '<';
		case KEY_RIGHTP: return '>';
		case KEY_COMMA:  return '\\';
		case KEY_ARROW:  return '|';
		case KEY_FRAC:   return '%';
		case KEY_FD:     return '&';
		case KEY_OPTN:   return '@';
		case KEY_VARS:   return '#';
		case KEY_POWER:  return '`';
		default:         break;
		}
		return 0;
	}
	if(!shift && alpha) {
		/* The first 3 rows have no useful characters */
		return (id < 18) ? 0 : map_alpha[id - 18];
	}
	if(shift && alpha) {
		int c = keymap_translate(key, false, true);
		return (c >= 'a' && c <= 'z') ? (c & ~0x20) : c;
	}

	return 0;
}
