import struct, sys

def inspect(path):
    print("Inspecting:", path)
    with open(path, "rb") as f:
        data = f.read(32)
        if len(data) < 32:
            print("File too short")
            return
        magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack("<IIIIIIII", data)
        print(f"Magic: {hex(magic)} (expected 0xfeedfacf for Mach-O 64)")
        print(f"CPUType: {hex(cputype)} Subtype: {hex(cpusubtype)}")
        print(f"FileType: {hex(filetype)} Ncmds: {ncmds} CmdsSize: {sizeofcmds}")
        
        for i in range(ncmds):
            cmd_hdr = f.read(8)
            if len(cmd_hdr) < 8:
                break
            cmd, cmdsize = struct.unpack("<II", cmd_hdr)
            payload = f.read(cmdsize - 8)
            if cmd == 0x19: # LC_SEGMENT_64
                segname, vmaddr, vmsize, fileoff, filesize, maxprot, initprot, nsects, sflags = struct.unpack("<16sQQQQiiii", payload[:64])
                name = segname.rstrip(b"\x00").decode("latin1", errors="replace")
                print(f"  Segment: {name:16s} vmaddr: {hex(vmaddr):18s} vmsize: {hex(vmsize):10s} fileoff: {hex(fileoff):10s} filesz: {hex(filesize):10s}")
            elif cmd == 0x5: # LC_UNIXTHREAD
                print(f"  Command: LC_UNIXTHREAD ({cmdsize} bytes)")
            elif cmd == 0x80000028: # LC_MAIN
                entryoff, stacksize = struct.unpack("<QQ", payload[:16])
                print(f"  Command: LC_MAIN entryoff: {hex(entryoff)}")

if __name__ == "__main__":
    inspect(sys.argv[1])
