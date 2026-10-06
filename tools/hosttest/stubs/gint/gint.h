/* Host-test stub for <gint/gint.h>.
 *
 * gint_world_switch() is the flash-write trampoline: on the calculator it
 * enters the OS world first. On the host the filesystem calls are plain POSIX,
 * so the stub just makes the call. GINT_CALL therefore collapses to a normal
 * invocation -- and, importantly, still evaluates its arguments once. */
#ifndef HOSTTEST_GINT_GINT_H
#define HOSTTEST_GINT_GINT_H

#include <stdbool.h>

#define GNORETURN

#define GINT_CALL(f, ...) (f)(__VA_ARGS__)

int gint_world_switch(int rc);
void gint_osmenu(void);

/* On the calculator this world-switches and shows the CASIO logo/poweroff
 * screen. The host stub only records the call (see hosttest.c) so the
 * SHIFT+AC/ON test can assert that the shortcut was actually reached. */
void gint_poweroff(bool show_logo);

#endif
