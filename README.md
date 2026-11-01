# smt560nu-ios

Booting Apple Darwin XNU and iOS on the Samsung Galaxy Tab E 9.6 (`SM-T560NU` / `gtelwifiue`).

Targeting **iOS 12.5.7** (`16H81`, iPad mini 2 `iPad4,4` / `J85AP` userland) and **Darwin XNU** (`xnu-8796` / `xnu-4903`).

---

## Hardware Specifications

| Component | Target Spec |
|-----------|-------------|
| **Device** | Samsung Galaxy Tab E 9.6 Wi-Fi (`SM-T560NU`, `gtelwifiue`, `gtesqwifi`) |
| **SoC** | Qualcomm Snapdragon 410 (APQ8016 / MSM8916) |
| **CPU** | 4× ARM Cortex-A53 @ 1.2 GHz (ARMv8.0-A, no PAC, `TGran4 == 0`, `TGran16 == 0`) |
| **RAM** | 1.5 GB LPDDR3 (Base `0x80000000`, Usable ~1,439 MB) |
| **Display** | Novatek NT51017 MIPI DSI Video Mode (800×1280 portrait, 24bpp RGB888, stride 2400) |
| **Framebuffer** | Continuous Splash Base `0x8e000000` |
| **Interrupt Controller** | ARM GIC-400 (GICv2) @ `0x0b000000` (GICD) / `0x0b0b2000` (GICC) |
| **Timers** | ARMv8 Generic Architected Timer (`CNTV`, Virtual PPI INTID 27) |
| **Boot Chain** | Samsung PBL -> SBL -> QSEE (TZ) -> LK (`lk2nd`) -> Bootloader Shim -> Darwin XNU |

---

## Memory Map

```
0x80000000 - 0x86000000 : Reserved / TrustZone / LK / Shim load space
0x86000000 - 0x86005000 : Darwin XNU Kernel Mach-O segments (__TEXT, __DATA)
0x86005000 - 0x86007000 : Apple Device Tree (ADT, ~6 KB)
0x86007000 - 0x86008000 : Apple boot_args (Rev 2 struct)
0x86008000 - 0x8600c000 : Early Boot Stack / Scratch
0x8e000000 - 0x8e3e8000 : Continuous Framebuffer (Novatek NT51017, 800x1280x3)
```

---

## Repository Structure

* `.github/workflows/xnu.yml`: Automated GitHub Actions workflow to build Darwin XNU on macOS arm64 runners.
* `xnu/patches/`: Modular patchset adapting open-source XNU for Qualcomm MSM8916 hardware.
* `shim/`: Bare-metal AArch64 bootloader shim that parses Apple Mach-O binaries, sets up ADT/boot-args, and jumps into XNU.
* `tools/`:
  * `pyfastboot.py`: LibUSB-based fastboot protocol client.
  * `mkadt.py`: Apple Device Tree generator for GTEL (`iPad4,4` profile).
  * `mkpayload.py`: Packages Mach-O + ADT + boot-args + ramdisk into flat `GTELXNU` payload.
  * `pack_bootimg.py`: Android boot.img v0 packer for `fastboot boot`.
  * `gtel_root_tweaks.py`: Applies bringup tweaks to iOS rootfs/ramdisk (bypasses PurpleBuddy, disables watchdogs).

---

## Building and Booting

### 1. Build the Darwin XNU Kernel
The kernel builds automatically via GitHub Actions:
1. Navigate to the **Actions** tab in this repository.
2. Select **xnu**, click **Run workflow**, and set `machine_config` to `GTEL`.
3. Download the compiled `xnu-kernel` artifact (`kernel.development.gtel`).

### 2. Package the Boot Image
```bash
python tools/mkadt.py -o gtel.adt
python tools/mkpayload.py kernel.development.gtel gtel.adt payload.bin \
  --ramdisk ramdisk.dmg \
  --cmdline "debug=0x14e serial=0x3 cpus=1 gtel_fbcon=1 keepsyms=1 rd=md0"

bash shim/build.sh payload.bin
```

### 3. Boot Device via Fastboot
With the tablet connected in `lk2nd` fastboot mode:
```bash
python tools/pyfastboot.py boot shim/out/shim-boot.img
```
