#!/usr/bin/env python3
"""Recover the last XNU kernel log from RAM after a reset, via lk2nd's `oem debug readq`.

DRAM keeps its contents across the PM8916 warm reset, so the sweet log ring
(_sweet_log_total / _sweet_log_ring, linked at a fixed VA) is still there when
lk2nd comes up. Kernel VA base 0xfffffff007000000 maps to PA 0x90000000.

  python tools/ramlog.py -o ramlog.txt            # last 16 KiB of the log
  python tools/ramlog.py --bytes 65536 -o r.txt   # more
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyfastboot import FastbootDevice  # noqa: E402

VA_BASE, PA_BASE = 0xfffffff007000000, 0x90000000
TOTAL_VA, RING_VA, RING_SIZE = 0xfffffff007c3a810, 0xfffffff007c3a818, 0x400000


def pa(va):
    return va - VA_BASE + PA_BASE


def readq(fb, addr):
    fb.ep_out.write(f'oem debug readq {addr:#x}'.encode())
    val = None
    while True:
        r = bytes(fb.ep_in.read(512)).decode('utf-8', errors='ignore')
        if r.startswith('INFO'):
            val = int(r[4:].strip(), 16)
        elif r.startswith('OKAY') or r.startswith('FAIL'):
            if val is None and r[4:].strip().startswith('0x'):
                val = int(r[4:].strip(), 16)
            return val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default='ramlog.txt')
    ap.add_argument('--bytes', type=int, default=16384)
    a = ap.parse_args()
    fb = FastbootDevice()
    if 'lk2nd' not in fb.getvar('product'):
        sys.exit('need lk2nd')
    fb.drain()
    total = readq(fb, pa(TOTAL_VA))
    print(f'log total {total}')
    if not total:
        sys.exit('no log total (RAM cleared?)')
    n = min(a.bytes, total, RING_SIZE)
    start = total - n
    buf = bytearray()
    off = start & ~7
    while off < total:
        q = readq(fb, pa(RING_VA) + (off % RING_SIZE))
        buf += struct.pack('<Q', q or 0)
        off += 8
    data = bytes(buf[start - (start & ~7):][:n])
    with open(a.out, 'wb') as f:
        f.write(data)
    print(f'wrote {len(data)} bytes to {a.out}')


if __name__ == '__main__':
    main()
