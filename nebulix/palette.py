# SPDX-License-Identifier: GPL-3.0-or-later
"""Token set derived from palette.json + user config (accent, variant, radius)."""
import colorsys
import json

from . import config, paths

DARKER = {"bg-0": "#000000", "bg-1": "#07050C", "bg-2": "#100B1C", "bg-3": "#1A1330", "border": "#2A2048"}


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexs(r, g, b):
    return "#%02X%02X%02X" % (round(r), round(g), round(b))


def shade(h, dl):
    r, g, b = (c / 255 for c in rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, max(0, min(1, l + dl)), s)
    return hexs(r * 255, g * 255, b * 255)


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


def load_palette():
    return json.loads((paths.data_dir() / "palette.json").read_text())


def tokens(cfg=None):
    cfg = cfg or config.DEFAULTS
    P = load_palette()
    t = dict(P["base"])
    if cfg["variant"] == "darker":
        t.update(DARKER)
    acc = config.accent_hex(cfg)
    t["purple"] = acc
    t["purple-dim"] = shade(acc, -.12)
    t["on-accent"] = t["bg-0"] if contrast(acc, t["bg-0"]) > contrast(acc, t["fg-0"]) else t["fg-0"]
    # solid fill behind selected rows / primary buttons, and the text color that stays readable on it
    fill = t["purple-dim"]
    for _ in range(8):
        if contrast(fill, t["fg-0"]) >= 4.5:
            break
        fill = shade(fill, -.04)
    if contrast(fill, t["fg-0"]) >= 4.5:
        t["accent-fill"], t["on-fill"] = fill, t["fg-0"]
    else:  # light accents (cyan, green, amber): use the accent itself with dark text
        t["accent-fill"], t["on-fill"] = acc, t["bg-0"]
    for i, c in enumerate(P["ansi"]["normal"] + P["ansi"]["bright"]):
        t[f"ansi-{i}"] = c
    r = cfg["radius"]
    t.update({"radius": str(r), "radius-sm": str(max(3, round(r * .6))), "radius-lg": str(round(r * 1.4)),
              "dock-radius": str(round(r * 1.6)), "dock-alpha": f"{cfg['dock_opacity'] / 100:g}"})
    return P, t


def contrast_report(cfg):
    P, t = tokens(cfg)
    rules = [("fg-0", "bg-0", 7), ("fg-0", "bg-2", 7), ("fg-1", "bg-1", 7), ("purple", "bg-1", 4.5),
             ("on-fill", "accent-fill", 4.5), ("on-accent", "purple", 4.5)]
    return [(a, b, contrast(t[a], t[b]), need) for a, b, need in rules]
