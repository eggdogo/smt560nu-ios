#!/usr/bin/env python3
"""
Patch bytes inside one 4 KiB block of an eMMC partition through lk2nd:
sends a sparse image that is DONT_CARE everywhere except that block.
The block's current content is taken from the image that was flashed
(raw or .zst), checked against --expect, then patched at --at.
Usage: python tools/flash_block.py <image[.zst]> <partition> <block>
           --expect-file old.bin --new-file new.bin [--at 0] [--dry-run]
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from flash_rootfs import BLK, FORBIDDEN, sparse, flash_cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('partition')
    ap.add_argument('block', type=int)
    ap.add_argument('--expect-file', required=True)
    ap.add_argument('--new-file', required=True)
    ap.add_argument('--at', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if a.partition in FORBIDDEN:
        raise SystemExit(f'refusing to flash {a.partition}')

    old = open(a.expect_file, 'rb').read()
    new = open(a.new_file, 'rb').read()
    if len(old) != len(new) or a.at + len(new) > BLK:
        raise SystemExit('new content must be the same length as the old and fit the block')

    if a.image.endswith('.zst'):
        from compression import zstd
        f = zstd.open(a.image, 'rb')
    else:
        f = open(a.image, 'rb')
    skip = a.block * BLK
    while skip:
        n = len(f.read(min(skip, 64 << 20)))
        if not n:
            raise SystemExit('image too short')
        skip -= n
    blk = bytearray(f.read(BLK))
    if bytes(blk[a.at:a.at + len(old)]) != old:
        raise SystemExit(f'block {a.block} does not hold the expected bytes: {bytes(blk[a.at:a.at + len(old)])!r}')
    blk[a.at:a.at + len(new)] = new
    print(f'block {a.block}: expected content found, patching {len(new)} bytes')

    if a.dry_run:
        return
    import pyfastboot
    fb = pyfastboot.FastbootDevice()
    size = int(fb.getvar(f'partition-size:{a.partition}').split()[-1], 16)
    img = sparse(size // BLK, [(a.block, bytes(blk))])
    fb.download(img)
    flash_cmd(fb, a.partition)
    print('flashed')


if __name__ == '__main__':
    main()
