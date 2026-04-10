"""Configuration dataclasses and YAML loader for projector bridge."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from projector_bridge.errors import ConfigError


@dataclass
class ProjectorConfig:
    host: str
    port: int = 53595
    password: str = ""
    timeout_connect: float = 5.0
    timeout_read: float = 3.0
    retries: int = 3
    retry_delay: float = 0.2


@dataclass
class CommandMapping:
    command: str
    repeat: bool = False
    description: str = ""


@dataclass
class IRConfig:
    device_name: str = "gpio_ir_recv"
    protocol: str = "sony"


@dataclass
class Config:
    projector: ProjectorConfig
    mappings: dict[str, CommandMapping]
    ir: IRConfig


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML config file, returning a typed Config instance."""
    path = Path(path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {path}: {e}") from e

    if raw is None:
        raise ConfigError(f"Config file is empty: {path}")

    # Validate projector section
    if "projector" not in raw:
        raise ConfigError("Missing required section: projector")

    proj_raw = raw["projector"]
    if not proj_raw.get("host"):
        raise ConfigError("Missing required field: projector.host")

    projector = ProjectorConfig(
        host=proj_raw["host"],
        port=proj_raw.get("port", 53595),
        password=proj_raw.get("password", ""),
        timeout_connect=proj_raw.get("timeout_connect", 5.0),
        timeout_read=proj_raw.get("timeout_read", 3.0),
        retries=proj_raw.get("retries", 3),
        retry_delay=proj_raw.get("retry_delay", 0.2),
    )

    # Build command mappings
    mappings: dict[str, CommandMapping] = {}
    for key, val in raw.get("mappings", {}).items():
        if not isinstance(val, dict) or "command" not in val:
            raise ConfigError(f"Mapping '{key}' missing required field: command")
        mappings[key] = CommandMapping(
            command=val["command"],
            repeat=val.get("repeat", False),
            description=val.get("description", ""),
        )

    # Build IR config
    ir_raw = raw.get("ir", {})
    ir = IRConfig(
        device_name=ir_raw.get("device_name", "gpio_ir_recv"),
        protocol=ir_raw.get("protocol", "sony"),
    )

    return Config(projector=projector, mappings=mappings, ir=ir)
