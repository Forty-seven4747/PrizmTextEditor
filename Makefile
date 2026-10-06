#! /usr/bin/make -f
# =============================================================================
# TEXTEDIT -- fxSDK-style Makefile for a gint add-in (fx-CG 50).
#
# This is the standard fxSDK "Makefile" project layout (see project.cfg).
# Modern gint no longer ships a Makefile.include, so this replaces the old
# `-include $(GINT)/Makefile.include` scheme.
#
#   Build:   fxsdk build-cg        (equivalent to: make all-cg)
#   Clean:   make clean
#
# Requires the sh-elf toolchain + gint installed in the fxSDK sysroot.
# On Windows this is built entirely in MSYS2 -- see BUILD.md.
# =============================================================================

include project.cfg

# Compiler / linker flag sets
CFLAGSFX = $(CFLAGS) $(CFLAGS_FX) $(INCLUDE_FX)
CFLAGSCG = $(CFLAGS) $(CFLAGS_CG) $(INCLUDE_CG)
LDFLAGSFX := $(LDFLAGS) $(LDFLAGS_FX)
LDFLAGSCG := $(LDFLAGS) $(LDFLAGS_CG)

# Dependency generation and ELF->binary flags
depflags = -MMD -MT $@ -MF $(@:.o=.d) -MP
BINFLAGS := -R .bss -R .gint_bss

# fxgxa argument sets (NAME_G3A / INTERNAL / icons come from project.cfg)
NAME_G1A ?= $(NAME)
NAME_G3A ?= $(NAME)
G1AF := -i "$(ICON_FX)" -n "$(NAME_G1A)" --internal="$(INTERNAL)"
G3AF := -n "$(NAME_G3A)" --icon-uns="$(ICON_CG_UNS)" --icon-sel="$(ICON_CG_SEL)"

NULL   :=
TARGET := $(subst $(NULL) $(NULL),-,$(NAME))

ifeq "$(TARGET_FX)" ""
TARGET_FX := $(TARGET).g1a
endif
ifeq "$(TARGET_CG)" ""
TARGET_CG := $(TARGET).g3a
endif

ELF_FX := build-fx/$(shell basename "$(TARGET_FX)" .g1a).elf
BIN_FX := $(ELF_FX:.elf=.bin)
ELF_CG := build-cg/$(shell basename "$(TARGET_CG)" .g3a).elf
BIN_CG := $(ELF_CG:.elf=.bin)

# Sources (everything under src/)
src := $(shell find src/ -name '*.[csS]')
obj-fx := $(src:%=build-fx/%.o)
obj-cg := $(src:%=build-cg/%.o)

# Assets: the menu icon is embedded directly by fxgxa, not by fxconv.
deps-fx := $(ICON_FX)
deps-cg := $(ICON_CG_UNS) $(ICON_CG_SEL)

# --- Targets ----------------------------------------------------------------

all: all-cg

all-fx: $(TARGET_FX)
all-cg: $(TARGET_CG)

$(TARGET_FX): $(obj-fx) $(deps-fx)
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_FX)-gcc -o $(ELF_FX) $(obj-fx) $(CFLAGSFX) $(LDFLAGSFX)
	$(TOOLCHAIN_FX)-objcopy -O binary $(BINFLAGS) $(ELF_FX) $(BIN_FX)
	fxgxa --g1a $(BIN_FX) -o $@ $(G1AF)

$(TARGET_CG): $(obj-cg) $(deps-cg)
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_CG)-gcc -o $(ELF_CG) $(obj-cg) $(CFLAGSCG) $(LDFLAGSCG)
	$(TOOLCHAIN_CG)-objcopy -O binary $(BINFLAGS) $(ELF_CG) $(BIN_CG)
	fxgxa --g3a $(BIN_CG) -o $@ $(G3AF)

# C sources
build-fx/%.c.o: %.c
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_FX)-gcc -c $< -o $@ $(CFLAGSFX) $(depflags)
build-cg/%.c.o: %.c
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_CG)-gcc -c $< -o $@ $(CFLAGSCG) $(depflags)

# Assembler
build-fx/%.s.o: %.s
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_FX)-gcc -c $< -o $@ -Wa,--dsp
build-cg/%.s.o: %.s
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_CG)-gcc -c $< -o $@ -Wa,--dsp

build-fx/%.S.o: %.S
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_FX)-gcc -c $< -o $@ $(INCLUDE_FX) -Wa,--dsp
build-cg/%.S.o: %.S
	@ mkdir -p $(dir $@)
	$(TOOLCHAIN_CG)-gcc -c $< -o $@ $(INCLUDE_CG) -Wa,--dsp

# --- Cleaning ---------------------------------------------------------------

-include $(shell find build-cg -name '*.d' 2> /dev/null)
build-cg/%.d: ;
.PRECIOUS: build-cg build-cg/%.d build-cg/%.o %/

clean:
	@ rm -rf build-cg/ build-fx/

distclean: clean
	@ rm -f $(TARGET_CG) $(TARGET_FX)

.PHONY: all all-fx all-cg clean distclean
