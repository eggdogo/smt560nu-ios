#!/usr/bin/env python3
"""Pure-Python Fastboot client over LibUSB.

Works seamlessly on Windows without requiring device interface GUID registry hacking.
"""
import argparse, os, sys, time
import usb.core, usb.util, libusb_package

FASTBOOT_VID = 0x18d1
FASTBOOT_PID = 0xd00d


class FastbootDevice:
    def __init__(self, vid=FASTBOOT_VID, pid=FASTBOOT_PID):
        self.backend = libusb_package.get_libusb1_backend()
        self.dev = usb.core.find(idVendor=vid, idProduct=pid, backend=self.backend)
        if not self.dev:
            raise RuntimeError(f"Fastboot device 0x{vid:04x}:0x{pid:04x} not found.")

        try:
            self.dev.set_configuration()
        except Exception:
            pass

        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self.ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        self.ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )

        if not self.ep_out or not self.ep_in:
            raise RuntimeError("Could not find fastboot bulk endpoints.")

    def raw_cmd(self, cmd):
        self.ep_out.write(cmd.encode() if isinstance(cmd, str) else cmd)
        resp = bytes(self.ep_in.read(512)).decode('utf-8', errors='ignore')
        return resp

    def getvar(self, var):
        self.ep_out.write(f"getvar:{var}".encode())
        res = []
        while True:
            try:
                resp = bytes(self.ep_in.read(512)).decode('utf-8', errors='ignore')
                if resp.startswith("INFO"):
                    res.append(resp[4:].strip())
                elif resp.startswith("OKAY"):
                    if resp[4:].strip():
                        res.append(resp[4:].strip())
                    break
                elif resp.startswith("FAIL"):
                    res.append(resp)
                    break
                else:
                    res.append(resp)
            except Exception:
                break
        return "\n".join(res)

    def oem(self, cmd):
        self.ep_out.write(f"oem {cmd}".encode())
        res = []
        while True:
            try:
                resp = bytes(self.ep_in.read(512)).decode('utf-8', errors='ignore')
                if resp.startswith("INFO"):
                    print(resp[4:].strip())
                    res.append(resp[4:].strip())
                elif resp.startswith("OKAY"):
                    print(f"OKAY {resp[4:].strip()}")
                    break
                elif resp.startswith("FAIL"):
                    print(f"FAIL {resp[4:].strip()}")
                    break
            except Exception:
                break
        return "\n".join(res)

    def upload(self, timeout=5000):
        self.ep_out.write(b"upload")
        resp = bytes(self.ep_in.read(512, timeout=timeout)).decode('utf-8', errors='ignore')
        if not resp.startswith("DATA"):
            raise RuntimeError(f"Upload command failed: {resp}")
        size = int(resp[4:12], 16)
        data = bytearray()
        while len(data) < size:
            chunk = self.ep_in.read(min(size - len(data), 65536), timeout=timeout)
            data.extend(chunk)
        resp2 = bytes(self.ep_in.read(512, timeout=timeout)).decode('utf-8', errors='ignore')
        if not resp2.startswith("OKAY"):
            raise RuntimeError(f"Upload trailing status failed: {resp2}")
        return bytes(data)

    def dmesg(self):
        return self.upload()

    def poweroff(self):
        try:
            self.ep_out.write(b"poweroff")
            while True:
                resp = bytes(self.ep_in.read(512, timeout=5000)).decode('utf-8', errors='ignore')
                if resp.startswith("INFO"):
                    print(resp[4:].strip())
                elif resp.startswith("OKAY"):
                    msg = resp[4:].strip()
                    print(f"OKAY {msg}" if msg else "OKAY")
                    return True
                elif resp.startswith("FAIL"):
                    print(f"FAIL {resp[4:].strip()}")
                    return False
                else:
                    print(resp.strip())
                    return False
        except Exception as e:
            print(f"Device powered off (fastboot disconnected: {e})")
            return True

    def reboot(self, target=None):
        cmd = "reboot" if not target else (target if target.startswith("reboot") else f"reboot-{target}")
        try:
            self.ep_out.write(cmd.encode())
            while True:
                resp = bytes(self.ep_in.read(512, timeout=5000)).decode('utf-8', errors='ignore')
                if resp.startswith("INFO"):
                    print(resp[4:].strip())
                elif resp.startswith("OKAY"):
                    msg = resp[4:].strip()
                    print(f"OKAY {msg}" if msg else "OKAY")
                    return True
                elif resp.startswith("FAIL"):
                    print(f"FAIL {resp[4:].strip()}")
                    return False
                else:
                    print(resp.strip())
                    return False
        except Exception as e:
            print(f"Device rebooted (fastboot disconnected: {e})")
            return True

    def download(self, data):
        size = len(data)
        cmd = f"download:{size:08x}"
        resp = self.raw_cmd(cmd)
        if not resp.startswith("DATA"):
            raise RuntimeError(f"Download command failed: {resp}")

        # Stream payload in chunks
        chunk_size = 65536
        for offset in range(0, size, chunk_size):
            chunk = data[offset:offset + chunk_size]
            self.ep_out.write(chunk)

        resp = bytes(self.ep_in.read(512)).decode('utf-8', errors='ignore')
        if not resp.startswith("OKAY"):
            raise RuntimeError(f"Data upload failed: {resp}")
        return True

    def boot(self, bootimg_path):
        data = open(bootimg_path, 'rb').read()
        print(f"Downloading {len(data)} bytes to device...")
        self.download(data)
        print("Booting downloaded image...")
        try:
            resp = self.raw_cmd("boot")
            print(f"Device response: {resp.strip()}")
            return resp.startswith("OKAY")
        except Exception as e:
            print(f"Device booted (fastboot disconnected: {e})")
            return True


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='command', required=True)

    sub.add_parser('devices')
    boot_cmd = sub.add_parser('boot')
    boot_cmd.add_argument('image', help='Path to boot.img')

    getvar_cmd = sub.add_parser('getvar')
    getvar_cmd.add_argument('var', default='all', nargs='?')

    oem_cmd = sub.add_parser('oem')
    oem_cmd.add_argument('cmd', nargs='+')

    upload_cmd = sub.add_parser('upload')
    upload_cmd.add_argument('outfile', nargs='?', default='staged.bin')

    dmesg_cmd = sub.add_parser('dmesg')
    dmesg_cmd.add_argument('outfile', nargs='?', help='Optional output file path')
    dmesg_cmd.add_argument('-o', '--out', dest='out_flag', help='Write log bytes to file')

    sub.add_parser('poweroff')
    reboot_cmd = sub.add_parser('reboot')
    reboot_cmd.add_argument('target', nargs='?', help='Optional reboot target (e.g. bootloader)')
    sub.add_parser('reboot-bootloader')

    args = p.parse_args()

    try:
        fb = FastbootDevice()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.command == 'devices':
        prod = fb.getvar('product')
        ver = fb.getvar('version')
        print(f"{fb.dev.serial_number}\tfastboot\t(Product: {prod}, Version: {ver})")

    elif args.command == 'getvar':
        val = fb.getvar(args.var)
        print(f"{args.var}:\n{val}")

    elif args.command == 'oem':
        fb.oem(' '.join(args.cmd))

    elif args.command == 'upload':
        data = fb.upload()
        with open(args.outfile, 'wb') as f:
            f.write(data)
        print(f"Fetched {len(data)} bytes to {args.outfile}")

    elif args.command == 'dmesg':
        data = fb.dmesg()
        out = args.out_flag or args.outfile
        if out:
            with open(out, 'wb') as f:
                f.write(data)
            print(f"Wrote {len(data)} bytes to {out}")
        else:
            sys.stdout.write(data.decode('utf-8', errors='replace'))

    elif args.command == 'poweroff':
        if not fb.poweroff():
            sys.exit(1)

    elif args.command == 'reboot':
        if not fb.reboot(args.target):
            sys.exit(1)

    elif args.command == 'reboot-bootloader':
        if not fb.reboot('bootloader'):
            sys.exit(1)

    elif args.command == 'boot':
        ok = fb.boot(args.image)
        if ok:
            print("Successfully sent boot command!")
        else:
            print("Boot command failed.")


if __name__ == '__main__':
    main()
