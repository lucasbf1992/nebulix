# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests run entirely in a throw-away HOME with fake gsettings/dconf/flatpak/gnome-extensions binaries."""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAKE_GS = '''#!/usr/bin/env python3
import json, os, sys
f = os.path.join(os.environ["FAKE_STATE"], "gs.json")
d = json.load(open(f)) if os.path.exists(f) else {}
a = sys.argv[1:]
key = "|".join(a[1:3])
if a[0] == "get": print(d.get(key, "'default'"))
elif a[0] == "set": d[key] = a[3]
elif a[0] == "reset": d.pop(key, None)
json.dump(d, open(f, "w"))
'''
FAKE_NOOP = '#!/bin/sh\nexit 0\n'


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nbx-test-"))
        (self.tmp / "bin").mkdir()
        (self.tmp / "state").mkdir()
        (self.tmp / "home").mkdir()
        (self.tmp / "bin/gsettings").write_text(FAKE_GS)
        for n in ("dconf", "flatpak", "gnome-extensions", "gtk-update-icon-cache"):
            (self.tmp / "bin" / n).write_text(FAKE_NOOP)
        for f in (self.tmp / "bin").iterdir():
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        self.old = dict(os.environ)
        for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            os.environ.pop(k, None)
        os.environ.update(HOME=str(self.tmp / "home"), FAKE_STATE=str(self.tmp / "state"),
                          PATH=f"{self.tmp/'bin'}:{self.old['PATH']}")
        self.home = self.tmp / "home"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gs(self):
        f = self.tmp / "state/gs.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*")
                if p.is_file() and "nebulix.removed" not in str(p)}


class TestConfig(unittest.TestCase):
    def test_validate(self):
        from nebulix import config
        self.assertEqual(config.validate({})["accent"], "nebulix")
        config.validate({"accent": "#12ABef", "radius": 6})
        for bad in ({"accent": "roxo"}, {"radius": 99}, {"variant": "x"}, {"components": ["nope"]}, {"dock_opacity": True}):
            with self.assertRaises(ValueError):
                config.validate(bad)

    def test_contrast_all_accents(self):
        from nebulix import config, palette
        for acc, var in product(config.ACCENTS, config.CHOICES["variant"]):
            for a, b, c, need in palette.contrast_report(config.validate({"accent": acc, "variant": var})):
                self.assertGreaterEqual(c, need, f"{acc}/{var} {a} on {b}")

    def test_templates_render_everywhere(self):
        from nebulix import config, palette, render, paths
        base = paths.data_dir() / "templates"
        for var, wb, bar, dock in product(("dark", "darker"), ("gnome", "mac"), ("floating", "solid"), ("macos", "ubuntu")):
            cfg = config.validate({"variant": var, "window_buttons": wb, "topbar": bar, "dock": dock, "radius": 20})
            _, t = palette.tokens(cfg)
            for f in base.rglob("*"):
                if f.is_file():
                    out = render.render(f.read_text(), t, cfg, str(f))
                    self.assertNotIn("${", out, f)
                    self.assertNotIn("@if", out, f)


class TestApply(Sandbox):
    def cfg(self, **kw):
        from nebulix import config
        base = {"wallpaper_size": "1080p", "wallpaper": "gen-horizon"}
        base.update(kw)
        return config.validate(base)

    def seed_user_files(self):
        (self.home / ".config/gtk-4.0").mkdir(parents=True)
        (self.home / ".config/gtk-4.0/gtk.css").write_text("/* mine */\n")
        (self.home / ".config/starship.toml").write_text("# mine\n")

    def test_apply_then_undo_restores_everything(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        self.seed_user_files()
        before = self.snapshot()
        apply(self.cfg(), log=lambda *_: None)
        g = self.gs()
        self.assertEqual(g["org.gnome.desktop.interface|gtk-theme"], "'Nebulix-Dark'")
        self.assertIn("Nebulix-Icons", g["org.gnome.desktop.interface|icon-theme"])
        self.assertEqual(g["org.gnome.shell.extensions.dash-to-dock|dock-position"], "'BOTTOM'")
        self.assertIn("NEBULIX-BEGIN", (self.home / ".config/gtk-4.0/gtk.css").read_text())
        self.assertIn("/* mine */", (self.home / ".config/gtk-4.0/gtk.css").read_text())
        self.assertTrue((self.home / ".local/share/themes/Nebulix-Dark/gtk-3.0/gtk.css").exists())
        self.assertTrue(list((self.home / ".local/share/backgrounds/nebulix").glob("nebulix-gen-horizon-*.png")))
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({k: v for k, v in self.gs().items()}, {k: "'default'" for k in self.gs()})

    def test_missing_requirements_reported_but_rest_applied(self):
        from nebulix.apply import apply
        lines = []
        st = apply(self.cfg(), log=lines.append)
        self.assertTrue(any("User Themes" in m for m, _ in st.missing))
        self.assertTrue(any("Requisitos faltando" in ln for ln in lines))
        self.assertEqual(self.gs()["org.gnome.desktop.interface|gtk-theme"], "'Nebulix-Dark'")

    def test_reset_uses_system_defaults(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        self.seed_user_files()
        before = self.snapshot()
        (self.tmp / "state/gs.json").write_text(json.dumps({"org.gnome.desktop.interface|gtk-theme": "'MyOwn'"}))
        apply(self.cfg(), log=lambda *_: None)
        restore("reset", log=lambda *_: None)
        self.assertEqual(self.gs(), {})  # every touched key reset (not restored to 'MyOwn')
        self.assertEqual(self.snapshot(), before)

    def test_reapply_changes_accent_and_cleans_old_wallpaper(self):
        from nebulix.apply import apply
        apply(self.cfg(), log=lambda *_: None)
        apply(self.cfg(accent="magenta", window_buttons="mac", dock="ubuntu"), log=lambda *_: None)
        css = (self.home / ".local/share/themes/Nebulix-Dark/gtk-4.0/colors.css").read_text()
        self.assertIn("#FF4FD8", css)
        self.assertEqual(len(list((self.home / ".local/share/backgrounds/nebulix").glob("*.png"))), 1)
        g = self.gs()
        self.assertEqual(g["org.gnome.desktop.wm.preferences|button-layout"], "'close,minimize,maximize:appmenu'")
        self.assertEqual(g["org.gnome.shell.extensions.dash-to-dock|dock-position"], "'default'")  # released back to the original
        self.assertEqual(g["org.gnome.desktop.interface|accent-color"], "'pink'")

    def test_dry_run_touches_nothing(self):
        from nebulix.apply import apply
        self.seed_user_files()
        before = self.snapshot()
        apply(self.cfg(), dry=True, log=lambda *_: None)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.gs(), {})

    def test_migrates_01_state(self):
        from nebulix.restore import restore
        sd = self.home / ".local/share/nebulix"
        (sd / "backup/files").mkdir(parents=True)
        f = self.home / ".config/starship.toml"
        f.parent.mkdir(parents=True)
        f.write_text("# nebulix generated")
        orig = sd / "backup/files" / str(f).lstrip("/")
        orig.parent.mkdir(parents=True)
        orig.write_text("# user original")
        (sd / "manifest").write_text(f"{f}\n")
        (sd / "backed-up").write_text(f"{f}\n")
        (sd / "gsettings.before").write_text("org.gnome.desktop.interface\tgtk-theme\t'Yaru'\n")
        restore("undo", log=lambda *_: None)
        self.assertEqual(f.read_text(), "# user original")
        self.assertEqual(self.gs()["org.gnome.desktop.interface|gtk-theme"], "'Yaru'")


class TestCli(Sandbox):
    def test_config_set_applies_and_persists(self):
        from nebulix import cli, config
        self.assertEqual(cli.main(["config", "set", "wallpaper=none", "accent=cyan", "radius=10"]), 0)
        c = config.load()
        self.assertEqual((c["accent"], c["radius"], c["wallpaper"]), ("cyan", 10, "none"))
        self.assertEqual(cli.main(["config", "set", "radius=99"]), 2)
        self.assertEqual(config.load()["radius"], 10)


if __name__ == "__main__":
    unittest.main()


class TestArtWallpaper(Sandbox):
    def test_art_wallpaper_copied_as_is(self):
        from nebulix import config
        from nebulix.apply import apply
        apply(config.validate({"wallpaper": "orbit"}), log=lambda *_: None, only=["wallpaper"])
        f = self.home / ".local/share/backgrounds/nebulix/nebulix-orbit.png"
        self.assertEqual(f.read_bytes(), (ROOT / "images/wallpapers/nebulix-orbit.png").read_bytes())
        self.assertIn("nebulix-orbit.png", self.gs()["org.gnome.desktop.background|picture-uri"])
