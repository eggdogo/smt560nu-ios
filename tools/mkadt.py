#!/usr/bin/env python3
"""Build the Apple Device Tree (ADT) for Samsung Galaxy Tab E 9.6 (SM-T560NU / MSM8916).

Usage:
  mkadt.py OUT.adt [--dump] [--target=ipad|iphone]
"""
import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

# MSM8916 (Snapdragon 410) RAM mapping
# Physical RAM begins at 0x80000000 (total 1.5 GB on SM-T560NU -> ends at 0xe0000000).
# Regions below 0x90000000 are used by lk2nd, boot.img scratch, TrustZone (0x86000000 tz-apps / smem),
# and continuous splash FB (0x8e000000).
# Free contiguous RAM starts safely at 0x90000000 through 0xdf000000 (~1.25 GB).
PHYS_BASE = 0x90000000
MEM_SIZE  = 0x20000000   # 512 MiB: 0x90000000-0xb0000000; 0xb0000000+ is a protected carveout (external abort at 0xb0020000)
PANIC_LOG_SIZE = 0x100000

# MSM8916 Hardware MMIO addresses
SOC_BASE = 0x01000000
GICD_BASE = 0x0b000000
GICD_SIZE = 0x00001000
GICC_BASE = 0x0b002000
GICC_SIZE = 0x00002000

# Qualcomm MSM UARTDM (serial console)
UART_BASE = 0x078b0000
UART_SIZE = 0x00001000

# Display Framebuffer (SM-T560NU NT51017 continuous splash: 800x1280, bpp 3)
FB_BASE   = 0x8e000000
FB_SIZE   = 800 * 1280 * 3  # 3,072,000 bytes
FB_W      = 800
FB_H      = 1280
FB_STRIDE = 2400            # 800 * 3 bytes

# ARM Generic Architected Timer
TIMEBASE  = 19200000     # 19.2 MHz Qualcomm QTimer frequency
VTIMER_INTID = 20        # MSM8916 QGIC2 wires the EL1 virtual timer to PPI 4 (INTID 20), not 27

# MSM8916 has 4x Cortex-A53 cores clocked up to 1.19 GHz
CPU_COUNT = 4
CPU_FREQ  = 1190400000

GTEL_ECID = 0x543536304e550001  # 'T560NU' + 1
BOOT_MANIFEST_HASH = hashlib.sha384(b'gtelwifiue boot manifest').digest()

u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def build(target='ipad'):
    """Generate the Apple Device Tree for SM-T560NU (MSM8916)."""
    phys_base = PHYS_BASE
    mem_size = MEM_SIZE
    panic_base = phys_base + mem_size
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(phys_base)),
        ('dram-size', u64(mem_size)),
        ('random-seed', os.urandom(64)),
        ('debug-enabled', u32(1)),
        ('firmware-version', cstr('lk2nd-gtel-shim')),
        ('system-firmware-version', cstr('lk2nd-gtel-shim')),
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        ('crypto-hash-method', cstr('sha2-384')),
        ('board-id', u32(2)),
        ('chip-id', u32(0x8960)),
        ('unique-chip-id', u64(GTEL_ECID)),
        ('die-id', u64(GTEL_ECID)),
        ('display-corner-radius', u32(0)),
        ('display-scale', u32(2)),
        ('display-rotation', u32(0)),
    ], [
        node('memory-map', [ph()]),
    ])

    # 4x Cortex-A53 Cores
    cpu_nodes = []
    for core in range(CPU_COUNT):
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr('arm,cortex-a53') + cstr('arm,armv8')),
            ('reg', u32(core)),       # MPIDR Aff0 for MSM8916
            ('cpu-id', u32(core)),
            ('cluster-id', u32(0)),
            ('cluster-type', u32(0)), # Homogeneous SMP
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(TIMEBASE)),
            ('clock-frequency', u32(CPU_FREQ)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(533000000)),
            ('peripheral-frequency', u32(TIMEBASE)),
            ('fixed-frequency', u32(TIMEBASE)),
        ]))
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)),
                         ('#size-cells', u32(0))], cpu_nodes)

    # ARM GIC-400 (GICv2)
    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-400') + cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(VTIMER_INTID)),
        ('reg', u64(GICD_BASE - SOC_BASE, GICD_SIZE, GICC_BASE - SOC_BASE, GICC_SIZE)),
    ])

    # Qualcomm MSM UARTDM (serial)
    uart = node('uart', [
        ph(),
        ('compatible', cstr('qcom,msm-uartdm') + cstr('arm,pl011')),
        ('reg', u64(UART_BASE - SOC_BASE, UART_SIZE)),
        ('clock-frequency', u32(TIMEBASE)),
    ])

    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('gtel-io')),
        ('compatible', cstr('gtel-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
        ('soc-generation', cstr('H6')),
        ('chip-revision', u32(0)),
    ], [
        gic,
        uart,
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('gtel,display') + cstr('sweet,display')),
            ('canvas-width', u32(FB_W)),
            ('canvas-height', u32(FB_H)),
            ('backlight-control', u32(1)),
        ])
    ])

    # Framebuffer console node (using 600x4 = 2400 stride mapping for 24bpp scanline alignment)
    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(FB_BASE, FB_SIZE)),
        ('width', u32(600)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    # Buttons: volume up, volume down, power, and physical Home button!
    # Samsung Galaxy Tab E has a physical Home button (home-button-type = 0)
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold') + cstr('menu')),
        ('home-button-type', u32(0)), # Physical home button
    ])

    defaults = node('defaults', [
        ph(),
        ('no-effaceable-storage', u32(1)),
        ('panic-reset-type', u32(1)),
        ('kern.maxvnodes', u32(3700)),
        ('kern.maxkfsevents', u32(1024)),
        ('kern.max_task_pmem', u32(700)),
        ('kern.io_throttle_period_tier3', u32(20)),
        ('kern.io_throttle_window_tier3', u32(100)),
        ('kern.hibernation_min_processes', u32(4)),
        ('kern.vm_compressor', u32(32)),
        ('cpx-encryption-mode', u32(0)),
    ])

    # Authentic iPad mini 2 (iPad4,4 / J85AP) Product Configuration
    camera = node('camera', [
        ph(),
        ('front-max-video-fps-720p', u32(30)),
        ('front-burst-image-duration', u32(100)),
        ('post-effects', u32(1)),
        ('auto-focus', u32(1)),
        ('rear-max-video-fps-1080p', u32(30)),
        ('panorama', u32(1)),
        ('front-max-video-zoom', u32(1)),
        ('rear-max-video-zoom', u32(3)),
        ('rear-hdr-on', u32(1)),
        ('video-cap', u32(2)),
        ('rear-burst-image-duration', u32(100)),
        ('rear-hdr', u32(1)),
        ('rear-max-video-fps-720p', u32(30)),
    ])
    facetime = node('facetime', [
        ph(),
        ('tnr-mode-back', u32(10)),
        ('decoding', b'@\x01\x00\x00\x0f\x00\xf0\x00\xe0\x01\x00\x00\x0f\x00p\x01\x80\x02\x00\x00\x1e\x00\xe0\x01\x00\x04\x00\x00\x1e\x00\x00\x03'),
        ('tnr-mode-front', u32(10)),
        ('pref-decoding', b'\x00\x04\x00\x00\x1e\x00\x00\x03'),
        ('bitrate-wifi', u32(2000)),
        ('encoding', b'@\x01\x00\x00\x0f\x00\xf0\x00@\x01\x00\x00\x1e\x00\xf0\x00\xe0\x01\x00\x00\x0f\x00p\x01\xe0\x01\x00\x00\x1e\x00p\x01\x80\x02\x00\x00\x1e\x00\xe0\x01\x00\x04\x00\x00\x1e\x00\x00\x03\x00\x05\x00\x00\x1e\x00\xd0\x02'),
    ])
    maps = node('maps', [
        ph(),
        ('3d-imagery', u32(0)),
        ('3d-maps', u32(0)),
    ])
    product = node('product', [
        ph(),
        ('graphics-featureset-fallbacks', cstr('GLES2,0')),
        ('device-perf-memory-class', u32(1)),
        ('artwork-device-subtype', u32(0)),
        ('product-description', cstr('iPad mini 2')),
        ('display-mirroring', u32(1)),
        ('builtin-mics', u32(2)),
        ('allow-32bit-apps', u32(1)),
        ('compatible-device-fallback', cstr('0')),
        ('mobiledevice-beta-min-ver', cstr('0.0.0.0.0')),
        ('hearingaid-low-energy-audio', u32(1)),
        ('device-color-policy', u32(0)),
        ('iap2-protocol-supported', u32(1)),
        ('sandman-support', u32(0)),
        ('itunes-min-ver', b'\x02\x02\x0c\x00'),
        ('RF-exposure-separation-distance', u32(5)),
        ('single-stage-boot', u32(0)),
        ('peek-ui-width', u32(346)),
        ('ui-background-quality', u32(100)),
        ('graphics-featureset-class', cstr('MTL1,2')),
        ('ui-pip', b''),
        ('mobiledevice-min-ver', cstr('988.200.73')),
        ('ui-traffic-cheap-shaders', b''),
        ('wifi-chipset', cstr('4324')),
        ('ui-weather-quality', u32(100)),
        ('ptp-large-files', u32(1)),
        ('artwork-dynamic-displaymode', cstr('0')),
        ('assistant', u32(1)),
        ('product-name', cstr('iPad mini 2')),
        ('product-id', b'b\xa3\x0fq\xd8mDt\xe4\x11\xe4z\x95\\\x17R|\xc1\xaej'),
        ('bluetooth-le', u32(1)),
        ('thin-bezel', u32(1)),
        ('dictation', u32(1)),
        ('lockdown-certtype', u32(1)),
        ('device-colors', cstr('syscfg/DClr')),
        ('udid-version', u32(1)),
        ('artwork-scale-factor', u32(2)),
        ('artwork-device-idiom', cstr('pad')),
        ('artwork-display-gamut', cstr('sRGB')),
    ], [camera, facetime, maps])

    # Target identity: default iPad mini 2 (iPad4,4 / J85AP) or iPhone 6 (iPhone7,2 / N61AP)
    if target == 'iphone':
        model_name = 'iPhone7,2'
        board_id   = 'N61AP'
        target_name = 'N61'
    else:
        model_name = 'iPad4,4'
        board_id   = 'J85AP'
        target_name = 'J85'

    return node('device-tree', [
        ph(),
        ('compatible', cstr(board_id) + cstr(model_name) + cstr('xiaomi,sweet') + cstr('samsung,gtelwifiue') + cstr('qcom,msm8916') + cstr('AppleARM')),
        ('model', cstr(model_name)),
        ('target-type', cstr(target_name)),
        ('target-sub-type', cstr(board_id)),
        ('manufacturer', cstr('Apple Inc.')),
        ('serial-number', cstr('DLXLT001FCM5')),
        ('model-number', cstr('ME276LL/A')),
        ('regulatory-model-number', cstr('A1489')),
        ('region-info', cstr('LL/A')),
        ('mlb-serial-number', cstr('DLX4123001AFCM5A1')),
        ('config-number', cstr('ME276')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon, buttons, product])


if __name__ == '__main__':
    target = 'ipad'
    if '--target=iphone' in sys.argv:
        target = 'iphone'
    out_file = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'gtel.adt'
    root = build(target=target)
    blob = adt.serialize(root)
    open(out_file, 'wb').write(blob)
    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])
    print(f'Wrote {out_file} ({len(blob)} bytes) [Target: {target}]', file=sys.stderr)
