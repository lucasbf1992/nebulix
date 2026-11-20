# SPDX-License-Identifier: GPL-3.0-or-later
"""Install state: manifest, backups of overwritten files and gsettings values (same format as 0.1)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import paths


def gs(*args, check=False):
    if not shutil.which("gsettings"):
        return None
    r = subprocess.run(["gsettings", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


class State:
    def __init__(self, dry=False, log=print):
        self.dir = paths.state_dir()
        self.bk = self.dir / "backup" / "files"
        self.dry, self.log = dry, log
        self.missing = []  # (message, fix command) for requirements not met
        self.manifest = self._read("manifest")
        self.backed = self._read("backed-up")
        self.before = {}
        f = self.dir / "gsettings.before"
        if f.exists():
            for ln in f.read_text().splitlines():
                p = ln.split("\t", 2)
                if len(p) == 3:
                    self.before[(p[0], p[1])] = p[2]

    def _read(self, name):
        f = self.dir / name
        return f.read_text().splitlines() if f.exists() else []

    def _write(self, name, lines):
        if not self.dry:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / name).write_text("".join(x + "\n" for x in lines))

    def save(self):
        self._write("manifest", self.manifest)
        self._write("backed-up", self.backed)
        self._write("gsettings.before", [f"{s}\t{k}\t{v}" for (s, k), v in self.before.items()])

    def note(self, entry):
        if entry not in self.manifest:
            self.manifest.append(entry)

    # ---- files ----
    def put_text(self, text, dest):
        dest = Path(dest)
        self.log(f"→ {dest}")
        if self.dry:
            return
        self._backup(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        self.note(str(dest))

    def put_tree(self, src, dest):
        dest = Path(dest)
        self.log(f"→ {dest}")
        if self.dry:
            return
        self._backup(dest)
        shutil.rmtree(dest, ignore_errors=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        self.note(str(dest))

    def _backup(self, dest):
        d = str(dest)
        if (dest.exists() or dest.is_symlink()) and d not in self.manifest and d not in self.backed:
            tgt = self.bk / d.lstrip("/")
            tgt.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_dir():
                shutil.copytree(dest, tgt, symlinks=True)
            else:
                shutil.copy2(dest, tgt, follow_symlinks=False)
            self.backed.append(d)

    def put_tracked_dir_file(self, text, dest):
        """Write a file inside a directory that is already tracked as a whole (no manifest entry)."""
        dest = Path(dest)
        if not self.dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)

    # ---- gsettings ----
    def gs_set(self, schema, key, value):
        if not shutil.which("gsettings"):
            return
        if self.dry:
            self.log(f"gsettings {schema} {key} = {value}")
            return
        cur = gs("get", schema, key)
        if cur is None:
            self.log(f"! gsettings {schema} {key} indisponível")
            return
        self.before.setdefault((schema, key), cur)
        r = subprocess.run(["gsettings", "set", schema, key, value], capture_output=True, text=True)
        if r.returncode:
            self.log(f"! falhou: gsettings set {schema} {key}")

    def gs_release(self, schema, key):
        """Put a key back to the value it had before Nebulix and stop tracking it."""
        v = self.before.pop((schema, key), None)
        if v is not None and not self.dry:
            subprocess.run(["gsettings", "set", schema, key, v], capture_output=True)


SHELL = "org.gnome.shell"


def set_extension_enabled(uuid, on, dry=False):
    """Add/remove `uuid` in the persistent enabled-extensions list (works for extensions the running Shell
    has not discovered yet, which is the case right after installing one on Wayland) and toggle it live."""
    if shutil.which("gsettings"):
        cur = gs("get", SHELL, "enabled-extensions") or ""
        lst = re.findall(r"'([^']+)'", cur) if "[" in cur else []
        new = [u for u in lst if u != uuid] + ([uuid] if on else [])
        if new != lst and not dry:
            subprocess.run(["gsettings", "set", SHELL, "enabled-extensions", "[" + ", ".join(f"'{u}'" for u in new) + "]"],
                           capture_output=True)
    if shutil.which("gnome-extensions") and not dry:
        subprocess.run(["gnome-extensions", "enable" if on else "disable", uuid], capture_output=True)
