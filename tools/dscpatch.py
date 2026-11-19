#!/usr/bin/env python3
"""Patch instructions of the iOS dyld shared cache on the tablet's userdata via lk2nd (run with the tablet in fastboot).
usage: dscpatch.py <va-hex> <expect-hex-bytes> <new-hex-bytes>   (e.g. 0x183810bf4 40000036 1f2003d5)
Finds the file offset with build/ios16h81/dsc.py's mapping, locates the bytes inside ipsw/gtelroot.img.zst (must be unique, 64-byte context),
then flashes one block with tools/flash_block.py."""
import sys, io, contextlib, subprocess, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
va = int(sys.argv[1], 16); old = bytes.fromhex(sys.argv[2]); new = bytes.fromhex(sys.argv[3])
sys.path.insert(0, os.path.join(root, 'build', 'ios16h81'))
sys.argv = ['dsc.py', 'images', '^$']
g = {'__name__': 'x', '__file__': os.path.join(root, 'build', 'ios16h81', 'dsc.py')}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(g['__file__']).read(), 'dsc.py', 'exec'), g)
d = g['d']; o = g['v2o'](va)
assert bytes(d[o:o+len(old)]) == old, ('local cache bytes differ', bytes(d[o:o+len(old)]).hex())
ctx0 = o - 32; pat = bytes(d[ctx0:ctx0+64])
from compression import zstd
f = zstd.open(os.path.join(root, 'ipsw', 'gtelroot.img.zst'), 'rb'); pos = 0; tail = b''; hits = []
while True:
    c = f.read(64 << 20)
    if not c: break
    buf = tail + c; i = buf.find(pat)
    while i >= 0:
        hits.append(pos - len(tail) + i); i = buf.find(pat, i + 1)
    tail = buf[-63:]; pos += len(c)
assert len(hits) == 1, hits
img_off = hits[0] + 32
blk, at = img_off >> 12, img_off & 4095
assert at + len(old) <= 4096
tmp = os.environ.get('TEMP', '.')
open(tmp + '/dp_old.bin', 'wb').write(old); open(tmp + '/dp_new.bin', 'wb').write(new)
print('block', blk, 'at', at)
subprocess.check_call([sys.executable, os.path.join(root, 'tools', 'flash_block.py'), os.path.join(root, 'ipsw', 'gtelroot.img.zst'), 'userdata', str(blk),
                       '--expect-file', tmp + '/dp_old.bin', '--new-file', tmp + '/dp_new.bin', '--at', str(at)])
