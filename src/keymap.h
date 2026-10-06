/* keymap.h -- text input mapping for Casio fx-CG (gint key_event_t -> char).
 * Adapted from PythonExtra (TheRainbowPhoenix), MIT licensed. */
#ifndef KEYMAP_H
#define KEYMAP_H

#include <stdbool.h>
#include <stdint.h>

/* Translate a gint key event into a character for text entry.
 * Returns 0 when the key combination has no printable character. */
uint32_t keymap_translate(int key, bool shift, bool alpha);

#endif /* KEYMAP_H */
