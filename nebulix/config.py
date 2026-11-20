# SPDX-License-Identifier: GPL-3.0-or-later
"""User configuration (~/.config/nebulix/config.toml)."""
import re
import tomllib

from . import paths

ACCENTS = {"nebulix": "#A66BFF", "magenta": "#FF4FD8", "cyan": "#3BE8E8",
           "blue": "#7C8CFF", "green": "#5CF2A0", "amber": "#F5D76E"}
GNOME_ACCENT = {"nebulix": "purple", "magenta": "pink", "cyan": "teal", "blue": "blue", "green": "green", "amber": "yellow"}
COMPONENTS = ("gtk", "shell", "terminal", "starship", "fastfetch", "btop", "vscode", "nvim", "wallpaper", "icons")
CHOICES = {
    "variant": ("dark", "darker"),
    "window_buttons": ("gnome", "mac"),
    "topbar": ("floating", "solid"),
    "dock": ("macos", "ubuntu"),
    "dock_position": ("bottom", "left"),
    "icons": ("whitesur", "papirus", "keep"),
    "wallpaper": ("orbit", "horizon", "circuit", "code", "gen-orbit", "gen-horizon", "gen-circuit", "gen-code", "none"),
    "wallpaper_size": ("1080p", "1440p", "4k", "ultrawide"),
}
DEFAULTS = {
    "accent": "nebulix", "variant": "dark", "radius": 14, "window_buttons": "gnome", "topbar": "floating",
    "dock": "macos", "dock_position": "bottom", "dock_icon_size": 48, "dock_opacity": 75,
    "icons": "whitesur", "wallpaper": "orbit", "wallpaper_size": "4k",
    "components": list(COMPONENTS),
}


def accent_hex(cfg) -> str:
    a = cfg["accent"]
    return ACCENTS.get(a, a).upper()


def validate(raw: dict) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    errs = []
    a = cfg["accent"]
    if a not in ACCENTS and not (isinstance(a, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", a)):
        errs.append(f"accent inválido: {a!r} (use {', '.join(ACCENTS)} ou #RRGGBB)")
    for k, ch in CHOICES.items():
        if cfg[k] not in ch:
            errs.append(f"{k} inválido: {cfg[k]!r} (use {', '.join(ch)})")
    for k, lo, hi in (("radius", 6, 20), ("dock_icon_size", 32, 64), ("dock_opacity", 20, 100)):
        if not isinstance(cfg[k], int) or isinstance(cfg[k], bool) or not lo <= cfg[k] <= hi:
            errs.append(f"{k} deve ser inteiro entre {lo} e {hi}")
    comps = cfg["components"]
    if not isinstance(comps, list) or any(c not in COMPONENTS for c in comps):
        errs.append(f"components inválido (use {', '.join(COMPONENTS)})")
    if errs:
        raise ValueError("; ".join(errs))
    return cfg


def load() -> dict:
    f = paths.config_file()
    raw = tomllib.loads(f.read_text()) if f.exists() else {}
    return validate(raw)


def _toml_value(v):
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(v)


def save(cfg: dict):
    f = paths.config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    body = "# Nebulix — edite aqui ou use `nebulix config set chave=valor` / o app Nebulix\n"
    body += "".join(f"{k} = {_toml_value(cfg[k])}\n" for k in DEFAULTS)
    f.write_text(body)


def parse_value(key, text):
    if key == "components":
        return [x for x in re.split(r"[,\s]+", text.strip()) if x]
    if isinstance(DEFAULTS[key], int):
        return int(text)
    return text
