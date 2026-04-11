"""Probe the projector for valid ADCP command names."""

import asyncio
from projector_bridge.adcp import send_command_with_retry
from projector_bridge.config import ProjectorConfig

cfg = ProjectorConfig(host="192.168.1.80")

PROBES = [
    # Picture preset values — current is cinema_film1
    'picture_mode "cinema_film1"',
    'picture_mode "cinema_film2"',
    'picture_mode "reference"',
    'picture_mode "tv"',
    'picture_mode "photo"',
    'picture_mode "game"',
    'picture_mode "bright_cinema"',
    'picture_mode "bright_tv"',
    'picture_mode "user"',
    'picture_mode "imax"',
    # Brightness relative — try setting +1/-1 from current (50)
    'brightness "51"',
    'brightness "50"',
    # Contrast enhancer candidates
    "contrast_enhancer ?",
    "adv_contrast ?",
    "dynamic_contrast ?",
    "contrast_remaster ?",
    # Key commands for remaining buttons
    'key "pattern"',
    'key "test_pattern"',
    'key "3d"',
    'key "3D"',
    'key "rcp"',
    'key "menu"',
    'key "up"',
    'key "enter"',
    'key "reset"',
    # Input cycling
    'input ?',
    'input "hdmi1"',
    'input "hdmi2"',
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
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
