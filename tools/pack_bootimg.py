#!/usr/bin/env python3
"""Pack kernel + ramdisk into Android boot.img v0/v1/v2 format."""
import argparse, os, struct, sys

BOOT_MAGIC = b'ANDROID!'
BOOT_MAGIC_SIZE = 8
PAGE_SIZE = 2048

def pad(buf, page_size):
    p = (len(buf) + page_size - 1) & ~(page_size - 1)
    return buf + b'\0' * (p - len(buf))

def pack_bootimg(kernel_path, ramdisk_path, out_path, cmdline="console=null", base=0x80000000,
                 kernel_offset=0x00008000, ramdisk_offset=0x02000000, tags_offset=0x00000100, dtb_path=None):
    k_data = open(kernel_path, 'rb').read() if kernel_path else b''
    r_data = open(ramdisk_path, 'rb').read() if ramdisk_path else b''
    d_data = open(dtb_path, 'rb').read() if dtb_path else b''

    kernel_size = len(k_data)
    ramdisk_size = len(r_data)
    second_size = 0
    dt_size = len(d_data)

    kernel_addr = base + kernel_offset
    ramdisk_addr = base + ramdisk_offset
    second_addr = 0
    tags_addr = base + tags_offset

    header = bytearray(PAGE_SIZE)
    struct.pack_into('<8s8II', header, 0,
                     BOOT_MAGIC,
                     kernel_size,
                     kernel_addr,
                     ramdisk_size,
                     ramdisk_addr,
                     second_size,
                     second_addr,
                     tags_addr,
                     PAGE_SIZE,
                     dt_size)

    # Cmdline
    cl = cmdline.encode()[:511]
    header[64:64 + len(cl)] = cl

    with open(out_path, 'wb') as f:
        f.write(header)
        if kernel_size > 0:
            f.write(pad(k_data, PAGE_SIZE))
        if ramdisk_size > 0:
            f.write(pad(r_data, PAGE_SIZE))
        if dt_size > 0:
            f.write(pad(d_data, PAGE_SIZE))

    print(f"Packed {out_path}: Kernel {kernel_size} bytes @ 0x{kernel_addr:08x}, Ramdisk {ramdisk_size} bytes, DTB {dt_size} bytes")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--kernel', required=True)
    p.add_argument('--ramdisk')
    p.add_argument('--dtb')
    p.add_argument('--out', required=True)
    p.add_argument('--cmdline', default='console=null')
    p.add_argument('--base', type=lambda x: int(x, 0), default=0x80000000)
    p.add_argument('--ramdisk-offset', type=lambda x: int(x, 0), default=0x02000000)
    args = p.parse_args()
    pack_bootimg(args.kernel, args.ramdisk, args.out, cmdline=args.cmdline, base=args.base,
                 ramdisk_offset=args.ramdisk_offset, dtb_path=args.dtb)
