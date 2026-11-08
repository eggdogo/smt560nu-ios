#!/usr/bin/env python3
"""Extend the SPAWN logger (patch_spawn_log.py) to also dump the timer and
GIC-400 state after every posix_spawn, to find out why timed wakeups never
fire (sleep() hangs, IOKit timeouts never expire):

  TIMER cntv_ctl daif tval | GICD ctlr igroupr0 isenabler0 ispendr0 isactiver0
        | GICC ctlr pmr hppir

Chain : spawn-log cave's final `b RET` (0xfffffff00741f928) -> b CAVE
Cave  : 0xfffffff007b16d00  (zero padding at the end of __TEXT_EXEC)
"""
import shutil, struct, os, subprocess

KERN = 'kernel.development.sweet'
TEXT_EXEC_VA, TEXT_EXEC_OFF = 0xfffffff00725c000, 0x258000
SPAWN_CAVE = 0xfffffff00741f900
CHAIN = SPAWN_CAVE + 0x28         # b RET at the end of the spawn-log cave
RET = 0xfffffff00779f46c          # instruction after the posix_spawn hook
CAVE = 0xfffffff007b16d00
PRINTF = 0xfffffff0072c93e0
GICD_BASE = 0xfffffff007c091d0
GICC_BASE = 0xfffffff007c091d8


def fo(va):
    return TEXT_EXEC_OFF + (va - TEXT_EXEC_VA)


def b(pc, tgt, link=False):
    off = (tgt - pc) >> 2
    assert -(1 << 25) <= off < (1 << 25)
    return (0x94000000 if link else 0x14000000) | (off & 0x3ffffff)


def adr(pc, tgt, rd):
    off = tgt - pc
    assert -(1 << 20) <= off < (1 << 20)
    return 0x10000000 | ((off & 3) << 29) | (((off >> 2) & 0x7ffff) << 5) | rd


def asm(lines):
    """Encode position-independent instructions with llvm-mc (in WSL)."""
    out = subprocess.run(['wsl', 'llvm-mc', '-triple=aarch64', '-show-encoding'],
                         input='\n'.join(lines), capture_output=True, text=True, check=True).stdout
    words = []
    for line in out.splitlines():
        if 'encoding: [' in line:
            bs = line.split('encoding: [')[1].split(']')[0].split(',')
            words.append(struct.unpack('<I', bytes(int(x, 16) for x in bs))[0])
    assert len(words) == len(lines), out
    return words


data = bytearray(open(KERN, 'rb').read())
u32 = lambda va: struct.unpack_from('<I', data, fo(va))[0]

assert u32(CHAIN) == b(CHAIN, RET), 'spawn-log cave not found (apply patch_spawn_log.py first?)'
assert data[fo(CAVE):fo(CAVE) + 0x200] == b'\x00' * 0x200, 'cave not empty'

if not os.path.exists(KERN + '.pre_timerdiag'):
    shutil.copy(KERN, KERN + '.pre_timerdiag')

FMT_OFF = 0x100
head = asm([
    'sub sp, sp, #0x70',
    'stp x29, x30, [sp, #0x60]',
])
body = asm([
    'ldr x9, [x9]',
    'ldr x10, [x10]',
    'mrs x1, CNTV_CTL_EL0',
    'mrs x2, DAIF',
    'mrs x3, CNTV_TVAL_EL0',
    'ldr w4, [x9]',
    'ldr w5, [x9, #0x80]',
    'ldr w6, [x9, #0x100]',
    'ldr w7, [x9, #0x200]',
    'ldr w8, [x9, #0x300]',
    'ldr w11, [x10]',
    'ldr w12, [x10, #4]',
    'ldr w13, [x10, #0x18]',
    'sxtw x3, w3',
    'stp x1, x2, [sp]',
    'stp x3, x4, [sp, #0x10]',
    'stp x5, x6, [sp, #0x20]',
    'stp x7, x8, [sp, #0x30]',
    'stp x11, x12, [sp, #0x40]',
    'str x13, [sp, #0x50]',
])
tail = asm([
    'ldp x29, x30, [sp, #0x60]',
    'add sp, sp, #0x70',
    'mov w0, w27',
])

cave = list(head)
cave.append(adr(CAVE + 4 * len(cave), GICD_BASE, 9))
cave.append(adr(CAVE + 4 * len(cave), GICC_BASE, 10))
cave += body
cave.append(adr(CAVE + 4 * len(cave), CAVE + FMT_OFF, 0))
cave.append(b(CAVE + 4 * len(cave), PRINTF, True))
cave += tail
cave.append(b(CAVE + 4 * len(cave), RET))
assert 4 * len(cave) <= FMT_OFF

for i, w in enumerate(cave):
    struct.pack_into('<I', data, fo(CAVE) + 4 * i, w)
fmt = (b'TIMER cntv_ctl=%llx daif=%llx tval=%lld | GICD ctlr=%x grp0=%08x en0=%08x '
       b'pend0=%08x act0=%08x | GICC ctlr=%x pmr=%x hppir=%x\n\x00')
data[fo(CAVE + FMT_OFF):fo(CAVE + FMT_OFF) + len(fmt)] = fmt
struct.pack_into('<I', data, fo(CHAIN), b(CHAIN, CAVE))

open(KERN, 'wb').write(data)

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
for va, n in [(CHAIN, 4), (CAVE, 4 * len(cave))]:
    for ins in md.disasm(bytes(data[fo(va):fo(va) + n]), va):
        print(f'0x{ins.address:x}: {ins.mnemonic} {ins.op_str}')
