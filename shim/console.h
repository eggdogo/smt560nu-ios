#pragma once
#include <stdint.h>

/* SM-T560NU NT51017 continuous splash: 800x1280, 24-bit RGB888, stride 2400 */
#define DEFAULT_FB_BASE     0x8e000000UL
#define DEFAULT_FB_W        800
#define DEFAULT_FB_H        1280
#define DEFAULT_FB_STRIDE   2400
#define DEFAULT_FB_BPP      24

#define RED     0x00ff0000U
#define BLUE    0x000000ffU
#define WHITE   0x00ffffffU
#define YELLOW  0x00ffff00U
#define GREEN   0x0000ff00U

extern volatile void *con_fb;
extern uint32_t con_w, con_h, con_stride, con_bpp;

void con_init(uintptr_t fb_base, uint32_t w, uint32_t h, uint32_t stride, uint32_t bpp);
void con_clear(uint32_t bg);
void con_rect(int rx, int ry, int rw, int rh, uint32_t color);
void con_skip(void);
void con_str(const char *label, const char *s);
void con_hex(const char *label, uint64_t v);
void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb);
