# Handoff: iOS 12.5.7 on Galaxy Tab E (SM-T560NU), 2026-11-13

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

## 0106 experiment — patch dyld's bind-at-load flag in the file (booted, log lost)

Image: `shim-boot-0106.img` (39,686,144 B) from CI `d4770cd`
(`kernel.development.sweet` 17,106,976 B; the three `SWEET: dyld bind-at-load ...`
strings are present in the packed image, so the code really is in there).

- `dyld_working` is **dyld-650.3.4**, 567,184 B, arm64, `__text` 0x1000..0x46294.
  `DYLD_BIND_AT_LAUNCH` sits at `__cstring` 0x46585; the env-name chain compares it at
  `__text` 0x293c (`adrp/add/strcmp`) and its handler at 0x2c58 is just
  `adrp x8,#0x5b000; add x8,x8,#0xa00; mov w9,#1; strb w9,[x8,#0x41]` — i.e. the switch
  is a single byte of dyld's own `__DATA` at file offset **0x5ba41** (0 in the file).
- `0106-gtel-dyld-bind-at-load.patch` adds `sweet_patch_dyld_bind_at_load()`, called
  immediately after the MobileGestalt write under `ARM64_BOARD_CONFIG_SWEET`. It first
  reads the 16 bytes at 0x2c58 and only proceeds if they match dyld-650.3.4 (otherwise it
  logs `... is not the expected dyld build ... skipping` and leaves the file alone), then
  flips 0x5ba41 0 -> 1, fsyncs, and logs `dyld bind-at-load enabled in /usr/lib/dyld`
  (or `already enabled` / `patch failed`).
- 0106 is a **delta on top of 0103** (its context includes the gestalt block), so it only
  applies after 0103 — verified by applying 0103 then 0106 to a pristine `bsd_init.c`.
- **0106 is lethal**: three boots, every time the tablet goes off USB within seconds and
  never comes back (no `18d1:d00d`, no `04e8`/`05c6`, no unknown device). 0105 stayed alive
  for minutes on the same flow. Either `sweet_patch_dyld_bind_at_load()` faults, or the byte
  patch works and dyld dies immediately at launchd start (`init died` -> panic -> reset).
- `0107-gtel-dyld-probe.patch` separates those two cases: it does the identical open + reads
  + signature check and then only logs `SWEET: dyld probe ok, bind-at-load byte is %d ...`,
  never writing. If 0107 survives and 0106 does not, the write is fine and the death is dyld
  itself - i.e. the flag took effect. Image: `shim-boot-0107.img` (39,686,144 B, `b4c6f51`).
- **0107 (probe, writes nothing) also dies** - the device never came back over ~4 minutes of
  polling. That kills the "our open path faults" theory and leaves one story that fits
  everything: **0106's write landed on the eMMC**, so `/usr/lib/dyld` is still patched and
  launchd/`init died` panics the box on *every* boot, whatever kernel you boot.
- Which also means the flag **did** take effect: with bind-at-load on, dyld resolves the bad
  `_rindex` slot eagerly at startup and dies there. So the defect is symbol resolution, not
  laziness - `bindAtLoad=1` only moves the crash earlier.
- `0108-gtel-dyld-revert.patch` is the recovery: it reads 0x5ba41 and, if it is non-zero,
  writes 0 back **before launchd starts** (logs `reverted to 0` / `already 0`). Image
  `shim-boot-0108.img` (39,686,144 B, `3197204`, built + packed, waiting for lk2nd).
- Boot attempt 2026-11-13: `fastboot boot` reported OK, then the tablet stopped
  enumerating on USB within ~3 minutes (no `18d1:d00d`, no `04e8`/`05c6`, no orphan
  python) so **no ring could be pulled**. Unknown cause: panic + reset, a dead USB link,
  or the tablet powering down. Nothing is flashed, eMMC untouched except the one dyld
  byte the kernel itself writes.
- Lesson: pull the ring **early** (first 32 KB after ~45 s) so the `SWEET: dyld ...` line
  is captured even if the device drops out later; the ring only exists while the kernel
  runs.
- **0108 boot attempt:** `fastboot boot shim-boot-0108.img` reported OK, then the tablet stopped
  enumerating within seconds and never came back over ~250 s of 5 s polling (no `18d1:d00d`, no
  `04e8`/`05c6`, no unknown device in Windows PnP, no orphan python). So **0108 is lethal too** —
  but note 0108 still does the `FREAD|FWRITE` open, so it does not discriminate anything yet.

## 0109 experiment — take the write out of the open (pushed, CI build was still running)

`0109-gtel-dyld-readonly.patch` (commit `a610632`) is the cleanest remaining probe: same file,
same offsets, same signature check, but
`vnode_open(SWEET_DYLD_PATH, FREAD, ...)` — **no write permission in the open, no `vn_rdwr`, no
`fsync`**, closed with `FREAD`. It only logs:

```text
SWEET: dyld read-only ok, bind-at-load byte is 0
```

Why it matters: 0107 read the file but opened it `FREAD|FWRITE`, and it died exactly like 0106. So
either (a) the byte 0106 wrote is still on the eMMC and every boot panics in `init died`, or (b) the
**write-capable open itself** is the killer (a MAC / code-signing check that only runs for a write
open of a platform binary, or a vnode-busy panic) and dyld was never modified at all.

0109 separates (a) from (b) only if the eMMC is clean — which is what the 0105 reference boot is for
(see below). CI run `43355654504` (`a610632`) was `in_progress` when this handoff was written; nothing
was fetched or packed yet, so `shim-boot-0109.img` does not exist on disk.

## Where things stand tonight (2026-11-13) — paused, tablet is off USB

**The tablet is not enumerating** (needs egg to hold the keys and reset it into lk2nd). Nothing is
half-flashed: everything went out with `fastboot boot`, and the only persistent writes are the ones
the kernel itself makes to the rootfs (`ufsrw=1 rootrw=1`). Clean stop point.

| image | patch | what it does | verdict |
| :--- | :--- | :--- | :--- |
| `shim-boot.img` | 0105 | `DYLD_BIND_AT_LAUNCH=1` in launchd's env only | **survives for minutes** — the known-good reference |
| `shim-boot-0106.img` | 0106 | open `FREAD+FWRITE`, flip 0x5ba41 → 1 | dies, 3/3 boots |
| `shim-boot-0107.img` | 0107 | same open, read + sig check, **no write** | dies, never back over ~4 min |
| `shim-boot-0108.img` | 0108 | same open, write 0 back to 0x5ba41 | packed (`3197204`), died on first boot |
| *(no image yet)* | 0109 | open **`FREAD` only**, read the byte, no write | CI `43355654504` still building |

## Action plan for next session

1. **Boot the known-good reference first: `python tools/pyfastboot.py boot shim-boot.img`** (0105,
the build that stays up for minutes), then poll `python tools/pyfastboot.py devices` every 4–5 s for
~250 s. This one boot settles the most important question — **is the on-disk dyld dirty?**
   - **It survives** → the eMMC dyld is clean, 0106's write never landed, and the killer is the
     write-capable open. Go to step 2.
   - **It also dies** → byte 0x5ba41 really is 1 on the eMMC and every boot panics in `init died`.
     Then recover at block level: `tools/hfs_locate.py` currently fails on this rootfs
     (`python tools/hfs_locate.py ipsw/gtelroot.img.zst /usr/lib/dyld` → `C: not found under CNID 2`),
     so use `tools/flash_block.py` with a block number found another way, or mount
     `ipsw/gtelroot.img.zst` on Linux and zero byte `0x5ba41` of `/usr/lib/dyld`
     (dyld-650.3.4, 567,184 B, `__text` 0x1000..0x46294).
2. **Fetch and pack 0109** (only if CI `43355654504` is green):
   `python tools/fetch_build.py --sha a610632`, then
   `RD=ufsroot0 EXTRA="sweetsample=launchd ufsrw=1 rootrw=1 nointr_consio=1" bash tools/local_pack.sh xnu_build/kernel.development.sweet shim-boot-0109.img`
   and boot it. Survives → the write open is the killer, and the next patch should read the byte
   through a read-only open (or skip the file and fix the value in memory once dyld is mapped).
3. **Pull the ring early** — `python tools/pull_log.py --head 8192 -o console_log_0109_head.txt`
   about 45 s after `fastboot boot` — because the `SWEET: dyld ...` line *is* the experiment and a
   bad patch drops the device off USB within ~3 minutes.
4. Only if dyld cannot be touched from the kernel this way, fall back to rootfs work: rewrite
   `/System/Library/LaunchDaemons/*.plist` `EnvironmentVariables` for every job.
5. **Then re-evaluate MobileGestalt** (the real defect: the `_rindex` `__la_symbol_ptr` slot at
   `0x3c618` holds garbage, so `br x16` jumps to `0x0f7870000`), and after that Step 4, SpringBoard
   on screen.
6. **Graphics note:** `backboardd` reaches `sel 72/73/74` + `notifications type 3 on`, then
   `SIGABRT` (sig 6) at `0x180adb094`, `far 0x1b7dda008` — already past the Nov 9 baseline.

### Tooling notes

- Windows Git Bash has no `strings`; use `grep -a -o "pattern" file` on binaries instead.
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
