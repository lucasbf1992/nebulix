# SPDX-License-Identifier: GPL-3.0-or-later
"""macOS-style icons: downloaded, pinned icon sets (WhiteSur, MacTahoe, McMojave-circle) + Nebulix squircle folder overlay."""
import colorsys
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import paths, palette, themes

# Downloadable icon sets: pinned release tarball + checksum + how to run the upstream installer. A test points
# NEBULIX_ICONS_SOURCE at a directory that holds `<file>` for each entry instead of the network (and may patch.dict
# an entry with its own sha256, or add a whole new set).
#   install: installer arguments; `{dest}` and `{color}` are filled in. McMojave-circle drops the token that follows
#            `-d <dir>` (so a harmless `-c` goes there) and WhiteSur/MacTahoe take plain `-d <dir> -t <color>`.
#   colors:  installer colour name -> reference hex (the accent -> colour mapping reads it). default_color is the colour used when
#            the theme asks for the plain blue; "default" means the installer's own default, which has no colour in
#            the folder name.
#   folders: the folder name is `<prefix>[-<color>]-<dark|light>`; the colour is left out when it is "default".
SETS = {
    "whitesur": {
        "label": "WhiteSur", "tag": "v2025-02-10", "prefix": "WhiteSur",
        "url": "https://github.com/vinceliuice/WhiteSur-icon-theme/archive/refs/tags/v2025-02-10.tar.gz",
        "file": "v2025-02-10.tar.gz",
        "sha256": "b94a3db27bd746c267b882a957f863e3ef62eebec7d21c4436b90913597386a6",
        "size_mb": 7, "license": "GPL-3.0",
        "install": ["-d", "{dest}", "-t", "{color}"],
        "colors": {"default": "#60C0F0", "purple": "#E791F3", "pink": "#FF85BD", "red": "#FF8180",
                   "orange": "#FFAE70", "yellow": "#FFD485", "green": "#B3EE96", "grey": "#8F8F8F", "nord": "#787F8F"},
        "default_color": "default", "neutral": "grey",
    },
    "mactahoe": {
        "label": "MacTahoe", "tag": "2026-09-10", "prefix": "MacTahoe",
        "url": "https://github.com/vinceliuice/MacTahoe-icon-theme/archive/refs/tags/2026-09-10.tar.gz",
        "file": "2026-09-10.tar.gz",
        "sha256": "6330369e9e10a28cfc8da598ebf63a7204be705403519963ff84e1cb84719d35",
        "size_mb": 10, "license": "GPL-3.0",
        "install": ["-d", "{dest}", "-t", "{color}"],
        "colors": {"blue": "#006EFD", "purple": "#AA5ADC", "green": "#27D83D", "red": "#FE342C",
                   "orange": "#FF8B1D", "yellow": "#FFC61D", "grey": "#686868", "nord": "#5A6885"},
        "default_color": "blue", "neutral": "grey",
    },
    "mcmojave": {
        "label": "McMojave-circle", "tag": "2025-08-07", "prefix": "McMojave-circle",
        "url": "https://github.com/vinceliuice/McMojave-circle/archive/refs/tags/2025-08-07.tar.gz",
        "file": "2025-08-07.tar.gz",
        "sha256": "409506b5ce2905c9b5a1cce109a7f1e6d0c76fdb012ad858d482a47c476e4ee6",
        "size_mb": 6, "license": "GPL-3.0",
        "install": ["-d", "{dest}", "-c", "-t", "{color}"],
        "colors": {"blue": "#4DACF6", "purple": "#B84DF6", "pink": "#FC3CBC", "red": "#FD4F4F", "orange": "#FC9350",
                   "yellow": "#FDE83B", "green": "#4DF688", "brown": "#CD7847", "grey": "#969696", "black": "#353333"},
        "default_color": "blue", "neutral": "grey",
    },
}
THEME_NAME = "Nebulix-Icons"


NEUTRAL_SATURATION = 0.15  # below this an accent is a grey, not a colour
_NOT_A_HUE = ("nord", "black")  # colours of a set that never win by hue (neutral tints)


def _hue_sat(hexcolor):
    r, g, b = (c / 255 for c in palette.rgb(hexcolor))
    h, s, _v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s


def _hue_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def set_color(set_id, accent_hex):
    """Installer colour of a set for an accent: the colour whose reference hue is closest to the accent's hue; an
    accent with little saturation goes to the set's neutral colour (grey) when it has one, else to the set's blue."""
    entry = SETS[set_id]
    hue, sat = _hue_sat(accent_hex)
    if sat < NEUTRAL_SATURATION:
        return entry["neutral"] if entry.get("neutral") in entry["colors"] else entry["default_color"]
    cands = {c: _hue_distance(hue, _hue_sat(h)[0]) for c, h in entry["colors"].items()
             if c != entry.get("neutral") and c not in _NOT_A_HUE}
    return min(cands, key=lambda c: (cands[c], c != entry["default_color"])) if cands else entry["default_color"]


def accent_color(set_id, theme, accent="auto"):
    """Colour of a set for the accent of a theme (`auto` is the theme's own default accent)."""
    return set_color(set_id, themes.accent_hex(theme, accent))


def folder_name(set_id, color, scheme):
    return SETS[set_id]["prefix"] + ("" if color == "default" else f"-{color}") + f"-{scheme}"


def base_name(theme, set_id="whitesur", accent="auto"):
    """Folder the accent asks for: its colour, in the dark or light variant of the theme's scheme."""
    return folder_name(set_id, accent_color(set_id, theme, accent), themes.get(theme)["scheme"])


def _closeness(set_id, a, b):
    """How far apart two colours of a set look (hue distance; a grey against a colour counts as far)."""
    colors = SETS[set_id]["colors"]
    (ha, sa), (hb, sb) = _hue_sat(colors[a]), _hue_sat(colors[b])
    if (sa < NEUTRAL_SATURATION) != (sb < NEUTRAL_SATURATION):
        return 360
    return _hue_distance(ha, hb)


def current_base(set_id, theme, accent="auto"):
    """Folder to use now: the one the accent asks for, else the installed colour of the set that is closest to it
    (same variant), else the wanted name (which then is not installed)."""
    want = base_name(theme, set_id, accent)
    if has_theme(want):
        return want
    color, scheme = accent_color(set_id, theme, accent), themes.get(theme)["scheme"]
    have = [c for c in SETS[set_id]["colors"] if has_theme(folder_name(set_id, c, scheme))]
    if not have:
        return want
    return folder_name(set_id, min(have, key=lambda c: (_closeness(set_id, color, c), c)), scheme)


def uses_overlay(theme):
    return themes.get(theme)["icons"]["overlay"]


def fallback_name(theme):
    return "Papirus-Dark" if themes.get(theme)["scheme"] == "dark" else "Papirus-Light"


def icon_dirs():
    return [paths.data_home() / "icons", Path("/usr/share/icons")]


def has_theme(name):
    return any((d / name).is_dir() for d in icon_dirs())


def fetch_tarball(set_id, dest):
    """Save the tarball of `SETS[set_id]` to `dest`: from $NEBULIX_ICONS_SOURCE/<file> when that is set, else from the URL."""
    entry = SETS[set_id]
    source = os.environ.get("NEBULIX_ICONS_SOURCE")
    if source:
        shutil.copyfile(Path(source) / entry["file"], dest)
        return
    req = urllib.request.Request(entry["url"], headers={"User-Agent": "nebulix"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def cache_dir():
    return paths.cache_home() / "nebulix" / "icons"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cached_tarball(set_id):
    """Path of the verified tarball kept from an earlier download, or None (a cached file whose sha256 changed is ignored)."""
    entry = SETS[set_id]
    f = cache_dir() / entry["file"]
    return f if f.is_file() and _sha256(f) == entry["sha256"] else None


def installed(set_id):
    """Whether any folder of the set (any colour or variant) is in the icon directories."""
    pre = SETS[set_id]["prefix"]
    return any(p.is_dir() and (p.name == pre or p.name.startswith(pre + "-")) for d in icon_dirs() if d.is_dir() for p in d.iterdir())


def ensure_set(set_id, log=print, theme="nebulix", accent="auto"):
    """Install the colour of `set_id` that the accent of `theme` asks for (both its dark and light folders) into ~/.local/share/icons
    with the set's own installer, from the verified tarball: the cache when it holds one, else the download (then
    kept in the cache, so another colour needs no network). Nothing happens when the folder is already there. A failing
    installer leaves none of the folders it created."""
    base = base_name(theme, set_id, accent)
    if has_theme(base):
        return True
    entry = SETS[set_id]
    color = accent_color(set_id, theme, accent)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tgz = cached_tarball(set_id)
        if tgz:
            log(f"usando {entry['label']} {entry['tag']} guardado em {cache_dir()}")
        else:
            log(f"baixando {entry['label']} {entry['tag']} (~{entry['size_mb']} MB, {entry['license']})")
            tgz = tmp / "set.tar.gz"
            fetch_tarball(set_id, tgz)
            if _sha256(tgz) != entry["sha256"]:
                raise RuntimeError(f"sha256 do {entry['label']} não confere; abortado")
        out = tmp / "x"
        with tarfile.open(tgz) as t:
            t.extractall(out, filter="data")
        if tgz.parent == tmp:  # verified and extractable: keep it for the next colour
            keep = cache_dir()
            keep.mkdir(parents=True, exist_ok=True)
            part = keep / (entry["file"] + ".part")
            shutil.copyfile(tgz, part)
            os.replace(part, keep / entry["file"])
        src = next(out.iterdir())
        dest = paths.data_home() / "icons"
        dest.mkdir(parents=True, exist_ok=True)
        before = {p.name for p in dest.iterdir()}
        args = [a.format(dest=dest, color=color) for a in entry["install"]]
        try:
            r = subprocess.run(["bash", str(src / "install.sh"), *args], cwd=src, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True)
            if r.returncode:
                raise RuntimeError(f"instalador do {entry['label']} falhou (código {r.returncode}) {r.stderr.strip()[-200:]}".strip())
        except BaseException:
            for p in dest.iterdir():
                if p.name not in before:
                    shutil.rmtree(p, ignore_errors=True) if p.is_dir() and not p.is_symlink() else p.unlink(missing_ok=True)
            raise
    return has_theme(base)


def _folder(t, glyph=""):
    a, d = t["purple"], t["purple-dim"]
    lt = palette.shade(a, .10)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{lt}"/><stop offset="1" stop-color="{d}"/></linearGradient>
<linearGradient id="b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{d}"/><stop offset="1" stop-color="{palette.shade(d, -.1)}"/></linearGradient></defs>
<path d="M6 14a6 6 0 0 1 6-6h13.5a6 6 0 0 1 4.6 2.2l2.3 2.8H52a6 6 0 0 1 6 6v6H6z" fill="url(#b)"/>
<rect x="6" y="18" width="52" height="38" rx="7" fill="url(#f)"/>
<rect x="6.5" y="18.5" width="51" height="37" rx="6.5" fill="none" stroke="#fff" stroke-opacity=".28"/>
<g fill="none" stroke="{t["ink-light"]}" stroke-opacity=".92" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>'''


GLYPHS = {
    "folder": "", "folder-documents": '<path d="M26 31h12M26 37h12M26 43h8"/>',
    "folder-download": '<path d="M32 30v14M26 38l6 6 6-6"/>', "folder-pictures": '<path d="M24 46l7-9 5 6 4-4 4 7z"/><circle cx="38" cy="32" r="2"/>',
    "folder-music": '<path d="M36 44V30l-9 2v12"/><circle cx="25" cy="44" r="2.5"/><circle cx="34" cy="44" r="2.5"/>',
    "folder-videos": '<path d="M28 31l10 6-10 6z"/>', "folder-publicshare": '<circle cx="32" cy="37" r="7"/><path d="M25 37h14"/>',
    "folder-templates": '<path d="M26 31h12v14H26zM26 36h12"/>', "folder-remote": '<path d="M24 40h16M32 31v18"/>',
    "folder-open": "", "user-home": '<path d="M24 38l8-8 8 8M26 36v9h12v-9"/>',
    "user-trash": '<path d="M26 32h12M29 32v-2h6v2M27 32l1 13h8l1-13"/>',
    "user-trash-full": '<path d="M26 32h12M29 32v-2h6v2M27 32l1 13h8l1-13M31 36v6M34 36v6"/>',
    "inode-directory": "",
}


def write_overlay(t, root=None, theme="nebulix", set_id="whitesur", accent="auto"):
    root = Path(root) if root else paths.data_home() / "icons" / THEME_NAME
    shutil.rmtree(root, ignore_errors=True)
    (root / "scalable/places").mkdir(parents=True)
    base, fb = current_base(set_id, theme, accent), fallback_name(theme)
    inherits = ",".join([base] if has_theme(base) else []) + ("," if has_theme(base) else "") + f"{fb},hicolor"
    (root / "index.theme").write_text(
        f"[Icon Theme]\nName={THEME_NAME}\nComment=Nebulix squircle folders over WhiteSur/Papirus\n"
        f"Inherits={inherits}\nDirectories=scalable/places\n\n"
        "[scalable/places]\nSize=64\nMinSize=16\nMaxSize=512\nType=Scalable\nContext=Places\n")
    for name, g in GLYPHS.items():
        (root / "scalable/places" / f"{name}.svg").write_text(_folder(t, g))
    if shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(root)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return root
