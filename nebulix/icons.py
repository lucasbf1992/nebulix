# SPDX-License-Identifier: GPL-3.0-or-later
"""macOS-style icons: WhiteSur (downloaded, pinned) + Nebulix squircle folder overlay."""
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import paths, palette

WHITESUR_TAG = "v2025-02-10"
WHITESUR_URL = f"https://github.com/vinceliuice/WhiteSur-icon-theme/archive/refs/tags/{WHITESUR_TAG}.tar.gz"
WHITESUR_SHA256 = "b94a3db27bd746c267b882a957f863e3ef62eebec7d21c4436b90913597386a6"
WHITESUR_SIZE_MB = 7
THEME_NAME = "Nebulix-Icons"
BASE = "WhiteSur-purple-dark"


def icon_dirs():
    return [paths.data_home() / "icons", Path("/usr/share/icons")]


def has_theme(name):
    return any((d / name).is_dir() for d in icon_dirs())


def ensure_whitesur(log=print):
    """Download the pinned tarball, verify sha256 and run its own installer into ~/.local/share/icons."""
    if has_theme(BASE):
        return True
    log(f"baixando WhiteSur {WHITESUR_TAG} (~{WHITESUR_SIZE_MB} MB, GPL-3.0)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tgz = tmp / "ws.tar.gz"
        req = urllib.request.Request(WHITESUR_URL, headers={"User-Agent": "nebulix"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tgz, "wb") as f:
            shutil.copyfileobj(r, f)
        if hashlib.sha256(tgz.read_bytes()).hexdigest() != WHITESUR_SHA256:
            raise RuntimeError("sha256 do WhiteSur não confere; abortado")
        out = tmp / "x"
        with tarfile.open(tgz) as t:
            t.extractall(out, filter="data")
        src = next(out.iterdir())
        dest = paths.data_home() / "icons"
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["bash", str(src / "install.sh"), "-d", str(dest), "-t", "purple"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=src)
    return has_theme(BASE)


def _folder(t, glyph=""):
    a, d = t["purple"], t["purple-dim"]
    lt = palette.shade(a, .10)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{lt}"/><stop offset="1" stop-color="{d}"/></linearGradient>
<linearGradient id="b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{d}"/><stop offset="1" stop-color="{palette.shade(d, -.1)}"/></linearGradient></defs>
<path d="M6 14a6 6 0 0 1 6-6h13.5a6 6 0 0 1 4.6 2.2l2.3 2.8H52a6 6 0 0 1 6 6v6H6z" fill="url(#b)"/>
<rect x="6" y="18" width="52" height="38" rx="7" fill="url(#f)"/>
<rect x="6.5" y="18.5" width="51" height="37" rx="6.5" fill="none" stroke="#fff" stroke-opacity=".28"/>
<g fill="none" stroke="{t["fg-0"]}" stroke-opacity=".92" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>'''


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


def write_overlay(t, root=None):
    root = Path(root) if root else paths.data_home() / "icons" / THEME_NAME
    shutil.rmtree(root, ignore_errors=True)
    (root / "scalable/places").mkdir(parents=True)
    inherits = ",".join([BASE] if has_theme(BASE) else []) + ("," if has_theme(BASE) else "") + "Papirus-Dark,hicolor"
    (root / "index.theme").write_text(
        f"[Icon Theme]\nName={THEME_NAME}\nComment=Nebulix squircle folders over WhiteSur/Papirus\n"
        f"Inherits={inherits}\nDirectories=scalable/places\n\n"
        "[scalable/places]\nSize=64\nMinSize=16\nMaxSize=512\nType=Scalable\nContext=Places\n")
    for name, g in GLYPHS.items():
        (root / "scalable/places" / f"{name}.svg").write_text(_folder(t, g))
    if shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(root)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return root
