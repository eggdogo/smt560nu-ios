#!/usr/bin/env python3
"""Downsampled screenshot of the panel framebuffer from RAM, via lk2nd `oem debug readq`.

The XNU framebuffer (AppleCLCD, 800x1280, 24 bpp, stride 2400) lives at PA 0x8e000000 and
survives the reboot into lk2nd. Reads one 8-byte word per sampled pixel (~2 ms each).

  python tools/ramshot.py -o shot.png --step 8     # 100x160 image, ~1 min
"""
import argparse
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyfastboot import FastbootDevice  # noqa: E402
from ramlog import readq  # noqa: E402

FB, W, H, STRIDE, BPP = 0x8e000000, 800, 1280, 2400, 3


def png(path, w, h, rows):
    raw = b''.join(b'\0' + bytes(r) for r in rows)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default='ramshot.png')
    ap.add_argument('--step', type=int, default=8)
    a = ap.parse_args()
    fb = FastbootDevice()
    if 'lk2nd' not in fb.getvar('product'):
        sys.exit('need lk2nd')
    fb.drain()
    rows = []
    for y in range(0, H, a.step):
        row = bytearray()
        for x in range(0, W, a.step):
            off = y * STRIDE + x * BPP
            base = off & ~7
            q = struct.pack('<Q', readq(fb, FB + base) or 0) + struct.pack('<Q', readq(fb, FB + base + 8) or 0) \
                if (off - base) > 5 else struct.pack('<Q', readq(fb, FB + base) or 0)
            b, g, r = q[off - base:off - base + 3]
            row += bytes((r, g, b))
        rows.append(row)
    png(a.out, W // a.step, len(rows), rows)
    print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
