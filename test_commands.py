"""Probe the projector for valid ADCP command names."""

import asyncio
from projector_bridge.adcp import send_command_with_retry
from projector_bridge.config import ProjectorConfig

cfg = ProjectorConfig(host="192.168.1.80")

PROBES = [
    # Brightness set — try unquoted numeric
    "brightness 51",
    "brightness 50",
    # Bright Cinema/TV name variants
    'picture_mode "bravia_cinema"',
    'picture_mode "brt_cine"',
    'picture_mode "brt_cinema"',
    'picture_mode "brightcine"',
    'picture_mode "cinema_bright"',
    'picture_mode "brt_tv"',
    'picture_mode "bravia_tv"',
    # Contrast enhancer / HDR enhancer variants
    "hdr ?",
    "hdr_enhance ?",
    "dynamic_range ?",
    "dci ?",
    "tone_mapping ?",
    # Motionflow values (current is true_cinema)
    "motionflow ?",
    # Gamma
    "gamma ?",
    # Color space
    "color_space ?",
    "color ?",
    # Color temp
    "color_temp ?",
    # Reality creation current
    "real_cre ?",
    # Key names — more attempts
    'key "colorspace"',
    'key "color"',
    'key "gammaCorrection"',
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
