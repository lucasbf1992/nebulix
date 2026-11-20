# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme catalogue (palette.json): base colours, accents and the default package of each theme."""
import json

from . import paths

ALIASES = {"macos": "macos-dark", "claro": "macos-light", "light": "macos-light", "macos-claro": "macos-light",
           "nebulix-claro": "nebulix-light"}
# keys a theme changes when it is chosen ("pacote"); each stays adjustable afterwards
PACKAGE_KEYS = ("window_buttons", "topbar", "radius", "icons", "dock", "dock_opacity", "variant")


def load_all() -> dict:
    return json.loads((paths.data_dir() / "palette.json").read_text())


def ids():
    return tuple(load_all()["themes"])


def resolve(name: str) -> str:
    name = ALIASES.get(name, name)
    if name not in load_all()["themes"]:
        raise ValueError(f"tema inválido: {name!r} (use {', '.join(ids())})")
    return name


def get(name: str) -> dict:
    return load_all()["themes"][name]


def accent_names(name: str):
    return tuple(get(name)["accents"])


def accent_hex(theme: str, accent: str) -> str:
    th = get(theme)
    if accent == "auto":
        accent = th["default_accent"]
    a = th["accents"].get(accent)
    return (a["hex"] if a else accent).upper()


def gnome_accent(theme: str, accent: str) -> str:
    th = get(theme)
    if accent == "auto":
        accent = th["default_accent"]
    a = th["accents"].get(accent)
    return a["gnome"] if a else th["gnome_accent_default"]
