/*
 * Framebuffer text console for SM-T560NU.
 * Works with the MMU off (strict device memory access).
 */
#include "console.h"
#include "font.h"

#define SCALE       2
#define CH_W        (8 * SCALE)
#define CH_H        (16 * SCALE)
#define MARGIN      16
#define LABEL_COLS  8

volatile void *con_fb = (volatile void *)DEFAULT_FB_BASE;
uint32_t con_w = DEFAULT_FB_W;
uint32_t con_h = DEFAULT_FB_H;
uint32_t con_stride = DEFAULT_FB_STRIDE;
uint32_t con_bpp = DEFAULT_FB_BPP;

static uint32_t con_bg = 0;
static int row = 0;

static inline uint16_t rgb32_to_565(uint32_t c)
{
	uint32_t r = (c >> 16) & 0xff;
	uint32_t g = (c >> 8) & 0xff;
	uint32_t b = c & 0xff;
	return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

void con_init(uintptr_t fb_base, uint32_t w, uint32_t h, uint32_t stride, uint32_t bpp)
{
	if (fb_base)
		con_fb = (volatile void *)fb_base;
	if (w)
		con_w = w;
	if (h)
		con_h = h;
	if (bpp)
		con_bpp = bpp;
	if (stride)
		con_stride = stride;
	else
		con_stride = con_w * (con_bpp / 8);
	row = 0;
}

void con_clear(uint32_t bg)
{
	if (con_bpp == 24) {
		uint8_t r = (bg >> 16) & 0xff;
		uint8_t g = (bg >> 8) & 0xff;
		uint8_t b = bg & 0xff;
		for (uint32_t y = 0; y < con_h; y++) {
			volatile uint8_t *line = (volatile uint8_t *)((uintptr_t)con_fb + y * con_stride);
			for (uint32_t x = 0; x < con_w; x++) {
				line[x * 3 + 0] = b;
				line[x * 3 + 1] = g;
				line[x * 3 + 2] = r;
			}
		}
	} else if (con_bpp == 16) {
		uint16_t bg16 = rgb32_to_565(bg);
		for (uint32_t y = 0; y < con_h; y++) {
			volatile uint16_t *line = (volatile uint16_t *)((uintptr_t)con_fb + y * con_stride);
			for (uint32_t x = 0; x < con_w; x++)
				line[x] = bg16;
		}
	} else {
		for (uint32_t y = 0; y < con_h; y++) {
			volatile uint32_t *line = (volatile uint32_t *)((uintptr_t)con_fb + y * con_stride);
			for (uint32_t x = 0; x < con_w; x++)
				line[x] = bg;
		}
	}
	con_bg = bg;
	row = 0;
	__asm__ volatile("dsb sy" ::: "memory");
}

void con_rect(int rx, int ry, int rw, int rh, uint32_t color)
{
	if (con_bpp == 24) {
		uint8_t r = (color >> 16) & 0xff;
		uint8_t g = (color >> 8) & 0xff;
		uint8_t b = color & 0xff;
		for (int y = ry; y < ry + rh && y < (int)con_h; y++) {
			volatile uint8_t *line = (volatile uint8_t *)((uintptr_t)con_fb + y * con_stride);
			for (int x = rx; x < rx + rw && x < (int)con_w; x++) {
				line[x * 3 + 0] = b;
				line[x * 3 + 1] = g;
				line[x * 3 + 2] = r;
			}
		}
	} else if (con_bpp == 16) {
		uint16_t c16 = rgb32_to_565(color);
		for (int y = ry; y < ry + rh && y < (int)con_h; y++) {
			volatile uint16_t *line = (volatile uint16_t *)((uintptr_t)con_fb + y * con_stride);
			for (int x = rx; x < rx + rw && x < (int)con_w; x++)
				line[x] = c16;
		}
	} else {
		for (int y = ry; y < ry + rh && y < (int)con_h; y++) {
			volatile uint32_t *line = (volatile uint32_t *)((uintptr_t)con_fb + y * con_stride);
			for (int x = rx; x < rx + rw && x < (int)con_w; x++)
				line[x] = color;
		}
	}
	__asm__ volatile("dsb sy" ::: "memory");
}

static inline void uart_putc(char c)
{
	uintptr_t pc;
	__asm__ volatile("adr %0, ." : "=r"(pc));
	/* Only write to PL011 UART if running under QEMU virt (RAM < 0x70000000) */
	if (pc < 0x70000000UL) {
		*(volatile uint32_t *)0x09000000UL = (uint32_t)c;
	}
}

static void put_char(int col, char ch, uint32_t fg)
{
	if (ch < 0x20 || ch > 0x7e)
		ch = '?';
	uart_putc(ch);
	const unsigned char *g = font8x16[ch - 0x20];
	int x0 = MARGIN + col * CH_W, y0 = MARGIN + row * CH_H;
	if (x0 + CH_W > (int)con_w || y0 + CH_H > (int)con_h)
		return;

	uint16_t fg16 = (con_bpp == 16) ? rgb32_to_565(fg) : 0;
	uint16_t bg16 = (con_bpp == 16) ? rgb32_to_565(con_bg) : 0;

	for (int gy = 0; gy < 16; gy++) {
		for (int gx = 0; gx < 8; gx++) {
			int on = (g[gy] & (0x80 >> gx)) != 0;
			uint32_t c = on ? fg : con_bg;
			if (con_bpp == 24) {
				uint8_t r = (c >> 16) & 0xff;
				uint8_t g = (c >> 8) & 0xff;
				uint8_t b = c & 0xff;
				for (int sy = 0; sy < SCALE; sy++) {
					volatile uint8_t *p = (volatile uint8_t *)((uintptr_t)con_fb
								+ (y0 + gy * SCALE + sy) * con_stride)
								+ (x0 + gx * SCALE) * 3;
					for (int sx = 0; sx < SCALE; sx++) {
						p[sx * 3 + 0] = b;
						p[sx * 3 + 1] = g;
						p[sx * 3 + 2] = r;
					}
				}
			} else if (con_bpp == 16) {
				uint16_t c16 = on ? fg16 : bg16;
				for (int sy = 0; sy < SCALE; sy++) {
					volatile uint16_t *p = (volatile uint16_t *)((uintptr_t)con_fb
								+ (y0 + gy * SCALE + sy) * con_stride)
								+ x0 + gx * SCALE;
					for (int sx = 0; sx < SCALE; sx++)
						p[sx] = c16;
				}
			} else {
				for (int sy = 0; sy < SCALE; sy++) {
					volatile uint32_t *p = (volatile uint32_t *)((uintptr_t)con_fb
								+ (y0 + gy * SCALE + sy) * con_stride)
								+ x0 + gx * SCALE;
					for (int sx = 0; sx < SCALE; sx++)
						p[sx] = c;
				}
			}
		}
	}
}

static int put_str(int col, const char *s, uint32_t fg)
{
	while (*s)
		put_char(col++, *s++, fg);
	return col;
}

static void fmt_hex(char *buf, uint64_t v, int digits)
{
	static const char hex[] = "0123456789ABCDEF";
	for (int i = 0; i < digits; i++)
		buf[i] = hex[(v >> (4 * (digits - 1 - i))) & 0xf];
	buf[digits] = 0;
}

void con_skip(void)
{
	uart_putc('\r');
	uart_putc('\n');
	row++;
}

void con_str(const char *label, const char *s)
{
	put_str(0, label, YELLOW);
	uart_putc(':');
	uart_putc(' ');
	put_str(LABEL_COLS, s, WHITE);
	uart_putc('\r');
	uart_putc('\n');
	row++;
}

void con_hex(const char *label, uint64_t v)
{
	char buf[17];
	fmt_hex(buf, v, 16);
	con_str(label, buf);
}

void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb)
{
	char buf[9];
	int col = put_str(0, label, YELLOW);
	uart_putc(':');
	uart_putc(' ');
	col = col < LABEL_COLS ? LABEL_COLS : col + 1;
	col = put_str(col, a, YELLOW);
	fmt_hex(buf, va, 8);
	col = put_str(col, buf, WHITE);
	if (b) {
		uart_putc(' ');
		col = put_str(col + 1, b, YELLOW);
		fmt_hex(buf, vb, 8);
		put_str(col, buf, WHITE);
	}
	uart_putc('\r');
	uart_putc('\n');
	row++;
}
