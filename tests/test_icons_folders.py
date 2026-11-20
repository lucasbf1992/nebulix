# SPDX-License-Identifier: GPL-3.0-or-later
"""icon_folders: the Nebulix squircle folders as a layer over the active icon set (auto | nebulix | conjunto)."""
import contextlib
import io
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import Sandbox  # noqa: E402

KEY = "org.gnome.desktop.interface|icon-theme"
THEMES = (("nebulix", "dark"), ("macos-dark", "dark"), ("nebulix-light", "light"), ("macos-light", "light"))
SET_FOLDERS = {"whitesur": "WhiteSur", "mactahoe": "MacTahoe", "mcmojave": "McMojave-circle"}


class IconFolders(Sandbox):
    def setUp(self):
        super().setUp()
        from nebulix import config, icons, paths
        self.config, self.icons, self.paths = config, icons, paths
        self.enter(self.no_network())
        for sid in SET_FOLDERS:
            for th, _ in THEMES:
                self.mkicons(icons.base_name(th, sid))
        for n in ("Papirus-Dark", "Papirus-Light"):
            self.mkicons(n)

    def enter(self, cm):
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def mkicons(self, name):
        (self.home / ".local/share/icons" / name).mkdir(parents=True, exist_ok=True)

    def cfg(self, theme="nebulix", **kw):
        return self.config.validate({**self.config.apply_theme(self.config.validate({}), theme), "wallpaper": "none", **kw})

    def apply(self, cfg):
        from nebulix.apply import apply
        apply(cfg, only=["icons"], log=lambda *_: None)
        return self.gs().get(KEY)

    def inherits(self):
        for ln in (self.home / ".local/share/icons/Nebulix-Icons/index.theme").read_text().splitlines():
            if ln.startswith("Inherits="):
                return ln[len("Inherits="):]

    def cli(self, *argv):
        from nebulix import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def overlay_exists(self):
        return (self.home / ".local/share/icons/Nebulix-Icons").exists()


class TestResolution(IconFolders):
    def test_default_is_auto_and_follows_the_theme(self):
        self.assertEqual(self.config.DEFAULTS["icon_folders"], "auto")
        for th, want in (("macos-dark", False), ("nebulix", True), ("macos-light", False), ("nebulix-light", True)):
            with self.subTest(th):
                self.assertIs(self.icons.uses_overlay(th), want)
                self.assertIs(self.icons.uses_overlay(th, "auto"), want)

    def test_explicit_values_override_the_theme(self):
        for th, _ in THEMES:
            self.assertTrue(self.icons.uses_overlay(th, "nebulix"))
            self.assertFalse(self.icons.uses_overlay(th, "conjunto"))

    def test_invalid_value_is_rejected(self):
        for bad in ("x", ""):
            with self.subTest(bad), self.assertRaises(ValueError) as cm:
                self.config.validate({"icon_folders": bad})
            self.assertIn("icon_folders", str(cm.exception))
        code, _ = self.cli("config", "set", "icon_folders=x", "--no-apply")
        self.assertNotEqual(code, 0)

    def test_icon_folders_is_not_part_of_a_theme_package(self):
        from nebulix import themes
        self.assertNotIn("icon_folders", themes.PACKAGE_KEYS)


class TestAutoFollowsTheme(IconFolders):
    def test_apply_follows_the_theme(self):
        want = {"macos-dark": "'WhiteSur-dark'", "nebulix": "'Nebulix-Icons'",
                "macos-light": "'WhiteSur-light'", "nebulix-light": "'Nebulix-Icons'"}
        for th in ("macos-dark", "nebulix", "macos-light", "nebulix-light"):
            with self.subTest(th):
                self.assertEqual(self.apply(self.cfg(th)), want[th])

    def test_theme_switch_through_the_cli_follows(self):
        self.cli("theme", "macos-dark", "--no-apply")
        self.assertEqual(self.apply(self.config.load()), "'WhiteSur-dark'")
        self.cli("theme", "nebulix", "--no-apply")
        self.assertEqual(self.config.load()["icon_folders"], "auto")
        self.assertEqual(self.apply(self.config.load()), "'Nebulix-Icons'")


class TestExplicitChoice(IconFolders):
    def test_nebulix_on_a_macos_theme_layers_the_overlay(self):
        for th, scheme in (("macos-dark", "dark"), ("macos-light", "light")):
            with self.subTest(th):
                self.assertEqual(self.apply(self.cfg(th, icon_folders="nebulix")), "'Nebulix-Icons'")
                self.assertTrue(self.inherits().startswith(f"WhiteSur-{scheme}"))

    def test_conjunto_on_a_nebulix_theme_uses_the_set_folder(self):
        self.assertEqual(self.apply(self.cfg("nebulix", icon_folders="conjunto")), "'WhiteSur-purple-dark'")
        self.assertFalse(self.overlay_exists())
        self.assertEqual(self.apply(self.cfg("nebulix-light", icon_folders="conjunto")), "'WhiteSur-purple-light'")

    def test_choice_survives_config_set_of_other_keys(self):
        self.cli("config", "set", "icon_folders=conjunto", "--no-apply")
        self.cli("config", "set", "radius=10", "--no-apply")
        self.cli("config", "set", "accent=green", "--no-apply")
        c = self.config.load()
        self.assertEqual((c["icon_folders"], c["radius"], c["accent"]), ("conjunto", 10, "green"))
        self.assertEqual(self.apply(c), f"'{self.icons.current_base('whitesur', 'nebulix', 'green')}'")
        self.assertFalse(self.overlay_exists())

    def test_choice_survives_a_theme_switch(self):
        self.cli("config", "set", "icon_folders=nebulix", "--no-apply")
        self.cli("theme", "macos-dark", "--no-apply")
        self.assertEqual(self.config.load()["icon_folders"], "nebulix")
        self.assertEqual(self.apply(self.config.load()), "'Nebulix-Icons'")

    def test_choice_is_saved_in_the_config_file(self):
        self.config.save(self.cfg("nebulix", icon_folders="conjunto"))
        self.assertIn('icon_folders = "conjunto"', self.paths.config_file().read_text())
        self.assertEqual(self.config.load()["icon_folders"], "conjunto")


class TestOverlayInheritance(IconFolders):
    def gs_set(self, value):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", value], check=True)

    def test_overlay_inherits_from_the_active_set(self):
        for sid, pre in SET_FOLDERS.items():
            for th, scheme in THEMES:
                with self.subTest(sid=sid, theme=th):
                    cfg = self.cfg(th, icons=sid, icon_folders="nebulix")
                    self.assertEqual(self.apply(cfg), "'Nebulix-Icons'")
                    base = self.icons.base_name(th, sid)
                    self.assertTrue(base.startswith(pre) and base.endswith(scheme))
                    self.assertEqual(self.inherits(), f"{base},Papirus-{scheme.capitalize()},hicolor")

    def test_conjunto_uses_the_set_folder_not_the_overlay(self):
        for sid in SET_FOLDERS:
            for th, _ in THEMES:
                with self.subTest(sid=sid, theme=th):
                    got = self.apply(self.cfg(th, icons=sid, icon_folders="conjunto"))
                    self.assertEqual(got, f"'{self.icons.base_name(th, sid)}'")

    def test_papirus_with_nebulix_inherits_from_papirus(self):
        for th, scheme in THEMES:
            with self.subTest(th):
                self.assertEqual(self.apply(self.cfg(th, icons="papirus", icon_folders="nebulix")), "'Nebulix-Icons'")
                self.assertEqual(self.inherits(), f"Papirus-{scheme.capitalize()},hicolor")

    def test_papirus_without_the_overlay_is_plain_papirus(self):
        self.assertEqual(self.apply(self.cfg("nebulix", icons="papirus", icon_folders="conjunto")), "'Papirus-Dark'")
        self.assertEqual(self.apply(self.cfg("macos-light", icons="papirus")), "'Papirus-Light'")

    def test_keep_never_touches_the_icon_theme(self):
        self.gs_set("'Adwaita'")
        for fo in ("auto", "nebulix", "conjunto"):
            with self.subTest(fo):
                self.apply(self.cfg("nebulix", icons="keep", icon_folders=fo))
                self.assertEqual(self.gs().get(KEY), "'Adwaita'")
                self.assertFalse(self.overlay_exists())

    def test_missing_set_folder_falls_back_to_papirus(self):
        for p in (self.home / ".local/share/icons").iterdir():
            if not p.name.startswith("Papirus"):
                shutil.rmtree(p)
        self.assertEqual(self.apply(self.cfg("macos-dark", icon_folders="nebulix")), "'Nebulix-Icons'")
        self.assertEqual(self.inherits(), "Papirus-Dark,hicolor")
        self.assertEqual(self.apply(self.cfg("macos-dark")), "'Papirus-Dark'")

    def test_overlay_folders_are_nebulix_squircles(self):
        self.apply(self.cfg("macos-dark", icon_folders="nebulix"))
        svg = (self.home / ".local/share/icons/Nebulix-Icons/scalable/places/folder.svg").read_text()
        self.assertIn("<svg", svg)

    def test_overlay_inherits_the_folder_current_base_resolves(self):
        cfg = self.cfg("nebulix", icon_folders="nebulix", accent="green")
        self.assertFalse(self.icons.has_theme(self.icons.base_name("nebulix", "whitesur", "green")))
        self.apply(cfg)
        self.assertEqual(self.inherits().split(",")[0], self.icons.current_base("whitesur", "nebulix", "green"))
