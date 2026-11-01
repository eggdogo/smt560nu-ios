ENTRY(_start)

SECTIONS {
	. = 0x86004000;

	.text : {
		*(.text .text.*)
	}

	.rodata : {
		*(.rodata .rodata.*)
	}

	.data : {
		*(.data .data.*)
	}

	.bss : {
		_bss_start = .;
		*(.bss .bss.*)
		*(COMMON)
		_bss_end = .;
	}
}
