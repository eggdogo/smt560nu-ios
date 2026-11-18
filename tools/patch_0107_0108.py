#!/usr/bin/env python3
"""Binary-patch 0107 (gtel USB fastboot + poweroff) and 0108 (iOS 12 0x278 SwapEnd)
directly into kernel.development.sweet so it can boot locally without waiting on CI.
"""
import os
import shutil
import struct
import subprocess
import sys

PROJ = r'C:\Users\Avett\Documents\Projects\iosont560nu'
PATCH_0107 = r'C:\Users\Avett\Documents\GitHub\smt560nu-ios\xnu\patches\0107-gtel-usb-fastboot.patch'
KERN = os.path.join(PROJ, 'kernel.development.sweet')
BAK = KERN + '.pre_0107_0108'
SCRATCH = r'C:\Users\Avett\.gemini\antigravity\brain\930aafe1-be5f-48c3-8932-b0d0a6bd3c94\scratch'

# Unused sweet_usb slot inside __TEXT_EXEC and _ud slot inside __DATA.__bss
CODE_BASE = 0xFFFFFFF0074936B0
CODE_MAX = 0x1D60  # 7520 bytes: 0xfffffff0074936b0 .. 0xfffffff007495410
BSS_BASE = 0xFFFFFFF00803AE38
BSS_MAX = 0x368    # 872 bytes:  0xfffffff00803ae38 .. 0xfffffff00803b1a0

TEXT_EXEC_VA = 0xFFFFFFF007260000
TEXT_EXEC_FOFF = 0x25C000

EXT_SYMS = {
    '_CleanPoC_DcacheRegion':     0xFFFFFFF007418C04,
    '_FlushPoC_Dcache':           0xFFFFFFF007418C10,
    '_FlushPoC_DcacheRegion':     0xFFFFFFF007418E64,
    '_PE_parse_boot_argn':        0xFFFFFFF007A57C40,
    '_SecureDTLookupEntry':       0xFFFFFFF007A56DF0,
    '_assert_wait_deadline':      0xFFFFFFF0072DA730,
    '_clock_interval_to_deadline': 0xFFFFFFF0072A0550,
    '_delay':                     0xFFFFFFF0072A0540,
    '_halt_all_cpus':             0xFFFFFFF00742D840,
    '_kernel_map':                0xFFFFFFF007177280,
    '_kernel_pmap':               0xFFFFFFF007178900,
    '_page_shift_var':            0xFFFFFFF007179118,
    '_kernel_thread_start':       0xFFFFFFF007301650,
    '_kmem_alloc_contig_guard':   0xFFFFFFF007374100,
    '_memcpy':                    0xFFFFFFF007B1F350,
    '_memset':                    0xFFFFFFF007B1F580,
    '_ml_io_map':                 0xFFFFFFF00742E610,
    '_pmap_find_phys':            0xFFFFFFF007409B80,
    '_printf':                    0xFFFFFFF0072CD260,
    '_snprintf':                  0xFFFFFFF0077EF960,
    '_strcmp':                    0xFFFFFFF0073E6430,
    '_strlen':                    0xFFFFFFF0074308C0,
    '_strncmp':                   0xFFFFFFF007430950,
    '_sweet_log_copy':            0xFFFFFFF00748A9F0,
    '_sweet_log_position':        0xFFFFFFF00748AB30,
    '_thread_block':              0xFFFFFFF0072DAEB0,
    '_thread_deallocate':         0xFFFFFFF0072FF8C0,
}

DARWIN_HDR = r'''
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef long long int64_t;
typedef int int32_t;
typedef unsigned long uintptr_t;
typedef unsigned long size_t;
typedef unsigned long vm_offset_t;
typedef unsigned long vm_size_t;
typedef uint64_t addr64_t;
typedef uint32_t ppnum_t;
typedef int kern_return_t;
typedef int boolean_t;
typedef void *pmap_t;
typedef void *thread_t;
typedef void *vm_map_t;
typedef void *event_t;
typedef void *DTEntry;
typedef int wait_result_t;
typedef void (*thread_continue_t)(void *, wait_result_t);
#define __unused __attribute__((unused))
#define bool _Bool
#define true 1
#define false 0
#define TRUE 1
#define FALSE 0
#define NULL ((void *)0)
#define KERN_SUCCESS 0
#define kSuccess 0

extern int page_shift_var;
#define PAGE_SHIFT ((unsigned)page_shift_var)
#define PAGE_SIZE (1ULL << PAGE_SHIFT)
#define PAGE_MASK (PAGE_SIZE - 1ULL)
#define ptoa_64(x) ((uint64_t)(x) << PAGE_SHIFT)

#define KMA_DATA             0x00100000u
#define KMA_PERMANENT        0x00008000u
#define KMA_ZERO             0x00000040u
#define VM_KERN_MEMORY_IOKIT 3u
#define THREAD_UNINT 0
#define THREAD_CONTINUE_NULL ((thread_continue_t)0)
#define NSEC_PER_MSEC 1000000ULL

struct kmem_return { uint64_t kmr_return; vm_offset_t kmr_address; };
extern struct kmem_return kmem_alloc_contig_guard(
    vm_map_t map, vm_size_t size, vm_offset_t mask,
    ppnum_t max_pnum, ppnum_t pnum_mask,
    uint32_t flags, uint64_t guard);
extern vm_map_t kernel_map;
extern pmap_t kernel_pmap;
static inline kern_return_t kmem_alloc_contig(
    vm_map_t map, vm_offset_t *addrp, vm_size_t size,
    vm_offset_t mask, ppnum_t max_pnum, ppnum_t pnum_mask,
    uint32_t flags, uint64_t tag) {
    struct kmem_return kmr = kmem_alloc_contig_guard(
        map, size, mask, max_pnum, pnum_mask, flags, tag);
    if ((kern_return_t)kmr.kmr_return == 0) *addrp = kmr.kmr_address;
    return (kern_return_t)kmr.kmr_return;
}

extern void CleanPoC_DcacheRegion(vm_offset_t va, size_t len);
extern void FlushPoC_DcacheRegion(vm_offset_t va, size_t len);
extern void FlushPoC_Dcache(void);
extern void delay(int us);
extern void clock_interval_to_deadline(uint64_t interval, uint64_t scale_factor, uint64_t *result);
extern wait_result_t assert_wait_deadline(event_t event, int interruptible, uint64_t deadline);
extern wait_result_t thread_block(thread_continue_t continuation);
extern void halt_all_cpus(boolean_t reboot);
extern int PE_parse_boot_argn(const char *arg_string, void *arg_ptr, int max_arg);
extern int SecureDTLookupEntry(const DTEntry searchPoint, const char *pathName, DTEntry *foundEntry);
extern int printf(const char *fmt, ...);
extern int snprintf(char *buf, unsigned long size, const char *fmt, ...);
extern int strncmp(const char *s1, const char *s2, unsigned long n);
extern int strcmp(const char *s1, const char *s2);
extern unsigned long strlen(const char *s);
extern void *memcpy(void *dst, const void *src, unsigned long n);
extern void *memset(void *dst, int c, unsigned long n);
extern void bzero(void *dst, unsigned long n);
extern vm_offset_t ml_io_map(vm_offset_t phys_addr, vm_size_t size);
extern ppnum_t pmap_find_phys(pmap_t pmap, addr64_t va);
extern kern_return_t kernel_thread_start(thread_continue_t, void *, thread_t *);
extern void thread_deallocate(thread_t);
extern uint32_t sweet_log_copy(uint64_t *pos, char *out, uint32_t max);
extern uint64_t sweet_log_position(void);
volatile uint32_t *gtel_ps_hold_reg;
'''


def fo(va):
    return TEXT_EXEC_FOFF + (va - TEXT_EXEC_VA)


def encode_bl(pc, tgt, link=True):
    off = (tgt - pc) >> 2
    assert -(1 << 25) <= off < (1 << 25), f'branch out of range {pc:#x} -> {tgt:#x}'
    return (0x94000000 if link else 0x14000000) | (off & 0x3FFFFFF)


def compile_gtel_usb():
    with open(PATCH_0107, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    start = lines.index('+++ b/bsd/dev/gtel_usb.c') + 2
    c_lines = []
    for l in lines[start:]:
        if l.startswith('diff --git '):
            break
        if l.startswith('+'):
            c_lines.append(l[1:])
    c_src = '\n'.join(c_lines)
    idx = c_src.index('void gtel_usb_start(void);')
    body = c_src[idx:c_src.rfind('#endif')]

    os.makedirs(SCRATCH, exist_ok=True)
    src_win = os.path.join(SCRATCH, 'gtel_usb_darwin.c')
    obj_win = os.path.join(SCRATCH, 'gtel_usb_darwin.o')
    with open(src_win, 'w', encoding='utf-8', newline='\n') as wf:
        wf.write(DARWIN_HDR + body + '\n')

    def to_wsl(p):
        p = p.replace('\\', '/')
        return '/mnt/' + p[0].lower() + p[2:]

    subprocess.check_call([
        'wsl', '-e', 'clang',
        '--target=arm64-apple-macos14.0', '-mkernel',
        '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-Os',
        '-fno-stack-protector', '-ffreestanding', '-fno-builtin',
        '-c', to_wsl(src_win), '-o', to_wsl(obj_win),
    ])
    return obj_win


def relocate_macho(obj_path):
    buf = open(obj_path, 'rb').read()
    magic, _, _, _, ncmds, _, _, _ = struct.unpack_from('<8I', buf, 0)
    assert magic == 0xFEEDFACF, f'bad Mach-O magic {magic:#x}'

    sections = []  # 1-based in n_sect / non-extern relocs
    symtab_info = None
    off = 32
    for _ in range(ncmds):
        cmd, sz = struct.unpack_from('<II', buf, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack_from('<I', buf, off + 64)[0]
            for i in range(nsects):
                so = off + 72 + i * 80
                sect = buf[so:so + 16].split(b'\x00')[0].decode()
                seg = buf[so + 16:so + 32].split(b'\x00')[0].decode()
                addr, size, foff, align, reloff, nreloc, flags = struct.unpack_from('<QQIIIII', buf, so + 32)
                sections.append({
                    'seg': seg,
                    'sect': sect,
                    'orig_addr': addr,
                    'size': size,
                    'foff': foff,
                    'align': 1 << align,
                    'reloff': reloff,
                    'nreloc': nreloc,
                    'flags': flags,
                    'is_zerofill': (flags & 0xFF) == 1,  # S_ZEROFILL
                })
        elif cmd == 0x02:  # LC_SYMTAB
            symtab_info = struct.unpack_from('<IIII', buf, off + 8)
        off += sz

    symoff, nsyms, stroff, strsize = symtab_info
    syms = []
    for i in range(nsyms):
        strx, n_type, n_sect, n_desc, n_value = struct.unpack_from('<IBBHQ', buf, symoff + i * 16)
        end = buf.find(b'\x00', stroff + strx)
        name = buf[stroff + strx:end].decode('latin1')
        syms.append({
            'name': name,
            'type': n_type,
            'sect': n_sect,
            'desc': n_desc,
            'val': n_value,
        })

    # Place non-zerofill sections into code_blob starting at CODE_BASE (put __text first)
    code_blob = bytearray()
    ordered_non_zf = [i for i, s in enumerate(sections) if not s['is_zerofill'] and s['sect'] == '__text'] + \
                     [i for i, s in enumerate(sections) if not s['is_zerofill'] and s['sect'] != '__text']
    for idx in ordered_non_zf:
        s = sections[idx]
        pad = (-len(code_blob)) & (max(s['align'], 4) - 1)
        code_blob.extend(b'\x00' * pad)
        s['new_off'] = len(code_blob)
        s['new_va'] = CODE_BASE + s['new_off']
        code_blob.extend(buf[s['foff']:s['foff'] + s['size']])

    # Place zerofill sections + tentative common symbols into BSS_BASE
    bss_cur = BSS_BASE
    for s in sections:
        if s['is_zerofill']:
            bss_cur = (bss_cur + s['align'] - 1) & ~(s['align'] - 1)
            s['new_va'] = bss_cur
            bss_cur += s['size']

    # Resolve all symbol VAs
    sym_vas = []
    for sym in syms:
        t = sym['type'] & 0x0E  # N_TYPE
        if t == 0x0E:  # N_SECT
            s = sections[sym['sect'] - 1]
            sym_vas.append(s['new_va'] + (sym['val'] - s['orig_addr']))
        elif t == 0x00 and sym['val'] != 0:  # N_UNDF tentative common (e.g. gtel_ps_hold_reg)
            bss_cur = (bss_cur + 7) & ~7
            va = bss_cur
            bss_cur += sym['val']
            sym_vas.append(va)
        elif sym['name'] in EXT_SYMS:
            sym_vas.append(EXT_SYMS[sym['name']])
        else:
            raise RuntimeError(f'Unresolved external symbol in gtel_usb.o: {sym}')

    assert bss_cur - BSS_BASE <= BSS_MAX, f'BSS overflow: {bss_cur - BSS_BASE} > {BSS_MAX}'

    def orig_va_to_new_va(ova):
        for s in sections:
            if s['orig_addr'] <= ova < s['orig_addr'] + s['size']:
                return s['new_va'] + (ova - s['orig_addr'])
        raise RuntimeError(f'Cannot map .o VA {ova:#x}')

    # Allocate 8-byte GOT entries inside code_blob on demand
    got_map = {}

    def get_got_va(target_va):
        if target_va not in got_map:
            pad = (-len(code_blob)) & 7
            code_blob.extend(b'\x00' * pad)
            off_in_blob = len(code_blob)
            code_blob.extend(struct.pack('<Q', target_va))
            got_map[target_va] = CODE_BASE + off_in_blob
        return got_map[target_va]

    # Apply ARM64 Mach-O relocations per non-zerofill section
    for s in sections:
        if s['is_zerofill'] or s['nreloc'] == 0:
            continue
        addend = 0
        has_addend = False
        for r_idx in range(s['nreloc']):
            r_addr, r_info = struct.unpack_from('<II', buf, s['reloff'] + r_idx * 8)
            r_sym = r_info & 0x00FFFFFF
            r_pcrel = (r_info >> 24) & 1
            r_len = (r_info >> 25) & 3
            r_extern = (r_info >> 27) & 1
            r_type = (r_info >> 28) & 0xF

            if r_type == 10:  # ARM64_RELOC_ADDEND
                assert not has_addend
                addend = r_sym if r_sym < 0x800000 else r_sym - 0x1000000
                has_addend = True
                continue

            cur_addend = addend if has_addend else 0
            addend = 0
            has_addend = False

            blob_off = s['new_off'] + r_addr
            pc = CODE_BASE + blob_off

            if r_extern:
                target = sym_vas[r_sym]
            else:
                # Non-extern: r_sym is 1-based section index; raw field holds original VA
                if r_type == 0 and r_len == 3:
                    orig_ptr = struct.unpack_from('<Q', code_blob, blob_off)[0]
                    target = orig_va_to_new_va(orig_ptr)
                else:
                    target = sections[r_sym - 1]['new_va']

            if r_type == 0:  # ARM64_RELOC_UNSIGNED
                assert r_len == 3, f'unexpected unsigned r_len={r_len}'
                struct.pack_into('<Q', code_blob, blob_off, target + cur_addend)
            elif r_type == 2:  # ARM64_RELOC_BRANCH26
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                disp = (target + cur_addend - pc) >> 2
                assert -(1 << 25) <= disp < (1 << 25), f'branch26 overflow at {pc:#x} -> {target + cur_addend:#x}'
                insn = (insn & 0xFC000000) | (disp & 0x03FFFFFF)
                struct.pack_into('<I', code_blob, blob_off, insn)
            elif r_type in (3, 5):  # PAGE21 / GOT_LOAD_PAGE21
                eff = get_got_va(target) if r_type == 5 else (target + cur_addend)
                page_diff = ((eff & ~0xFFF) - (pc & ~0xFFF)) >> 12
                immlo = page_diff & 0x3
                immhi = (page_diff >> 2) & 0x7FFFF
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                insn = (insn & 0x9F00001F) | (immlo << 29) | (immhi << 5)
                struct.pack_into('<I', code_blob, blob_off, insn)
            elif r_type in (4, 6):  # PAGEOFF12 / GOT_LOAD_PAGEOFF12
                eff = get_got_va(target) if r_type == 6 else (target + cur_addend)
                off12 = eff & 0xFFF
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                if (insn & 0x3B000000) == 0x39000000:  # LDR/STR unsigned offset
                    if (insn & 0x04800000) == 0x04800000:
                        shift = 4
                    else:
                        shift = (insn >> 30) & 3
                    assert (off12 & ((1 << shift) - 1)) == 0, f'unaligned off12 {off12:#x} shift={shift}'
                    imm12 = off12 >> shift
                else:
                    imm12 = off12
                insn = (insn & 0xFFC003FF) | (imm12 << 10)
                struct.pack_into('<I', code_blob, blob_off, insn)
            else:
                raise RuntimeError(f'Unsupported ARM64 Mach-O reloc type {r_type} at {pc:#x}')

    assert len(code_blob) <= CODE_MAX, f'code_blob too large: {len(code_blob)} > {CODE_MAX}'

    start_va = None
    power_va = None
    for i, sym in enumerate(syms):
        if sym['name'] == '_gtel_usb_start':
            start_va = sym_vas[i]
        elif sym['name'] == '_gtel_pmic_power_action':
            power_va = sym_vas[i]
    assert start_va is not None, '_gtel_usb_start not found'
    assert power_va is not None, '_gtel_pmic_power_action not found'

    print(f'Relocated gtel_usb: code+rodata+GOT = {len(code_blob)} / {CODE_MAX} bytes')
    print(f'                    BSS+common      = {bss_cur - BSS_BASE} / {BSS_MAX} bytes')
    return bytes(code_blob), start_va, power_va, bss_cur - BSS_BASE


def patch_u32(data, foff, expect, repl, label):
    cur = struct.unpack_from('<I', data, foff)[0]
    assert cur == expect, f'{label} @ 0x{foff:x}: expected 0x{expect:08x}, got 0x{cur:08x}'
    struct.pack_into('<I', data, foff, repl)


def main():
    if not os.path.exists(BAK):
        shutil.copyfile(KERN, BAK)
        print(f'Backed up {KERN} -> {BAK}')
    data = bytearray(open(BAK, 'rb').read())

    obj_path = compile_gtel_usb()
    code_blob, start_va, power_va, bss_sz = relocate_macho(obj_path)

    # 1. Overwrite unused sweet_usb slot (0xfffffff0074936b0 .. 0xfffffff007495410)
    slot_foff = fo(CODE_BASE)
    data[slot_foff:slot_foff + CODE_MAX] = b'\x00' * CODE_MAX
    data[slot_foff:slot_foff + len(code_blob)] = code_blob

    # Zero unused _ud BSS region in __DATA? (__DATA.__bss may be zerofill or in file, check)
    # _sweet_usb_probe is dead now, so zero the call site in _sweet_ufs_rootdev
    patch_u32(data, fo(0xFFFFFFF00748C1DC), encode_bl(0xFFFFFFF00748C1DC, CODE_BASE, True), 0xD503201F, 'nop sweet_usb_probe')

    # 2. Hook _load_init_program (0xfffffff0077aa7c8 was bl _gtel_mmc_probe -> call _gtel_usb_start)
    # Wait: preserve _gtel_mmc_probe?! No! The USB probe ALREADY ran? Let's call BOTH in a small trampoline in the cave?
    # Wait: load_init_program calls:
    #   0x77aa7c4: bl _sweet_sample_start
    #   0x77aa7c8: bl _gtel_mmc_probe
    # So replacing 0x77aa7c8 MUST STILL CALL _gtel_mmc_probe BEFORE _gtel_usb_start!
    # Put a 20-byte trampoline right after code_blob (at CODE_BASE + len(code_blob) aligned to 4)
    tramp_va = CODE_BASE + ((len(code_blob) + 3) & ~3)
    assert (tramp_va + 20) <= CODE_BASE + CODE_MAX, 'No room for load_init_program trampoline'
    tramp = [
        0xA9BF7BFD,                         # stp x29, x30, [sp, #-0x10]!
        0x910003FD,                         # mov x29, sp
        encode_bl(tramp_va + 8,  0xFFFFFFF00748EA50, True),  # bl _gtel_mmc_probe
        encode_bl(tramp_va + 12, start_va,           True),  # bl _gtel_usb_start
        0xA8C17BFD,                         # ldp x29, x30, [sp], #0x10
        0xD65F03C0,                         # ret
    ]
    for i, w in enumerate(tramp):
        struct.pack_into('<I', data, fo(tramp_va + 4 * i), w)
    patch_u32(data, fo(0xFFFFFFF0077AA7C8), encode_bl(0xFFFFFFF0077AA7C8, 0xFFFFFFF00748EA50, True),
              encode_bl(0xFFFFFFF0077AA7C8, tramp_va, True), 'hook load_init_program -> mmc_probe + gtel_usb_start')

    # 3. Patch _halt_all_cpus to use PM8916 PON + MPM2_MPM_PS_HOLD (fastboot on panic) with PSCI fallback
    patch_u32(data, fo(0xFFFFFFF00742D870), 0x340000F4, 0x2A1403E0, 'halt_all_cpus mov w0, w20')
    patch_u32(data, fo(0xFFFFFFF00742D874), 0x52800120, 0x2A1403E1, 'halt_all_cpus mov w1, w20')
    patch_u32(data, fo(0xFFFFFFF00742D878), 0x52800034,
              encode_bl(0xFFFFFFF00742D878, power_va, True), 'halt_all_cpus bl _gtel_pmic_power_action')
    patch_u32(data, fo(0xFFFFFFF00742D87C), 0x72B08000, 0x34000094, 'halt_all_cpus cbz w20, halt')
    patch_u32(data, fo(0xFFFFFFF00742D888), 0xD4000003, 0xD503201F, 'halt_all_cpus nop old smc')

    # 4. Patch 0108 iOS 12.5.7 IOMobileFramebuffer SwapEnd struct (0x278) & offsets in AppleCLCD::present + externalMethod
    patch_u32(data, 0xA44898, 0xB9410429, 0xB940C829, 'present mask +0xc8')
    patch_u32(data, 0xA448E8, 0x91019268, 0x91014268, 'present rect_a +0x50')
    patch_u32(data, 0xA448F8, 0x91031268, 0x91026268, 'present rect_b +0x98')
    patch_u32(data, 0xA44918, 0xF100133F, 0xF1000F3F, 'present max_layers = 3')
    patch_u32(data, 0xA44934, 0xB9405517, 0xB9404517, 'present surface_id +0x44')
    patch_u32(data, 0xA449B8, 0xB940518C, 0xB940418C, 'present swap_id +0x40')
    patch_u32(data, 0xA453F0, 0x7111B11F, 0x7109E11F, 'externalMethod SwapEnd min size 0x278')
    patch_u32(data, 0xA453FC, 0x52808D95, 0x52804F15, 'externalMethod SwapEnd copy_len 0x278')

    with open(KERN, 'wb') as wf:
        wf.write(data)
    print(f'Successfully wrote patched {KERN}!')


if __name__ == '__main__':
    main()
