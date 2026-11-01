#!/usr/bin/env python3
"""Wrap a flat AArch64 raw binary into a valid 64-bit Mach-O kernel executable.

Used to test XNU boot transitions and bare-metal handoff.
"""
import struct, sys

MH_MAGIC_64 = 0xfeedfacf
CPU_TYPE_ARM64 = 0x0100000c
CPU_SUBTYPE_ARM64_ALL = 0
MH_EXECUTE = 0x2
LC_SEGMENT_64 = 0x19
LC_UNIXTHREAD = 0x5
ARM_THREAD_STATE64 = 6
ARM_THREAD_STATE64_COUNT = 68

PAGE = 0x1000


def create_macho(raw_code, vmaddr=0xfffffff007004000, entry_va=None):
    if entry_va is None:
        entry_va = vmaddr

    # Header calculations
    code_size = len(raw_code)
    file_offset = PAGE
    file_size = (code_size + PAGE - 1) & ~(PAGE - 1)
    vm_size = file_size

    # LC_SEGMENT_64 (__TEXT)
    seg_cmd_size = 72 + 80  # segment + 1 section (__text)
    # LC_UNIXTHREAD
    thread_cmd_size = 16 + (ARM_THREAD_STATE64_COUNT * 4)
    sizeofcmds = seg_cmd_size + thread_cmd_size

    header = struct.pack(
        '<8I',
        MH_MAGIC_64,
        CPU_TYPE_ARM64,
        CPU_SUBTYPE_ARM64_ALL,
        MH_EXECUTE,
        2,  # ncmds
        sizeofcmds,
        0x1,  # flags
        0,    # reserved
    )

    # __TEXT segment
    seg = struct.pack(
        '<II16s4Q4I',
        LC_SEGMENT_64,
        seg_cmd_size,
        b'__TEXT\0\0\0\0\0\0\0\0\0\0',
        vmaddr - file_offset,  # vmaddr (including header page)
        vm_size + file_offset,
        0,  # fileoff
        file_size + file_offset,
        7,  # maxprot: rwx
        7,  # initprot: rwx
        1,  # nsects
        0,  # flags
    )

    # __text section (80 bytes)
    sect = struct.pack(
        '<16s16s2Q8I',
        b'__text\0\0\0\0\0\0\0\0\0\0',
        b'__TEXT\0\0\0\0\0\0\0\0\0\0',
        vmaddr,
        code_size,
        file_offset,
        2,  # align
        0,  # reloff
        0,  # nreloc
        0x80000400,  # flags: S_ATTR_SOME_INSTRUCTIONS | S_ATTR_PURE_INSTRUCTIONS
        0, 0, 0,  # reserved1, reserved2, reserved3
    )

    # arm_thread_state64: x0..x28, fp, lr, sp, pc, cpsr
    thread_state = bytearray(ARM_THREAD_STATE64_COUNT * 4)
    # PC is at index 32 * 8 = offset 256
    struct.pack_into('<Q', thread_state, 32 * 8, entry_va)

    thread_cmd = struct.pack(
        '<4I',
        LC_UNIXTHREAD,
        thread_cmd_size,
        ARM_THREAD_STATE64,
        ARM_THREAD_STATE64_COUNT,
    ) + bytes(thread_state)

    macho = bytearray(file_offset)
    cmds = header + seg + sect + thread_cmd
    macho[:len(cmds)] = cmds
    macho.extend(raw_code)
    # Pad to page
    if len(macho) % PAGE:
        macho.extend(b'\0' * (PAGE - (len(macho) % PAGE)))

    return bytes(macho)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: mkmacho.py input.bin output.macho [entry_va]")
        sys.exit(1)
    raw = open(sys.argv[1], 'rb').read()
    va = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0xfffffff007004000
    m = create_macho(raw, vmaddr=va)
    open(sys.argv[2], 'wb').write(m)
    print(f"Created Mach-O: {sys.argv[2]} ({len(m)} bytes, entry=0x{va:x})")
