# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared test infrastructure: a throw-away HOME with fake gsettings/dconf/flatpak/gnome-extensions binaries,
fakes for the other tools (S4), a fake icon tarball factory (S3), a clock (S5), a network block (S6),
rc-file helpers (S7) and a folder listing of the icon directory (S8)."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import socket
import stat
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request
from collections import namedtuple
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAKE_GS = '''#!/usr/bin/env python3
import json, os, sys
f = os.path.join(os.environ["FAKE_STATE"], "gs.json")
d = json.load(open(f)) if os.path.exists(f) else {}
a = sys.argv[1:]
key = "|".join(a[1:3])
if a[0] in ("set", "reset"):
    with open(os.path.join(os.environ["FAKE_STATE"], "calls.log"), "a") as log:
        log.write("gsettings " + " ".join(a) + "\\n")
if a[0] == "get": print(d.get(key, "'default'"))
elif a[0] == "set": d[key] = a[3]
elif a[0] == "reset": d.pop(key, None)
json.dump(d, open(f, "w"))
'''
FAKE_NOOP = '#!/bin/sh\nexit 0\n'
# commands a test can fake with Sandbox.fake (S4); every call is appended to $FAKE_STATE/calls.log as "<name> <argv>"
FAKE_TOOLS = ("systemctl", "tmux", "starship", "delta", "bat", "batcat", "fzf", "eza", "hostname", "apt", "apt-get",
              "pip", "pip3", "flatpak")
# real binaries linked into the restricted PATH (Sandbox.restrict_path)
CORE_TOOLS = ("python3", "sh", "bash", "env", "cat", "ls", "mkdir", "rm", "rmdir", "cp", "mv", "ln", "chmod", "touch",
              "dirname", "basename", "tr", "sort", "head", "tail", "wc", "date", "sed", "grep", "tee", "find", "tar",
              "gzip", "uname", "id", "readlink", "true", "false", "test", "[", "sleep", "mktemp", "realpath")

Tarball = namedtuple("Tarball", "path sha256 size")

# fake icon-theme installer: records $PWD and argv, creates <Set>-<color>-<dark|light> folders inside -d
_INSTALL_SH = r'''#!/usr/bin/env bash
argv="$*"
dest="$HOME/.local/share/icons"; color=default
while [ $# -gt 0 ]; do
  case "$1" in -d) dest="$2"; shift 2;; -t) color="$2"; shift 2;; *) shift;; esac
done
printf 'PWD=%s ARGV=%s\n' "$PWD" "$argv" >> "$FAKE_STATE/installer.log"
mkdir -p "$dest"
colors="@COLORS@"
[ "$color" != "all" ] && colors="$color"
for c in $colors; do
  for v in @VARIANTS@; do
    if [ "$c" = default ]; then name="@SET@-$v"; else name="@SET@-$c-$v"; fi
    mkdir -p "$dest/$name"
    printf '[Icon Theme]\nName=%s\n' "$name" > "$dest/$name/index.theme"
    [ "@OK@" = no ] && exit 1
  done
done
exit 0
'''


def make_icon_tarball(directory, set_name, colors=("default",), variants=("dark", "light"), installer_ok=True,
                      evil=False, filename=None):
    """Build a fake `<directory>/<filename>` (default `<set_name>.tar.gz`) that looks like an upstream icon-theme
    release: one top directory with an `install.sh`. The fake installer logs `PWD=... ARGV=...` to
    $FAKE_STATE/installer.log (the number of downloads is the number of distinct PWDs), creates the folders
    `<set_name>-<color>-<dark|light>` (`<set_name>-<variant>` for the color `default`) inside its `-d` for every
    color when given `-t all` and for just that color otherwise, and, with installer_ok=False, exits with an error
    right after the first folder. evil=True adds members that escape the extraction directory (`../evil.txt`,
    `../../evil.txt`) and an absolute symlink. Returns Tarball(path, sha256, size_bytes)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (filename or f"{set_name}.tar.gz")
    script = (_INSTALL_SH.replace("@COLORS@", " ".join(colors)).replace("@VARIANTS@", " ".join(variants))
              .replace("@SET@", set_name).replace("@OK@", "yes" if installer_ok else "no"))
    top = f"{set_name}-icon-theme-fake"
    with tarfile.open(path, "w:gz") as t:
        d = tarfile.TarInfo(top)
        d.type, d.mode = tarfile.DIRTYPE, 0o755
        t.addfile(d)
        data = script.encode()
        i = tarfile.TarInfo(f"{top}/install.sh")
        i.size, i.mode = len(data), 0o755
        t.addfile(i, io.BytesIO(data))
        if evil:
            for name in ("../evil.txt", "../../evil.txt"):
                e = tarfile.TarInfo(name)
                e.size = 4
                t.addfile(e, io.BytesIO(b"evil"))
            ln = tarfile.TarInfo(f"{top}/abs-link")
            ln.type, ln.linkname = tarfile.SYMTYPE, "/etc/passwd"
            t.addfile(ln)
    raw = path.read_bytes()
    return Tarball(path, hashlib.sha256(raw).hexdigest(), len(raw))


@contextlib.contextmanager
def no_network():
    """S6: any attempt to open a socket, resolve a name or call urlopen raises AssertionError."""
    def boom(*_a, **_k):
        raise AssertionError("network access attempted in a test")
    with mock.patch("socket.socket.connect", boom), mock.patch("socket.getaddrinfo", boom), \
            mock.patch("urllib.request.urlopen", boom):
        yield


class Sandbox(unittest.TestCase):
    no_network = staticmethod(no_network)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nbx-test-"))
        (self.tmp / "bin").mkdir()
        (self.tmp / "state").mkdir()
        (self.tmp / "home").mkdir()
        (self.tmp / "bin/gsettings").write_text(FAKE_GS)
        for n in ("dconf", "gnome-extensions", "gtk-update-icon-cache"):
            (self.tmp / "bin" / n).write_text(FAKE_NOOP)
        for f in (self.tmp / "bin").iterdir():
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        self.old = dict(os.environ)
        for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            os.environ.pop(k, None)
        os.environ.update(HOME=str(self.tmp / "home"), FAKE_STATE=str(self.tmp / "state"),
                          PATH=f"{self.tmp/'bin'}:{self.old['PATH']}")
        self.home = self.tmp / "home"
        self.fake("flatpak")  # records its calls too

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        time.tzset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gs(self):
        f = self.tmp / "state/gs.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*")
                if p.is_file() and "nebulix.removed" not in str(p)}

    # ---- S4: fake commands ----
    def fake(self, name, script="exit 0"):
        """Create `name` in the Sandbox bin. `script` is a /bin/sh snippet run after the call is logged to
        $FAKE_STATE/calls.log (one line, `<name> <argv>`); environment variables such as FAKE_TMUX_RUNNING,
        FAKE_STARSHIP_VERSION or FAKE_HOSTNAME are read by the snippet itself."""
        f = self.tmp / "bin" / name
        f.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "$FAKE_STATE/calls.log"\n{script}\n')
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
        return f

    def calls(self):
        """Lines of $FAKE_STATE/calls.log (every logged fake call, in order)."""
        f = self.tmp / "state/calls.log"
        return f.read_text().splitlines() if f.exists() else []

    def restrict_path(self):
        """PATH = the Sandbox bin plus a bin that only links python3, sh, bash, env and the coreutils the tests need,
        so a tool that is not faked counts as absent."""
        real = self.tmp / "realbin"
        real.mkdir(exist_ok=True)
        for n in CORE_TOOLS:
            src = shutil.which(n, path=self.old["PATH"])
            if src and not (real / n).exists():
                (real / n).symlink_to(src)
        os.environ["PATH"] = f"{self.tmp/'bin'}:{real}"

    # ---- S5: clock ----
    def at(self, stamp):
        """Fix the clock the auto-switch reads: NEBULIX_NOW=<YYYY-MM-DDTHH:MM> and TZ=UTC."""
        os.environ.update(NEBULIX_NOW=stamp, TZ="UTC")
        time.tzset()

    # ---- S7: user rc files ----
    def write_rc(self, name, text):
        p = self.home / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def read_rc(self, name):
        p = self.home / name
        return p.read_text() if p.exists() else None

    # ---- S8: icon folders ----
    def tree(self):
        """Sorted names of the folders in ~/.local/share/icons."""
        d = self.home / ".local/share/icons"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def installer_runs(self):
        """Lines of the fake installer's log; a download is a distinct PWD."""
        f = self.tmp / "state/installer.log"
        return f.read_text().splitlines() if f.exists() else []

    def downloads(self):
        return len({ln.split(" ARGV=", 1)[0] for ln in self.installer_runs()})
