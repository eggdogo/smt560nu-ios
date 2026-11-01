#!/usr/bin/env python3
"""HTTP Range-based remote ZIP inspector and extractor.

Allows inspecting and downloading individual files (like kernelcache or ramdisks)
from large Apple IPSWs without downloading the full multi-gigabyte archive.
"""
import io, os, struct, sys, urllib.request, zipfile


class RemoteZipFile:
    def __init__(self, url):
        self.url = url
        # Query total size via HEAD or range
        req = urllib.request.Request(url, headers={'Range': 'bytes=0-0'})
        with urllib.request.urlopen(req) as resp:
            cr = resp.headers.get('Content-Range', '')
            if '/' in cr:
                self.size = int(cr.split('/')[-1])
            else:
                self.size = int(resp.headers.get('Content-Length', 0))

    def read_range(self, start, length):
        end = start + length - 1
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={start}-{end}'})
        with urllib.request.urlopen(req) as resp:
            return resp.read()

    def get_zip_file(self):
        # Read the last 64KB to find the End of Central Directory (EOCD)
        tail_size = min(65536, self.size)
        tail_data = self.read_range(self.size - tail_size, tail_size)

        # Locate EOCD signature: 0x06054b50
        eocd_pos = tail_data.rfind(b'\x50\x4b\x05\x06')
        if eocd_pos == -1:
            raise RuntimeError("Could not find EOCD in remote file.")

        eocd = tail_data[eocd_pos:]
        num_entries, cd_size, cd_offset = struct.unpack_from('<HII', eocd, 10)

        # Download the Central Directory
        cd_data = self.read_range(cd_offset, cd_size)

        # Create a virtual file with empty space, CD, and EOCD for zipfile.ZipFile
        class SeekableRemote(io.RawIOBase):
            def __init__(self, rz, cd_off, cd_bytes, eocd_bytes):
                self.rz = rz
                self.cd_off = cd_off
                self.cd_bytes = cd_bytes
                self.eocd_bytes = eocd_bytes
                self.pos = 0

            def seek(self, offset, whence=io.SEEK_SET):
                if whence == io.SEEK_SET:
                    self.pos = offset
                elif whence == io.SEEK_CUR:
                    self.pos += offset
                elif whence == io.SEEK_END:
                    self.pos = self.rz.size + offset
                return self.pos

            def tell(self):
                return self.pos

            def read(self, size=-1):
                if size == -1:
                    size = self.rz.size - self.pos
                if size <= 0 or self.pos >= self.rz.size:
                    return b''

                # If within Central Directory
                if self.pos >= self.cd_off and self.pos < self.cd_off + len(self.cd_bytes):
                    rel = self.pos - self.cd_off
                    avail = self.cd_bytes[rel:rel + size]
                    self.pos += len(avail)
                    return avail

                # Fetch via HTTP
                chunk = self.rz.read_range(self.pos, size)
                self.pos += len(chunk)
                return chunk

        stream = SeekableRemote(self, cd_offset, cd_data, eocd)
        return zipfile.ZipFile(stream)


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith('http') else "https://updates.cdn-apple.com/2023FCSWinter/fullrestores/032-14132/A3C10B93-0E34-405D-8A92-92AA354BABF0/iPad_64bit_12.5.7_16H81_Restore.ipsw"
    extract_target = None
    for arg in sys.argv[1:]:
        if not arg.startswith('http') and not arg.startswith('--'):
            extract_target = arg

    rz = RemoteZipFile(url)
    print(f"Remote archive size: {rz.size / (1024**3):.2f} GB")
    zf = rz.get_zip_file()

    if extract_target:
        print(f"Extracting '{extract_target}'...")
        data = zf.read(extract_target)
        out_name = os.path.basename(extract_target)
        with open(out_name, 'wb') as f:
            f.write(data)
        print(f"Successfully extracted {len(data)} bytes to {out_name}")
    else:
        for info in zf.infolist():
            print(f"  {info.file_size / (1024**2):8.2f} MB  {info.filename}")
