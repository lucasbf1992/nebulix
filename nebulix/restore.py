# SPDX-License-Identifier: GPL-3.0-or-later
"""Undo (back to before Nebulix) and factory reset (Ubuntu defaults)."""
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import icons, paths, vscode
from .apply import TOUCHED_KEYS
from .state import State, lock, set_extension_enabled


def restore(*a, **kw):
    with lock():
        return _restore(*a, **kw)


def _restore(mode="undo", log=print, remove_icons=False, dry=False):
    """mode='undo': gsettings back to the values saved before Nebulix.
    mode='reset': gsettings reset to the system defaults. Both remove Nebulix files and restore overwritten originals."""
    assert mode in ("undo", "reset")
    st = State(dry=dry, log=log)
    sd = st.dir
    if not st.manifest and not st.before:
        log("nada instalado pelo Nebulix para este usuário.")
        if mode != "reset":
            return False
    if shutil.which("gsettings"):
        if mode == "undo":
            for (s, k), v in st.before.items():
                log(f"gsettings {s} {k} ← {v}")
                if not dry:
                    subprocess.run(["gsettings", "set", s, k, v], capture_output=True)
        else:
            for s, k in dict.fromkeys([*TOUCHED_KEYS, *st.before]):
                log(f"gsettings reset {s} {k}")
                if not dry:
                    subprocess.run(["gsettings", "reset", s, k], capture_output=True)
    for e in st.manifest:
        if e.startswith("gtkblock:"):
            _strip_block(Path(e[9:]), dry, drop_if_empty=True)  # backed-up originals are restored below
        elif e == "flatpak" and shutil.which("flatpak"):
            if not dry:
                subprocess.run(["flatpak", "override", "--user", "--nofilesystem=xdg-config/gtk-4.0",
                                "--nofilesystem=xdg-config/gtk-3.0", "--nofilesystem=xdg-data/themes"], capture_output=True)
        elif e.startswith("gnt:") and shutil.which("dconf"):
            u, old = e[4:].split(":", 1)
            if not dry:
                subprocess.run(["dconf", "write", "/org/gnome/terminal/legacy/profiles:/list", old] if old
                               else ["dconf", "reset", "/org/gnome/terminal/legacy/profiles:/list"])
                subprocess.run(["dconf", "reset", "-f", f"/org/gnome/terminal/legacy/profiles:/:{u}/"])
        elif e.startswith("ptyxis:") and shutil.which("dconf"):
            if not dry:
                subprocess.run(["dconf", "reset", "-f", f"/org/gnome/Ptyxis/Profiles/{e[7:]}/"])
        elif e.startswith("vscext:"):
            vscode.unregister(e, dry, log)
        elif e.startswith("vscode:"):
            vscode.restore_entry(e, mode, dry, log)
        elif e.startswith("ext:"):
            set_extension_enabled(e[4:], False, dry)
        elif e.startswith("/"):
            log(f"remove {e}")
            if not dry:
                shutil.rmtree(e, ignore_errors=True) if Path(e).is_dir() else Path(e).unlink(missing_ok=True)
    for f in st.backed:
        src = st.bk / f.lstrip("/")
        if src.exists() or src.is_symlink():
            log(f"restaura {f}")
            if not dry:
                p = Path(f)
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() and not p.is_symlink() else p.unlink(missing_ok=True)
                shutil.copytree(src, p, symlinks=True) if src.is_dir() else shutil.copy2(src, p, follow_symlinks=False)
    _strip_block(paths.conf_home() / "gtk-4.0/gtk.css", dry, drop_if_empty=True)
    if remove_icons:
        for n in icons.owned_folders():
            p = paths.data_home() / "icons" / n
            if p.is_symlink() or p.exists():
                log(f"remove {p}")
                if not dry:
                    shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
        cache = icons.cache_dir()
        if cache.exists():
            log(f"remove {cache}")
            if not dry:
                shutil.rmtree(cache, ignore_errors=True)
                try:
                    cache.parent.rmdir()
                except OSError:
                    pass
    if not dry:
        for d in (paths.data_home() / "backgrounds/nebulix", paths.data_home() / "org.gnome.Ptyxis/palettes"):
            try:
                d.rmdir()
            except OSError:
                pass
        for old in sd.parent.glob("nebulix.removed.*"):
            shutil.rmtree(old, ignore_errors=True)
        if sd.exists():
            sd.rename(sd.parent / f"nebulix.removed.{int(time.time())}")
    log("pronto. Saia e entre na sessão se o Shell ainda mostrar o tema." if not dry else "dry-run: nada foi alterado.")
    return True


def _strip_block(f: Path, dry, drop_if_empty=False):
    if not f.exists():
        return
    s = f.read_text()
    n = re.sub(r"/\* NEBULIX-BEGIN \*/.*?/\* NEBULIX-END \*/\n?", "", s, flags=re.S)
    if n != s and not dry:
        if drop_if_empty and not n.strip():
            f.unlink()
        else:
            f.write_text(n)
