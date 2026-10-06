/* Host-test stub for <gint/exc.h>. */
#ifndef HOSTTEST_GINT_EXC_H
#define HOSTTEST_GINT_EXC_H

#include <stdint.h>

typedef int (*gint_exc_catcher_t)(uint32_t code);
void gint_exc_catch(gint_exc_catcher_t catcher);
void gint_panic_set(void (*handler)(uint32_t code));

#endif
