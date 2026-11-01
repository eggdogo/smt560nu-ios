# SM-T560NU iOS / XNU Porting Notes

## 1. Silicon Differences vs. dipa-studio/ios-sweet

| Attribute | dipa-studio/ios-sweet (SM7150) | iosont560nu (MSM8916) | Notes |
| :--- | :--- | :--- | :--- |
| **SoC** | Snapdragon 732G | Snapdragon 410 | MSM8916 has cleaner mainline/lk2nd support |
| **Cores** | 2× A76 + 6× A55 | 4× Cortex-A53 | Homogeneous SMP on MSM8916 |
| **TGran16 (16KB MMU)** | Supported (`TGran16 != 0`) | **NOT IMPLEMENTED (`TGran16 == 0`)** | Cortex-A53 cannot walk 16KB tables |
| **Page Table Granule** | 16 KB | **4 KB** | XNU MUST use 4KB pages |
| **Interrupt Controller** | GICv3 (System Regs ICC_*) | GIC-400 (GICv2 Memory Mapped) | Distributor at 0x0b000000, CPU at 0x0b002000 |
| **RAM** | 6-8 GB | **1.5 GB** | iOS 16 Jetsam killer would thrash; iOS 12 fits easily |
| **Storage** | UFS 2.2 | eMMC 5.0 (SDHCI) | Bring-up first with RAM-disk root |

## 2. Page Table Strategy (4KB Granule)

The ARM Cortex-A53 TRM specifies:
- `ID_AA64MMFR0_EL1[23:20]` (`TGran16`) = `0x0` (16KB granule not supported).
- `ID_AA64MMFR0_EL1[31:28]` (`TGran4`)  = `0x0` (4KB granule supported).

In XNU:
- Define `__ARM_16K_PG__ = 0`.
- Machine constants resolve to `ARM_PGBYTES 4096`, `ARM_PGSHIFT 12`.
- Bootstrap page table allocation (`bootstrap_pagetables` in `start.s` / `arm_vm_init.c`) uses 4KB translation level 1, 2, and 3 entries.

## 3. GIC-400 (GICv2) vs. GICv3

On `sweet` (GICv3), interrupts and virtual timer were delivered through Group 1 IRQs using system registers:
```c
uint64_t iar = __builtin_arm_rsr64("ICC_IAR1_EL1");
...
__builtin_arm_wsr64("ICC_EOIR1_EL1", iar);
```

On MSM8916 (GIC-400), interrupts are accessed via standard MMIO memory-mapped registers:
- `GICD_BASE`: `0x0b000000`
- `GICC_BASE`: `0x0b002000`
- Acknowledge interrupt: read `*(volatile uint32_t *)(GICC_BASE + 0x0c)` (`GICC_IAR`)
- End of Interrupt: write `*(volatile uint32_t *)(GICC_BASE + 0x10)` (`GICC_EOIR`)
- Virtual timer is standard ARM Architected Timer PPI 27.

## 4. Why Target iOS 12.5.7 (iPad mini 2 / iPad4,4)?

1. **Hardware Parity**: The iPad mini 2 (`iPad4,4`) ran on Apple A7 (Cyclone, ARMv8.0-A), which natively used 4KB MMU translation tables with 1 GB of RAM!
2. **RAM Headroom**: On SM-T560NU with 1.5 GB RAM, iOS 12 will comfortably keep `launchd`, `notifyd`, `configd`, `backboardd`, and `SpringBoard` resident without triggering aggressive `jetsam` out-of-memory memory kills.
3. **Form Factor**: iPad mini 2 shares the tablet UI layout, portrait/landscape orientation, and tablet SpringBoard gesture/home button paradigm.
