#!/usr/bin/env python3
"""Patch backboardd's -[BKBootUIPresenter _queue_addOverlay] and _queue_addUnderlay to `ret` (never show the boot logo overlay).
backboardd is decmpfs type 4 (zlib, 64 KiB chunks) in a resource fork at userdata block 1019012;
recompress chunk 6 with the patch (level 9 fits in the old slot) and flash the touched blocks.
  python tools/bbd_overlay_patch.py [--dry-run]     (tablet in lk2nd)
"""
import os, struct, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flash_block import sparse, flash_cmd, BLK
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RSRC_BLK, IMG = 1019012, os.path.join(ROOT, 'ipsw/gtelroot.img.zst')
r = bytearray(open(os.path.join(ROOT, 'build/ios16h81/bbd.rsrc'), 'rb').read())
base = 0x104
o, l = struct.unpack_from('<II', r, base + 4 + 8 * 6)
u = bytearray(zlib.decompress(bytes(r[base + o:base + o + l])))
for off, old, new in ((0xbf34, 'ff8301d1', os.environ.get('ADDOV', 'c0035fd6')),  # -[BKBootUIPresenter _queue_addOverlay] -> ret (ADDOV=200020d4: brk test)
                      (0xc12c, 'ff8301d1', 'c0035fd6'),            # -[BKBootUIPresenter _queue_addUnderlay] -> ret
                      (0x3b00, None, '000080d2c0035fd6')):          # -[BKBootUIOverlayVendor currentOverlayWithLevel:] -> nil
    n = len(new) // 2
    if old: assert u[off:off + 4] == bytes.fromhex(old), u[off:off + 4].hex()
    u[off:off + n] = bytes.fromhex(new)
z = zlib.compress(bytes(u), 9)
assert len(z) <= l
new = bytearray(r); new[base + o:base + o + l] = z + b'\0' * (l - len(z))
b0, b1 = (base + o) // BLK, (base + o + l - 1) // BLK
from compression import zstd
f = zstd.open(IMG, 'rb'); skip = (RSRC_BLK + b0) * BLK
while skip: skip -= len(f.read(min(skip, 64 << 20)))
disk = f.read((b1 - b0 + 1) * BLK)
assert disk == bytes(r[b0 * BLK:(b1 + 1) * BLK]), 'image does not match bbd.rsrc'
blocks = [(RSRC_BLK + b, bytes(new[b * BLK:(b + 1) * BLK])) for b in range(b0, b1 + 1)]
print(f'chunk 6: {l} -> {len(z)} bytes, blocks {RSRC_BLK + b0}..{RSRC_BLK + b1}')
if '--dry-run' in sys.argv: sys.exit()
import pyfastboot
fb = pyfastboot.FastbootDevice()
size = int(fb.getvar('partition-size:userdata').split()[-1], 16)
fb.download(sparse(size // BLK, blocks)); flash_cmd(fb, 'userdata'); print('flashed')
