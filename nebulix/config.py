# SPDX-License-Identifier: GPL-3.0-or-later
"""User configuration (~/.config/nebulix/config.toml)."""
import re
import tomllib

from . import paths, themes

COMPONENTS = ("gtk", "shell", "terminal", "starship", "fastfetch", "btop", "vscode", "nvim", "wallpaper", "icons")
CHOICES = {
    "theme": ("nebulix", "macos-dark", "macos-light", "nebulix-light"),
    "variant": ("dark", "darker"),
    "window_buttons": ("gnome", "mac"),
    "topbar": ("floating", "solid", "translucent"),
    "dock": ("macos", "ubuntu"),
    "dock_position": ("bottom", "left", "right"),
    "dock_zoom": ("off", "on"),
    "icons": ("whitesur", "papirus", "keep"),
    "font": ("auto", "keep"),
    "vscode_theme": ("keep", "follow", "nebulix", "macos-dark", "macos-light", "nebulix-light"),
    "wallpaper": ("orbit", "horizon", "circuit", "code", "gen-orbit", "gen-horizon", "gen-circuit", "gen-code", "none"),
    "wallpaper_size": ("1080p", "1440p", "4k", "ultrawide"),
    "terminal_cursor": ("block", "ibeam", "underline"),
    "terminal_font": ("auto", "keep"),
    "terminal_padding": ("on", "off"),
}
INT_RANGES = (("radius", 6, 20), ("dock_icon_size", 32, 64), ("dock_opacity", 20, 100), ("dock_zoom_factor", 120, 200),
              ("terminal_opacity", 70, 100), ("terminal_font_size", 8, 20), ("terminal_line_height", 100, 140),
              ("terminal_columns", 80, 240), ("terminal_rows", 24, 80))
DEFAULTS = {
    "theme": "nebulix", "accent": "auto", "variant": "dark", "radius": 14, "window_buttons": "gnome", "topbar": "floating",
    "dock": "macos", "dock_position": "bottom", "dock_icon_size": 48, "dock_opacity": 75,
    "dock_zoom": "off", "dock_zoom_factor": 160,
    "terminal_opacity": 90, "terminal_cursor": "block", "terminal_font": "auto", "terminal_font_size": 11,
    "terminal_padding": "on", "terminal_line_height": 100, "terminal_columns": 80, "terminal_rows": 24,
    "icons": "whitesur", "font": "auto", "vscode_theme": "keep", "wallpaper": "orbit", "wallpaper_size": "4k",
    "components": list(COMPONENTS),
}


def accent_hex(cfg) -> str:
    return themes.accent_hex(cfg["theme"], cfg["accent"])


def gnome_accent(cfg) -> str:
    return themes.gnome_accent(cfg["theme"], cfg["accent"])


def apply_theme(cfg: dict, name: str) -> dict:
    """Return cfg with the theme's package of values applied (accent back to the theme default)."""
    name = themes.resolve(name)
    new = dict(cfg)
    new.update({k: v for k, v in themes.get(name)["package"].items() if k in themes.PACKAGE_KEYS})
    new["theme"], new["accent"] = name, "auto"
    return validate(new)


def validate(raw: dict) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    errs = []
    if cfg["theme"] not in CHOICES["theme"]:
        raise ValueError(f"theme inválido: {cfg['theme']!r} (use {', '.join(CHOICES['theme'])})")
    a = cfg["accent"]
    names = themes.accent_names(cfg["theme"])
    if a != "auto" and a not in names and not (isinstance(a, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", a)):
        errs.append(f"accent inválido: {a!r} (use auto, {', '.join(names)} ou #RRGGBB)")
    for k, ch in CHOICES.items():
        if cfg[k] not in ch:
            errs.append(f"{k} inválido: {cfg[k]!r} (use {', '.join(ch)})")
    for k, lo, hi in INT_RANGES:
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
