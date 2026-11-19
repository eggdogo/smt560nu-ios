#!/usr/bin/env python3
"""Live kernel-log watcher over the XNU USB fastboot gadget (no lk2nd needed).

The gtel gadget (patch 0107) serves the whole kernel log ring on `upload`
and its length on `getvar:log-size`.  This tool polls the length, pulls the ring
only when it grew, saves every snapshot to disk (so a panic that drops the
device still leaves the last good log), prints new lines as they appear, and
recovers from USB timeouts by resetting and re-finding the device.

  python tools/xlog.py watch -o log.txt                 # follow a running XNU
  python tools/xlog.py run shim-boot.img -o log.txt     # boot from lk2nd, then follow
  python tools/xlog.py pull -o log.txt                  # one snapshot, with retries

Common options: --seconds N (stop after N s), --until REGEX (stop when the
new log text matches), --interval S, --finish reboot-bootloader|poweroff|none.
"""
import argparse
import os
import re
import sys
import time

import usb.core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyfastboot import FastbootDevice  # noqa: E402

PRODUCT = 'gtel-xnu-ios'


def log(msg):
    print(f'[xlog {time.strftime("%H:%M:%S")}] {msg}', flush=True)


def open_dev(want_xnu=True):
    """Open the fastboot device; None if absent. With want_xnu, require the gadget."""
    try:
        fb = FastbootDevice()
    except Exception:
        return None
    if want_xnu:
        try:
            if PRODUCT not in fb.getvar('product'):
                return None
        except Exception:
            return None
    return fb


def reset_dev():
    try:
        d = usb.core.find(idVendor=0x18d1, idProduct=0xd00d)
        if d:
            d.reset()
    except Exception:
        pass


def log_size(fb):
    v = fb.getvar('log-size').strip().split()
    return int(v[-1]) if v and v[-1].isdigit() else None


def fetch(fb, have, state):
    """Return the whole log so far. Uses incremental `upload:<offset>` windows when the gadget
    supports them (a full dump stalls above 64 KiB); otherwise falls back to the old full dump."""
    if state.get('windowed', True):
        try:
            buf = bytearray(have)
            end = log_size(fb)
            while end is not None and len(buf) < end:
                part = fb.upload_from(len(buf))
                if not part:
                    break
                buf += part
            return bytes(buf)
        except RuntimeError:  # old gadget: "FAILunknown command"
            state['windowed'] = False
            log('gadget has no upload:<offset>; using full dumps (limit ~64 KiB)')
            fb.drain()
    return fb.upload(timeout=15000)


def write_atomic(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def watch(args):
    out = args.out
    last_size = -1
    last_data = b''
    printed = 0
    started = time.time()
    seen_gadget = False
    gone_since = None
    hiccups = 0
    state = {}
    pattern = re.compile(args.until) if args.until else None
    fb = None

    log(f'watching for {PRODUCT} (interval {args.interval}s, out {out})')
    while True:
        if args.seconds and time.time() - started > args.seconds:
            log(f'time limit {args.seconds}s reached')
            break

        if fb is None:
            fb = open_dev()
            if fb is None:
                if seen_gadget:
                    gone_since = gone_since or time.time()
                    if time.time() - gone_since > args.gone_timeout:
                        log(f'device gone for {args.gone_timeout}s (panic/reset?) - '
                            f'last good log kept in {out}')
                        return 2
                elif time.time() - started > args.wait_timeout:
                    log(f'gadget never appeared within {args.wait_timeout}s')
                    return 1
                time.sleep(1)
                continue
            if not seen_gadget:
                log('gadget is up')
            seen_gadget = True
            gone_since = None

        try:
            fb.drain()
            size = log_size(fb)
            if size is not None and size == last_size:
                time.sleep(args.interval)
                continue
            fb.drain()
            data = fetch(fb, last_data, state)
            hiccups = 0
        except Exception as e:  # timeout / pipe error / device vanished
            hiccups += 1
            log(f'USB hiccup #{hiccups} ({type(e).__name__})')
            if hiccups >= 3:  # a reset re-enumerates the gadget, so only as a last resort
                log('3 hiccups in a row; resetting the device')
                reset_dev()
                hiccups = 0
            fb = None
            gone_since = gone_since or time.time()
            time.sleep(2)
            continue

        gone_since = None
        if len(data) >= len(last_data):
            write_atomic(out, data)
            new = data[len(last_data):] if data.startswith(last_data) else data[-(len(data) - printed):]
            last_data, last_size = data, size if size is not None else len(data)
            printed = len(data)
            text = new.decode('utf-8', errors='replace')
            if text.strip():
                sys.stdout.write(text if args.follow else '')
                sys.stdout.flush()
            log(f'{len(data)} bytes (+{len(new)})')
            if pattern and pattern.search(text):
                log(f'matched --until /{args.until}/')
                break
        time.sleep(args.interval)

    if fb is None:
        fb = open_dev()
    if fb is not None and args.finish != 'none':
        try:
            if args.finish == 'reboot-bootloader':
                fb.reboot('bootloader')
            elif args.finish == 'poweroff':
                fb.poweroff()
        except Exception as e:
            log(f'finish action: {e}')
    log(f'done; log in {out} ({len(last_data)} bytes)')
    return 0


def cmd_run(args):
    fb = None
    for _ in range(30):
        fb = open_dev(want_xnu=False)
        if fb:
            break
        time.sleep(1)
    if fb is None:
        log('no fastboot device (put the tablet in lk2nd first)')
        return 1
    prod = fb.getvar('product')
    if PRODUCT in prod:
        log('XNU is already running; use `watch` instead')
        return 1
    log(f'booting {args.image} on {prod.strip()}')
    fb.boot(args.image)
    time.sleep(args.settle)
    return watch(args)


def cmd_pull(args):
    for attempt in range(1, args.tries + 1):
        fb = open_dev()
        if fb:
            try:
                data = fb.upload(timeout=15000)
                write_atomic(args.out, data)
                log(f'wrote {len(data)} bytes to {args.out}')
                return 0
            except Exception as e:
                log(f'attempt {attempt}: {type(e).__name__}')
                reset_dev()
        time.sleep(2)
    log('pull failed')
    return 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def common(sp):
        sp.add_argument('-o', '--out', default='xlog.txt')
        sp.add_argument('--interval', type=float, default=5.0)
        sp.add_argument('--seconds', type=int, default=0, help='stop after N seconds (0 = until stopped)')
        sp.add_argument('--until', help='stop when new log text matches this regex')
        sp.add_argument('--follow', action='store_true', help='print new log text to stdout')
        sp.add_argument('--gone-timeout', type=int, default=20, help='give up this long after the device drops')
        sp.add_argument('--wait-timeout', type=int, default=180, help='give up if the gadget never appears')
        sp.add_argument('--finish', choices=['reboot-bootloader', 'poweroff', 'none'], default='none')

    w = sub.add_parser('watch')
    common(w)
    r = sub.add_parser('run')
    r.add_argument('image')
    r.add_argument('--settle', type=int, default=15, help='seconds to wait after boot before polling')
    common(r)
    g = sub.add_parser('pull')
    g.add_argument('-o', '--out', default='xlog.txt')
    g.add_argument('--tries', type=int, default=5)

    args = p.parse_args()
    try:
        sys.exit({'watch': watch, 'run': cmd_run, 'pull': cmd_pull}[args.cmd](args))
    except KeyboardInterrupt:
        log('interrupted; last good log is on disk')
        sys.exit(130)


if __name__ == '__main__':
    main()
