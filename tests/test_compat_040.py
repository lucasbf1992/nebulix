# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility with what 0.4.0 wrote and produced (fixtures in tests/fixtures/0.4.0, captured from the 0.4.0 code)."""
import json
import shutil
import sys
import tempfile
import tomllib
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import ROOT, Sandbox  # noqa: E402

FIX = ROOT / "tests/fixtures/0.4.0"
THEMES = ("macos-dark", "macos-light", "nebulix", "nebulix-light")
FIXED_UUID = uuid.UUID("00000000-0000-4000-8000-000000000040")
V040_KEYS = {"theme", "accent", "variant", "radius", "window_buttons", "topbar", "dock", "dock_position", "dock_icon_size",
             "dock_opacity", "dock_zoom", "dock_zoom_factor", "terminal_opacity", "terminal_cursor", "terminal_font",
             "terminal_font_size", "terminal_padding", "terminal_line_height", "terminal_columns", "terminal_rows",
             "icons", "font", "vscode_theme", "wallpaper", "wallpaper_size", "components"}
EXT = '#!/bin/sh\nif [ "$1" = list ] && [ -z "$2" ]; then echo user-theme@gnome-shell-extensions.gcampax.github.com; fi\nexit 0\n'


def _components():
    from nebulix import config
    return [c for c in config.COMPONENTS if c != "wallpaper"]  # wallpapers are generated images, not part of the goldens


class Compat040(Sandbox):
    def setUp(self):
        super().setUp()
        for p in (mock.patch("nebulix.apply.uuid.uuid4", return_value=FIXED_UUID),
                  mock.patch("nebulix.apply.has_font", side_effect=lambda f: f in ("Inter", "JetBrains Mono"))):
            p.start()
            self.addCleanup(p.stop)

    def install_whitesur(self):
        for n in ("WhiteSur-dark", "WhiteSur-light", "WhiteSur-purple-dark", "WhiteSur-purple-light"):
            (self.home / ".local/share/icons" / n).mkdir(parents=True)

    def load_config(self, theme):
        from nebulix import config, paths
        paths.config_file().parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / "configs" / f"{theme}.toml", paths.config_file())
        return config.load()

    def install_manifest_home(self):
        """Put the 0.4.0 install (HOME after apply + fake gsettings) in the Sandbox."""
        src = FIX / "manifest/home"
        for f in sorted(src.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(src)).replace("@HOMEREL@", str(self.home).lstrip("/"))
                dest = self.home / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(f.read_bytes().replace(b"@HOME@", str(self.home).encode()))
        (self.tmp / "state/gs.json").write_text((FIX / "manifest/gs-after.json").read_text())
        (self.tmp / "bin/gnome-extensions").write_text(EXT)

    def expected_before(self):
        src = FIX / "manifest/before"
        return {str(f.relative_to(src)): f.read_bytes().replace(b"@HOME@", str(self.home).encode())
                for f in sorted(src.rglob("*")) if f.is_file()}

    def assert_back_to_before(self):
        self.assertEqual(self.snapshot(), self.expected_before())
        before = json.loads((FIX / "manifest/gs-before.json").read_text())
        before.setdefault("org.gnome.shell.extensions.user-theme|name", "''")  # 0.4.0 blanks it before recording it
        for k, v in self.gs().items():
            self.assertEqual(v, before.get(k, "'default'"), k)


class TestConfig040(Compat040):
    def test_fixture_configs_are_literal_040_and_load_unchanged(self):  # AC-1, AC-3
        from nebulix import config
        for th in THEMES:
            raw = tomllib.loads((FIX / "configs" / f"{th}.toml").read_text())
            self.assertEqual(set(raw), V040_KEYS, th)
            cfg = self.load_config(th)
            self.assertEqual(cfg["theme"], th)
            for k, v in raw.items():
                self.assertEqual(cfg[k], v, f"{th}/{k}")
            self.assertEqual(config.validate(raw)["theme"], th)


class TestGoldens040(Compat040):
    def apply_theme(self, th):
        from nebulix.apply import apply
        self.install_whitesur()
        apply(self.load_config(th), only=_components(), log=lambda *_: None)

    def test_icon_theme_per_theme_like_040(self):  # TC-6, TC-7
        key = "org.gnome.desktop.interface|icon-theme"
        for th, want in (("macos-dark", "WhiteSur-dark"), ("macos-light", "WhiteSur-light"),
                         ("nebulix", "Nebulix-Icons"), ("nebulix-light", "Nebulix-Icons")):
            with self.subTest(th):
                self.setUp_clean()
                self.apply_theme(th)
                self.assertEqual(self.gs()[key], f"'{want}'")
                overlay = self.home / ".local/share/icons/Nebulix-Icons"
                if th.startswith("macos"):
                    self.assertFalse(overlay.exists())
                else:
                    scheme = "light" if th.endswith("light") else "dark"
                    self.assertIn(f"Inherits=WhiteSur-purple-{scheme}", (overlay / "index.theme").read_text())

    def setUp_clean(self):
        """Fresh HOME and fake gsettings between the themes of a subTest loop."""
        shutil.rmtree(self.home)
        self.home.mkdir()
        (self.tmp / "state/gs.json").unlink(missing_ok=True)

    def test_applied_result_matches_the_040_goldens(self):  # TC-8
        for th in THEMES:
            with self.subTest(th):
                self.setUp_clean()
                self.apply_theme(th)
                gold = FIX / "goldens" / th
                got = self.gs()
                for k, v in json.loads((gold / "gs.json").read_text()).items():
                    self.assertEqual(got.get(k), v, k)  # keys added by later versions are not compared
                for f in sorted((gold / "files").rglob("*")):
                    if f.is_file():
                        rel = f.relative_to(gold / "files")
                        self.assertEqual((self.home / rel).read_text(), f.read_text(), str(rel))

    def test_rendered_terminal_files_match_the_040_goldens(self):  # TC-8 (terminal)
        from nebulix.apply import render_all
        for th in THEMES:
            with self.subTest(th):
                stage = Path(tempfile.mkdtemp(prefix="nbx-stage-"))
                self.addCleanup(shutil.rmtree, stage, True)
                render_all(self.load_config(th), stage, log=lambda *_: None)
                for f in sorted((FIX / "goldens" / th / "terminal").iterdir()):
                    self.assertEqual((stage / "terminal" / f.name).read_text(), f.read_text(), f"{th}/{f.name}")


class TestManifest040(Compat040):
    def test_manifest_covers_every_040_prefix(self):  # guards the fixture itself
        man = (FIX / "manifest/home/.local/share/nebulix/manifest").read_text().splitlines()
        for prefix in ("gtkblock:", "ptyxis:", "gnt:", "vscode:", "vscext:", "ext:", "flatpak"):
            self.assertTrue(any(m.startswith(prefix) for m in man), prefix)

    def test_undo_restores_a_040_install(self):  # TC-3
        from nebulix.restore import restore
        self.install_manifest_home()
        self.assertTrue(restore("undo", log=lambda *_: None))
        self.assert_back_to_before()

    def test_reset_removes_a_040_install_files(self):  # TC-3 (reset)
        from nebulix.restore import restore
        self.install_manifest_home()
        self.assertTrue(restore("reset", log=lambda *_: None))
        want, got = self.expected_before(), self.snapshot()
        code = ".config/Code/User/settings.json"
        self.assertNotIn("workbench.colorTheme", got.pop(code).decode())  # reset drops the key instead of restoring "Mine"
        want.pop(code)
        self.assertEqual(got, want)
        self.assertEqual(self.gs(), {})

    def test_reapply_over_a_040_install_then_undo(self):  # TC-3 (upgrade path)
        from nebulix import config
        from nebulix.apply import apply
        from nebulix.restore import restore
        self.install_manifest_home()
        cfg = config.apply_theme(config.validate({"vscode_theme": "follow"}), "nebulix")
        apply(cfg, only=_components(), log=lambda *_: None)
        restore("undo", log=lambda *_: None)
        self.assert_back_to_before()
