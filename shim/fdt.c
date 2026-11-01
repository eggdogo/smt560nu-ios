/*
 * Flattened Device Tree parser for lk2nd.
 * Extracts /chosen properties and simple-framebuffer node.
 */
#include "fdt.h"

#define FDT_MAGIC       0xd00dfeed
#define FDT_BEGIN_NODE  1
#define FDT_END_NODE    2
#define FDT_PROP        3
#define FDT_NOP         4
#define FDT_END         9

static uint32_t be32(uintptr_t a)
{
	return __builtin_bswap32(*(volatile uint32_t *)a);
}

static int streq(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return *a == *b;
}

static int strstart(const char *str, const char *prefix)
{
	while (*prefix) {
		if (*prefix++ != *str++)
			return 0;
	}
	return 1;
}

static uintptr_t align4(uintptr_t a)
{
	return (a + 3) & ~3UL;
}

static uintptr_t skip_str(uintptr_t p)
{
	while (*(volatile char *)p)
		p++;
	return p + 1;
}

int fdt_chosen_u64(uintptr_t fdt, const char *prop, uint64_t *out)
{
	if (!fdt || be32(fdt) != FDT_MAGIC)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8);
	uintptr_t strings = fdt + be32(fdt + 12);
	int depth = 0, in_chosen = 0;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		switch (tok) {
		case FDT_BEGIN_NODE: {
			const char *name = (const char *)p;
			depth++;
			in_chosen = (depth == 2 && streq(name, "chosen"));
			p = align4(skip_str(p));
			break;
		}
		case FDT_END_NODE:
			if (in_chosen)
				return 0;
			depth--;
			break;
		case FDT_PROP: {
			uint32_t len = be32(p), nameoff = be32(p + 4);
			uintptr_t val = p + 8;
			if (in_chosen && streq((const char *)(strings + nameoff), prop)) {
				if (len == 4)
					*out = be32(val);
				else if (len == 8)
					*out = (uint64_t)be32(val) << 32 | be32(val + 4);
				else
					return 0;
				return 1;
			}
			p = align4(val + len);
			break;
		}
		case FDT_NOP:
			break;
		default:
			return 0;
		}
	}
}

static int strstr_check(const char *haystack, const char *needle)
{
	if (!haystack || !needle) return 0;
	for (int i = 0; haystack[i]; i++) {
		int j = 0;
		while (needle[j] && haystack[i + j] == needle[j])
			j++;
		if (!needle[j])
			return 1;
	}
	return 0;
}

int fdt_find_simplefb(uintptr_t fdt, uint64_t *base, uint32_t *w, uint32_t *h, uint32_t *stride, uint32_t *bpp)
{
	if (!fdt || be32(fdt) != FDT_MAGIC)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8);
	uintptr_t strings = fdt + be32(fdt + 12);
	int is_fb = 0;
	uint64_t fb_reg = 0;
	uint32_t fb_w = 0, fb_h = 0, fb_stride = 0, fb_bpp = 32;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		switch (tok) {
		case FDT_BEGIN_NODE: {
			const char *name = (const char *)p;
			is_fb = (strstr_check(name, "framebuffer") || strstr_check(name, "simplefb")
				 || strstr_check(name, "display") || streq(name, "fb"));
			fb_reg = 0;
			fb_w = 0;
			fb_h = 0;
			fb_stride = 0;
			fb_bpp = 32;
			p = align4(skip_str(p));
			break;
		}
		case FDT_END_NODE:
			if (is_fb && fb_reg && fb_w && fb_h) {
				*base = fb_reg;
				*w = fb_w;
				*h = fb_h;
				*stride = fb_stride ? fb_stride : fb_w * (fb_bpp / 8);
				*bpp = fb_bpp;
				return 1;
			}
			is_fb = 0;
			break;
		case FDT_PROP: {
			uint32_t len = be32(p), nameoff = be32(p + 4);
			uintptr_t val = p + 8;
			const char *pname = (const char *)(strings + nameoff);
			if (streq(pname, "compatible") && strstr_check((const char *)val, "simple-framebuffer"))
				is_fb = 1;

			if (is_fb) {
				if (streq(pname, "reg")) {
					if (len >= 8 && be32(val) == 0)
						fb_reg = be32(val + 4);
					else if (len >= 4)
						fb_reg = be32(val);
				} else if (streq(pname, "width")) {
					fb_w = be32(val);
				} else if (streq(pname, "height")) {
					fb_h = be32(val);
				} else if (streq(pname, "stride")) {
					fb_stride = be32(val);
				} else if (streq(pname, "format")) {
					const char *fmt = (const char *)val;
					if (strstr_check(fmt, "565"))
						fb_bpp = 16;
					else if (strstr_check(fmt, "888") && !strstr_check(fmt, "8888") && !strstr_check(fmt, "a8r8g8b8") && !strstr_check(fmt, "x8r8g8b8"))
						fb_bpp = 24;
					else
						fb_bpp = 32;
				}
			}
			p = align4(val + len);
			break;
		}
		case FDT_NOP:
			break;
		default:
			return 0;
		}
	}
}
