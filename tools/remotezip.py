#!/usr/bin/env python3
"""
List or extract single members of a remote zip (e.g. an IPSW on Apple's CDN)
with HTTP range requests, without downloading the whole archive.

Usage: python tools/remotezip.py <url> list
       python tools/remotezip.py <url> get <member> <outfile>
"""
import struct, sys, urllib.request, zlib, os


def fetch(url, start, end):
    req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
    with urllib.request.urlopen(req) as r:
        return r.read()


def size_of(url):
    req = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(req) as r:
        return int(r.headers['Content-Length'])


def central_directory(url):
    total = size_of(url)
    tail = fetch(url, max(0, total - 65536 - 22), total - 1)
    i = tail.rfind(b'PK\x05\x06')
    cd_size, cd_off = struct.unpack_from('<II', tail, i + 12)
    # ZIP64: the end-of-central-directory locator sits just before
    if cd_off == 0xffffffff or cd_size == 0xffffffff:
        j = tail.rfind(b'PK\x06\x06')
        cd_size, cd_off = struct.unpack_from('<QQ', tail, j + 40)
    cd = fetch(url, cd_off, cd_off + cd_size - 1)
    entries, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b'PK\x01\x02':
        method, = struct.unpack_from('<H', cd, p + 10)
        csize, usize = struct.unpack_from('<II', cd, p + 20)
        nlen, xlen, clen = struct.unpack_from('<HHH', cd, p + 28)
        off, = struct.unpack_from('<I', cd, p + 42)
        name = cd[p + 46:p + 46 + nlen].decode()
        extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
        q = 0
        while q < len(extra):
            hid, hlen = struct.unpack_from('<HH', extra, q)
            if hid == 1:            # ZIP64 extended sizes/offset, in field order
                vals, k = [], q + 4
                while k < q + 4 + hlen:
                    vals.append(struct.unpack_from('<Q', extra, k)[0]); k += 8
                if usize == 0xffffffff: usize = vals.pop(0)
                if csize == 0xffffffff: csize = vals.pop(0)
                if off == 0xffffffff: off = vals.pop(0)
            q += 4 + hlen
        entries.append(dict(name=name, method=method, csize=csize, usize=usize, off=off))
        p += 46 + nlen + xlen + clen
    return entries


def extract(url, e, out):
    lh = fetch(url, e['off'], e['off'] + 29)
    nlen, xlen = struct.unpack_from('<HH', lh, 26)
    start = e['off'] + 30 + nlen + xlen
    dec = zlib.decompressobj(-15) if e['method'] == 8 else None
    chunk, done = 32 << 20, 0
    with open(out + '.part', 'wb') as f:
        while done < e['csize']:
            data = fetch(url, start + done, start + min(done + chunk, e['csize']) - 1)
            done += len(data)
            f.write(dec.decompress(data) if dec else data)
            print(f'\r  {done >> 20}/{e["csize"] >> 20} MiB', end='', flush=True)
        if dec:
            f.write(dec.flush())
    print()
    os.replace(out + '.part', out)


if __name__ == '__main__':
    url, cmd = sys.argv[1], sys.argv[2]
    ents = central_directory(url)
    if cmd == 'list':
        for e in sorted(ents, key=lambda e: -e['usize'])[:25]:
            print(f"{e['usize']:>12,}  m{e['method']}  {e['name']}")
    elif cmd == 'get':
        e = next(e for e in ents if e['name'] == sys.argv[3])
        extract(url, e, sys.argv[4])
