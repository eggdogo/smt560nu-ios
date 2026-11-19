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
