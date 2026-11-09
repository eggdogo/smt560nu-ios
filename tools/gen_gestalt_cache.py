#!/usr/bin/env python3
"""Generate an authentic com.apple.MobileGestalt.plist cache for iPad mini 2 (iPad4,4 / 16H81).

Used to eliminate MobileGestalt dynamic resolution fallbacks on non-Apple silicon,
preventing crashes in locationd, SpringBoard, CommCenter, wifid, imagent, ptpd, etc.
"""
import os, plistlib, re, struct, sys

BUILD_VERSION = "16H81"
CACHE_UUID = "34156B22-E548-4F28-827E-7FDBA7A2CF33"
CACHE_DATA_LEN = 3780  # 0xec4 bytes

def load_precacheable_keys():
    """Load all valid precacheable question mappings."""
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    proj_dir = os.path.abspath(os.path.join(cur_dir, ".."))
    
    # Try mapping-gestalt.h
    h_path = os.path.join(proj_dir, "mapping-gestalt.h")
    if not os.path.exists(h_path):
        h_path = os.path.join(cur_dir, "mapping-gestalt.h")
    
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
        "WLANBkgScanCache": True,
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

def generate_plist(out_path):
    """Generate the complete com.apple.MobileGestalt.plist binary file."""
    _, clear_to_obf = load_precacheable_keys()
    cache_extra = build_cache_extra(clear_to_obf)

    cache_dict = {
        "CacheVersion": BUILD_VERSION,
        "CacheUUID": CACHE_UUID,
        "CacheData": b"\x00" * CACHE_DATA_LEN,
        "CacheExtra": cache_extra,
    }

    with open(out_path, "wb") as f:
        plistlib.dump(cache_dict, f, fmt=plistlib.FMT_BINARY)

    size = os.path.getsize(out_path)
    print(f"Generated {out_path} ({size} bytes, {len(cache_extra)} precached properties)")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "com.apple.MobileGestalt.plist"
    generate_plist(out_file)
