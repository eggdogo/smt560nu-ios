/*
 * SM-T560NU Boot Shim Main Entry.
 *
 * Verifies Cortex-A53 / MSM8916 hardware state, detects display via FDT,
 * checks GIC-400 and PSCI, and executes the XNU payload.
 */
#include <stdint.h>
#include "console.h"
#include "fdt.h"
#include "loader.h"

#define GICD_BASE           0x0b000000UL
#define GICC_BASE           0x0b002000UL
#define GICD_CTLR           0x000
#define GICD_TYPER          0x004
#define GICC_CTLR           0x000
#define GICC_PMR            0x004

#define PSCI_VERSION        0x84000000UL
#define PSCI_CPU_ON         0xc4000003UL
#define PSCI_SYSTEM_RESET   0x84000009UL
#define SMCCC_VERSION       0x80000000UL

#define NR_CPUS             4

#define rsr(r) ({ uint64_t _v; __asm__ volatile("mrs %0, " r : "=r"(_v)); _v; })
#define wsr(r, v) __asm__ volatile("msr " r ", %0" : : "r"((uint64_t)(v)))
#define isb() __asm__ volatile("isb" ::: "memory")

static inline uint32_t rd32(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void wr32(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

extern char secondary_entry[];
static const char *stage = "init";

static uint64_t smc(uint64_t fn, uint64_t a1, uint64_t a2, uint64_t a3)
{
	register uint64_t x0 __asm__("x0") = fn;
	register uint64_t x1 __asm__("x1") = a1;
	register uint64_t x2 __asm__("x2") = a2;
	register uint64_t x3 __asm__("x3") = a3;
	__asm__ volatile("smc #0"
			 : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
			 :
			 : "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11",
			   "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	return x0;
}

static uint64_t hvc(uint64_t fn, uint64_t a1, uint64_t a2, uint64_t a3)
{
	register uint64_t x0 __asm__("x0") = fn;
	register uint64_t x1 __asm__("x1") = a1;
	register uint64_t x2 __asm__("x2") = a2;
	register uint64_t x3 __asm__("x3") = a3;
	__asm__ volatile("hvc #0"
			 : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
			 :
			 : "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11",
			   "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	return x0;
}

static uint64_t psci_call(uint64_t fn, uint64_t a1, uint64_t a2, uint64_t a3)
{
	uint64_t el = (rsr("CurrentEL") >> 2) & 3;
	uintptr_t pc;
	__asm__ volatile("adr %0, ." : "=r"(pc));

	/* In QEMU virt (RAM at 0x40000000), PSCI is invoked via HVC */
	if (el == 2 || pc < 0x70000000UL)
		return hvc(fn, a1, a2, a3);

	/* On physical Qualcomm MSM8916 hardware, PSCI is handled by TrustZone via SMC */
	return smc(fn, a1, a2, a3);
}

static uint64_t now(void)
{
	isb();
	return rsr("cntpct_el0");
}

static void __attribute__((unused)) delay_ms(unsigned ms)
{
	uint64_t end = now() + (rsr("cntfrq_el0") / 1000) * ms;
	while (now() < end)
		;
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	con_clear(BLUE);
	con_str("PANIC", "EXCEPTION IN BOOT SHIM");
	con_hex2("SLOT", "slot=", slot, "cpu=", rsr("mpidr_el1"));
	con_str("STAGE", stage);
	con_hex("ESR", rsr("esr_el1"));
	con_hex("ELR", rsr("elr_el1"));
	con_hex("FAR", rsr("far_el1"));
	con_hex("SPSR", rsr("spsr_el1"));
	con_hex("X0", regs[0]);
	con_hex("X1", regs[1]);
	for (;;)
		__asm__ volatile("wfe");
}

void secondary_main(uint64_t cpu_id __attribute__((unused)))
{
	/* Secondary core idle loop until XNU reboots/claims it */
	for (;;)
		__asm__ volatile("wfe");
}

void shim_main(uint64_t fdt)
{
	uintptr_t pc;
	__asm__ volatile("adr %0, ." : "=r"(pc));

	uint64_t fb_base = 0;
	uint32_t fb_w = 0, fb_h = 0, fb_stride = 0, fb_bpp = 32;

	/* 1. Try to find active framebuffer from lk2nd FDT */
	int found_fb = fdt_find_simplefb(fdt, &fb_base, &fb_w, &fb_h, &fb_stride, &fb_bpp);
	if (found_fb) {
		con_init(fb_base, fb_w, fb_h, fb_stride, fb_bpp);
	} else {
		con_init(DEFAULT_FB_BASE, DEFAULT_FB_W, DEFAULT_FB_H, DEFAULT_FB_STRIDE, DEFAULT_FB_BPP);
	}
	con_clear(BLUE);

	/* Diagnostic shapes to identify exact stride/orientation */
	con_rect(16, 16, 80, 80, WHITE);
	con_rect(112, 16, 80, 80, YELLOW);
	con_skip();
	con_skip();
	con_skip();

	con_str("SHIM", "GTEL BOOT SHIM (SM-T560NU)");
	con_hex2("FB", "fdt=", found_fb, "stride=", con_stride);
	con_hex2("RES", "w=", con_w, "h=", con_h);
	con_hex2("ADDR", "base=", (uint64_t)con_fb, 0, 0);
	con_skip();

	/* 2. Hardware sanity inspection */
	stage = "hw info";
	uint64_t mmfr0 = rsr("id_aa64mmfr0_el1");
	uint32_t tgran4 = (mmfr0 >> 28) & 0xf;
	uint32_t tgran16 = (mmfr0 >> 20) & 0xf;
	uint32_t tgran64 = (mmfr0 >> 24) & 0xf;

	con_hex2("MMFR0", "4K=", tgran4, "16K=", tgran16);
	con_hex2("MMU", "64K=", tgran64, "pa_range=", mmfr0 & 0xf);
	con_hex2("CPU", "id=", rsr("midr_el1"), "mpidr=", rsr("mpidr_el1"));
	con_hex2("TIMER", "cntfrq=", rsr("cntfrq_el0"), 0, 0);

	/* 3. Probe PSCI and GIC */
	stage = "psci probe";
	uint64_t psci_ver = psci_call(PSCI_VERSION, 0, 0, 0);
	con_hex2("PSCI", "ver=", psci_ver, "smccc=", psci_call(SMCCC_VERSION, 0, 0, 0));

	stage = "gic probe";
	uintptr_t gicd_base = (pc < 0x70000000UL) ? 0x08000000UL : GICD_BASE;
	uint32_t gicd_typer = rd32(gicd_base + GICD_TYPER);
	con_hex2("GIC", "lines=", (gicd_typer & 0x1f) * 32, "cpus=", ((gicd_typer >> 5) & 0x7) + 1);
	con_skip();

	/* 4. Boot XNU if payload present in ramdisk */
	stage = "xnu loader";
	con_str("LOADER", "probing /chosen initrd for GTELXNU...");
	const char *why = loader_boot(fdt);
	con_str("LOADER", why);
	con_skip();

	/* If loader returned, wait on diagnostic screen */
	stage = "standby";
	con_str("STATUS", "No XNU payload. Shim alive! Waiting...");
	for (;;)
		__asm__ volatile("wfe");
}
