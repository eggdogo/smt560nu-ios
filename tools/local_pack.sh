#!/bin/bash
# Build shim-boot.img locally for a kernel-only change, skipping the pack CI.
# Reuses slim_ramdisk.dmg from the last CI artifact (only macOS can build the
# HFS image) and takes gtel.adt, the shim and the boot-args from the repo, so
# the result matches what pack.yml would produce.
# Usage: [RD=ufsroot0] bash tools/local_pack.sh [kernel] [out.img]
set -e
if [ -d "/mnt/c/Users/Avett/Documents/Projects/iosont560nu" ]; then
  PROJ=/mnt/c/Users/Avett/Documents/Projects/iosont560nu
  REPO_DIR=/mnt/c/Users/Avett/Documents/GitHub/smt560nu-ios
else
  PROJ=/c/Users/Avett/Documents/Projects/iosont560nu
  REPO_DIR=/c/Users/Avett/Documents/GitHub/smt560nu-ios
fi
KERNEL=${1:-$PROJ/kernel.development.sweet}
OUT=${2:-$PROJ/shim-boot.img}
cd "$PROJ"

PYTHON=$(command -v python3 || command -v python)
CMDLINE=$($PYTHON -I -c "
import re,sys
s=open(sys.argv[1]).read()
print(re.search(r'mkpayload\.py.*?--cmdline \"([^\"]*)\"', s, re.S).group(1))" "$REPO_DIR/.github/workflows/pack.yml")
# RD=ufsroot0 boots the root from the eMMC instead of the ramdisk
if [ -n "$CPUS" ]; then CMDLINE=$(echo "$CMDLINE" | sed "s/cpus=[^ ]*/cpus=$CPUS/"); fi
if [ -n "$FBCON" ]; then CMDLINE=$(echo "$CMDLINE" | sed "s/gtel_fbcon=[^ ]*/gtel_fbcon=$FBCON/"); fi
if [ -n "$RD" ]; then CMDLINE=$(echo "$CMDLINE" | sed "s/rd=[^ ]*/rd=$RD/"); fi
# EXTRA="sweetsample=launchd ..." adds boot-args; a sweetsample there replaces the default
if [ -n "$EXTRA" ]; then
  case "$EXTRA" in *sweetsample=*) CMDLINE=$(echo "$CMDLINE" | sed "s/ sweetsample=[^ ]*//");; esac
  CMDLINE="$CMDLINE $EXTRA"
fi
echo "cmdline: $CMDLINE"

$PYTHON tools/mkpayload.py "$KERNEL" "$REPO_DIR/gtel.adt" payload.bin --ramdisk slim_ramdisk.dmg --cmdline "$CMDLINE"
$PYTHON tools/pack_bootimg.py --kernel "$REPO_DIR/shim/out/Image" --ramdisk payload.bin --cmdline "console=null" --out "$OUT"
ls -l "$OUT"
