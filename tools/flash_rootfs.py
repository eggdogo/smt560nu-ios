#!/usr/bin/env python3
"""
Flash a raw filesystem image to an eMMC partition through lk2nd fastboot,
as a series of Android sparse images.

lk2nd accepts at most max-download-size (256 MiB) per transfer, so the raw
image is cut into pieces: each piece is a sparse image covering the whole
partition with DONT_CARE everywhere except its own RAW chunks, and all-zero
4 KiB blocks are skipped outright (an HFS image is mostly empty space).

A .zst image is decompressed on the fly (Python 3.14 compression.zstd), and
'-' reads the raw image from stdin.
Usage: python tools/flash_rootfs.py <image[.zst]|-> <partition> [--dry-run]
"""
import argparse, struct, sys, time, os
sys.path.insert(0, os.path.dirname(__file__))

BLK = 4096
SPARSE_MAGIC = 0xed26ff3a
CHUNK_RAW, CHUNK_DONT_CARE = 0xcac1, 0xcac3
PIECE_DATA = 200 << 20          # RAW payload per transfer, well under 256 MiB
ZERO = bytes(BLK)
# Never flash these: lk2nd, the bootloaders and firmware the tablet needs to boot
FORBIDDEN = {'aboot', 'sbl1', 'rpm', 'qsee', 'qhee', 'ddr', 'sec', 'modem', 'apnhlos',
             'efs', 'modemst1', 'modemst2', 'fsg', 'boot', 'lk2nd', 'param', 'persist'}


def sparse(total_blocks, runs):
    """runs: list of (start_block, bytes) in increasing order."""
    chunks, pos = [], 0
    for start, data in runs:
        if start > pos:
            chunks.append(struct.pack('<HHII', CHUNK_DONT_CARE, 0, start - pos, 12))
        n = len(data) // BLK
        chunks.append(struct.pack('<HHII', CHUNK_RAW, 0, n, 12 + len(data)) + data)
        pos = start + n
    if pos < total_blocks:
        chunks.append(struct.pack('<HHII', CHUNK_DONT_CARE, 0, total_blocks - pos, 12))
    hdr = struct.pack('<IHHHHIIII', SPARSE_MAGIC, 1, 0, 28, 12, BLK, total_blocks, len(chunks), 0)
    return hdr + b''.join(chunks)


def pieces(stream, total_blocks):
    """Yield (runs, payload bytes) per transfer.

    Only unallocated all-zero blocks are omitted (CHUNK_DONT_CARE). Allocated
    all-zero blocks in an HFS+ filesystem (e.g. dyld_shared_cache BSS pages)
    are written explicitly as zeros so stale eMMC data cannot corrupt them.
    """
    runs, size, blk = [], 0, 0
    cur_start, cur = None, bytearray()
    hfs_alloc_sz, hfs_alloc_ranges, alloc_bmap = 0, [], bytearray()
    while True:
        b = stream.read(BLK)
        if not b:
            break
        if len(b) < BLK:
            b = b + bytes(BLK - len(b))
        if blk >= total_blocks:
            raise SystemExit(f'image is larger than the partition ({total_blocks} blocks)')
        if blk == 0:
            sig = b[0x400:0x402]
            if sig in (b'H+', b'HX') and struct.unpack_from('>I', b, 0x428)[0] == BLK:
                hfs_alloc_sz = struct.unpack_from('>Q', b, 0x470)[0]
                for i in range(8):
                    sb, bc = struct.unpack_from('>II', b, 0x480 + i * 8)
                    if bc:
                        hfs_alloc_ranges.append((sb, sb + bc))
        elif hfs_alloc_ranges:
            for sb, eb in hfs_alloc_ranges:
                if sb <= blk < eb:
                    alloc_bmap += b
                    break
        if len(alloc_bmap) >= hfs_alloc_sz and hfs_alloc_sz > 0:
            byte_i = blk >> 3
            is_allocated = byte_i < hfs_alloc_sz and bool(alloc_bmap[byte_i] & (1 << (7 - (blk & 7))))
        else:
            is_allocated = True
        if b == ZERO and (not hfs_alloc_sz or not is_allocated):
            if cur:
                runs.append((cur_start, bytes(cur))); cur = bytearray()
        else:
            if not cur:
                cur_start = blk
            cur += b
            size += BLK
            if size >= PIECE_DATA:
                runs.append((cur_start, bytes(cur))); cur = bytearray()
                yield runs, size
                runs, size = [], 0
        blk += 1
    if cur:
        runs.append((cur_start, bytes(cur)))
    if runs:
        yield runs, size
    print(f'image: {blk} blocks ({blk * BLK >> 20} MiB)')


def flash_cmd(fb, part):
    fb.ep_out.write(f'flash:{part}'.encode())
    while True:
        r = bytes(fb.ep_in.read(512, 120000)).decode('latin1')
        if r.startswith('INFO'):
            print('   ', r[4:].strip())
        elif r.startswith('OKAY'):
            return
        else:
            raise RuntimeError(f'flash failed: {r}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('partition')
    ap.add_argument('--dry-run', action='store_true', help='build the pieces, send nothing')
    a = ap.parse_args()
    if a.partition in FORBIDDEN:
        raise SystemExit(f'refusing to flash {a.partition}: the tablet needs it to boot')

    fb = None
    if not a.dry_run:
        import pyfastboot
        fb = pyfastboot.FastbootDevice()
        size = int(fb.getvar(f'partition-size:{a.partition}').split()[-1], 16)
    else:
        size = 12175 << 20
    total_blocks = size // BLK
    print(f'{a.partition}: {size >> 20} MiB')

    if a.image == '-':
        stream = sys.stdin.buffer
    elif a.image.endswith('.zst'):
        from compression import zstd       # Python 3.14+
        stream = zstd.open(a.image, 'rb')
    else:
        stream = open(a.image, 'rb')
    t0, sent = time.time(), 0
    for n, (runs, data) in enumerate(pieces(stream, total_blocks)):
        img = sparse(total_blocks, runs)
        sent += data
        print(f'piece {n}: {len(runs)} runs, {data >> 20} MiB data, blocks {runs[0][0]}..'
              f'{runs[-1][0] + len(runs[-1][1]) // BLK}, {sent >> 20} MiB total, {time.time() - t0:.0f}s')
        if fb:
            fb.download(img)
            flash_cmd(fb, a.partition)
    print(f'done: {sent >> 20} MiB written in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
