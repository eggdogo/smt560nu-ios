#include <stdint.h>

typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef unsigned long size_t;
typedef int IOReturn;

#define NULL ((void *)0)

struct IOExternalMethodArguments {
    uint32_t            version;
    uint32_t            selector;
    uint32_t            asyncWakePort;
    uint32_t            _pad0;
    void *              asyncReference;
    uint32_t            asyncReferenceCount;
    uint32_t            _pad1;
    const uint64_t *    scalarInput;
    uint32_t            scalarInputCount;
    uint32_t            _pad2;
    const void *        structureInput;
    uint32_t            structureInputSize;
    uint32_t            _pad3;
    void *              structureInputDescriptor;
    uint64_t *          scalarOutput;
    uint32_t            scalarOutputCount;
    uint32_t            _pad4;
    void *              structureOutput;
    uint32_t            structureOutputSize;
    uint32_t            _pad5;
    void *              structureOutputDescriptor;
    uint64_t            structureOutputDescriptorSize;
};

// External symbols from kernel.development.sweet
extern void *OSDictionary_withCapacity(uint32_t capacity);
extern void OSDictionary_setObject(void *dict, const char *key, const void *val);
extern void *OSArray_withCapacity(uint32_t capacity);
extern void OSArray_setObject(void *arr, const void *val);
extern void *OSNumber_withNumber(uint64_t val, uint32_t bits);
extern int IORegistryEntry_setProperty(void *entry, const char *key, void *val);
extern int IORegistryEntry_setPropertyBool(void *entry, const char *key, int val);
extern void OSObject_release(void *obj, int freeResult);

extern void bzero(void *dst, size_t n);
extern void *memcpy(void *dst, const void *src, size_t n);
extern int printf(const char *fmt, ...);

#define K_OS_BOOLEAN_FALSE (*(void * const *)0xfffffff00804d2e0ULL)

void gtel_publish_display_modes(void *fb) {
    if (!fb) return;

    // Refresh dictionary
    void *refresh = OSDictionary_withCapacity(4);
    if (refresh) {
        uint64_t interval = (1ULL << 32) / 60ULL; // 71582788ULL
        uint64_t ticks = 320000ULL; // 19.2 MHz / 60
        void *n1 = OSNumber_withNumber(interval, 64);
        void *n2 = OSNumber_withNumber(interval, 64);
        void *n3 = OSNumber_withNumber(interval, 64);
        void *n4 = OSNumber_withNumber(ticks, 64);
        OSDictionary_setObject(refresh, "displayMinRefreshInterval", n1);
        OSDictionary_setObject(refresh, "displayMaxRefreshInterval", n2);
        OSDictionary_setObject(refresh, "displayRefreshStep", n3);
        OSDictionary_setObject(refresh, "displayRefreshStepMachTime", n4);
        IORegistryEntry_setProperty(fb, "IOMFBDisplayRefresh", refresh);
        OSObject_release(refresh, 1);
        if (n1) OSObject_release(n1, 1);
        if (n2) OSObject_release(n2, 1);
        if (n3) OSObject_release(n3, 1);
        if (n4) OSObject_release(n4, 1);
    }

    // Color dictionary
    void *colors = OSArray_withCapacity(1);
    void *color = OSDictionary_withCapacity(8);
    if (colors && color) {
        void *c_id = OSNumber_withNumber(1, 32);
        void *c_enc = OSNumber_withNumber(0, 32);
        void *c_depth = OSNumber_withNumber(8, 32);
        void *c_col = OSNumber_withNumber(1, 32);
        void *c_eotf = OSNumber_withNumber(1, 32);
        void *c_dr = OSNumber_withNumber(0, 32);
        void *c_sc = OSNumber_withNumber(1, 32);
        OSDictionary_setObject(color, "ID", c_id);
        OSDictionary_setObject(color, "PixelEncoding", c_enc);
        OSDictionary_setObject(color, "Depth", c_depth);
        OSDictionary_setObject(color, "Colorimetry", c_col);
        OSDictionary_setObject(color, "EOTF", c_eotf);
        OSDictionary_setObject(color, "DynamicRange", c_dr);
        OSDictionary_setObject(color, "Score", c_sc);
        OSDictionary_setObject(color, "IsVirtual", K_OS_BOOLEAN_FALSE);
        OSArray_setObject(colors, color);
        if (c_id) OSObject_release(c_id, 1);
        if (c_enc) OSObject_release(c_enc, 1);
        if (c_depth) OSObject_release(c_depth, 1);
        if (c_col) OSObject_release(c_col, 1);
        if (c_eotf) OSObject_release(c_eotf, 1);
        if (c_dr) OSObject_release(c_dr, 1);
        if (c_sc) OSObject_release(c_sc, 1);
    }

    // Timing dictionary
    void *timings = OSArray_withCapacity(1);
    void *timing = OSDictionary_withCapacity(8);
    void *horiz = OSDictionary_withCapacity(4);
    void *vert = OSDictionary_withCapacity(4);
    if (timings && timing && horiz && vert && colors) {
        uint32_t rate = 60 << 16;
        void *h_act = OSNumber_withNumber(800, 32);
        void *h_tot = OSNumber_withNumber(800, 32);
        void *h_rate = OSNumber_withNumber(rate, 32);
        void *h_prate = OSNumber_withNumber(rate, 32);
        OSDictionary_setObject(horiz, "Active", h_act);
        OSDictionary_setObject(horiz, "Total", h_tot);
        OSDictionary_setObject(horiz, "SyncRate", h_rate);
        OSDictionary_setObject(horiz, "PreciseSyncRate", h_prate);

        void *v_act = OSNumber_withNumber(1280, 32);
        void *v_tot = OSNumber_withNumber(1280, 32);
        void *v_rate = OSNumber_withNumber(rate, 32);
        void *v_prate = OSNumber_withNumber(rate, 32);
        OSDictionary_setObject(vert, "Active", v_act);
        OSDictionary_setObject(vert, "Total", v_tot);
        OSDictionary_setObject(vert, "SyncRate", v_rate);
        OSDictionary_setObject(vert, "PreciseSyncRate", v_prate);

        void *t_id = OSNumber_withNumber(1, 32);
        void *t_sc = OSNumber_withNumber(1, 32);
        OSDictionary_setObject(timing, "ID", t_id);
        OSDictionary_setObject(timing, "Score", t_sc);
        OSDictionary_setObject(timing, "IsVirtual", K_OS_BOOLEAN_FALSE);
        OSDictionary_setObject(timing, "IsOverscanned", K_OS_BOOLEAN_FALSE);
        OSDictionary_setObject(timing, "HorizontalAttributes", horiz);
        OSDictionary_setObject(timing, "VerticalAttributes", vert);
        OSDictionary_setObject(timing, "ColorModes", colors);
        OSArray_setObject(timings, timing);

        IORegistryEntry_setProperty(fb, "TimingElements", timings);
        IORegistryEntry_setProperty(fb, "ColorElements", colors);

        if (h_act) OSObject_release(h_act, 1);
        if (h_tot) OSObject_release(h_tot, 1);
        if (h_rate) OSObject_release(h_rate, 1);
        if (h_prate) OSObject_release(h_prate, 1);
        if (v_act) OSObject_release(v_act, 1);
        if (v_tot) OSObject_release(v_tot, 1);
        if (v_rate) OSObject_release(v_rate, 1);
        if (v_prate) OSObject_release(v_prate, 1);
        if (t_id) OSObject_release(t_id, 1);
        if (t_sc) OSObject_release(t_sc, 1);
    }
    if (horiz) OSObject_release(horiz, 1);
    if (vert) OSObject_release(vert, 1);
    if (timing) OSObject_release(timing, 1);
    if (timings) OSObject_release(timings, 1);
    if (color) OSObject_release(color, 1);
    if (colors) OSObject_release(colors, 1);

    IORegistryEntry_setPropertyBool(fb, "backlight-control", 1);
    printf("SWEET FB: published TimingElements, ColorElements, IOMFBDisplayRefresh, backlight-control\n");
}

void gtel_handle_sel_74(struct IOExternalMethodArguments *args) {
    if (args->scalarOutput && args->scalarOutputCount >= 1) {
        args->scalarOutput[0] = 1;
        for (uint32_t i = 1; i < args->scalarOutputCount; i++) {
            args->scalarOutput[i] = 0;
        }
    }
    if (args->structureOutput && args->structureOutputSize > 0) {
        bzero(args->structureOutput, args->structureOutputSize);
        if (args->structureOutputSize >= 16) {
            uint32_t *fi = (uint32_t *)args->structureOutput;
            fi[0] = 800;  // width
            fi[1] = 1280; // height
            fi[2] = 2400; // rowBytes
            fi[3] = 60;   // refresh
        }
    }
}

/*
 * Mach message trace (diagnostic): why does [CADisplay mainDisplay] come back nil in
 * backboardd? Wraps mach_msg traps 31/32 (pre-hook only; a blocking receive never comes
 * back through here). Prints, for backboardd and SpringBoard, every message that names
 * com.apple.CARenderServer (launchd lookup / check-in) and every CAS GetDisplays request
 * (0x9d27) or reply (0x9d8b); for launchd, small replies that carry an "error" key.
 * Stateless: this code lives in read-only text.
 */
extern int copyin(uint64_t uaddr, void *kaddr, size_t len);
extern int copyout(const void *kaddr, uint64_t uaddr, size_t len);

/* Sandbox stand-in, op 2 (sandbox_check / sandbox_check_by_audit_token).
 * libsystem_sandbox sets args[0] = pointer to an UNINITIALISED 8-byte stack slot, calls
 * __mac_syscall("Sandbox", 2, args) and returns (*slot != 0). The real kext writes the decision
 * into that slot; the stand-in used to leave it alone, so launchd saw stale stack junk (often
 * non-zero) and denied mach lookups with EPERM -> BOOTSTRAP_NOT_PRIVILEGED (1100). Write 0 = allow. */
void gtel_sandbox_op2(uint64_t arg) {
    uint64_t slot = 0, zero = 0;
    if (copyin(arg, &slot, sizeof(slot)) == 0 && slot != 0) {
        copyout(&zero, slot, sizeof(zero));
    }
}
extern void proc_selfname(char *buf, int size);
extern int mach_msg_trap(void *args);
extern int mach_msg_overwrite_trap(void *args);

#define GTEL_TRACE_MAX 512

static int gtel_streq(const char *a, const char *b) {
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}

static int gtel_find(const uint8_t *buf, uint32_t n, const char *s) {
    uint32_t len = 0;
    while (s[len]) len++;
    for (uint32_t i = 0; i + len <= n; i++) {
        uint32_t j = 0;
        while (j < len && buf[i + j] == (uint8_t)s[j]) j++;
        if (j == len) return (int)i;
    }
    return -1;
}

static void gtel_dump_words(const char *tag, const uint8_t *buf, uint32_t from, uint32_t n) {
    for (uint32_t o = from; o < n; o += 32) {
        const uint32_t *w = (const uint32_t *)(buf + o);
        uint32_t left = (n - o) / 4;
        printf("MSG %s +%03x: %08x %08x %08x %08x %08x %08x %08x %08x\n", tag, o,
               left > 0 ? w[0] : 0, left > 1 ? w[1] : 0, left > 2 ? w[2] : 0, left > 3 ? w[3] : 0,
               left > 4 ? w[4] : 0, left > 5 ? w[5] : 0, left > 6 ? w[6] : 0, left > 7 ? w[7] : 0);
    }
}

extern void *current_proc(void);
extern int cs_entitlements_blob_get(void *proc, void **blob, size_t *len);
static void gtel_ent_probe(const char *name) {
    void *blob = 0;
    size_t len = 0;
    int r = cs_entitlements_blob_get(current_proc(), &blob, &len);
    const unsigned char *b = (const unsigned char *)blob;
    printf("ENTPROBE %s: rc %d len %d blob %p first %02x%02x%02x%02x %02x%02x%02x%02x\n", name, r, (int)len, blob,
           b ? b[0] : 0, b ? b[1] : 0, b ? b[2] : 0, b ? b[3] : 0, b ? b[4] : 0, b ? b[5] : 0, b ? b[6] : 0, b ? b[7] : 0);
    static const char key[] = "com.apple.backboard.client";
    for (int i = 0; b && i + 120 < (int)len; i++) {
        int j = 0;
        while (key[j] && b[i + j] == (unsigned char)key[j]) j++;
        if (!key[j]) {
            char tail[64];
            for (int k = 0; k < 60; k++) { unsigned char c = b[i + 26 + k]; tail[k] = (c >= 32 && c < 127) ? c : '.'; }
            tail[60] = 0;
            printf("ENTPROBE %s: found backboard.client at %d: %s\n", name, i, tail);
        }
    }
}

/* returns 1 if the trap's return value should be printed */
static int gtel_msg_trace(const uint64_t *args) {
    char name[24];
    uint8_t buf[GTEL_TRACE_MAX];
    uint64_t option = args[1];
    uint32_t size = (uint32_t)args[2];

    if (!(option & 1) || size < 24) return 0;          /* not a send */
    name[0] = 0;
    proc_selfname(name, sizeof(name));
    int is_ui = gtel_streq(name, "backboardd") || gtel_streq(name, "SpringBoard");
    if (is_ui && gtel_streq(name, "SpringBoard")) {
        volatile uint32_t *pc = (volatile uint32_t *)0xfffffff00803b18cULL;
        uint32_t n = *pc + 1;
        *pc = n;
        if (n == 1 || n == 100 || n == 400 || n == 1500) { printf("ENTPROBE send #%u\n", n); gtel_ent_probe(name); }
    }
    /* launchd: only the few replies right after a UI process asked about CARenderServer
     * (counter in the gtel_usb BSS slack, 0xfffffff00803b180: writable, unused by usb) */
    volatile uint32_t *watch = (volatile uint32_t *)0xfffffff00803b180ULL;
    int is_launchd = gtel_streq(name, "launchd") && *watch != 0;
    if (!is_ui && !is_launchd) return 0;

    uint32_t n = size < GTEL_TRACE_MAX ? size : GTEL_TRACE_MAX;
    n &= ~3u;
    if (copyin(args[0], buf, n) != 0) return 0;
    const uint32_t *h = (const uint32_t *)buf;
    uint32_t id = h[5];

    if (is_ui) {
        int ca = gtel_find(buf, n, "CARenderServer");
        if (ca < 0) ca = gtel_find(buf, n, "profiled");
        if (id != 0x9d27 && id != 0x9d8b && ca < 0) {
            /* compact one-liner for every other send, first 200 only (free BSS word next to `watch`) */
            volatile uint32_t *cnt = (volatile uint32_t *)0xfffffff00803b184ULL;
            if (*cnt < 200) {
                *cnt = *cnt + 1;
                printf("MSGS %s id 0x%x bits 0x%x size %u remote 0x%x\n", name, id, h[0], h[1], h[2]);
            }
            return 0;
        }
        printf("MSG %s send id 0x%x bits 0x%x size %u remote 0x%x local 0x%x opt 0x%llx rcv 0x%llx%s\n",
               name, id, h[0], h[1], h[2], h[3], option, args[4], ca >= 0 ? " [CARenderServer]" : "");
        gtel_dump_words(name, buf, 24, n < 216 ? n : 216);
        if (ca >= 0) *watch = 4;
        return 1;
    }
    /* launchd: the next few sends after a CARenderServer request */
    *watch = *watch - 1;
    printf("MSG launchd send id 0x%x bits 0x%x size %u remote 0x%x (watch %u)\n", id, h[0], h[1], h[2], *watch);
    gtel_dump_words("launchd", buf, 24, n < 152 ? n : 152);
    return 0;
}

int gtel_mach_msg_trap(uint64_t *args) {
    int show = gtel_msg_trace(args);
    int r = mach_msg_trap(args);
    if (show) printf("MSG trap31 ret 0x%x\n", r);
    return r;
}

int gtel_mach_msg_overwrite_trap(uint64_t *args) {
    int show = gtel_msg_trace(args);
    int r = mach_msg_overwrite_trap(args);
    if (show) printf("MSG trap32 ret 0x%x\n", r);
    return r;
}

void gtel_handle_sel_79(struct IOExternalMethodArguments *args) {
    if (args->structureOutput && args->structureOutputSize > 0) {
        bzero(args->structureOutput, args->structureOutputSize);
        if (args->structureOutputSize >= 12 &&
            args->scalarInput && args->scalarInputCount >= 1 && args->scalarInput[0] == 0x40) {
            uint32_t ids[2] = { 1, 1 }; // ColorID=1, TimingID=1
            memcpy((uint8_t *)args->structureOutput + 4, ids, sizeof(ids));
        }
    }
}


/* read back the injected MobileGestalt cache (head/tail) and report zero-filled content */
extern int vnode_open(const char *path, int fmode, int cmode, int flags, void **vpp, void *ctx);
extern int vnode_close(void *vp, int flags, void *ctx);
extern int vn_rdwr(int rw, void *vp, char *base, int len, long long off, int seg, int ioflag, void *cred, int *aresid, void *p);
extern void *vfs_context_kernel(void);
extern void *vfs_context_ucred(void *ctx);
extern void *vfs_context_proc(void *ctx);
static void gtel_peek(const char *path) {
    unsigned char buf[32];
    void *vp = 0;
    void *ctx = vfs_context_kernel();
    int e = vnode_open(path, 1, 0, 0, &vp, ctx);
    if (e) { printf("PEEK %s: open err %d\n", path, e); return; }
    int resid = 0;
    for (int i = 0; i < 32; i++) buf[i] = 0xEE;
    int r = vn_rdwr(0, vp, (char *)buf, 32, 0, 2, 0, vfs_context_ucred(ctx), &resid, vfs_context_proc(ctx));
    printf("PEEK %s: rc %d read %d first %02x%02x%02x%02x%02x%02x%02x%02x\n", path, r, 32 - resid,
           buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
    vnode_close(vp, 1, ctx);
}
static void gtel_mgcheck(const char *tag) {
    unsigned char buf[512];
    void *vp = 0;
    void *ctx = vfs_context_kernel();
    int e = vnode_open("/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches/com.apple.MobileGestalt.plist",
                       1, 0, 0, &vp, ctx);
    if (e) { printf("MGCHK %s: open err %d\n", tag, e); return; }
    long long offs[6] = {0, 2048, 3900, 0, 2048, 3900};
    for (int k = 0; k < 6; k++) {
        int resid = 0, zeros = 0;
        for (int i = 0; i < 512; i++) buf[i] = 0xEE;
        int r = vn_rdwr(0, vp, (char *)buf, 512, offs[k], 2, k >= 3 ? 0x0808 : 0, vfs_context_ucred(ctx), &resid, vfs_context_proc(ctx));
        for (int i = 0; i < 512 - resid && i < 512; i++) if (buf[i] == 0) zeros++;
        printf("MGCHK %s: off %d rc %d resid %d zeros %d first %02x%02x%02x%02x%02x%02x%02x%02x\n", tag, (int)offs[k], r, resid, zeros,
               buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
    }
    vnode_close(vp, 1, ctx);
}

/* proc_exit() hook: log how interesting processes leave (exit code / terminating signal) */
extern int proc_pid(void *p);
extern void proc_name(int pid, char *buf, int size);
void gtel_exit_log(uint64_t p) {
    char name[24];
    name[0] = 0;
    int pid = proc_pid((void *)p);
    proc_name(pid, name, sizeof(name));
    uint32_t x = *(volatile uint16_t *)(p + 0x480);
    if (gtel_streq(name, "SpringBoard") || gtel_streq(name, "backboardd") || gtel_streq(name, "profiled") ||
        gtel_streq(name, "accountsd") || (x != 0 && x != 0x100)) {
        if (gtel_streq(name, "backboardd")) {
            volatile uint32_t *c = (volatile uint32_t *)0xfffffff00803b188ULL;
            if (*c < 3) { *c = *c + 1; gtel_mgcheck("backboardd-exit"); gtel_peek("/private/var/mobile/Library/Caches/com.apple.MobileGestalt.plist"); gtel_peek("/private/var/mobile/Library/Preferences/com.apple.MobileGestalt.plist"); gtel_peek("/private/var/mobile/Library/Preferences/com.apple.springboard.plist"); gtel_peek("/private/var/mobile/Library/Preferences/com.apple.backboardd.plist"); }
        }
        printf("EXIT %s[%d] xstat 0x%x (exit code %u, signal %u)\n", name, pid, x, (x >> 8) & 0xff, x & 0x7f);
    }
}

/* psignal_internal() hook: who kills SpringBoard & friends? */
extern int proc_selfpid(void);
extern void proc_selfname(char *buf, int size);
void gtel_sig_log(uint64_t p, uint64_t sig) {
    if (sig == 0) return;
    char tn[24], sn[24];
    tn[0] = 0; sn[0] = 0;
    int tpid = proc_pid((void *)p);
    proc_name(tpid, tn, sizeof(tn));
    if (!(gtel_streq(tn, "SpringBoard") || gtel_streq(tn, "backboardd") || gtel_streq(tn, "profiled") || gtel_streq(tn, "accountsd") || sig == 9)) return;
    proc_selfname(sn, sizeof(sn));
    printf("SIGKILL? %s[%d] gets signal %d from %s[%d]\n", tn, tpid, (int)sig, sn, proc_selfpid());
}

/* csops_internal() hook: what do entitlement queries look like? */
extern int proc_pidversion(void *p);
extern uint32_t proc_getcsflags(void *p);
extern int copyin(uint64_t uaddr, void *kaddr, size_t len);
void gtel_csops_log(int pid, int ops, uint64_t uaddr, uint64_t usize, uint64_t utok) {
    if (ops != 7) return;
    char sn[24];
    sn[0] = 0;
    proc_selfname(sn, sizeof(sn));
    if (!gtel_streq(sn, "SpringBoard")) return;
    uint32_t tok[8];
    for (int i = 0; i < 8; i++) tok[i] = 0xdeadbeef;
    int ce = utok ? copyin(utok, tok, 32) : -1;
    volatile uint32_t *c = (volatile uint32_t *)0xfffffff00803b190ULL;
    if (*c > 40) return;
    *c = *c + 1;
    printf("CSOPS %s pid %d ops %d usize %d tokcopy %d tok pid %u ver %u cur pid %d ver %d\n", sn, pid, ops, (int)usize, ce, tok[5], tok[7],
           proc_selfpid(), proc_pidversion(current_proc()));
    void *eb = 0; size_t el = 0;
    int er = cs_entitlements_blob_get(current_proc(), &eb, &el);
    printf("CSOPS csflags 0x%x blob_get rc %d len %d ptr %p\n", (unsigned)proc_getcsflags(current_proc()), er, (int)el, eb);
}
