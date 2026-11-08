#!/usr/bin/env python3
"""
Pull the XNU console log ("sweetlog" RAM ring) out of a warm-rebooted tablet.

The kernel copies every console byte into _sweet_log_ring (4 MiB) and counts
them in _sweet_log_total. After a reboot back into lk2nd, DRAM still holds
both, and lk2nd's `oem debug readq` reads physical memory 8 bytes at a time.

Usage: python tools/pull_log.py [kernel] [-o out.txt]
"""
import argparse, re, struct, subprocess, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import pyfastboot

PHYS_BASE = 0x90000000          # tools/mkadt.py
VIRT_ALIGN = 0x200000           # tools/mkpayload.py rounds __TEXT down to 2 MiB
RING_SIZE = 4 << 20


def kernel_symbols(kernel):
    """Look up the ring symbols and __TEXT base with llvm-nm/objdump in WSL."""
    wpath = subprocess.check_output(['wsl', 'wslpath', '-a', kernel.replace('\\', '/')]).decode().strip()
    nm = subprocess.check_output(['wsl', 'llvm-nm', wpath]).decode()
    syms = {}
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in ('_sweet_log_ring', '_sweet_log_total'):
            syms[parts[2]] = int(parts[0], 16)
    hdr = subprocess.check_output(['wsl', 'llvm-objdump', '--macho', '--private-headers', wpath]).decode()
    m = re.search(r'segname __TEXT\s+vmaddr (0x[0-9a-f]+)', hdr)
    virt_base = int(m.group(1), 16) & ~(VIRT_ALIGN - 1)
    return {k: v - virt_base + PHYS_BASE for k, v in syms.items()}


class Reader:
    def __init__(self):
        self.fb = pyfastboot.FastbootDevice()

    def readq(self, pa):
        self.fb.ep_out.write(f'oem debug readq {pa:#x}'.encode())
        val = None
        while True:
            r = bytes(self.fb.ep_in.read(512, 3000)).decode('latin1')
            if r.startswith('INFO'):
                val = int(r[4:].strip(), 16)
            elif r.startswith('OKAY'):
                return val
            elif r.startswith('FAIL'):
                raise RuntimeError(f'readq {pa:#x}: {r}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kernel', nargs='?', default='kernel.development.sweet')
    ap.add_argument('-o', '--out', default='console_log.txt')
    ap.add_argument('--max', type=int, default=256 << 10, help='max bytes to pull (newest kept)')
    args = ap.parse_args()

    pa = kernel_symbols(args.kernel)
    rd = Reader()
    total = rd.readq(pa['_sweet_log_total'])
    print(f'ring at {pa["_sweet_log_ring"]:#x}, {total} bytes logged')
    if total == 0 or total > (1 << 40):
        sys.exit('no log found (cold boot, or RAM was cleared)')

    # Newest bytes only; byte n of the stream lives at ring[n % RING_SIZE]
    start = max(0, total - min(args.max, RING_SIZE))
    data = bytearray()
    n = start & ~7
    while n < total:
        data += struct.pack('<Q', rd.readq(pa['_sweet_log_ring'] + n % RING_SIZE))
        n += 8
        if (n - start) % 8192 < 8:
            print(f'\r  {n - start}/{total - start} bytes', end='', flush=True)
    data = data[start - (start & ~7):][:total - start]
    print()

    with open(args.out, 'wb') as f:
        f.write(data)
    print(f'wrote {len(data)} bytes to {args.out}')


if __name__ == '__main__':
    main()
