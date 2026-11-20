# SPDX-License-Identifier: GPL-3.0-or-later
"""Locate shipped data (palette, templates) in the repo checkout or in /usr/share/nebulix."""
import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
_CANDIDATES = [Path(os.environ["NEBULIX_DATA"]) if os.environ.get("NEBULIX_DATA") else None,
               PKG.parent, Path("/usr/share/nebulix")]


def data_dir() -> Path:
    for c in _CANDIDATES:
        if c and (c / "palette.json").exists() and (c / "templates").is_dir():
            return c
    raise FileNotFoundError("palette.json/templates not found (set NEBULIX_DATA)")


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def conf_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config")


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local/share")


def state_dir() -> Path:
    return data_home() / "nebulix"


def config_file() -> Path:
    return conf_home() / "nebulix" / "config.toml"
