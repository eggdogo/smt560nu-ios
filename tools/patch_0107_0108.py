#!/usr/bin/env python3
"""Binary-patch 0107 (gtel USB fastboot + poweroff), 0108 (iOS 12 0x278 SwapEnd),
and 0109 (display modes and backboardd appointment) into kernel.development.sweet.
"""
import os
import shutil
import struct
import subprocess
import sys

PROJ = r'C:\Users\Avett\Documents\Projects\iosont560nu'
PATCH_0107 = r'C:\Users\Avett\Documents\GitHub\smt560nu-ios\xnu\patches\0107-gtel-usb-fastboot.patch'
SRC_DISP = os.path.join(PROJ, 'tools', 'gtel_display.c')
KERN = os.path.join(PROJ, 'kernel.development.sweet')
BAK = KERN + '.pre_0107_0108'
SCRATCH = r'C:\Users\Avett\.gemini\antigravity\brain\930aafe1-be5f-48c3-8932-b0d0a6bd3c94\scratch'

CODE_BASE = 0xFFFFFFF0074936B0
CODE_MAX = 0x1D60  # 7520 bytes: 0xfffffff0074936b0 .. 0xfffffff007495410
BSS_BASE = 0xFFFFFFF00803AE38
BSS_MAX = 0x368    # 872 bytes:  0xfffffff00803ae38 .. 0xfffffff00803b1a0

DISP_CODE_BASE = 0xFFFFFFF00748FEF0
DISP_CODE_MAX = 0x34B0  # 13488 bytes: 0xfffffff00748fef0 .. 0xfffffff0074933a0 (_sweet_touch_init.._rh_sync, before _sweet_spmi_init)

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
    # Display symbols
    '_OSDictionary_withCapacity':        0xFFFFFFF007920850,
    '_OSDictionary_setObject':          0xFFFFFFF007921350,
    '_OSArray_withCapacity':             0xFFFFFFF00791CB30,
    '_OSArray_setObject':               0xFFFFFFF00791CF50,
    '_OSNumber_withNumber':              0xFFFFFFF00793C8C0,
    '_IORegistryEntry_setProperty':     0xFFFFFFF0079845B0,
    '_IORegistryEntry_setPropertyBool': 0xFFFFFFF0079846B0,
    '_OSObject_release':                0xFFFFFFF00791C060,
    '_bzero':                           0xFFFFFFF007B1F500,  # was 0x7B1F580 (= _memset): bzero(buf,n) ran memset(buf,n,garbage)
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


def encode_b_cond(pc, tgt, cond):
    disp = (tgt - pc) >> 2
    assert -(1 << 18) <= disp < (1 << 18), f'b.cond out of range {pc:#x} -> {tgt:#x}'
    return 0x54000000 | ((disp & 0x7FFFF) << 5) | (cond & 0xF)


def to_wsl(p):
    p = p.replace('\\', '/')
    return '/mnt/' + p[0].lower() + p[2:]


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

    subprocess.check_call([
        'wsl', '-e', 'clang',
        '--target=arm64-apple-macos14.0', '-mkernel',
        '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-Os',
        '-fno-stack-protector', '-ffreestanding', '-fno-builtin',
        '-c', to_wsl(src_win), '-o', to_wsl(obj_win),
    ])
    return obj_win


def compile_gtel_display():
    os.makedirs(SCRATCH, exist_ok=True)
    obj_win = os.path.join(SCRATCH, 'gtel_display.o')
    subprocess.check_call([
        'wsl', '-e', 'clang',
        '--target=arm64-apple-macos14.0', '-mkernel',
        '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-Os',
        '-fno-stack-protector', '-ffreestanding', '-fno-builtin',
        '-c', to_wsl(SRC_DISP), '-o', to_wsl(obj_win),
    ])
    return obj_win


def relocate_macho_file(obj_path, code_base, code_max, bss_base=0, bss_max=0):
    buf = open(obj_path, 'rb').read()
    magic, _, _, _, ncmds, _, _, _ = struct.unpack_from('<8I', buf, 0)
    assert magic == 0xFEEDFACF, f'bad Mach-O magic {magic:#x}'

    sections = []
    symtab_info = None
    off = 32
    for _ in range(ncmds):
        cmd, sz = struct.unpack_from('<II', buf, off)
        if cmd == 0x19:
            nsects = struct.unpack_from('<I', buf, off + 64)[0]
            for i in range(nsects):
                so = off + 72 + i * 80
                sect = buf[so:so + 16].split(b'\x00')[0].decode()
                seg = buf[so + 16:so + 32].split(b'\x00')[0].decode()
                addr, size, foff, align, reloff, nreloc, flags = struct.unpack_from('<QQIIIII', buf, so + 32)
                sections.append({
                    'seg': seg, 'sect': sect, 'orig_addr': addr, 'size': size,
                    'foff': foff, 'align': 1 << align, 'reloff': reloff,
                    'nreloc': nreloc, 'flags': flags,
                    'is_zerofill': (flags & 0xFF) == 1,
                })
        elif cmd == 0x02:
            symtab_info = struct.unpack_from('<IIII', buf, off + 8)
        off += sz

    symoff, nsyms, stroff, strsize = symtab_info
    syms = []
    for i in range(nsyms):
        strx, n_type, n_sect, n_desc, n_value = struct.unpack_from('<IBBHQ', buf, symoff + i * 16)
        end = buf.find(b'\x00', stroff + strx)
        name = buf[stroff + strx:end].decode('latin1')
        syms.append({'name': name, 'type': n_type, 'sect': n_sect, 'desc': n_desc, 'val': n_value})

    code_blob = bytearray()
    ordered_non_zf = [i for i, s in enumerate(sections) if not s['is_zerofill'] and s['sect'] == '__text'] + \
                     [i for i, s in enumerate(sections) if not s['is_zerofill'] and s['sect'] != '__text']
    for idx in ordered_non_zf:
        s = sections[idx]
        pad = (-len(code_blob)) & (max(s['align'], 4) - 1)
        code_blob.extend(b'\x00' * pad)
        s['new_off'] = len(code_blob)
        s['new_va'] = code_base + s['new_off']
        code_blob.extend(buf[s['foff']:s['foff'] + s['size']])

    bss_cur = bss_base
    for s in sections:
        if s['is_zerofill']:
            bss_cur = (bss_cur + s['align'] - 1) & ~(s['align'] - 1)
            s['new_va'] = bss_cur
            bss_cur += s['size']

    sym_vas = []
    sym_map = {}
    for sym in syms:
        t = sym['type'] & 0x0E
        if t == 0x0E:
            s = sections[sym['sect'] - 1]
            va = s['new_va'] + (sym['val'] - s['orig_addr'])
            sym_vas.append(va)
            sym_map[sym['name']] = va
        elif t == 0x00 and sym['val'] != 0:
            bss_cur = (bss_cur + 7) & ~7
            va = bss_cur
            bss_cur += sym['val']
            sym_vas.append(va)
            sym_map[sym['name']] = va
        elif sym['name'] in EXT_SYMS:
            va = EXT_SYMS[sym['name']]
            sym_vas.append(va)
            sym_map[sym['name']] = va
        else:
            raise RuntimeError(f'Unresolved external symbol in {os.path.basename(obj_path)}: {sym}')

    if bss_max > 0:
        assert bss_cur - bss_base <= bss_max, f'BSS overflow: {bss_cur - bss_base} > {bss_max}'

    def orig_va_to_new_va(ova):
        for s in sections:
            if s['orig_addr'] <= ova < s['orig_addr'] + s['size']:
                return s['new_va'] + (ova - s['orig_addr'])
        raise RuntimeError(f'Cannot map .o VA {ova:#x}')

    got_map = {}
    def get_got_va(target_va):
        if target_va not in got_map:
            pad = (-len(code_blob)) & 7
            code_blob.extend(b'\x00' * pad)
            off_in_blob = len(code_blob)
            code_blob.extend(struct.pack('<Q', target_va))
            got_map[target_va] = code_base + off_in_blob
        return got_map[target_va]

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

            if r_type == 10:
                assert not has_addend
                addend = r_sym if r_sym < 0x800000 else r_sym - 0x1000000
                has_addend = True
                continue

            cur_addend = addend if has_addend else 0
            addend = 0
            has_addend = False

            blob_off = s['new_off'] + r_addr
            pc = code_base + blob_off

            if r_extern:
                target = sym_vas[r_sym]
            else:
                if r_type == 0 and r_len == 3:
                    orig_ptr = struct.unpack_from('<Q', code_blob, blob_off)[0]
                    target = orig_va_to_new_va(orig_ptr)
                else:
                    target = sections[r_sym - 1]['new_va']

            if r_type == 0:
                assert r_len == 3
                struct.pack_into('<Q', code_blob, blob_off, target + cur_addend)
            elif r_type == 2:
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                disp = (target + cur_addend - pc) >> 2
                assert -(1 << 25) <= disp < (1 << 25), f'branch26 overflow at {pc:#x} -> {target + cur_addend:#x}'
                insn = (insn & 0xFC000000) | (disp & 0x03FFFFFF)
                struct.pack_into('<I', code_blob, blob_off, insn)
            elif r_type in (3, 5):
                eff = get_got_va(target) if r_type == 5 else (target + cur_addend)
                page_diff = ((eff & ~0xFFF) - (pc & ~0xFFF)) >> 12
                immlo = page_diff & 0x3
                immhi = (page_diff >> 2) & 0x7FFFF
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                insn = (insn & 0x9F00001F) | (immlo << 29) | (immhi << 5)
                struct.pack_into('<I', code_blob, blob_off, insn)
            elif r_type in (4, 6):
                eff = get_got_va(target) if r_type == 6 else (target + cur_addend)
                off12 = eff & 0xFFF
                insn = struct.unpack_from('<I', code_blob, blob_off)[0]
                if (insn & 0x3B000000) == 0x39000000:
                    shift = 4 if (insn & 0x04800000) == 0x04800000 else (insn >> 30) & 3
                    assert (off12 & ((1 << shift) - 1)) == 0, f'unaligned off12 {off12:#x} shift={shift}'
                    imm12 = off12 >> shift
                else:
                    imm12 = off12
                insn = (insn & 0xFFC003FF) | (imm12 << 10)
                struct.pack_into('<I', code_blob, blob_off, insn)
            else:
                raise RuntimeError(f'Unsupported reloc type {r_type} in {obj_path}')

    assert len(code_blob) <= code_max, f'code_blob overflow in {obj_path}: {len(code_blob)} > {code_max}'
    return bytes(code_blob), sym_map, bss_cur - bss_base


def patch_u32(data, foff, expect, repl, label):
    cur = struct.unpack_from('<I', data, foff)[0]
    assert cur == expect, f'{label} @ 0x{foff:x}: expected 0x{expect:08x}, got 0x{cur:08x}'
    struct.pack_into('<I', data, foff, repl)


def main():
    data = bytearray(open(BAK, 'rb').read())

    # 1. Compile & relocate gtel_usb
    usb_obj = compile_gtel_usb()
    usb_blob, usb_syms, bss_sz = relocate_macho_file(usb_obj, CODE_BASE, CODE_MAX, BSS_BASE, BSS_MAX)
    start_va = usb_syms['_gtel_usb_start']
    power_va = usb_syms['_gtel_pmic_power_action']
    print(f'Relocated gtel_usb: code={len(usb_blob)}/{CODE_MAX}, BSS={bss_sz}/{BSS_MAX}')

    # 2. Compile & relocate gtel_display
    disp_obj = compile_gtel_display()
    disp_blob, disp_syms, _ = relocate_macho_file(disp_obj, DISP_CODE_BASE, DISP_CODE_MAX)
    publish_va = disp_syms['_gtel_publish_display_modes']
    handle_74_va = disp_syms['_gtel_handle_sel_74']
    handle_79_va = disp_syms['_gtel_handle_sel_79']
    print(f'Relocated gtel_display: code={len(disp_blob)}/{DISP_CODE_MAX}')

    # 3. Write USB slot
    usb_foff = fo(CODE_BASE)
    data[usb_foff:usb_foff + CODE_MAX] = b'\x00' * CODE_MAX
    data[usb_foff:usb_foff + len(usb_blob)] = usb_blob

    # Trampoline for load_init_program in CODE_BASE
    tramp_va = CODE_BASE + ((len(usb_blob) + 3) & ~3)
    assert (tramp_va + 24) <= CODE_BASE + CODE_MAX, 'No room for trampoline'
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
              encode_bl(0xFFFFFFF0077AA7C8, tramp_va, True), 'hook load_init_program')

    # Nop sweet_touch_init and sweet_usb_probe in sweet_ufs_rootdev
    patch_u32(data, fo(0xFFFFFFF00748C1D8), encode_bl(0xFFFFFFF00748C1D8, DISP_CODE_BASE, True), 0xD503201F, 'nop sweet_touch_init')
    patch_u32(data, fo(0xFFFFFFF00748C1DC), encode_bl(0xFFFFFFF00748C1DC, CODE_BASE, True), 0xD503201F, 'nop sweet_usb_probe')

    # 4. Write Display slot
    disp_foff = fo(DISP_CODE_BASE)
    disp_slot = bytearray(disp_blob)

    # Hooks in DISP_CODE_BASE right after disp_blob
    pad = (-len(disp_slot)) & 3
    disp_slot.extend(b'\x00' * pad)

    start_hook_va = DISP_CODE_BASE + len(disp_slot)
    start_hook = [
        0xA9BF7BFD,                         # stp x29, x30, [sp, #-0x10]!
        0x910003FD,                         # mov x29, sp
        0xAA1303E0,                         # mov x0, x19 (AppleCLCD *this)
        encode_bl(start_hook_va + 12, publish_va, True), # bl gtel_publish_display_modes
        0xA8C17BFD,                         # ldp x29, x30, [sp], #0x10
        encode_bl(start_hook_va + 20, 0xFFFFFFF007A48374, False), # b 0xfffffff007a48374
    ]
    disp_slot.extend(struct.pack(f'<{len(start_hook)}I', *start_hook))

    ext_hook_va = DISP_CODE_BASE + len(disp_slot)
    # ext_hook structure:
    # +0:  cmp w19, #74
    # +4:  b.eq handle_74 (+24)
    # +8:  cmp w19, #79
    # +12: b.eq handle_79 (+44)
    # +16: cmp w19, #73
    # +20: b.eq handle_73 (+64)
    # +24: b default_fallback (+88)
    h_74_va = ext_hook_va + 28
    h_79_va = ext_hook_va + 56
    h_73_va = ext_hook_va + 84
    h_def_va = ext_hook_va + 92

    ext_hook = [
        0x71012A7F,                         # cmp w19, #74
        encode_b_cond(ext_hook_va + 4, h_74_va, 0), # b.eq h_74
        0x71013E7F,                         # cmp w19, #79
        encode_b_cond(ext_hook_va + 12, h_79_va, 0), # b.eq h_79
        0x7101267F,                         # cmp w19, #73
        encode_b_cond(ext_hook_va + 20, h_73_va, 0), # b.eq h_73
        encode_bl(ext_hook_va + 24, h_def_va, False), # b h_def
        # handle_74 (+28):
        0xA9BF7BFD,                         # stp x29, x30, [sp, #-0x10]!
        0x910003FD,                         # mov x29, sp
        0xAA1403E0,                         # mov x0, x20 (args)
        encode_bl(h_74_va + 12, handle_74_va, True), # bl gtel_handle_sel_74
        0xA8C17BFD,                         # ldp x29, x30, [sp], #0x10
        0x2A1F03F5,                         # mov w21, wzr
        encode_bl(h_74_va + 24, 0xFFFFFFF007A49668, False), # b 0xfffffff007a49668 (skip bzero!)
        # handle_79 (+56):
        0xA9BF7BFD,                         # stp x29, x30, [sp, #-0x10]!
        0x910003FD,                         # mov x29, sp
        0xAA1403E0,                         # mov x0, x20 (args)
        encode_bl(h_79_va + 12, handle_79_va, True), # bl gtel_handle_sel_79
        0xA8C17BFD,                         # ldp x29, x30, [sp], #0x10
        0x2A1F03F5,                         # mov w21, wzr
        encode_bl(h_79_va + 24, 0xFFFFFFF007A49668, False), # b 0xfffffff007a49668
        # handle_73 (+84):
        0x2A1F03F5,                         # mov w21, wzr
        encode_bl(h_73_va + 4, 0xFFFFFFF007A49668, False), # b 0xfffffff007a49668
        # default fallback (+92):
        # matches 0xfffffff007a4949c original logic:
        # ldr w8, [x20, #0x50]; cmp w8, #1; b.ne 0x7a49608; b 0x7a4936c
        # Note: b.ne cannot reach 0x7a49608 (19-bit limit +/-1MB), so use b.eq +8 followed by unconditional b
        0xB9405288,                         # ldr w8, [x20, #0x50]
        0x7100051F,                         # cmp w8, #1
        encode_b_cond(h_def_va + 8, h_def_va + 16, 0), # b.eq +8 (skip to b 0x7a4936c)
        encode_bl(h_def_va + 12, 0xFFFFFFF007A49608, False), # b 0xfffffff007a49608 (when ne)
        encode_bl(h_def_va + 16, 0xFFFFFFF007A4936C, False), # b 0xfffffff007a4936c (when eq)
    ]
    disp_slot.extend(struct.pack(f'<{len(ext_hook)}I', *ext_hook))

    assert len(disp_slot) <= DISP_CODE_MAX, f'disp_slot overflow: {len(disp_slot)} > {DISP_CODE_MAX}'
    data[disp_foff:disp_foff + DISP_CODE_MAX] = b'\x00' * DISP_CODE_MAX
    data[disp_foff:disp_foff + len(disp_slot)] = disp_slot
    print(f'Wrote disp_slot: {len(disp_slot)} / {DISP_CODE_MAX} bytes')

    # Hook AppleCLCD::start
    patch_u32(data, fo(0xFFFFFFF007A484E0), 0x17FFFFA5,
              encode_bl(0xFFFFFFF007A484E0, start_hook_va, False), 'hook AppleCLCD::start -> publish_modes')

    # Hook AppleCLCD::externalMethod
    patch_u32(data, fo(0xFFFFFFF007A4949C), 0xB9405288,
              encode_bl(0xFFFFFFF007A4949C, ext_hook_va, False), 'hook AppleCLCD::externalMethod -> ext_hook')

    # 5. Patch halt_all_cpus to use PM8916 PON + MPM2_MPM_PS_HOLD
    patch_u32(data, fo(0xFFFFFFF00742D870), 0x340000F4, 0x2A1403E0, 'halt_all_cpus mov w0, w20')
    patch_u32(data, fo(0xFFFFFFF00742D874), 0x52800120, 0x2A1403E1, 'halt_all_cpus mov w1, w20')
    patch_u32(data, fo(0xFFFFFFF00742D878), 0x52800034,
              encode_bl(0xFFFFFFF00742D878, power_va, True), 'halt_all_cpus bl _gtel_pmic_power_action')
    patch_u32(data, fo(0xFFFFFFF00742D87C), 0x72B08000, 0x34000094, 'halt_all_cpus cbz w20, halt')
    patch_u32(data, fo(0xFFFFFFF00742D888), 0xD4000003, 0xD503201F, 'halt_all_cpus nop old smc')

    # 6. Patch 0108 iOS 12.5.7 IOMobileFramebuffer SwapEnd struct (0x278) & offsets
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
