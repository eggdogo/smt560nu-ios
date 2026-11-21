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
python tools/dscpatch.py 0x18380987c a83a1ad008b583b9 00008052c0035fd6 | tail -1   # BKSSystemApplication waitForDataMigration -> NO
python tools/dscpatch.py 0x1932f755c eb2bb86de923016d e00302aac0035fd6 | tail -1   # SBFStaticWallpaperView imageByScalingImage -> return input (CFRelease(NULL) crash)
python tools/dscpatch.py 0x186a34910 e923ba6dfa6701a9 000080d2c0035fd6 | tail -1   # +[AVSystemController sharedAVSystemController] -> nil (mediaserverd crash-loops, SpringBoard blocked)
python tools/dscpatch.py 0x18391214c f85fbca9f65701a9 000080d2c0035fd6 | tail -1   # liblockdown send_get_value -> NULL (lockdownd never answers)
python tools/dscpatch.py 0x188e8cc8c ff8302d1fc6f04a9 000080d2c0035fd6 | tail -1   # CoreUI csiCompressImageProviderCopyIOSurface -> NULL (decode into IOSurface faults)
python tools/flash_block.py ipsw/gtelroot.img.zst userdata 612083 --expect-file tools/blockpatches/mediaserverd_orig.plist --new-file tools/blockpatches/mediaserverd_nosvc.plist | tail -1   # mediaserverd crash-loops: hide its mach services so clients fail fast
python tools/dscpatch.py 0x1a39ef940 ff8301d1f65703a9 c0035fd61f2003d5 | tail -1   # CCUI _reparentCollectionViewController -> ret (throws)
python tools/dscpatch.py 0x1ad487118 ff8301d1f65703a9 c0035fd61f2003d5 | tail -1   # _UIStatusBarTimeStringServerCache setTimeString: -> ret (A8 blit segfault)
python tools/dscpatch.py 0x1a39ee790 28400bf0088541f9 000080d2c0035fd6 | tail -1   # CCUI _sharedCollectionViewController -> nil (throws)
python tools/dscpatch.py 0x183da0bb8 ff8305d1fc6f10a9 000080d2c0035fd6 | tail -1   # DMPluginFileSystemRep allReps -> nil (datamigrator never finishes; SB keeps boot UI)
# MCProfile.migrator calls profiled from inside the migration that profiled waits for: break the plugin (principal class name)
python - <<PY
open(r'$SP/mo.bin','wb').write(b'MCProfileMigrator'); open(r'$SP/mn.bin','wb').write(b'MCProfileMigratox')
PY
python tools/flash_block.py ipsw/gtelroot.img.zst userdata 480215 --expect-file $SP/mo.bin --new-file $SP/mn.bin --at 624 | tail -1
python tools/dscpatch.py 0x183d2c47c ff4302d1f65706a9 000080d2c0035fd6 | tail -1   # ACAccountStore accounts -> nil (breaks lsd/profiled/accountsd cycle)
python tools/dscpatch.py 0x183e02a70 f657bda9f44f01a9 c0035fd61f2003d5 | tail -1   # MCProfileConnection checkIn -> ret
python tools/dscpatch.py 0x1a92767b8 ff4303d1f6570aa9 000080d2c0035fd6 | tail -1   # _LSServer_LSEnumerateAndRegisterAllBundles -> return 0 (lsd seeding is far too slow on PIO eMMC)
echo "reset done (bootcycle.sh flips the HFS dirty bit before each boot)"
python tools/dscpatch.py 0x183da1900 080540f901610039 080540f91f610039   # DMIsMigrationNeeded block -> store NO
python tools/dscpatch.py 0x18c24e128 ff0302d1fa6703a9 00008052c0035fd6   # WiFiManagerClientGetServerPort -> 0 (wifid hang blocks SB main thread)
python tools/dscpatch.py 0x183810ccc ff8302d1e923036d be000014e923036d   # BKSSystemApplicationClient checkIn -> b finishBooting (dismiss boot logo)
python tools/bbd_overlay_patch.py   # backboardd: never add boot logo overlay
python tools/dscpatch.py 0x198d0dfd0 ffc302d1f65708a9 c0035fd61f2003d5   # MTXPCConnectionProvider didReceiveLifecycleNotification -> ret (sema wait blocks SB main)
python tools/dscpatch.py 0x196bc4938 ff4304d1e9230c6d 000080d2c0035fd6   # MadGate getActivationState: -> nil (mobileactivationd sync XPC hang)
python tools/dscpatch.py 0x1844ee870 ff0301d1f65701a9 00008012c0035fd6   # figXPC_PingServerConnection -> -1 (mediaserverd hidden, avoid sync wait)
python tools/dscpatch.py 0x18380f2d8 ff8301d1fa6701a9 00008052c0035fd6   # BKSDisplayRenderOverlay presentWithAnimationSettings: -> NO (SB-sustained boot logo)
python tools/dscpatch.py 0x1948c6734 ff4301d1f85f01a9 c0035fd61f2003d5   # PUIProgressWindow setVisible: -> ret (apple logo progress window)
