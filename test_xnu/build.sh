#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
CC="${CROSS_COMPILE}gcc"
OBJCOPY="${CROSS_COMPILE}objcopy"

CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"

mkdir -p out
$CC $CFLAGS -c start.S -o out/start.o
$CC $CFLAGS -c main.c -o out/main.o

$CC $CFLAGS -static -T xnu.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments \
	out/start.o out/main.o -o out/test_kernel.elf

$OBJCOPY -O binary out/test_kernel.elf out/test_kernel.bin

# Wrap into Mach-O 64-bit binary
python3 ../tools/mkmacho.py out/test_kernel.bin out/test_kernel.macho 0x86004000

# Generate finalized Apple Device Tree
python3 ../tools/mkadt.py out/gtel.adt --target=ipad

# Package into GTELXNU payload
python3 ../tools/mkpayload.py out/test_kernel.macho out/gtel.adt out/payload.bin \
	--cmdline "debug=0x14e serial=0x3 cpus=1 gtel_fbcon=1 keepsyms=1"

# Rebuild shim with this payload embedded as ramdisk in boot.img
cd ../shim
bash build.sh ../test_xnu/out/payload.bin
echo "Successfully created out/shim-boot.img with GTELXNU Mach-O payload!"
