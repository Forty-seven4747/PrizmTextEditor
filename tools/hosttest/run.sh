#!/bin/sh
# Build and run the PC-side document-model tests (see hosttest.c).
# Uses the MSYS2 host gcc; nothing here is part of the calculator build.
#
# src/keymap.c is compiled in for real (it is pure table lookup) so the typed
# character path is exercised by the same code the add-in uses.
set -e
cd "$(dirname "$0")"
gcc -std=gnu99 -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers \
    -g -O1 -I stubs -I ../../src \
    -o hosttest.exe hosttest.c ../../src/keymap.c
./hosttest.exe
