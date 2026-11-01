#!/usr/bin/env python3
"""Run SM-T560NU Boot Shim in QEMU virt (Cortex-A53).

Simulates the lk2nd EL1 boot flow for local testing without physical hardware.
"""
import os, subprocess, sys

SHIM_IMG = os.path.join(os.path.dirname(__file__), '../shim/out/Image')

def main():
    if not os.path.exists(SHIM_IMG):
        print(f"Error: {SHIM_IMG} does not exist. Run 'cd shim && bash build.sh' first.")
        sys.exit(1)

    cmd = [
        'qemu-system-aarch64',
        '-M', 'virt',
        '-cpu', 'cortex-a53',
        '-smp', '4',
        '-m', '2G',
        '-kernel', SHIM_IMG,
        '-nographic',
        '-serial', 'mon:stdio',
    ]

    print(f"Starting QEMU Cortex-A53 simulation: {' '.join(cmd)}")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nQEMU terminated.")

if __name__ == '__main__':
    main()
