# Handoff: display bring-up, 2026-11-18 night session

## TL;DR
`backboardd` no longer dies with `No window server display found` (BKDisplay.m:417). Root cause was **not**
the display driver: it was the Sandbox stand-in policy in the kernel. With the fix, backboardd and SpringBoard
stay alive (checked for 200+ s, 429 execs). Screen contents are **not verified** (nobody looked at the tablet).

Working image: `shim-boot-0109m.img` (kernel `kernel.development.sweet`, built by `tools/patch_0107_0108.py`).
Boot it with: `python tools/xlog.py run shim-boot-0109m.img -o log.txt --seconds 300 --until "CRASH |Kernel data abort|MACH Reboot"`

## Root cause chain (all verified in logs / disassembly)
1. After `backboardd` set up AppleCLCD (selectors 18..74, 72, 73 all fine) it did two XPC requests for
   `com.apple.CARenderServer`. launchd answered the 2nd (routine 0xCF, with `instance`) with
   `error = 0x44c` = 1100 = BOOTSTRAP_NOT_PRIVILEGED, `req_pid` = backboardd's pid.
2. launchd maps errno 1 (EPERM) -> 0x44c (translator at launchd 0x1000258a4). The EPERM comes from
   `lookup_service()` (launchd 0x10001e39c): `sandbox_check_by_audit_token(token, "mach-lookup", ..., name) != 0`.
3. `libsystem_sandbox` `sandbox_check_common` does `__mac_syscall("Sandbox", 2, args)` with `args[0]` = pointer to an
   **uninitialised 8-byte stack slot** and returns `(*slot != 0)`. The real Sandbox kext writes the decision there.
4. Our stand-in (`sweet_sandbox_syscall`, patch 0050) returned 0 for op 2 and never wrote the slot -> launchd read stack
   junk (often non-zero) -> denied the lookup -> CARenderServer could not start -> `[CAWindowServer serverWithOptions:]`
   returned nil -> the assertion message "No window server display found" (misleading).

## What changed (all local, NOT yet in the GitHub repo except item 5)
1. `tools/gtel_display.c`: new `gtel_sandbox_op2(arg)`: `copyin(arg,&slot,8)`, `copyout(&zero, slot, 8)`.
2. `tools/patch_0107_0108.py`: trampoline at the stand-in's entry (0xfffffff007735a30): `cmp w1,#2; b.ne orig; ... bl gtel_sandbox_op2;
   mov w0,wzr; ret`; added `_copyout` (0xfffffff007419400) to EXT_SYMS; `_bzero` fixed to 0xfffffff007b1f500
   (it pointed at `_memset`, causing the earlier kernel data abort in the selector-74 handler).
3. `tools/gtel_display.c`: mach_msg tracer prints a one-line `MSGS ...` for the first 200 other sends (free BSS word 0x803b184).
4. `tools/xlog.py` (new) + `tools/pyfastboot.py`: live log pulling over the XNU gadget (no lk2nd); tolerates the missing
   trailing OKAY; `upload_from(offset)` windowed pulls.
5. `xnu/patches/0107-gtel-usb-fastboot.patch` in the GitHub repo (uncommitted): gadget gets `upload:<hexoffset>` (single
   <=60 KiB window). Full `upload` stalls above 64 KiB (multi-chunk TX bug in the gadget). Backup:
   `0107-gtel-usb-fastboot.patch.pre_upload_from` in this folder. gtel_usb code is now 7464/7520 bytes (56 spare).

**To make it permanent in CI**, port item 1+2's sandbox part into a source patch for `bsd/kern/sweet_amfi.c`, in
`sweet_sandbox_syscall()`:
```c
if (call == 2) {                 /* sandbox_check*: write "allow" into libsandbox's result slot */
    user_addr_t slot = 0; uint64_t zero = 0;
    if (copyin(arg, &slot, sizeof(slot)) == 0 && slot) (void)copyout(&zero, slot, sizeof(zero));
    return 0;
}
```
(the `arg` parameter is currently marked `__unused`).

## Things I tried that did NOT matter (reverted)
- Selector 18 (display id) returning 0: wrong. IOMFB `OpenByName` calls `GetDisplay(&p, isPrimary=1, ...)` which matches the
  framebuffer whose sel-18 id == 1, so the shim's value 1 is correct. Reverted; kernel identical to `.pre_sel18`.
- Sandbox op 4 -> allow: no effect (op 4 is not the mach-lookup check). Reverted.

## State at the end of the session
- Tablet is running `shim-boot-0109m.img` (XNU, USB gadget up). `backboardd`/`SpringBoard` alive; framebuffer selectors seen:
  18,57,7,15,22,8,33,74,72,73, then one `sel 6` and more 72s. No SwapEnd/present traffic yet (SpringBoard not drawing yet).
- Crashers: `mediaserverd` crash loop (SIGSEGV pc 0x1a7e73a04, far 0, and SIGTRAP at ___abort), `securityd` once (SIGTRAP at ___abort).
- Another agent (Antigravity) was editing `tools/gtel_display.c` / `tools/patch_0107_0108.py` and building `shim-boot-0109d..h` earlier
  tonight (21:20-22:12). Its mach_msg tracer is still in the source. Check before overwriting each other's work.

## Late finding (23:40): SpringBoard now dies in libMobileGestalt, not in the display path
- SpringBoard was NOT hung: with `sweetsample=SpringBoard` (image `shim-boot-0109n.img`) its main thread was still running dyld
  `+load` initialisers (`+[SpringBoardUI load]` ...); this boot is just very slow (1 CPU, emulated crypto), ~5-7 min to get there.
- Then SpringBoard (pid 43), `securityd` and `mediaserverd` all die the same way: SIGTRAP, `___abort <- abort_message <-
  std::terminate <- objc_terminate`, i.e. an uncaught exception, thrown inside a `dispatch_once` block in libMobileGestalt
  (frames 0x18143a500 / 0x18143c3b4 = MG offsets 0x1a500 / 0x1c3b4; block invoke at 0x18143a520 -> 0x181439d24, arg 1).
  The caller chain includes `___getMGAnswers_block_invoke` (0x193bff768).
- The exception text is unknown: the kernel's `STR scan of heap` only runs for sig 6, these are sig 5. Widening that check
  (inside `_sweet_crash_log`, kernel 0xfffffff0072a8f30) or adding boot-arg `sweetscan=SpringBoard,securityd` with a sig-5 patch
  would print it. This is the next blocker; likely a MobileGestalt cache/answer problem (see HANDOFF.md, MG cache).
- **EXCEPTION TEXT FOUND (image `shim-boot-0109o.img`, crash-scan widened to SIGTRAP + `sweetscan=SpringBoard,securityd`):**
  `NSInvalidArgumentException: -[NSNull objectForKey:]: unrecognized selector`, thrown at MG `0x181439dd8`.
  That is MobileGestalt's cache loader (function `0x181439d24`, MG offset 0x19d24): it loads the plist from the path literal
  at `0x18145eee3`, does `CFDictionaryGetValue(plist, "CacheExtra")` (non-NULL) and then
  `CFDictionaryGetValue(CacheExtra, "9UCjT7Qfi4xLVvPAKIzTCQ")`; CF forwards to ObjC `objectForKey:` because the object is an
  `NSNull`, not a CFDictionary. So at runtime `CacheExtra` (or the loaded root object) is not what we wrote
  (`com.apple.MobileGestalt.plist` on disk locally has CacheExtra = dict of 16 keys). Suspects, in order: (a) the file on the
  device is not our plist (stale/other copy, truncated or zero-padded write; check `/private/var/containers/Shared/SystemGroup/
  systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist` size/contents on the rootfs);
  (b) the loader decodes a `CacheExtra` value we encode as a bplist type it maps to null (compare with a real 16H81 cache;
  `CacheExtra` entries are also written by `gen_gestalt_cache.py` with a nested `list` and two nested dicts - try removing
  those three entries first); (c) key `9UCjT7Qfi4xLVvPAKIzTCQ` is looked up on `ReleaseType`-style data we must provide.
- Checked at 23:50: the plist embedded in `kernel.development.sweet` (file offset 0x1fc60, 4844 bytes) is byte-identical to the local
  `com.apple.MobileGestalt.plist` and parses with `CacheExtra` = dict of 16. So suspect (a) narrows to "what is actually on the device
  after the kernel's write" (truncation/stale copy/wrong path) or the loader's decoding; verify by reading the file back from the
  rootfs after a boot (HFS+ image `ipsw/gtelroot.img.zst`, tools `tools/hfs_locate.py` is currently broken) or by logging the
  written size/readback in `sweet_inject_gestalt_cache()`.
- Debug patch to keep: `patch_u32(... 0xFFFFFFF0072A9EA0, 0x7100191F -> 0x7100151F ...)` in `tools/patch_0107_0108.py`
  (crash heap-string scan also for sig 5). Boot-arg `sweetscan=SpringBoard,securityd` selects processes.
- UserEventAgent also crash-loops (20x): "error on event stream <private>: 3 - No such process".

## Next steps
0. Get the MobileGestalt exception text (see above); fix that first, SpringBoard cannot reach the window server before it aborts.
1. Look at the tablet screen. If blank: SpringBoard has to issue SwapBegin/SwapEnd (selectors around 3-6 / the 0x278 struct from patch 0108);
   find what it is waiting for (likely `mediaserverd`/`securityd` or a missing launchd service).
2. `mediaserverd` crash is already localised: `FigPreloadShadersInternal` (Celestial) -> `sbp_HDR_setProperty` ->
   `gl_prewarm_caches` -> `createHDRFromYCC420Buffers` -> `gl_combineandrender` null deref, all inside
   `/System/Library/VideoProcessors/HDR.videoprocessor` (OpenGL shader pre-warm with no GPU/GL context). Likely skippable
   (e.g. move/neutralise HDR.videoprocessor on the rootfs, or make the GL entry points fail gracefully); it should not block the window server.
3. `securityd` aborts (___abort): get its reason string (kernel STR scan only prints for sig 6; add securityd to boot-arg `sweetscan` or extend).
4. Port the sandbox fix + gadget `upload:` change into the repo patches and push.

## Tooling notes
- `build/ios16h81/dsc.py` (shared cache disassembler/symbolizer), `macho.py`, `ann.py`: used for all userland analysis. Run them without `python -I`.
- Annotation helper (strings from adrp/add) and decoders are in the session scratchpad only; easy to recreate.
- launchd disassembly: `launchd.asm` (project root).

## Last experiment (23:58): trimmed CacheExtra (image `shim-boot-0109p.img`, kernel `kernel.development.sweet.variant`)
Embedded plist rewritten in place with the nested list + 2 nested dicts removed from `CacheExtra` (13 keys, 4409 bytes; both
`mov w?,#0x12ec` size immediates in the kernel patched to the new size; written OK per kernel log). Result in a 400 s run:
no `NSNull objectForKey:` exception, **no crash of SpringBoard/securityd/mediaserverd** (they crashed before). But new picture:
`logd` crash-loops (147 CRASH blocks) and no `SWEET FB: backboardd sel` lines were seen in this run (possibly just slower; recheck).
So hypothesis (b) is confirmed: one of the nested `CacheExtra` entries (key `9MZ5AdH43csAUajl/dU+IQ` list, `oBbtJ8x+s1q0OkaiocPuog`
or `oPeik/9e8lQWMszEjbPzng` dict) makes MobileGestalt's loader hand back NSNull. Next: bisect those three entries one at a time (keep
the useful ones) and look at the `logd` crash (get its exception/abort reason with `sweetscan=logd`).
Nothing committed; variant script is ad hoc (python snippet in the transcript: find plist bytes in kernel, replace, patch the two movz).

## 07:15 session: bisect results (script: `tools/mkvar_gestalt.py <out_kernel> [L] [A] [B]`, run from project root; builds from `kernel.development.sweet.pre_variant`, keeps the named nested CacheExtra entries L=list, A=oBbt..., B=oPeik...)
- `local_pack.sh` works from Git Bash (WSL failed with NO_SYSTEM_RESOURCES). Note boot-args are limited, keep EXTRA short.
- Runs: 0109q = keep A+B (list removed): no NSNull, no SpringBoard/securityd crash. 0109r = L only: same. 0109t = A+B again without `logd` in sweetscan: same.
  So removing the LIST alone is enough to avoid the NSNull exception? (q/t) but L-only (r) is also clean, meaning A and B are not what produces it either;
  all three trimmed variants are clean, only the full cache throws. Not narrowed further (needs a run with L+A and L+B, ~7 min each).
- **logd crash-loop is NOT caused by the plist**: the untouched full-cache kernel (`.pre_variant`, 0109u, same args as the earlier clean run 0109o) now also
  crash-loops logd (80x, SIGSEGV pthread_mutex_lock far 0x40). Earlier boots (m, o) had zero logd crashes. Likely persistent rootfs state (rootrw=1 boots
  leave /private/var/db/diagnostics etc. behind) or the logd data from earlier boots. Next: reflash userdata/rootfs fresh (or delete logd state) and retest.
- IOK/SWEET FB selector lines: only 2-4 per run now vs 19-35 in m. Unclear if that is logd-crash CPU starvation (xpcproxy 227 execs) or a regression. Re-test on a clean rootfs.

## 07:38 WARNING: userdata was reflashed and now the tablet no longer boots to userland
- Bisect caveat: runs q/r/t/v (trimmed cache) were starved by the logd crash-loop (SpringBoard barely ran), so "no NSNull" there is NOT proof. Only 0109o-style healthy runs count.
- I suspected stale logd state and ran `python tools/flash_rootfs.py ipsw/gtelroot.img.zst userdata` (4099 MiB, 237 s; log `flash_userdata.log`).
  Result: **every boot (0109w, x, y; image shim-boot-0109u.img) now resets silently right after `exec cc_fips_test`** (before the FIPSPOST lines that the
  old userdata printed), device drops off USB and lands back in lk2nd. Root mounts fine (`hfs: mounted gtelroot`, not "dirty non-journaled ... read-write" as before).
- Old userdata was a patchwork: it contained Antigravity's HFS metadata repairs (`.gemini/.../scratch/build_hfs_meta_sparse.py` -> `hfs_meta_repair.sparse`, "zero-fill pages",
  see HANDOFF_SESSION.md) and leftovers under the all-zero blocks that flash_rootfs.py skips. The plain zst alone is NOT equivalent. Probably need those repairs
  (flash `hfs_meta_repair.sparse` with `fastboot flash userdata`, and check the mount message "dirty non-journaled root") before anything boots again.
- Tablet is currently in lk2nd. The logd crash was therefore never explained; it was probably a symptom of the earlier patchwork state.

## 07:45 Update on the userdata reflash (boot still fails, but the cause is now known)
- Fresh volume header says "unmounted/clean" (attrs 0x80000100), so the kernel mounts root **read-only**; the old volume was "dirty", which the kernel hack
  (`hfs_mounthfsplus: SWEET: mounting dirty non-journaled root read-write`) mounts rw. The unmounted bit gets set again by every clean shutdown, so clear it
  before each boot: attrs bytes at offset 1028 of block 0 (`0x80000100` -> `0x80000000`):
  `python tools/flash_block.py ipsw/gtelroot.img.zst userdata 0 --expect-file old.bin --new-file new.bin --at 1028` (old.bin = 80 00 01 00, new.bin = 80 00 00 00; both big-endian).
- With that the kernel mounts rw (0109ac), but then launchd's `fstab` task runs `mount_hfs` and fails (`GetMasterBlock: Error 2 opening /dev/rdisk0s2`) -> "Boot task failed: fstab" -> shutdown.
  The old (working) userdata must have had a modified /etc/fstab (or no fstab entry) - the pristine gtelroot image has the stock one. Needs an offline edit of /etc/fstab
  on the HFS+ image (mount the zst image in Linux/WSL, or find the file's block with hfs_locate/Antigravity's hfs_extract.py and use flash_block.py), then reflash.
- Net: the tablet's userdata is currently pristine-ish and does NOT boot to userland until /etc/fstab is fixed. Everything else in this file still stands.

## 07:50 Further attempts (still not booting past fstab)
- Ran Antigravity's `fix_emmc_zeros.py` (scratch dir of `.gemini/antigravity/brain/930aafe1-.../scratch`) after the reflash: writes the 15355 allocated-but-all-zero blocks and the
  clean /usr/lib/dyld blocks (flash_rootfs.py skips zero blocks, leaving stale data there). Together with the dirty-bit flip the kernel now prints
  "mounting dirty non-journaled root read-write" and "hfs: mounted gtelroot", but launchd's fstab step still ends in `mount_hfs ... GetMasterBlock: Error 2 opening /dev/rdisk0s2`,
  and `mount` reports `/dev/disk0s1 on / (hfs, local, read-only, noatime)` (old good run 0109m reported `(hfs, local, noatime)`, i.e. rw, and had hit
  "BlockMarkFreeInternal ... runtime corruption" on its first mount, so the old volume was in a different state than this clean one).
- Procedure to retry from here: `fix_emmc_zeros.py` (once), then before EVERY boot the dirty-bit flip (block 0, offset 1028: 80 00 01 00 -> 80 00 00 00), then
  `python tools/xlog.py run shim-boot-0109u.img ...`. Open question: why root ends up read-only for launchd on the clean volume (maybe the kernel's rw hack only applies to the
  dirty+inconsistent path, so look at `hfs_mounthfsplus` rw logic and whether `mount -uw` of `/` can work), or edit /etc/fstab offline.
- Lesson for the next session: do not reflash userdata for a guess; the existing rootfs state was hand-repaired and is not reproducible from the zst alone.

## 07:53 Source patch ported
- `smt560nu-ios/xnu/patches/0050-sweet-sandbox-policy.patch` now has the op-2 result-slot write (hunk counts fixed to +67 / +338; not test-applied, there is no xnu tree locally; backup `0050-sweet-sandbox-policy.patch.pre_op2` here). Uncommitted, together with the 0107 `upload:<offset>` change. Needs a CI run to confirm it applies and builds.

## 07:53 Last observation
- Repeat boot (0109ae, same prep) dropped off USB after `Tracing: disabled` right after `exec cc_fips_test`, i.e. before the fstab step, so the failure is not even deterministic:
  some boots reset silently ~90 s in (panic text never reached the ring), others get to the fstab failure. Next session: poll `log-size` at 1 s from the start and catch the final ring, or set `sweetsample=cc_fips_test`.

- Correction (07:55): with 1 s polling (0109af) the same prep ends deterministically in `Boot task failed: fstab` (mount_hfs: GetMasterBlock Error 2 opening /dev/rdisk0s2); the "silent reset" in 0109ae was just the 4 s poll missing the ring tail. So the single open blocker for the fresh userdata is the fstab / read-only root problem above.

- Pointer (07:56): the rw-root hack is `xnu/patches/0031-sweet-read-write-root.patch` (vfs_subr.c: boot-arg rootrw=1 clears MNT_RDONLY; hfs_vfsutils.c: dirty non-journaled root accepted). Both print/act as expected in 0109af, yet the later `mount` line says read-only, so something after the kernel mount (launchd `mount -uw`, or an HFS flag such as an fsck-needed/inconsistent state in the volume header) forces ro on the clean volume; compare the old volume header attributes (not saved) with 0x80000000.

- Best explanation (07:57), fits the log exactly: the 1st `mount_hfs` is the fstab line for `/` and re-applies `ro` ("/dev/disk0s1 on / (hfs, local, read-only)"), the 2nd `mount_hfs` is the `/dev/disk0s2` -> /private/var line (no such device: SWEET has no data volume) -> "Boot task failed: fstab".
  The old working rootfs evidently had a patched /etc/fstab (root rw, no disk0s2 line). So: edit /etc/fstab inside the HFS image (`/` entry rw, drop the /private/var entry), the kernel hack for a dirty root is then enough.

## 07:59 FIXED: tablet boots past fstab again
- /etc/fstab lives in block 140674 of userdata (`/dev/disk0s1 / hfs ro 0 1` + the disk0s2 /private/var line). Patched in place, same length: `ro`->`rw`, second line commented with `#`
  (`python tools/flash_block.py ipsw/gtelroot.img.zst userdata 140674 --expect-file fo.bin --new-file fn.bin --at 0`), plus the dirty-bit flip before each boot.
  Result 0109ag: `/dev/disk0s1 on / (hfs, local, noatime)` and launchd proceeds to keybagd. Userland is back; the bisect/logd/display checks can resume on this fresh state.

## 08:40 Healthy-state results (rootfs fixed, `tools/bootcycle.sh image log seconds` = dirty-bit flip + boot + watch)
- Control 0109ah/ai (full cache, fresh rootfs): **no logd crashes** (so that was stale rootfs state), no NSNull seen within 590 s. Display driver traffic from backboardd is fine
  (sel 18,57,7,15,22,8,33,74,72,73,6, notifications). Crashers: securityd (CKException "missing required entitlement com.apple.developer.icloud-services": AMFI
  stand-in gives no entitlements; keychain/CloudKit init, sig 5 loop), mediaserverd (GL prewarm), mobileactivationd, UserEventAgent once.
- **SpringBoard main thread is stuck (0109aj, sweetsample=SpringBoard)**: the same pc for 15+ samples, in a synchronous XPC: `-[PTSettings initWithDefaultValues]` ->
  `-[MCProfileConnection effectiveBoolValueForSetting:outAsk:]` -> `-[MCProfileConnection checkIn]` -> NSXPCConnection sync send -> `_dispatch_mach_send_and_wait_for_reply`.
  It is waiting for **profiled** (ManagedConfiguration), which is running (exec profiled, ~20x `SWEET AKS: profiled sel 17`, all ok). Next: sample profiled (0109pf) to see why it never replies.
- 0109ak (sweetsample=profiled): profiled worker thread blocks in `-[ACAccountStore accounts]` (sync XPC to **accountsd**); profiled main thread sits in its runloop. So the chain is
  SpringBoard -> profiled (MCProfileConnection checkIn) -> accountsd. accountsd is exec'd (p=88). Next: sample accountsd (0109al) for what it waits on (likely securityd/keychain or a DB).

## 09:20 Why SpringBoard never reaches the window server (log-only analysis, no screen access)
Chain, all from kernel thread samples (`sweetsample=<proc>`; images shim-boot-0109sb / pf / ad; logs console_log_0109aj/ak/al/am/an):
1. **SpringBoard main thread** is blocked for the whole run in `-[PTSettings initWithDefaultValues]` -> `-[MCProfileConnection effectiveBoolValueForSetting:outAsk:]` -> `checkIn` -> synchronous NSXPC to **profiled**.
2. **profiled** (alive, runloop main thread) has a worker thread blocked in `-[ACAccountStore accounts]` -> synchronous XPC to **accountsd**.
3. **accountsd**: two threads wait forever (`dispatch_semaphore_wait(…, -1)`) in `ACDServer init` blocks (one nested inside DataMigration `DMCopyOrderedPluginIdentifiers`), and another thread does
   `ACDKeychainCleanupActivity checkInIfNecessary` -> `-[ACAccountStore allCredentialItems]`, a sync XPC to accountsd's own (not yet listening) service. Classic start-up deadlock, or just
   extreme slowness (1 CPU, emulated crypto): the samples show identical stacks for 12+ consecutive samples (several minutes), so I believe deadlock.
- Tried: renaming the mach service names in the launchd plists of accountsd (`com.apple.accountsd.accountmanager`) and profiled (`com.apple.managedconfiguration.profiled`), same length, offline in userdata
  blocks 611928 / 612074. No effect (jobs still run and still hang; services probably re-register). **Both reverted to the pristine blocks.**
- Ideas for next time: (a) stop accountsd and profiled from being started at all (remove their plists from /System/Library/LaunchDaemons: clients then fail fast with bootstrap errors, or make
  launchd's job fail to spawn), (b) find what accountsd's `ACDServer init` semaphore waits for (DataMigration plugin scan; the AKS stand-in answers `com.apple.datamigrator sel 34` with 0xe00002c7),
  (c) fix securityd's `CKException ... missing entitlement com.apple.developer.icloud-services` (AMFI stand-in gives no entitlements) since accountsd/keychain paths hit securityd.
- Rootfs edits in place on the tablet right now: fstab block 140674 (rw, disk0s2 line commented), dirty-bit flip must be re-applied before every boot (`tools/bootcycle.sh`).
- 09:29 Renaming ALL mach service keys of both plists (accountsd 4, profiled 2; 0109ao) changed nothing either: profiled still exec'd once, SpringBoard main thread still blocked in
  MCProfileConnection checkIn. So either launchd takes these jobs from a different source than the HFS blocks I edited, or a sync NSXPC to an undeclared name also hangs on this launchd.
  Both blocks reverted again (pristine). Next idea: look at launchd's own log for lookups of `com.apple.managedconfiguration.profiled` (sweetsample=launchd, MSG trace of SpringBoard's send)
  to see which port SpringBoard actually messages and whether launchd replies.

## 09:40 Trace of SpringBoard's profiled lookup (0109ap, kernel traces any send containing "profiled")
- SpringBoard (pid ~) sends the launchd lookup routine 0x324 for `com.apple.managedconfiguration.profiled.public` (so the checkIn goes to the **.public** service, which is why renaming only
  the main name did nothing); the following launchd sends in the trace are unrelated spawns (xpcproxy), no obvious reply to that request. Needs a targeted trace of launchd->SpringBoard replies.
- Committed locally in `smt560nu-ios` (not pushed; push via the Terminal panel): d5b3f89 (patches 0050 op-2 fix + 0107 `upload:`) and a tools commit (xlog, pyfastboot, patch_0107_0108, gtel_display.c, mkvar_gestalt, bootcycle).
  `kernel.development.sweet` in the project dir is now built from the tracer with the "profiled" match (backup `kernel.development.sweet.pre_prof`, source backup `gtel_display.c.pre_prof`).

- 09:50 0109aq (long SpringBoard-sampled run): main thread still in MCProfileConnection checkIn after ~10 min of samples, so it is a real hang, not slowness. No SpringBoard display traffic (no SwapBegin/End) ever happens because of it.

## 12:30 Big progress: the hang chain is understood and SpringBoard now gets past it (log-only, no screen)
Tools: `tools/bootcycle.sh image log secs` (dirty-bit flip + boot + watch), `tools/dscpatch.py <va> <old> <new>` (patch dyld shared cache bytes on userdata via lk2nd; finds the block by
searching the image for 64 bytes of context), kernel `kernel.development.sweet.variant` (trimmed CacheExtra), `sweetsample=<16-char proc name>` (e.g. `com.apple.datami`).
Chain that blocked SpringBoard's main thread, from thread samples:
 SpringBoard -> profiled (MCProfileConnection checkIn) -> accountsd (ACAccountStore accounts) -> accountsd is inside **DMPerformMigration** (ACDServer init block: "Blocking non-migration
 connections until migration finishes") -> datamigrator.xpc -> migrationpluginwrapper runs data migrators one by one; **MCProfile.migrator calls profiled again = cycle**.
Fixes applied on the tablet's userdata (all offline block patches):
 1. dyld cache: entry of the DataMigration "perform migration" function at VA 0x183da20cc (file offset 0x3da20cc) `sub sp,sp,#0x50...` -> `mov x0,xzr; ret` (bytes ff4301d1 f65702a9 -> e0031faa c0035fd6; patch ran at image block 81406 off 0xcc).
 2. `MCProfile.migrator/Info.plist` NSPrincipalClass MCProfileMigrator -> MCProfileMigratox (block 480215 off 624) (probably redundant with 1).
 3. dyld cache `-[BKSSystemApplicationClient initWithCalloutQueue:]` `tbz w0,#0,...` at 0x183810bf4 (40010036) -> nop (1f2003d5): SpringBoard asserted "Client lacks entitlement com.apple.backboard.client"
    from `BSSelfTaskHasEntitlement` (SecTaskCopyValueForEntitlement on itself) although the kernel logs 227 entitlements for com.apple.springboard. **Open question: why does the self entitlement query fail?**
    (csops(CS_OPS_ENTITLEMENTS_BLOB) path in our AMFI stand-in? same symptom as securityd's CKException "missing icloud-services".) Fixing that properly is better than the nop.
 State after 1-3 (0109bc, sweetsample=SpringBoard): SpringBoard no longer hangs in profiled; its main thread then sits in `BKSSystemApplicationClient` connect loop (`_sendMessageOfType:packer:replyHandler:waitForReply:`
 with infinite semaphore wait at 0x183810f24) i.e. **waiting for backboardd to answer**; SpringBoard then dies quietly (no CRASH line, launchd respawns it; pids 43, 90, 112, 144, 153...).
Warning: with `sweetsample=backboardd` (and sometimes `launchd`) the MobileGestalt NSNull exception flood comes back even with the trimmed cache (0109bd, be); sampling other processes is clean. Use other probes.
Next: (a) why backboardd does not answer BKSSystemApplicationClient (look for a server-side entitlement check in backboardd on the connecting task, `com.apple.backboard.client` string at backboardd 0x8631d / 0xd03a6),
(b) fix the self-entitlement query, (c) why SpringBoard exits silently.

## 13:40 Findings: userdata degrades with every boot (HFS runtime corruption), plus the lsd chain
- `fsck.hfsplus -f -y` (WSL, hfsprogs) on the pristine image: "appears to be OK", so the zst image is fine. The damage is done at runtime by our rw HFS port/eMMC write path:
  `hfs: BlockMarkFreeInternal() trying to free unallocated blocks <1078195,1>` (allocation bitmap bits lost between mark-allocated and free: stale bitmap read or lost write), then
  `hfs_swap_BTNode: offset #0 invalid ... node=1 fileID=4` (catalog node read garbage). Counts per boot after a fresh `tools/reset_userdata.sh`: boot1 0, boot2 5 inconsistent msgs, boot3 146 + 130 BTNode errors
  (then lsd crash-loops in `__nls_free_resources`/`_sflush_locked` right after those errors). The earlier flaky `NSNull objectForKey:` MobileGestalt flood is very probably the same disease
  (reads of freshly written/cross-linked data returning zeros/garbage), it appears only on "used" userdata. **Root fix needed in the HFS/eMMC write path** (bitmap coherency or missing flush; start with patches 0098-gtel-emmc-write, sweet_hfs allocation code).
  Workaround: `tools/reset_userdata.sh` (fresh image + all offline fixes, ~8 min) before test sessions; use at most 2 boots per reset. `tools/bootcycle.sh` flips the dirty bit.
- First boot after reset: SpringBoard main thread is stuck in profiled `checkIn` again; second boot passes that and blocks in CoreServices `getServerStoreWithCompletionHandler:` = sync XPC to **lsd**;
  lsd's main thread (boot 3) waits on a sync call to **lsdiconservice** (`clearCachedItemsForBundleID:validateIconName:...`), then lsd crashes (see corruption above).
- Kernel debug hooks now in tools/gtel_display.c: EXIT log for SpringBoard/backboardd/profiled/accountsd (xstat is not final at that point, useless), MG cache readback (`MGCHK`, file is intact), `PEEK` of prefs files.
- Scripts: `tools/reset_userdata.sh`, `tools/dscpatch.py`, `tools/bootcycle.sh`, `tools/mkvar_gestalt.py` (SRC=kernel env), logs `console_log_0109b*.txt`.

## 16:25 BREAKTHROUGH: entitlements fixed -> SpringBoard unblocked, backboardd now RENDERS (crashes in CA software GL)
Root cause of ALL the failing entitlement lookups (SpringBoard "Client lacks entitlement com.apple.backboard.client", securityd "missing icloud-services", profiled/accountsd/lsd waits...):
every process's `p_csflags` is 0x22000000 (CS_VALID is cleared by the "cs_invalid_page ... allowing (remove VALID)" path, cs_enforcement_disable), and `csops_internal`
refuses CS_OPS_ENTITLEMENTS_BLOB (and BLOB/etc.) with EINVAL unless `p_csflags & (CS_VALID|CS_DEBUGGED)` -> SecTask returns no entitlements at all. The kernel blob itself is fine
(`cs_entitlements_blob_get` rc 0, 18911 bytes for SpringBoard, contains com.apple.backboard.client=true).
**Fix (tools/patch_0107_0108.py, binary patch, kernel 8796 addresses):** NOP the three `b.eq` after `tst x0,#0x10000001` in csops_internal:
`0xfffffff0077bf888` (0x54002D80), `0xfffffff0077bfa5c` (0x54001EE0), `0xfffffff0077bfc14` (0x54001120). Also patched `0xfffffff0077bf73c` (audit token pidversion compare, probably not needed).
**Source-level equivalent to port into a real xnu patch**: in `csops_internal`, do not require CS_VALID/CS_DEBUGGED for the CS_OPS_ENTITLEMENTS_BLOB / CS_OPS_BLOB / CS_OPS_IDENTITY-style cases on SWEET (or stop clearing CS_VALID).
Result (0109h1, kernel.exit.variant + shim-boot-0109cv.img, userdata = tools/reset_userdata.sh state, BKS assert nop REVERTED): `lacks entitlement` = 0, SpringBoard no longer hangs in profiled,
and **backboardd now runs the display bring-up to the end** (`SWEET FB: display on`, selectors 17/27/50/68 ...) and starts rendering with CoreAnimation's *software OpenGL rasterizer*
`CA::OGL::SW::scanline` -> SIGSEGV at 0x18537e43c (`ldrb w10,[x8,#3]` with x8 = [x29-0xf8] = NULL: converting an RGBA8 source to A8, source pixel pointer NULL, i.e. a texture/IOSurface whose base address is NULL).
backboardd then crash-loops (10x). Next: find which texture/surface has a NULL base (IOSurface stand-in `IOCoreSurfaceRoot` returning no mapping? `SWEET SURF` log), or the A8 conversion source being an IOSurface-backed layer.
Other findings this session: pristine image is fsck-clean; the per-boot corruption came from rebooting without sync (fixed: gtel_do_reboot/poweroff call sync_internal(), patch 0107 + kernel).
Debug hooks in gtel_display.c (SIG/EXIT/CSOPS/ENTPROBE/MGCHK/PEEK) are noisy; keep only if needed.
Usage note: weekly plan usage was 36% at this point.
- 16:40 IOSurface check: iOS 12 `IOSurfaceGetBaseAddress` = `*(client+0x58)` + `*(client+0x84)`; client+0x58 holds the lock result, so result+0x00 = data address and result+0x2c = offset, plane count at result+0x38:
  this matches what patch 0046 writes (`sweet_surface_fill_result`), so the surface base is probably fine. The NULL source pointer in `CA::OGL::SW::scanline` (RGBA8 -> A8 copy,
  `ldrb w10,[x8,#3]` x8=[x29-0xf8]) is therefore something else: a software-GL texture/level whose data pointer is NULL (maybe a failed malloc/vm_allocate in backboardd, or a zero-size/unallocated A8 level).
  Next probes: dump backboardd's memory/vm stats at crash, check JetsamMemoryLimit / vm limits, run `sweetsample=backboardd` (beware earlier NSNull bistability, fixed by the sync patch), log failed allocations.
- 16:50 scanline analysis: in `CA::OGL::SW::scanline` the slot [x29-0xf8] is either a 1 KiB stack scratch buffer or NULL; it is set to NULL exactly when
  `x24 != 0 && x11 == 0 && state->fmt (+0x678) == 0x20` where `x11 = base + (row*stride - ...)` i.e. the **render target's base pointer is 0** (direct-to-surface rendering of an A8-ish target).
  So the destination surface's mapped base address is NULL even though `SWEET SURF: create id N 800x1280 BGRA ... -> 0x0` succeeds (10 surfaces, one per backboardd restart, never looked up with selector 4).
  Check next: `IOSurfaceRootUserClient::create()` -> `returnSurface()` -> `addRef()` (`createMappingInTask` result for `ref->data->getAddress()`; maybe 0 for kIOMapAnywhere mapping created from a kernel task map, or the
  mapping is returned lazily), and whether iOS 12 expects the create reply to contain the address at +0 (it does: base = *(client+0x58)+*(client+0x84)). Log `ref->data->getAddress()` in create to confirm.

## 17:30 iOS 12 IOSurface protocol mismatch found (this is the cause of the null render target)
- Photo of the tablet at 16:35 showed the kernel console on the panel (gtel_fbcon) = display hardware + framebuffer work.
- iOS 12 `IOSurfaceLock` is **IOConnectCallMethod selector 2** (input struct {id, options}, output = lock result, client copies 0x50 bytes of it over its surface record at client+0x58:
  +0x00 data address, +0x08 state-page address, +0x2c offset, +0x38 plane count, +0x48 seed). `IOSurfaceUnlock` = selector 3 (4-byte seed out). Patch 0046 (iOS 16 numbering) treated selector 2 as
  "unknown, zero the output", so every lock wiped the client's base address -> `CA::OGL::SWContext::make_buffer_current` got NULL -> null destination in `scanline`.
- Binary-patch fix (tools/patch_0107_0108.py + tools/gtel_display.c): `IOSurfaceRootUserClient::externalMethod` pre-hook `gtel_surf_pre` rewrites selector 2 -> 4 (lookup) with the surface id as scalar input, so the existing lookup code answers with the lock result.
  Real fix belongs in patch 0046: add iOS 12 selectors (2 lock = same reply as lookup, keep use count, 3 unlock) and make `sweet_surface_fill_result` reuse the address given at create.
- Secondary bug: the lock/lookup reply carried data address 0xffffffffffffffff (the IOMemoryMap address of an already-mapped surface reads back -1 on re-lookups); `gtel_surf_log` now puts back the address remembered from the create reply (16-entry table in BSS slack at 0xfffffff00803b1c0).
- Result (0109k2/k3): backboardd's render target is non-NULL now; the SW GL crash is gone. New crash (still 6-13 restarts/boot): `memcpy(dst, 0x30, 100)` in IOSurface.framework at 0x1821dd06c..0xb0
  (`[client+0x60] + 0x30` = a read of the surface's shared *state page* timestamps with client+0x60 == NULL) so some IOSurface client record has no state-page address (a client created from some other selector's reply: iOS 12 selectors 5/9/22/26 and a
  possible lookup-from-port are still answered with zeros by the default case). REGS dump of x22+0x50 was all zeros (register had been reused; not conclusive).
- Next: identify which selector builds the client record that ends up with state==0 (log every IOSurfaceRoot selector with its input/output sizes, give each its real iOS 12 reply), then re-test; keep the display photo workflow (user can look at the tablet).
