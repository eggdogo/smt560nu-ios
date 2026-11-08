#!/usr/bin/env python3
"""List the GPT partitions of a raw disk image and the filesystem signature
at the start of each (HFS+ 'H+', HFSX 'HX', APFS container 'NXSB').

Usage: python3 tools/gptinfo.py <disk.img>
"""
import struct, sys

f = open(sys.argv[1], 'rb')
f.seek(512)
h = f.read(92)
assert h[:8] == b'EFI PART', 'no GPT'
entry_lba, = struct.unpack_from('<Q', h, 72)
nent, esz = struct.unpack_from('<II', h, 80)
f.seek(entry_lba * 512)
ents = [f.read(esz) for _ in range(nent)]
for i, e in enumerate(ents):
    if e[:16] == bytes(16):
        continue
    first, last = struct.unpack_from('<QQ', e, 32)
    name = e[56:128].decode('utf-16le').split('\0')[0]
    f.seek(first * 512)
    blk = f.read(2048)
    sig = blk[1024:1026].decode('latin1')
    print(f'{i + 1}: {name!r} sectors {first}-{last} ({(last - first + 1) * 512 >> 20} MiB) '
          f'HFS sig {sig!r} APFS sig {blk[32:36]!r}')
