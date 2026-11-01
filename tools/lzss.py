#!/usr/bin/env python3
"""Apple complzss decompressor in pure Python.

Unpacks Apple kernelcache 'complzss' payloads to raw 64-bit Mach-O.
"""
import struct, sys

N = 4096
F = 18
THRESHOLD = 2


def decompress_lzss(src, uncompressed_size):
    dst = bytearray(uncompressed_size)
    text_buf = bytearray(N + F - 1)
    text_buf[:N - F] = b' ' * (N - F)
    r = N - F
    src_pos = 0
    dst_pos = 0
    flags = 0

    while dst_pos < uncompressed_size and src_pos < len(src):
        flags >>= 1
        if (flags & 0x100) == 0:
            if src_pos >= len(src):
                break
            flags = src[src_pos] | 0xff00
            src_pos += 1

        if flags & 1:
            if src_pos >= len(src):
                break
            c = src[src_pos]
            src_pos += 1
            dst[dst_pos] = c
            dst_pos += 1
            text_buf[r] = c
            r = (r + 1) & (N - 1)
        else:
            if src_pos + 1 >= len(src):
                break
            i = src[src_pos]
            j = src[src_pos + 1]
            src_pos += 2
            i |= (j & 0xf0) << 4
            j = (j & 0x0f) + THRESHOLD
            for k in range(j + 1):
                c = text_buf[(i + k) & (N - 1)]
                if dst_pos < uncompressed_size:
                    dst[dst_pos] = c
                    dst_pos += 1
                text_buf[r] = c
                r = (r + 1) & (N - 1)

    return bytes(dst)


def unpack_kernelcache(in_path, out_path):
    data = open(in_path, 'rb').read()
    off = data.find(b'complzss')
    if off == -1:
        # Check if already raw Mach-O
        magic, = struct.unpack_from('<I', data, 0)
        if magic == 0xfeedfacf:
            print("File is already an uncompressed 64-bit Mach-O.")
            open(out_path, 'wb').write(data)
            return
        raise ValueError("Could not find 'complzss' magic in input file.")

    magic, csum, usize, csize = struct.unpack_from('>8sIII', data, off)
    print(f"Found 'complzss': uncompressed {usize} bytes ({usize / (1024**2):.2f} MB), compressed {csize} bytes")
    # Data starts after 0x180 (384 bytes) header from complzss offset
    compressed_data = data[off + 0x180:off + 0x180 + csize]
    decompressed = decompress_lzss(compressed_data, usize)
    assert len(decompressed) == usize, f"Decompressed size mismatch: got {len(decompressed)}, expected {usize}"

    # Verify Mach-O magic
    macho_magic, = struct.unpack_from('<I', decompressed, 0)
    assert macho_magic == 0xfeedfacf, f"Expected 64-bit Mach-O magic 0xfeedfacf, got 0x{macho_magic:x}"

    with open(out_path, 'wb') as f:
        f.write(decompressed)
    print(f"Successfully unpacked to {out_path} ({len(decompressed)} bytes)")


if __name__ == '__main__':
    inp = sys.argv[1] if len(sys.argv) > 1 else 'kernelcache.release.ipad4'
    outp = sys.argv[2] if len(sys.argv) > 2 else 'kernelcache.macho'
    unpack_kernelcache(inp, outp)
