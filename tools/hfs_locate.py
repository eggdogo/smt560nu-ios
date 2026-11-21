#!/usr/bin/env python3
"""
Find where a file's data lives inside an HFS+/HFSX image, streaming the
image (raw or .zst) once: read the volume header, collect the catalog file,
walk its leaf records to the path, print the data fork's extents as byte
offsets into the partition.
Usage: python tools/hfs_locate.py <image[.zst]> /private/etc/fstab
"""
import os
import struct, sys

CHUNK = 64 << 20


def open_stream(path):
    if path.endswith('.zst'):
        from compression import zstd
        return zstd.open(path, 'rb')
    return open(path, 'rb')


def fork_extents(fd):
    """HFSPlusForkData (80 bytes) -> logical size, [(start, count)]"""
    size = struct.unpack('>Q', fd[0:8])[0]
    ext = [struct.unpack('>II', fd[16 + 8 * i:24 + 8 * i]) for i in range(8)]
    return size, [(s, c) for s, c in ext if c]


def main():
    img, path = sys.argv[1], sys.argv[2]
    parts = [p for p in path.split('/') if p]
    f = open_stream(img)
    head = f.read(CHUNK)
    vh = head[1024:1536]
    assert vh[0:2] in (b'H+', b'HX'), vh[0:2]
    bs = struct.unpack('>I', vh[0x28:0x2c])[0]
    csize, cext = fork_extents(vh[0x110:0x160])
    print(f'block size {bs}, catalog {csize} bytes in {cext}')

    # collect catalog bytes while streaming
    want = sorted((s * bs, c * bs, i) for i, (s, c) in enumerate(cext))
    pieces = {}
    pos, buf = 0, head
    while want and buf:
        end = pos + len(buf)
        for off, ln, i in list(want):
            if off < end and off + ln > pos:
                a, b = max(off, pos), min(off + ln, end)
                pieces.setdefault(i, bytearray(ln))[a - off:b - off] = buf[a - pos:b - pos]
            if off + ln <= end:
                want.remove((off, ln, i))
        pos = end
        buf = f.read(CHUNK) if want else b''
    cat = b''.join(bytes(pieces[i]) for i in range(len(cext)))[:csize]

    nodesize = struct.unpack('>H', cat[32:34])[0]
    parent = 2          # root folder CNID
    target = None
    for depth, name in enumerate(parts):
        last = depth == len(parts) - 1
        found = None
        for n in range(len(cat) // nodesize):
            node = cat[n * nodesize:(n + 1) * nodesize]
            if node[8] != 0xff:         # kind -1 = leaf
                continue
            nrec = struct.unpack('>H', node[10:12])[0]
            offs = [struct.unpack('>H', node[nodesize - 2 * (r + 1):nodesize - 2 * r])[0] for r in range(nrec)]
            for o in offs:
                klen, pid, nlen = struct.unpack('>HIH', node[o:o + 8])
                if pid != parent:
                    continue
                nm = node[o + 8:o + 8 + 2 * nlen].decode('utf-16-be')
                if nm != name:
                    continue
                rec = node[o + 2 + klen:]
                rtype = struct.unpack('>h', rec[0:2])[0]
                found = (rtype, rec)
                break
            if found:
                break
        if not found:
            sys.exit(f'{name} not found under CNID {parent}')
        rtype, rec = found
        cnid = struct.unpack('>I', rec[8:12])[0]
        if rtype == 1:          # folder
            parent = cnid
            print(f'{name}: folder {cnid}')
        elif rtype == 2:        # file
            size, ext = fork_extents(rec[88:168])
            rsz, rext = fork_extents(rec[168:248])
            if rsz: print(f"  rsrc {rsz} bytes: " + " ".join(f"block {s} x{c}" for s, c in rext))
            flags = struct.unpack('>H', rec[2:4])[0]
            print(f'{name}: file {cnid}, flags 0x{flags:x}, data {size} bytes')
            for s, c in ext:
                print(f'  extent: block {s} x{c} -> byte offset {s * bs} (0x{s * bs:x})')
            target = ext
        else:
            sys.exit(f'{name}: record type {rtype}')
        if not last and rtype != 1:
            sys.exit(f'{name} is not a folder')
    if os.environ.get('LIST') and target is None:   # LIST=1: list the final folder's entries
        for n in range(len(cat) // nodesize):
            node = cat[n * nodesize:(n + 1) * nodesize]
            if node[8] != 0xff:
                continue
            nrec = struct.unpack('>H', node[10:12])[0]
            for r in range(nrec):
                o = struct.unpack('>H', node[nodesize - 2 * (r + 1):nodesize - 2 * r])[0]
                klen, pid, nlen = struct.unpack('>HIH', node[o:o + 8])
                if pid == parent and nlen:
                    print('  ', node[o + 8:o + 8 + 2 * nlen].decode('utf-16-be', 'replace'))
    return target


if __name__ == '__main__':
    main()
