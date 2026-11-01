/*
 * Darwin/XNU Entry Point for SM-T560NU Bringup Test.
 *
 * Called from gtel shim with MMU/caches off, x0 = boot_args physical address.
 */
	.text
	.globl _start
_start:
	msr	daifset, #0xf
	mov	x19, x0			/* Save boot_args pointer */

	/* Allocate stack above topOfKernelData (offset 32 in boot_args) */
	ldr	x1, [x19, #32]
	add	sp, x1, #0x4000

	/* Zero BSS */
	adr	x1, _bss_start
	adr	x2, _bss_end
1:	cmp	x1, x2
	b.hs	2f
	str	xzr, [x1], #8
	b	1b

2:	mov	x0, x19
	bl	xnu_main
3:	wfe
	b	3b
