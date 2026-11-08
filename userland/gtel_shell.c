/*
 * gtel_shell.c - Self-contained Interactive Bringup Shell for iOS 12.5.7 on MSM8916
 * Target: Samsung Galaxy Tab E 9.6 (SM-T560NU)
 * Installed as: /usr/local/bin/restored_external
 */

typedef unsigned long size_t;
typedef long ssize_t;
typedef int pid_t;
typedef unsigned int uid_t;
typedef unsigned int gid_t;
typedef long long off_t;
typedef unsigned short mode_t;  /* Darwin's mode_t is 16-bit; int shifted every later stat field */

#define STDIN_FILENO  0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2

#define O_RDONLY 0x0000
#define O_WRONLY 0x0001
#define O_RDWR   0x0002

#define S_IFMT   0170000
#define S_IFDIR  0040000
#define S_IFCHR  0020000
#define S_IFBLK  0060000
#define S_IFREG  0100000
#define S_IFLNK  0120000

#define S_ISDIR(m)  (((m) & S_IFMT) == S_IFDIR)
#define S_ISREG(m)  (((m) & S_IFMT) == S_IFREG)
#define S_ISLNK(m)  (((m) & S_IFMT) == S_IFLNK)
#define S_ISCHR(m)  (((m) & S_IFMT) == S_IFCHR)
#define S_ISBLK(m)  (((m) & S_IFMT) == S_IFBLK)

/* Darwin utsname */
struct utsname {
    char sysname[256];
    char nodename[256];
    char release[256];
    char version[256];
    char machine[256];
};

/* Darwin stat64 */
struct stat {
    int             st_dev;
    mode_t          st_mode;
    unsigned short  st_nlink;
    unsigned long long st_ino;
    uid_t           st_uid;
    gid_t           st_gid;
    int             st_rdev;
    long long       st_atime;
    long long       st_atimensec;
    long long       st_mtime;
    long long       st_mtimensec;
    long long       st_ctime;
    long long       st_ctimensec;
    long long       st_birthtime;
    long long       st_birthtimensec;
    off_t           st_size;
    long long       st_blocks;
    int             st_blksize;
    unsigned int    st_flags;
    unsigned int    st_gen;
    int             st_lspare;
    long long       st_qspare[2];
};

/* Darwin dirent */
struct dirent {
    unsigned long long d_ino;
    unsigned long long d_seekoff;
    unsigned short     d_reclen;
    unsigned short     d_namlen;
    unsigned char      d_type;
    char               d_name[1024];
};

typedef void DIR;

/* Libc prototypes */
extern int printf(const char *fmt, ...);
extern int snprintf(char *str, size_t size, const char *fmt, ...);
extern int puts(const char *s);
extern size_t strlen(const char *s);
extern int strcmp(const char *s1, const char *s2);
extern int strncmp(const char *s1, const char *s2, size_t n);
extern char *strchr(const char *s, int c);
extern char *strstr(const char *haystack, const char *needle);
extern char *strtok(char *str, const char *delim);
extern char *strerror(int errnum);
extern int *__error(void);
#define errno (*__error())

extern ssize_t write(int fd, const void *buf, size_t count);
extern ssize_t read(int fd, void *buf, size_t count);
extern int open(const char *path, int flags, ...);
extern int close(int fd);
extern int sleep(unsigned int seconds);
extern void sync(void);
extern int reboot(int howto);

extern pid_t getpid(void);
extern pid_t getppid(void);
extern uid_t getuid(void);
extern gid_t getgid(void);
extern int uname(struct utsname *buf);
extern int sysctlbyname(const char *name, void *oldp, size_t *oldlenp, void *newp, size_t newlen);
extern pid_t waitpid(pid_t pid, int *stat_loc, int options);

extern DIR *opendir(const char *name);
extern struct dirent *readdir(DIR *dirp);
extern int closedir(DIR *dirp);
extern int lstat(const char *path, struct stat *buf);
extern int posix_spawn(pid_t *pid, const char *path, const void *file_actions, const void *attrp, char *const argv[], char *const envp[]);

extern char **environ;

static void banner(void) {
    puts("");
    puts("================================================================");
    puts("  iOS 12.5.7 (Build 16H81) Darwin on Samsung Galaxy Tab E 9.6");
    puts("  SoC: Qualcomm Snapdragon 410 (MSM8916) - 4x Cortex-A53 @ 1.2GHz");
    puts("  Port: iOS on SM-T560NU (GTEL)");
    puts("================================================================\n");
}

static void print_sysinfo(void) {
    struct utsname u;
    if (uname(&u) == 0) {
        printf("[gtel] Kernel : %s %s %s\n", u.sysname, u.release, u.version);
        printf("[gtel] Machine: %s\n", u.machine);
    }
    printf("[gtel] PID: %d, PPID: %d, UID: %d, GID: %d\n", getpid(), getppid(), getuid(), getgid());

    /* sysctl queries */
    char bootargs[512] = {0};
    size_t sz = sizeof(bootargs);
    if (sysctlbyname("kern.bootargs", bootargs, &sz, (void*)0, 0) == 0) {
        printf("[gtel] Cmdline: %s\n", bootargs);
    }

    int ncpu = 0;
    sz = sizeof(ncpu);
    sysctlbyname("hw.ncpu", &ncpu, &sz, (void*)0, 0);

    unsigned long long memsize = 0;
    sz = sizeof(memsize);
    sysctlbyname("hw.memsize", &memsize, &sz, (void*)0, 0);

    printf("[gtel] Hardware: %d CPU core(s), %llu MiB RAM\n", ncpu, memsize / (1024 * 1024));
}

static void cmd_ls(const char *path) {
    if (!path || !*path) path = "/";
    DIR *dir = opendir(path);
    if (!dir) {
        printf("ls: cannot open '%s': errno %d\n", path, errno);
        return;
    }
    struct dirent *de;
    int count = 0;
    while ((de = readdir(dir)) != (void*)0) {
        char full[1280];
        snprintf(full, sizeof(full), "%s/%s", strcmp(path, "/") == 0 ? "" : path, de->d_name);
        struct stat st;
        if (lstat(full, &st) == 0) {
            char type = '?';
            if (S_ISDIR(st.st_mode)) type = 'd';
            else if (S_ISREG(st.st_mode)) type = '-';
            else if (S_ISLNK(st.st_mode)) type = 'l';
            else if (S_ISCHR(st.st_mode)) type = 'c';
            else if (S_ISBLK(st.st_mode)) type = 'b';
            printf("%c %8lld  %s\n", type, (long long)st.st_size, de->d_name);
        } else {
            printf("?           %s\n", de->d_name);
        }
        count++;
    }
    closedir(dir);
    printf("Total: %d entries in '%s'\n", count, path);
}

static void cmd_scan_dev(void) {
    DIR *dir = opendir("/dev");
    if (!dir) {
        printf("scan_dev: cannot open /dev: errno %d\n", errno);
        return;
    }
    struct dirent *de;
    int block_cnt = 0, char_cnt = 0, total_cnt = 0;
    puts("[dev] Interesting block & terminal nodes in /dev:");
    while ((de = readdir(dir)) != (void*)0) {
        total_cnt++;
        char full[1280];
        snprintf(full, sizeof(full), "/dev/%s", de->d_name);
        struct stat st;
        if (lstat(full, &st) == 0) {
            if (S_ISBLK(st.st_mode)) {
                printf("  [BLOCK] %-16s rdev=0x%04x size=%lld\n", de->d_name, st.st_rdev, (long long)st.st_size);
                block_cnt++;
            } else if (S_ISCHR(st.st_mode)) {
                /* Filter for disks, ttys, consoles; skip the pty pairs (ttyw5 etc.) */
                int pty = strncmp(de->d_name, "tty", 3) == 0 && strlen(de->d_name) == 5;
                if (pty) continue;
                if (strncmp(de->d_name, "tty", 3) == 0 ||
                    strncmp(de->d_name, "ptm", 3) == 0 ||
                    strncmp(de->d_name, "console", 7) == 0 ||
                    strncmp(de->d_name, "rdisk", 5) == 0 ||
                    strncmp(de->d_name, "rmd", 3) == 0) {
                    printf("  [CHAR ] %-16s rdev=0x%04x\n", de->d_name, st.st_rdev);
                    char_cnt++;
                }
            }
        }
    }
    closedir(dir);
    printf("[dev] Total in /dev: %d (%d block, %d key char devices)\n", total_cnt, block_cnt, char_cnt);
}

static void cmd_cat(const char *path) {
    if (!path || !*path) {
        puts("usage: cat <path>");
        return;
    }
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("cat: cannot open '%s': errno %d\n", path, errno);
        return;
    }
    char buf[512];
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf) - 1)) > 0) {
        buf[n] = '\0';
        write(STDOUT_FILENO, buf, (size_t)n);
    }
    close(fd);
    puts("");
}

static void cmd_spawn(int argc, char **argv) {
    if (argc < 2) {
        puts("usage: spawn <path> [args...]");
        return;
    }
    pid_t pid = 0;
    int ret = posix_spawn(&pid, argv[1], (void*)0, (void*)0, &argv[1], environ);
    if (ret != 0) {
        printf("posix_spawn failed for '%s': errno %d\n", argv[1], ret);
    } else {
        printf("Spawned '%s' with PID %d\n", argv[1], pid);
    }
}

extern int sysctl(int *name, unsigned int namelen, void *oldp, size_t *oldlenp, void *newp, size_t newlen);

/* struct kinfo_proc (arm64 Darwin): 648 bytes, p_pid @40, p_comm @243, e_ppid @560 */
#define KP_SIZE  648
#define KP_PID   40
#define KP_COMM  243
#define KP_PPID  560

static void cmd_ps(void) {
    static char buf[KP_SIZE * 256];
    int mib[3] = {1 /* CTL_KERN */, 14 /* KERN_PROC */, 0 /* KERN_PROC_ALL */};
    size_t sz = sizeof(buf);
    if (sysctl(mib, 3, buf, &sz, (void*)0, 0) != 0) {
        printf("ps: sysctl failed: errno %d\n", errno);
        return;
    }
    puts("  PID  PPID  COMMAND");
    for (size_t off = 0; off + KP_SIZE <= sz; off += KP_SIZE) {
        int pid = *(int *)(buf + off + KP_PID);
        int ppid = *(int *)(buf + off + KP_PPID);
        char comm[17];
        for (int i = 0; i < 16; i++) comm[i] = buf[off + KP_COMM + i];
        comm[16] = '\0';
        printf("%5d %5d  %s\n", pid, ppid, comm);
    }
    printf("ps: %d processes\n", (int)(sz / KP_SIZE));
}

static int parse_uint(const char *s) {
    int v = 0;
    while (s && *s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    return v;
}

/*
 * The kernel keeps a RAM copy of the console (sweetlog) that tools/pull_log.py
 * reads back from lk2nd after a reset, but a reset drops dirty cache lines.
 * Writing a buffer bigger than the 512 KiB L2 pushes the log out to DRAM.
 */
static void flush_log(void) {
    static volatile char evict[2 << 20];
    for (unsigned long i = 0; i < sizeof(evict); i += 64) evict[i]++;
}

/* The kernel fbcon wraps instead of scrolling; a screenful of newlines blanks it */
static void cmd_clear(void) {
    for (int i = 0; i < 100; i++) write(STDOUT_FILENO, "\n", 1);
}

static void execute_line(char *line) {
    while (*line == ' ' || *line == '\t') line++;
    if (*line == '\0' || *line == '#') return;

    char *toks[16];
    int ntoks = 0;
    char *p = strtok(line, " \t\r\n");
    while (p && ntoks < 15) {
        toks[ntoks++] = p;
        p = strtok((void*)0, " \t\r\n");
    }
    toks[ntoks] = (void*)0;
    if (ntoks == 0) return;

    if (strcmp(toks[0], "help") == 0) {
        puts("Available commands:");
        puts("  help            Show this help");
        puts("  uname           Display kernel info");
        puts("  id              Display user and process IDs");
        puts("  ls [path]       List directory contents");
        puts("  dev             Scan /dev for disks and ttys");
        puts("  ps              List running processes");
        puts("  cat <path>      Display file contents");
        puts("  spawn <path>    Spawn binary with posix_spawn");
        puts("  echo <text>     Print text");
        puts("  sleep <secs>    Pause (time to take a photo)");
        puts("  spin <M>        Busy-wait M million loops (no timer needed)");
        puts("  clear           Blank the screen");
        puts("  sync            Sync filesystems");
        puts("  reboot          Reboot device");
    } else if (strcmp(toks[0], "uname") == 0) {
        print_sysinfo();
    } else if (strcmp(toks[0], "id") == 0) {
        printf("uid=%d gid=%d pid=%d ppid=%d\n", getuid(), getgid(), getpid(), getppid());
    } else if (strcmp(toks[0], "ls") == 0) {
        cmd_ls(ntoks > 1 ? toks[1] : "/");
    } else if (strcmp(toks[0], "dev") == 0) {
        cmd_scan_dev();
    } else if (strcmp(toks[0], "cat") == 0) {
        if (ntoks > 1) cmd_cat(toks[1]);
        else puts("usage: cat <path>");
    } else if (strcmp(toks[0], "spawn") == 0) {
        cmd_spawn(ntoks, toks);
    } else if (strcmp(toks[0], "echo") == 0) {
        for (int i = 1; i < ntoks; i++) printf(i > 1 ? " %s" : "%s", toks[i]);
        puts("");
    } else if (strcmp(toks[0], "sleep") == 0) {
        sleep(ntoks > 1 ? parse_uint(toks[1]) : 1);
    } else if (strcmp(toks[0], "ps") == 0) {
        cmd_ps();
    } else if (strcmp(toks[0], "spin") == 0) {
        /* Busy-wait that needs no timer interrupt, unlike sleep */
        unsigned long n = (unsigned long)(ntoks > 1 ? parse_uint(toks[1]) : 100) * 1000000UL;
        for (volatile unsigned long i = 0; i < n; i++) { }
        puts("spin done");
    } else if (strcmp(toks[0], "clear") == 0) {
        cmd_clear();
    } else if (strcmp(toks[0], "sync") == 0) {
        sync();
        puts("synced.");
    } else if (strcmp(toks[0], "reboot") == 0) {
        puts("Rebooting device...");
        sync();
        reboot(1);
    } else {
        printf("Unknown command: %s (type 'help' for commands)\n", toks[0]);
    }
}

static void auto_diagnostics(void) {
    puts("\n--- AUTOMATED BOOT DIAGNOSTICS ---");

    puts("\n[diag 1/4] Scanning /dev for storage and terminals:");
    cmd_scan_dev();

    puts("\n[diag 2/4] Configured LaunchDaemons:");
    cmd_ls("/System/Library/LaunchDaemons");

    puts("\n[diag 3/4] SystemVersion.plist:");
    cmd_cat("/System/Library/CoreServices/SystemVersion.plist");

    puts("\n[diag 4/4] Spawning syslogd (/usr/sbin/syslogd):");
    char *syslog_argv[] = {"/usr/sbin/syslogd", (void*)0};
    pid_t spid = 0;
    int sret = posix_spawn(&spid, "/usr/sbin/syslogd", (void*)0, (void*)0, syslog_argv, environ);
    if (sret == 0) {
        printf("syslogd running with PID %d\n", spid);
    } else {
        printf("syslogd spawn failed: errno %d\n", sret);
    }

    puts("--- DIAGNOSTICS COMPLETE ---\n");
}

#define GTEL_RC "/gtel.rc"

/* Run each line of the boot script through the normal command parser */
static int run_script(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    static char buf[16384];
    ssize_t total = 0, n;
    while (total < (ssize_t)sizeof(buf) - 1 &&
           (n = read(fd, buf + total, sizeof(buf) - 1 - total)) > 0)
        total += n;
    close(fd);
    buf[total] = '\0';

    printf("\n[gtel] Running %s (%d bytes)\n", path, (int)total);
    char *line = buf;
    while (line && *line) {
        char *next = strchr(line, '\n');
        if (next) *next++ = '\0';
        /* Strip comments/blanks before echoing so the screen only shows real commands */
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p && *p != '#' && *p != '\r') {
            printf("gtel-ios# %s\n", p);
            flush_log();
            execute_line(p);
            flush_log();
        }
        line = next;
    }
    printf("[gtel] %s finished.\n", path);
    flush_log();
    return 0;
}

int main(int argc, char **argv) {
    banner();
    print_sysinfo();

    /* Boot script replaces the built-in diagnostics when present */
    if (run_script(GTEL_RC) != 0) {
        puts("\n[gtel] Root filesystem listing (/):");
        cmd_ls("/");
        auto_diagnostics();
    }

    puts("\n[gtel] Interactive bring-up console ready.");
    puts("Type 'help' for available commands.\n");

    char line[256];
    while (1) {
        write(STDOUT_FILENO, "gtel-ios# ", 10);

        int pos = 0;
        while (pos < (int)sizeof(line) - 1) {
            char c;
            ssize_t r = read(STDIN_FILENO, &c, 1);
            if (r <= 0) {
                sleep(1);
                continue;
            }
            if (c == '\r' || c == '\n') {
                write(STDOUT_FILENO, "\n", 1);
                break;
            }
            /* Echo character */
            write(STDOUT_FILENO, &c, 1);
            line[pos++] = c;
        }
        line[pos] = '\0';

        if (pos == 0) continue;
        execute_line(line);
    }

    return 0;
}
