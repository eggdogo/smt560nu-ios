# Handoff: iOS 12.5.7 on Galaxy Tab E (SM-T560NU), 2026-11-12

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

## What changed since the 2026-11-09 handoff

Committed as `8ad5d67`, CI build `c3c108e` (2026-11-11).

1. **`0104-gtel-kernel-mkdir.patch`** — exports `sweet_kernel_mkdir(const char *path, int mode)`,
   which builds a `vnode_attr` and calls `mkdir1at(vfs_context_kernel(), ..., UIO_SYSSPACE)`, so the
   kernel can create directories with a kernel-space path.

2. **`0103-gtel-inject-gestalt-cache.patch`** — `sweet_inject_gestalt_cache()` now:
   - `mkdir`s every component of
     `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches`
     with mode `0755` (logging `SWEET: mkdir <path> failed (errno N)` on failure),
   - always rewrites `com.apple.MobileGestalt.plist` (mode `0644`) instead of skipping when the
     legacy `/var/mobile/Library/Caches` copy exists.

3. **`tools/gen_gestalt_cache.py`** — scalars (`bool` / `int32` / `int64` / `float32`) now go into
   `CacheData` as raw values with their present flags instead of into `CacheExtra` (which is stored
   as retained CF pointers, so scalars there read back as pointer bits). Keys are validated against
   the dylib's question table (one non-precacheable key invalidates the whole cache), and
   `WLANBkgScanCache` is an `int`, not a `bool`.

4. **New plist**: `com.apple.MobileGestalt.plist` is now **4,844 bytes** (was 7,905) — binary bplist,
   `CacheVersion = "16H81"`, `CacheUUID = 34156B22-E548-4F28-827E-7FDBA7A2CF33`,
   `CacheData` = 3,780 bytes (`0xec4`) with 184 non-zero bytes, `CacheExtra` = 16 keys.

---

## Boot verdict, 2026-11-12 — the kernel side works, the cache was never the blocker

Booted `shim-boot.img` (kernel `sha256 a203820f…`, identical to the CI artifact) on lk2nd and pulled
the ring: **289,319 bytes** logged (`console_log_fix_head.txt` = first 64 KB,
`console_log_fix.txt` = newest 256 KB).

**Kernel injection now lands exactly where `libMobileGestalt` looks:**

```text
SWEET: Writing iPad4,4 MobileGestalt cache to /private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist (4844 bytes)...
SWEET: MobileGestalt cache written successfully!
```

**But daemons still crash**, so we disassembled the crash sites instead of guessing:

- `libMobileGestalt.dylib` is mapped at **`0x181420000`** in the shared region (this makes every
  crash address line up inside `__text`, `0xe7c`–`0x24af0`).
- `lr 0x18143c664` = offset **`0x1c664`**, which is exactly the instruction after
  `bl 0x252e8` inside MobileGestalt's **container-path lookup**
  (`…/MobileGestalt-645.270.1/MobileGestalt.c`, line 5811, the site that logs
  `Failed to look up system group container path: %llu`).
- `0x252e8` is a `__stubs` trampoline: `adrp x16, #0x3c000; ldr x16, [x16, #0x618]; br x16`.
  Slot `0x3c618` is in `__la_symbol_ptr` and binds the import **`_rindex`**.
- That slot holds garbage, so the `br x16` jumps into unmapped memory —
  `pc = far = 0xf7870000` for keybagd, locationd, SpringBoard, and the rest.

**Conclusion:** MobileGestalt dies in its container-path lookup *before it ever opens the plist*, so
no cache file can fix these crashes. Every daemon that touches MobileGestalt dies the same way.
Crash counts in the new window: `0x18143c540` ×28, `0x18143c664` ×62, `0x18143a4a0` ×0
(Nov 9: 2 / 3 / 11) — the old `atc`/`backboardd` site is gone, and the system now runs much longer
(495 `exec`s vs 165).

### Loader requirements recovered (for whoever revisits the cache)

- Path literal: `__cstring` `0x28ee3` (`/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist`).
- CFString keys in `__cfstring`: `CacheVersion` `0x7fd10`, `CacheData` `0x7fd30`,
  `CacheExtra` `0x7fd50`, `CacheUUID` `0x7fd70`; expected UUID literal `0x7fd90` =
  `34156B22-…`.
- `CacheData` must be exactly `0xec4` (3,780) bytes; `CacheExtra` questions must be precacheable
  (`verify_generated_cache.py` passes).
- Our plist satisfies all of these statically, so **Option C from the Nov 9 handoff (patch
  `0x3d70` `add #0xee3` → `#0xd44`) is obsolete** — the path is already correct.

---

## 0105 experiment, 2026-11-13 — the env route does **not** reach the daemons

`0105-gtel-launchd-bind-at-launch.patch` (commit `a464aca`, kernel `52bf490`, `sha256 7c853352…`):
`load_init_program_at_path()` now copies `DYLD_BIND_AT_LAUNCH=1` into the scratch page, writes a
one-entry `envp` array next to `argv`, and sets `init_exec_args.envp`. Until now that field was
`USER_ADDR_NULL`, so **launchd had no environment at all**.

**First run looked like a win, and it was wrong.** That boot only logged 33,633 bytes (~16 sampler
ticks) and stopped before the crashy phase: 1 crash block. The follow-up soak (96,497 bytes) shows
the loops are all still there:

| | 0103/0104 run | 0105 short run | 0105 soak run |
| :--- | :--- | :--- | :--- |
| log size | 289,319 B | 33,633 B | 96,497 B |
| execs | 495 | 98 | 181 (head window) |
| crash blocks | 142 | 1 | **15 in 64 KB, 49 CRASH lines in the last 8 KB** |
| respawns | constant | none seen yet | ptpd ×6, configd ×6, atc ×6, locationd ×4 |

So the env var is set for launchd, but it is **not taking effect in the daemons** — either launchd
builds each job's environment from its plist instead of inheriting, or dyld prunes `DYLD_*` for
platform binaries. Either way, `DYLD_BIND_AT_LAUNCH` is not a usable lever from the kernel side.
Lesson worth keeping: a 33 KB ring is only the pre-crash phase — always compare windows of similar
length.

`SWEET: MobileGestalt cache written successfully!` still appears, so 0103/0104 keep working; they
were never the blocker either. The lazy/importer jump is.

## Action plan for next session

1. **Patch dyld itself (no env, no plist).** dyld reads `DYLD_BIND_AT_LAUNCH` from the environment;
   force the bind-at-load path unconditionally instead. `/usr/lib/dyld` is a normal file on the
   eMMC rootfs, and 0103 already proves the kernel can open + rewrite files at early boot
   (`vn_open`/`vn_rdwr`), so a targeted in-place byte patch is preferable to embedding ~800 KB.
   Start from `dyld_working` in this project, find the `getenv("DYLD_BIND_AT_LAUNCH")` site, and
   pin the flag to 1.
2. Only if dyld turns out not to be patchable this way, fall back to rewriting
   `/System/Library/LaunchDaemons/*.plist` `EnvironmentVariables` for every job (rootfs work).
3. **Then re-evaluate MobileGestalt**, and after that go for Step 4 (SpringBoard on screen).
4. **Graphics note:** `backboardd` reaches `sel 72/73/74` + `notifications type 3 on`, then
   `SIGABRT` (sig 6) at `0x180adb094`, `far 0x1b7dda008` — already past the Nov 9 baseline.

### Tooling notes
- `tools/pull_log.py` reads 8 bytes per USB round trip (~340–460 B/s): a 256 KB pull takes ~10 min,
  so run it in the background and poll its log.
- If lk2nd goes silent (`USBTimeoutError` on the *first* `readq`, `getvar` also timing out), a
  libusb `dev.reset()` unblocks it without touching the tablet — the DRAM ring survives:
  `python -c "import usb.core, libusb_package; usb.core.find(idVendor=0x18d1,idProduct=0xd00d,backend=libusb_package.get_libusb1_backend()).reset()"`

---

## Useful Paths & Commands
- Repo: `C:\Users\Avett\Documents\GitHub\smt560nu-ios` (`main` branch)
- Project: `c:\Users\Avett\Documents\Projects\iosont560nu`
- Fastboot check: `python tools/pyfastboot.py getvar product`
- Pull log: `python tools/pull_log.py kernel.development.sweet -o console_log.txt` (or `--head 65536`)
- Build & cycle: `python tools/kcycle.py <commit_sha>`
