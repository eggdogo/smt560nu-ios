#!/bin/bash
# Fresh userdata from ipsw/gtelroot.img.zst plus every offline fix we rely on (tablet must be in lk2nd fastboot).
set -e
cd /c/Users/Avett/Documents/Projects/iosont560nu
SP=$LOCALAPPDATA/Temp/claude/890fdba863215d43/87928fd3-9a59-42ff-8aa3-3ccea25000ee/scratchpad
python tools/flash_rootfs.py ipsw/gtelroot.img.zst userdata | tail -2
python "/c/Users/Avett/.gemini/antigravity/brain/930aafe1-be5f-48c3-8932-b0d0a6bd3c94/scratch/fix_emmc_zeros.py" | tail -2
# /etc/fstab: root rw, no disk0s2 line (block 140674)
python - <<PY
open(r'$SP/fo.bin','wb').write(b'/dev/disk0s1 / hfs ro 0 1\n/dev/disk0s2 /private/var hfs rw,nosuid,nodev 0 2\n')
open(r'$SP/fn.bin','wb').write(b'/dev/disk0s1 / hfs rw 0 1\n#dev/disk0s2 /private/var hfs rw,nosuid,nodev 0 2\n')
PY
python tools/flash_block.py ipsw/gtelroot.img.zst userdata 140674 --expect-file $SP/fo.bin --new-file $SP/fn.bin --at 0 | tail -1
# dyld cache: skip DataMigration perform-migration, BKS client entitlement assert
python tools/dscpatch.py 0x183da20cc ff4301d1f65702a9 e0031faac0035fd6 | tail -1
python tools/dscpatch.py 0x183810bf4 40010036 1f2003d5 | tail -1
# MCProfile.migrator calls profiled from inside the migration that profiled waits for: break the plugin (principal class name)
python - <<PY
open(r'$SP/mo.bin','wb').write(b'MCProfileMigrator'); open(r'$SP/mn.bin','wb').write(b'MCProfileMigratox')
PY
python tools/flash_block.py ipsw/gtelroot.img.zst userdata 480215 --expect-file $SP/mo.bin --new-file $SP/mn.bin --at 624 | tail -1
python tools/dscpatch.py 0x183d2c47c ff4302d1f65706a9 000080d2c0035fd6 | tail -1   # ACAccountStore accounts -> nil (breaks lsd/profiled/accountsd cycle)
python tools/dscpatch.py 0x183e02a70 f657bda9f44f01a9 c0035fd61f2003d5 | tail -1   # MCProfileConnection checkIn -> ret
echo "reset done (bootcycle.sh flips the HFS dirty bit before each boot)"
