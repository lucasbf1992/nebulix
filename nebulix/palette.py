# SPDX-License-Identifier: GPL-3.0-or-later
"""Token set derived from the chosen theme (palette.json) + user config (accent, variant, radius)."""
import colorsys

from . import config, themes

STATUS = ("red", "green", "yellow", "magenta", "cyan", "blue", "purple-dim")


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
    return themes.load_all()


def _on(color, dark, light):
    """Text colour (one of the theme's two inks) that reads best on `color`."""
    return dark if contrast(color, dark) > contrast(color, light) else light


def tokens(cfg=None):
    cfg = cfg or config.DEFAULTS
    full = load_palette()
    th = themes.get(cfg["theme"])
    scheme = th["scheme"]
    t = dict(th["base"])
    if cfg["variant"] == "darker" and "darker" in th:
        t.update(th["darker"])
    t["scheme"] = scheme
    t["scheme-suffix"] = "-dark" if scheme == "dark" else ""
    t["theme-name"] = "Nebulix-Light" if scheme == "light" else "Nebulix-Dark"
    t["theme-label"] = th["label"]
    for k, src in (("tl-red", "red"), ("tl-yellow", "yellow"), ("tl-green", "green")):
        t.setdefault(k, t[src])  # window-button colours (macOS traffic lights) can differ from the status colours
    inks = sorted((t["bg-0"], t["fg-0"]), key=lum)
    ink_dark, ink_light = inks[0], inks[1]
    t["ink-dark"], t["ink-light"] = ink_dark, ink_light
    acc = config.accent_hex(cfg)
    t["purple"] = acc
    t["purple-dim"] = shade(acc, -.12)
    # accent used as text/glyph colour: moved away from the background until it reads at 4.5:1
    at = acc
    for _ in range(25):
        if min(contrast(at, t["bg-1"]), contrast(at, t["bg-2"])) >= 4.5:
            break
        at = shade(at, .03 if scheme == "dark" else -.03)
    t["accent-text"] = at
    t["on-accent"] = t["bg-0"] if contrast(acc, t["bg-0"]) > contrast(acc, t["fg-0"]) else t["fg-0"]
    # solid fill behind selected rows / primary buttons, and the text color that stays readable on it
    fill = t["purple-dim"]
    for _ in range(12):
        if contrast(fill, ink_light) >= 4.5:
            break
        fill = shade(fill, -.04)
    if contrast(fill, ink_light) >= 4.5:
        t["accent-fill"], t["on-fill"] = fill, ink_light
    else:  # light accents (cyan, green, amber): use the accent itself with dark text
        t["accent-fill"], t["on-fill"] = acc, ink_dark
    # surfaces painted in the accent (terminal prompt, editor status bar, toggles): the theme picks the look
    if th["solid_accent"] or contrast(acc, t["on-accent"]) < 4.5:  # mid-tone custom accents fall back to the fill
        t["accent-solid"], t["on-solid"] = t["accent-fill"], t["on-fill"]
        t["accent-solid-hover"] = shade(t["accent-fill"], -.06)
    else:
        t["accent-solid"], t["on-solid"] = acc, t["on-accent"]
        t["accent-solid-hover"] = t["purple-dim"]
    t["link"] = t["accent-text"] if th["link"] == "accent" else t[th["link"]]
    for k in STATUS:
        t[f"on-{k}"] = _on(t[k], ink_dark, ink_light)
    for i, c in enumerate(th["ansi"]["normal"] + th["ansi"]["bright"]):
        t[f"ansi-{i}"] = c
    r = cfg["radius"]
    t.update({"radius": str(r), "radius-sm": str(max(3, round(r * .6))), "radius-lg": str(round(r * 1.4)),
              "dock-radius": str(round(r * 1.6)), "dock-alpha": f"{cfg['dock_opacity'] / 100:g}"})
    P = {"name": full["name"], "version": full["version"], "scheme": scheme, "label": th["label"], "ansi": th["ansi"]}
    return P, t


RULES = [("fg-0", "bg-0", 7), ("fg-0", "bg-2", 7), ("fg-1", "bg-1", 7), ("fg-2", "bg-1", 3),
         ("accent-text", "bg-1", 4.5), ("accent-text", "bg-2", 4.5),
         ("on-fill", "accent-fill", 4.5), ("on-solid", "accent-solid", 4.5),
         ("on-red", "red", 4.5), ("on-green", "green", 4.5), ("on-yellow", "yellow", 4.5), ("on-magenta", "magenta", 4.5),
         ("red", "bg-1", 3), ("green", "bg-1", 3), ("yellow", "bg-1", 3), ("link", "bg-1", 4.5)]


def contrast_report(cfg):
    P, t = tokens(cfg)
    return [(a, b, contrast(t[a], t[b]), need) for a, b, need in RULES]


def terminal_contrast(cfg, opacity=None):
    """Worst case of the translucent terminal: text `fg-0` over the background blended at `opacity` (default: the
    lowest allowed, 70%) onto pure white and pure black desktops. Returns the lower ratio."""
    P, t = tokens(cfg)
    o = (opacity or 70) / 100
    bg = rgb(t["bg-0"])
    worst = 21
    for back in ((255, 255, 255), (0, 0, 0)):
        mixed = hexs(*(o * c + (1 - o) * k for c, k in zip(bg, back)))
        worst = min(worst, contrast(t["fg-0"], mixed))
    return worst
