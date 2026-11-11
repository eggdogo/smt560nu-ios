#!/usr/bin/env python3
"""Generate an authentic com.apple.MobileGestalt.plist cache for iPad mini 2 (iPad4,4 / 16H81).

Used to eliminate MobileGestalt dynamic resolution fallbacks on non-Apple silicon,
preventing crashes in locationd, SpringBoard, CommCenter, wifid, imagent, ptpd, etc.
"""
import os, plistlib, re, struct, sys

BUILD_VERSION = "16H81"
CACHE_UUID = "34156B22-E548-4F28-827E-7FDBA7A2CF33"
CACHE_DATA_LEN = 3780  # 0xec4 bytes
# Local working tree holding mapping-gestalt.h and the extracted 16H81 ramdisk
PROJECT_DIR = os.path.expanduser(os.path.join("~", "Documents", "Projects", "iosont560nu"))

def load_precacheable_keys():
    """Load all valid precacheable question mappings."""
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    proj_dir = os.path.abspath(os.path.join(cur_dir, ".."))
    
    # Try mapping-gestalt.h
    h_path = os.path.join(proj_dir, "mapping-gestalt.h")
    for cand in (os.path.join(cur_dir, "mapping-gestalt.h"), os.path.join(PROJECT_DIR, "mapping-gestalt.h")):
        if not os.path.exists(h_path):
            h_path = cand

    with open(h_path) as f:
        obf_to_clear = dict(re.findall(r'"([^"]+)",\s*"([^"]+)"', f.read()))
    clear_to_obf = {v: k for k, v in obf_to_clear.items()}
    return obf_to_clear, clear_to_obf

def build_cache_extra(clear_to_obf):
    """Build the CacheExtra dictionary for iPad mini 2 (iPad4,4 / J85AP)."""
    # Key-value map using clear names
    props = {
        # Device Identification
        "ProductType": "iPad4,4",
        "ProductVersion": "12.5.7",
        "BuildVersion": BUILD_VERSION,
        "HWModelStr": "J85AP",
        "DeviceClass": "iPad",
        "DeviceName": "iPad",
        "ModelNumber": "ME276LL/A",
        "RegionInfo": "LL/A",
        "RegulatoryModelNumber": "A1489",
        "BoardId": 2,
        "ChipID": 0x8960,
        "CPUArchitecture": "arm64",
        "CPUType": 0x0100000C,      # CPU_TYPE_ARM64
        "CPUSubType": 1,            # CPU_SUBTYPE_ARM64_V8
        "SupportedDeviceFamilies": [2], # 1 = iPhone/iPod, 2 = iPad
        "ipad": True,
        "Allow32BitApps": True,

        # Display & Graphics
        "ArtworkTraits": {
            "artwork-device-idiom": "pad",
            "artwork-scale-factor": 2,
            "artwork-display-gamut": "sRGB",
            "artwork-dynamic-displaymode": "0",
            "artwork-device-subtype": 0,
        },
        "main-screen-scale": 2,
        "main-screen-pitch": 326,
        "main-screen-class": 2,
        "main-screen-orientation": 0,
        "MainDisplayRotation": 0,
        "MainScreenStaticInfo": {
            "main-screen-scale": 2,
            "main-screen-width": 1536,
            "main-screen-height": 2048,
            "main-screen-orientation": 0,
            "main-screen-pitch": 326,
            "main-screen-class": 2,
        },
        "DeviceSupportsASTC": True,
        "DevicePrefersProceduralAntiAliasing": True,
        "DevicePrefersTrafficAlpha": True,
        "RenderWideGamutImagesAtDisplayTime": False,
        "HasExtendedColorDisplay": False,
        "OLEDDisplay": False,
        "display-mirroring": True,
        "airplay-mirroring": True,
        "UIParallaxCapability": True,
        "UIProceduralWallpaperCapability": True,
        "homescreen-wallpaper": True,
        "UIBackgroundQuality": 100,

        # Multitasking (iPad specific)
        "MedusaPIPCapability": True,
        "MedusaPinnedAppCapability": True,
        "MedusaOverlayAppCapability": True,
        "MedusaFloatingLiveAppCapability": True,
        "MedusaOverlayAppCapability": True,
        "PeekUICapability": False,
        "ScreenRecorderCapability": True,
        "StarkCapability": False,
        "accessibility": True,
        "assistant": True,
        "dictation": True,

        # Hardware & Sensors
        "accelerometer": True,
        "ambient-light-sensor": True,
        "hall-effect-sensor": True,
        "proximity-sensor": False,
        "hardware-keyboard": False,
        "volume-buttons": True,
        "voice-control": True,
        "VibratorCapability": False,
        "BacklightCapability": True,
        "stand-alone-contacts": True,
        "location-services": True,
        "CoreRoutineCapability": True,
        "SupportsLowPowerMode": True,
        "SupportsForceTouch": False,
        "SupportsIrisCapture": False,
        "SupportsRotateToWake": False,
        "SupportsSOS": False,
        "SupportsTouchRemote": False,
        "TouchDelivery120Hz": False,
        "WirelessChargingCapability": False,
        "HasAppleNeuralEngine": False,

        # Networking & Wireless
        "wifi": True,
        "WifiVendor": "Broadcom",
        "WifiChipset": "4324",
        "bluetooth": True,
        "AWDLCapability": True,
        "AirDropCapability": True,
        "ContinuityCapability": True,
        "iAP2Capability": True,
        "wapi": False,
        "WLANBkgScanCache": 1,
        "telephony": False,
        "any-telephony": False,
        "data-plan": False,

        # Audio
        "AudioPlaybackCapability": True,
        "unified-ipod": True,
        "TimeSyncCapability": True,

        # Cameras
        "still-camera": True,
        "video-camera": True,
        "video-stills": True,
        "camera-flash": False,
        "camera-front-flash": False,
        "auto-focus-camera": True,
        "RearCameraCapability": True,
        "ForwardCameraCapability": True,
        "PanoramaCameraCapability": True,
        "CameraLiveEffectsCapability": True,
        "CameraMaxBurstLength": 100,
        "FrontFacingCameraHDRCapability": True,
        "RearFacingCameraHDRCapability": True,
        "FrontFacingCameraHDROnCapability": True,
        "RearFacingCameraHDROnCapability": True,
        "FrontFacingCameraVideoCapture720pMaxFPS": 30,
        "RearFacingCameraVideoCapture720pMaxFPS": 30,
        "RearFacingCameraVideoCapture1080pMaxFPS": 30,
        "FrontFacingCameraMaxVideoZoomFactor": 1,
        "RearFacingCameraMaxVideoZoomFactor": 3,
        "FrontFacingCameraStillDurationForBurst": 100,
        "RearFacingCameraStillDurationForBurst": 100,
        "FaceTimeCameraRequiresFastSwitchOptions": False,
        "FaceTimeCameraSupportsHardwareFaceDetection": True,
        "FaceTimeBackCameraTemporalNoiseReductionMode": 10,
        "FaceTimeFrontCameraTemporalNoiseReductionMode": 10,
        "PhotosPostEffectsCapability": True,
        "PhotoSharingCapability": True,
        "CloudPhotoLibraryCapability": True,

        # Codecs
        "H264EncoderCapability": True,
        "HEVCEncodingCapability": False,
        "PipelinedStillImageProcessingCapability": False,

        # System Software
        "AppStore": True,
        "applicationInstallation": True,
        "shoebox": True,
        "siri-gesture": False,
        "SoftwareDimmingAlpha": 1.0,
    }

    cache_extra = {}
    for clear_name, val in props.items():
        obf = clear_to_obf.get(clear_name)
        if not obf:
            print(f"Warning: clear key {clear_name} not found in mapping", file=sys.stderr)
            continue
        cache_extra[obf] = val

    return cache_extra

# libMobileGestalt (16H81) question table: __DATA_CONST 0x3c9e8, 0x69c slots of 0xa0 bytes.
# +0x00 key name ptr, +0x98 flags (0x10 = precacheable), +0x9a int16 cache index, +0x9c int32 type.
MG_TABLE, MG_SLOTS, MG_STRIDE = 0x3c9e8, 0x69c, 0xa0
N_INDEX = 0x1a4               # CacheData = N_INDEX 8-byte value slots + N_INDEX "present" bytes
# The loader memcpy()s CacheData into its fast table and reads scalars back raw
# (store routine at 0x453c): 5 = SInt32, 6 = SInt64, 7 = Float32, 11 = bool byte.
# Every other type is a CF object and must come from CacheExtra, which is stored as a
# retained pointer -- so a scalar placed in CacheExtra would read back as pointer bits.
SCALAR = {5: '<i', 6: '<q', 7: '<f', 11: '<B'}
DEFAULT_DYLIB = os.path.join(PROJECT_DIR, 'ramdisk_extracted', 'PeaceUpdate16H81.arm64CustomerRamDisk',
    'usr', 'lib', 'libMobileGestalt.dylib')


def load_question_table(dylib):
    d = open(dylib, 'rb').read()
    table = {}
    for k in range(MG_SLOTS):
        e = d[MG_TABLE + k * MG_STRIDE:MG_TABLE + (k + 1) * MG_STRIDE]
        if not any(e):
            continue
        p = struct.unpack_from('<Q', e, 0)[0] & 0xffffffff
        name = d[p:d.index(b'\0', p)].decode()
        table[name] = (e[0x98], struct.unpack_from('<h', e, 0x9a)[0], struct.unpack_from('<i', e, 0x9c)[0])
    return table


def generate_plist(out_path, dylib=DEFAULT_DYLIB):
    """Generate the complete com.apple.MobileGestalt.plist binary file."""
    obf_to_clear, clear_to_obf = load_precacheable_keys()
    answers = build_cache_extra(clear_to_obf)
    table = load_question_table(dylib)

    data = bytearray(CACHE_DATA_LEN)
    cache_extra = {}
    for obf, val in answers.items():
        flags, idx, ty = table.get(obf, (0, -1, 0))
        name = obf_to_clear.get(obf, obf)
        if not flags & 0x10 or not 0 <= idx < N_INDEX:
            sys.exit(f"{name} is not precacheable: one such key invalidates the whole cache")
        if ty in SCALAR:
            if ty == 11 and not isinstance(val, bool):
                sys.exit(f"{name} is a bool question, got {val!r}")
            if ty in (5, 6) and (isinstance(val, bool) or not isinstance(val, int)):
                sys.exit(f"{name} is an integer question, got {val!r}")
            struct.pack_into(SCALAR[ty], data, idx * 8, val)
            data[N_INDEX * 8 + idx] = 1
        else:
            if isinstance(val, (bool, int, float)) and ty != 4:
                sys.exit(f"{name} (type {ty}) needs a CF object, got {val!r}")
            cache_extra[obf] = val

    cache_dict = {
        "CacheVersion": BUILD_VERSION,
        "CacheUUID": CACHE_UUID,
        "CacheData": bytes(data),
        "CacheExtra": cache_extra,
    }

    with open(out_path, "wb") as f:
        plistlib.dump(cache_dict, f, fmt=plistlib.FMT_BINARY)

    size = os.path.getsize(out_path)
    n_data = sum(data[N_INDEX * 8:])
    print(f"Generated {out_path} ({size} bytes): {n_data} scalars in CacheData, "
          f"{len(cache_extra)} objects in CacheExtra")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "com.apple.MobileGestalt.plist"
    generate_plist(out_file, *sys.argv[2:3])
