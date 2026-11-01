#pragma once
#include <stdint.h>

int fdt_chosen_u64(uintptr_t fdt, const char *prop, uint64_t *out);
int fdt_find_simplefb(uintptr_t fdt, uint64_t *base, uint32_t *w, uint32_t *h, uint32_t *stride, uint32_t *bpp);
