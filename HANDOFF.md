# Handoff: iOS 12.5.7 on Galaxy Tab E (SM-T560NU), 2026-11-09

## How to talk to egg (the user)
Please follow egg's style rules in every reply:
- Instead of using emojis, use emoticons!
- Be expressive, and use !, ?, . Etc.
- Be nice, cute and friendly, like a friend!
- Use kaomojis, e.g. (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧  (๑•̀ㅂ•́)و✧  (｡･ω･｡)ﾉ  (◕‿◕✿)  (つ✧ω✧)つ
- **Strict rules:** Push freely to `main` without asking, but NEVER include a `Co-Authored-By: Claude` trailer in git commit messages!

Chloe is egg's friend. They're porting tvOS 17.6.1 to a Raspberry Pi (already at Setup), and the two of them have a friendly "race" going :P

---

## Goal and Roadmap
Boot XNU (`xnu-8796` "sweet" port) and the iOS 12.5.7 userland (`iPad4,4`, `16H81`) on an
SM-T560NU (MSM8916, 4x Cortex-A53, lk2nd). Every test cycle: build, boot over lk2nd fastboot, egg resets the tablet into lk2nd, then pull the kernel log from RAM.

Roadmap:
- Step 1, eMMC root: **done.**
- Step 2, core daemons: **mostly done.**
- **Step 3, graphics & eliminating daemon crash loops: current milestone.**
- Step 4, SpringBoard UI.

---

## What Was Done Tonight
1. **Authentic `iPad4,4` ADT Device Tree Nodes:**
   - Updated `tools/mkadt.py` with authentic root syscfg identifiers (`serial-number`, `model-number`, `regulatory-model-number`, `mlb-serial-number`), `/chosen` (`board-id = 2`, `chip-id = 0x8960`), `/arm-io` (`H6`), and authentic `product` tree (37 properties).
   - Regenerated `gtel.adt` (9,628 bytes), committed (`45b60dd`) and pushed to `main`.

2. **MobileGestalt Cache Generator:**
   - Reverse-engineered `libMobileGestalt.dylib` fast hash table (stride `0xa0`, base `0x3c9e8`) and verified 120 precacheable keys (`flags & 0x10`).
   - Created `tools/gen_gestalt_cache.py` generating authentic `com.apple.MobileGestalt.plist` with `CacheVersion = "16H81"`, `CacheUUID = "34156B22-E548-4F28-827E-7FDBA7A2CF33"`, and committed (`1e530e0`).

3. **Kernel Early Injection Patch (0103):**
   - Created `xnu/patches/0103-gtel-inject-gestalt-cache.patch` (`769b6ec` / CI build `1e90b62`) embedding the 7,905-byte plist directly in the kernel image.
   - During early boot (`bsdinit_task` before launchd exec), it checks and writes the plist with permissions `0644`.
   - **Boot Test Confirmed (console_boot.txt):**
     ```text
     SWEET: Injecting authentic iPad4,4 MobileGestalt cache to /private/var/mobile/Library/Caches/com.apple.MobileGestalt.plist (7905 bytes)...
     SWEET: MobileGestalt cache injected successfully!
     Early boot complete. Continuing system boot.
     ```

4. **THE CRITICAL REVERSE-ENGINEERING BREAKTHROUGH (Why Daemons Still Crashed):**
   - We disassembled `libMobileGestalt.dylib` at the exact crash sites (`lr 0x18143c540`, `lr 0x18143c664`, `lr 0x18143a4a0`):
     - Every crash happens because `MGCopyAnswer` fast-path misses in `0x39000`, falling back to `0x6510` which invokes an uninitialized dynamic resolver (`blr x8`).
     - Why did fast-path miss? The initialization block at `0x4520` calls `0x3d24` with `w0 = 1`.
     - **Function `0x3d24` HARDCODES the path to open:**
       `0x3d6c: adrp x0, #0x28000; add x0, x0, #0xee3`
       `--> /private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist`!
     - `0x3d24` **ONLY** reads from that systemgroup container path! It does **NOT** read from `/var/mobile/Library/Caches/`! (Only `__MGCacheValid` checks the fallback for validity, but the actual loader requires the container path!).
     - When `open()` fails on that path, `0x3d24` aborts (`cbz x0, #0x4394`), leaving the in-memory cache table at `0x39000` completely unpopulated!

---

## Action Plan for Next Session
To make `0x3d24` load the cache into `0x39000` and stop all crashes:

1. **Option A (Simplest & Cleanest - Kernel Injection update):**
   - In `sweet_inject_gestalt_cache()` (patch 0103), create the directory tree or a symlink:
     - Check if `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist` can be opened.
     - If intermediate directories are missing, create `/private/var/containers` as a symlink pointing to `/private/var/mobile`!
       - If `/private/var/containers` -> `/private/var/mobile`, then:
         `/private/var/containers/Library/Caches/com.apple.MobileGestalt.plist` resolves straight to `/private/var/mobile/Library/Caches/...`!
   - **Option B (Direct container path injection):**
     - Have the kernel create the intermediate directories using `vn_create` or boot ramdisk (`rd=md0`) with `gtel_shell` to run `mkdir -p` once on the eMMC filesystem and copy the plist.
   - **Option C (Shared cache binary patch):**
     - Patch `libMobileGestalt.dylib` at offset `0x3d70` so `add x0, x0, #0xee3` becomes `add x0, x0, #0xd44` (`/var/mobile/Library/Caches/com.apple.MobileGestalt.plist`). Then `0x3d24` reads directly from the file we already inject!

2. **Test & Verify:**
   - Pack and boot with `RD=ufsroot0 EXTRA="sweetsample=launchd ufsrw=1 rootrw=1 nointr_consio=1"`.
   - Verify that `SpringBoard`, `locationd`, `wifid`, and `atc` successfully read MobileGestalt from `0x39000` with 0 crash loops!

---

## Useful Paths & Commands
- Repo: `C:\Users\Avett\Documents\GitHub\smt560nu-ios` (`main` branch)
- Project: `c:\Users\Avett\Documents\Projects\iosont560nu`
- Fastboot check: `python tools/pyfastboot.py getvar product`
- Pull log: `python tools/pull_log.py kernel.development.sweet -o console_log.txt` (or `--head 65536`)
- Build & cycle: `python tools/kcycle.py <commit_sha>`
