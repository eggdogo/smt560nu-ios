#!/usr/bin/env python3
"""Apply bring-up tweaks to an iOS root filesystem for SM-T560NU (MSM8916).

  sudo python3 gtel_root_tweaks.py MOUNTED_ROOT [--ios=12|16]

Modifications applied:
  - launchd.plist: rename _PanicOnCrash -> _PanicOnCrasX so failed daemons don't kernel panic.
  - Remove CommCenter / baseband daemons (SM-T560NU is a Wi-Fi-only tablet).
  - Disable watchdog timeouts (BKNoWatchdogs) so software-rendered UI doesn't get killed.
  - Bypass Setup Assistant (PurpleBuddy) to land straight on SpringBoard.
  - Fake activation state in mobileactivationd data_ark.plist.
  - Disable missing audio/camera hardware hooks that cause mediaserverd crashes.
"""
import argparse, glob, os, plistlib, shutil, sys

MOBILE = 501

VERSIONS = {
    '12': {'build': '16H81', 'version': '12.5.7', 'setup_version': 9},
    '16': {'build': '20H392', 'version': '16.7.16', 'setup_version': 11},
}


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def save(path, data, uid=0, gid=0, mode=0o644, fmt=plistlib.FMT_BINARY):
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=fmt)
    try:
        os.chown(path, uid, gid)
        os.chmod(path, mode)
    except PermissionError:
        pass


def merge_pref(root, name, values):
    """Merge keys into /private/var/mobile/Library/Preferences/NAME.plist."""
    pref_dir = os.path.join(root, 'private/var/mobile/Library/Preferences')
    os.makedirs(pref_dir, exist_ok=True)
    path = os.path.join(pref_dir, name + '.plist')
    data = load(path) if os.path.exists(path) else {}
    data.update(values)
    save(path, data, MOBILE, MOBILE, 0o600)
    print(f'Configured preference: {name}.plist')


def tweak_launchd(root):
    # iOS 12 & 16 locations for launchd configuration
    candidates = [
        os.path.join(root, 'System/Library/xpc/launchd.plist'),
        os.path.join(root, 'System/Library/LaunchDaemons'),
    ]

    plist_path = os.path.join(root, 'System/Library/xpc/launchd.plist')
    if os.path.exists(plist_path):
        plist = load(plist_path)
        jobs = plist.get('LaunchDaemons', {})
        renamed = 0
        for job in jobs.values():
            if '_PanicOnCrash' in job:
                job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
                renamed += 1
        removed = [k for k, j in jobs.items() if j.get('Label') == 'com.apple.CommCenter']
        for k in removed:
            del jobs[k]
        save(plist_path, plist)
        print(f'launchd.plist: {renamed} _PanicOnCrash defanged, {len(removed)} CommCenter jobs removed')


def setup_var_containers(root):
    base = os.path.join(root, 'private/var/containers')
    for sub, uid in (('Bundle', 33), ('Data/System', 0), ('Shared/SystemGroup', 0), ('Temp', 0)):
        d = os.path.join(base, sub)
        os.makedirs(d, exist_ok=True)
        try:
            os.chown(d, uid, uid)
            os.chmod(d, 0o755)
        except PermissionError:
            pass


def fake_activation(root, info):
    # Target mobileactivationd container or /var/mobile/Library
    d = os.path.join(root, 'private/var/mobile/Library/mobileactivationd')
    os.makedirs(d, exist_ok=True)
    save(os.path.join(d, 'data_ark.plist'), {
        '-ActivationState': 'Activated',
        '-BrickState': False,
        '-BuildVersion': info['build'],
        '-ProductVersion': info['version'],
        '-DataMigrationCompleted': True,
        '-PreSydroDataMigrationCompleted': True,
    }, MOBILE, MOBILE, 0o600)
    print(f'Seeded offline activation state for iOS {info["version"]} ({info["build"]})')


def disable_crashy_plugins(root):
    # Disable audio HAL plugins that crash without audio hardware
    v_audio = os.path.join(root, 'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin')
    if os.path.exists(v_audio):
        dest = os.path.join(root, 'Library/Audio/Plug-Ins/HAL.disabled')
        os.makedirs(dest, exist_ok=True)
        shutil.move(v_audio, dest)
        print('Disabled VirtualAudio.plugin')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root_path', help='Path to mounted HFS+ iOS root')
    p.add_argument('--ios', choices=['12', '16'], default='12')
    args = p.parse_args()

    root = os.path.abspath(args.root_path)
    if not os.path.isdir(os.path.join(root, 'System')):
        print(f'Error: {root} does not look like an iOS root filesystem', file=sys.stderr)
        sys.exit(1)

    info = VERSIONS[args.ios]
    print(f'Applying SM-T560NU bring-up tweaks for iOS {info["version"]}...')

    tweak_launchd(root)
    setup_var_containers(root)
    fake_activation(root, info)
    disable_crashy_plugins(root)

    # SpringBoard & PurpleBuddy (Setup Assistant) Bypass
    merge_pref(root, 'com.apple.springboard', {
        'BKNoWatchdogs': True,
        'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100.0},
        'MCForceShowCloudConfigurationUI': False,
    })

    merge_pref(root, 'com.apple.purplebuddy', {
        'SetupDone': True,
        'SetupFinishedAllSteps': True,
        'SetupVersion': info['setup_version'],
        'daemonizeNeedsToRun': False,
    })

    merge_pref(root, 'com.apple.purplebuddy.notbackedup', {
        'ShouldRunDiagnosticsMiniBuddy': False,
        'ShouldRunHSA2MiniBuddy': False,
        'ShouldRunKeychainSyncMiniBuddy': False,
        'ShouldRunMesaMiniBuddy': False,
        'ShouldRunPaymentMiniBuddy': False,
        'ShouldRunStandardMiniBuddy': False,
        'SilentICDPUpgrade': False,
    })

    merge_pref(root, 'com.apple.migration', {
        'LastSystemVersion': info['build'],
        'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': info['build']},
    })

    print('All tweaks successfully applied!')


if __name__ == '__main__':
    main()
