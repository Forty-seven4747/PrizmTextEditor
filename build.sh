#!/bin/sh
export MSYSTEM=MSYS
export PATH="$HOME/.local/bin:$PATH"
SYSROOT="$(fxsdk path sysroot)"
export PATH="$SYSROOT/bin:$HOME/.local/bin:$PATH"
LOG=/e/Desktop/textedit/gint-port/build.log
exec > "$LOG" 2>&1
echo "SYSROOT=$SYSROOT"
echo "gcc=$(which sh-elf-gcc)"
echo "cc1=$(sh-elf-gcc -print-prog-name=cc1)"
cd /e/Desktop/textedit/gint-port || exit 1
fxsdk build-cg
echo "EXIT=$?"
