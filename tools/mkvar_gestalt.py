import plistlib,struct,sys
src='kernel.development.sweet.pre_variant'
k=bytearray(open(src,'rb').read())
o=0x1fc60;OLD=4844
p=plistlib.loads(bytes(k[o:o+OLD]))
keep=set(sys.argv[2:])   # nested keys to keep
names={'L':'9MZ5AdH43csAUajl/dU+IQ','A':'oBbtJ8x+s1q0OkaiocPuog','B':'oPeik/9e8lQWMszEjbPzng'}
for n,key in names.items():
    if n not in keep: del p['CacheExtra'][key]
b=plistlib.dumps(p,fmt=plistlib.FMT_BINARY)
assert len(b)<=OLD,len(b)
# locate size immediates
hits=[]
for i in range(0,len(k)-3,4):
    w=struct.unpack('<I',k[i:i+4])[0]
    if (w&0xFF800000)==0x52800000 and ((w>>5)&0xFFFF)==OLD: hits.append(i)
print('movz hits',[hex(h) for h in hits],'newlen',len(b))
for h in hits:
    w=struct.unpack('<I',k[h:h+4])[0]
    k[h:h+4]=struct.pack('<I',(w&~(0xFFFF<<5))|(len(b)<<5))
k[o:o+OLD]=b+b'\0'*(OLD-len(b))
open(sys.argv[1],'wb').write(k)
