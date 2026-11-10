import os

PROJ_DIR = r"c:\Users\Avett\Documents\Projects\iosont560nu"
REPO_DIR = r"C:\Users\Avett\Documents\GitHub\smt560nu-ios"

plist_path = os.path.join(PROJ_DIR, "com.apple.MobileGestalt.plist")
with open(plist_path, "rb") as f:
    plist_bytes = f.read()

print(f"Read {len(plist_bytes)} bytes from {plist_path}")

# Format bytes into C hex array
hex_lines = []
for i in range(0, len(plist_bytes), 16):
    chunk = plist_bytes[i:i+16]
    hex_str = ", ".join(f"0x{b:02x}" for b in chunk)
    if i + 16 < len(plist_bytes):
        hex_str += ","
    hex_lines.append(f"\t{hex_str}")
c_array_str = "\n".join(hex_lines)

patch_code = f"""#if defined(ARM64_BOARD_CONFIG_SWEET)
#include <sys/fcntl.h>

static const uint8_t sweet_gestalt_plist[{len(plist_bytes)}] = {{
{c_array_str}
}};

static void
sweet_inject_gestalt_cache(void)
{{
\tvnode_t vp = NULLVP;
\tvfs_context_t ctx = vfs_context_kernel();
\tconst char *path = "/private/var/mobile/Library/Caches/com.apple.MobileGestalt.plist";

\tif (vnode_open(path, FREAD, 0, 0, &vp, ctx) == 0) {{
\t\tprintf("SWEET: MobileGestalt cache already present at %s\\n", path);
\t\tvnode_close(vp, FREAD, ctx);
\t\treturn;
\t}}

\tprintf("SWEET: Injecting authentic iPad4,4 MobileGestalt cache to %s (%lu bytes)...\\n",
\t    path, (unsigned long)sizeof(sweet_gestalt_plist));

\tmount_t mp = rootvnode ? rootvnode->v_mount : NULL;
\tuint64_t saved_flags = 0;
\tif (mp && (mp->mnt_flag & MNT_RDONLY)) {{
\t\tsaved_flags = mp->mnt_flag;
\t\tmp->mnt_flag &= ~MNT_RDONLY;
\t}}

\tint error = vnode_open(path, (O_CREAT | FWRITE | O_TRUNC | O_NOFOLLOW), 0644, 0, &vp, ctx);
\tif (error == 0) {{
\t\tint resid = 0;
\t\tint err = vn_rdwr(UIO_WRITE, vp, (caddr_t)sweet_gestalt_plist,
\t\t    (int)sizeof(sweet_gestalt_plist), 0, UIO_SYSSPACE,
\t\t    IO_NODELOCKED | IO_UNIT, vfs_context_ucred(ctx), &resid,
\t\t    vfs_context_proc(ctx));
\t\t(void)VNOP_FSYNC(vp, MNT_WAIT, ctx);
\t\tvnode_close(vp, FWRITE, ctx);
\t\tif (err == 0) {{
\t\t\tprintf("SWEET: MobileGestalt cache injected successfully!\\n");
\t\t}} else {{
\t\t\tprintf("SWEET: MobileGestalt cache write failed with errno %d\\n", err);
\t\t}}
\t}} else {{
\t\tprintf("SWEET: Failed to create %s (errno %d)\\n", path, error);
\t}}

\tif (mp && saved_flags) {{
\t\tmp->mnt_flag = saved_flags;
\t}}
}}
#endif
"""

# Let's inspect xnu/bsd/kern/bsd_init.c around bsdinit_task
orig_bsd_init = os.path.join(PROJ_DIR, "xnu", "bsd", "kern", "bsd_init.c")
with open(orig_bsd_init, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find: bsd_init_kprintf("done\n");
# and: void\nbsdinit_task(void)
# and: load_init_program(p);

target_before_bsdinit = 'void\nbsdinit_task(void)\n'
target_load_init = '\tload_init_program(p);\n'

content = "".join(lines)
assert target_before_bsdinit in content, "target_before_bsdinit not found"
assert target_load_init in content, "target_load_init not found"

new_content = content.replace(
    target_before_bsdinit,
    f"{patch_code}\nvoid\nbsdinit_task(void)\n"
).replace(
    target_load_init,
    f"#if defined(ARM64_BOARD_CONFIG_SWEET)\n\tsweet_inject_gestalt_cache();\n#endif\n\n\tload_init_program(p);\n"
)

# Generate unified diff
import difflib
diff = list(difflib.unified_diff(
    lines,
    new_content.splitlines(keepends=True),
    fromfile="a/bsd/kern/bsd_init.c",
    tofile="b/bsd/kern/bsd_init.c"
))
patch_text = "".join(diff)

out_patch_repo = os.path.join(REPO_DIR, "xnu", "patches", "0103-gtel-inject-gestalt-cache.patch")
with open(out_patch_repo, "w", encoding="utf-8", newline="\n") as f:
    f.write(patch_text)

print(f"Wrote patch to {out_patch_repo} ({len(patch_text)} chars)")
