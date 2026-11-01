#!/bin/bash
# Build the SM-T560NU boot shim and pack into boot.img format
set -euo pipefail
cd "$(dirname "$0")"

CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
CC="${CROSS_COMPILE}gcc"
OBJCOPY="${CROSS_COMPILE}objcopy"
NM="${CROSS_COMPILE}nm"

CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"

mkdir -p out
for f in start.S shim.c console.c fdt.c loader.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done

# Compile Device Tree (DTB) for SM-T560NU (APQ8016 / MSM8916)
dtc -I dts -O dtb -o out/gtel.dtb gtel.dts
$OBJCOPY -I binary -O elf64-littleaarch64 -B aarch64 --rename-section .data=.dtb out/gtel.dtb out/dtb.o

$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out/start.o out/shim.o out/console.o out/fdt.o out/loader.o out/dtb.o -o out/shim.elf

$OBJCOPY -O binary out/shim.elf out/Image

# Pad Image to _end so bss, stacks, and dtb exist
size=$($NM out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image

dtb_off=$($NM out/shim.elf | awk '$3=="_dtb_start"{print strtonum("0x"$1)}')
echo "Compiled shim binary: out/Image ($size bytes, DTB at offset $dtb_off)"

# Pack boot.img
CMDLINE="console=null"

if [ -n "${1:-}" ]; then
	python3 ../tools/pack_bootimg.py --kernel out/Image --ramdisk "$1" --cmdline "$CMDLINE" --out out/shim-boot.img
else
	python3 ../tools/pack_bootimg.py --kernel out/Image --cmdline "$CMDLINE" --out out/shim-boot.img
fi
echo "Done. Test with: fastboot boot out/shim-boot.img"
