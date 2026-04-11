"""Probe the projector for valid ADCP command names."""

import asyncio
from projector_bridge.adcp import send_command_with_retry
from projector_bridge.config import ProjectorConfig

cfg = ProjectorConfig(host="192.168.1.80")

PROBES = [
    # Picture preset command name candidates
    "calibration_preset ?",
    "picture_mode ?",
    "preset ?",
    "pic_preset ?",
    "image_preset ?",
    # Brightness/contrast/sharpness — relative vs absolute
    "brightness ?",
    "contrast ?",
    "sharpness ?",
    # Advanced settings
    "real_cre ?",
    "reality_creation ?",
    "motion_enhancer ?",
    "motionflow ?",
    "contrast_enhancer ?",
    # Key-based commands
    'key "pattern"',
    'key "aspect"',
    'key "3d"',
    'key "color_space"',
    'key "color_temp"',
    'key "gamma"',
    'key "rcp"',
]


async def try_cmd(cmd):
    try:
        r = await send_command_with_retry(cfg, cmd)
        print(f"  OK: {cmd} -> {r}")
    except Exception as e:
        print(f"  ERR: {cmd} -> {e}")


async def main():
    print("Probing projector at 192.168.1.80:53595...\n")
    for cmd in PROBES:
        await try_cmd(cmd)
    print("\nDone. Commands that returned OK are valid.")


if __name__ == "__main__":
    asyncio.run(main())
