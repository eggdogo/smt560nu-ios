#!/bin/bash
# usage: bootcycle.sh image log seconds  -- clears HFS unmounted bit (kernel rw-root hack needs a "dirty" root), boots, watches
SP=$LOCALAPPDATA/Temp/claude/890fdba863215d43/87928fd3-9a59-42ff-8aa3-3ccea25000ee/scratchpad
cd /c/Users/Avett/Documents/Projects/iosont560nu
python tools/pyfastboot.py reboot-bootloader >/dev/null 2>&1; sleep 6
python tools/flash_block.py ipsw/gtelroot.img.zst userdata 0 --expect-file $SP/old.bin --new-file $SP/new.bin --at 1028 2>&1 | tail -1
python tools/xlog.py run "$1" -o "$2" --seconds "$3" --interval 3 --settle 3 --gone-timeout 90 --finish none 2>&1 | tail -1
