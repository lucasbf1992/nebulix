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
        self.assertEqual(config.validate({})["accent"], "auto")
        self.assertEqual(config.accent_hex(config.validate({})), "#A66BFF")
        config.validate({"accent": "#12ABef", "radius": 6})
        for bad in ({"accent": "roxo"}, {"radius": 99}, {"variant": "x"}, {"components": ["nope"]}, {"dock_opacity": True}):
            with self.assertRaises(ValueError):
                config.validate(bad)

    def test_contrast_all_themes_and_accents(self):
        from nebulix import config, palette, themes
        for th in config.CHOICES["theme"]:
            for acc, var in product(("auto", *themes.accent_names(th)), config.CHOICES["variant"]):
                for a, b, c, need in palette.contrast_report(config.validate({"theme": th, "accent": acc, "variant": var})):
                    self.assertGreaterEqual(c, need, f"{th}/{acc}/{var} {a} on {b}")

    def test_custom_hex_accent_keeps_contrast_in_every_theme(self):
        from nebulix import config, palette
        for th in config.CHOICES["theme"]:
            for hx in ("#FFFF00", "#000080", "#808080", "#00FF00"):
                for a, b, c, need in palette.contrast_report(config.validate({"theme": th, "accent": hx})):
                    if a in ("accent-text", "on-fill", "on-solid"):
                        self.assertGreaterEqual(c, need, f"{th}/{hx} {a} on {b}")

    def test_theme_catalogue_matches_config_choices(self):
        from nebulix import config, themes
        self.assertEqual(set(config.CHOICES["theme"]), set(themes.ids()))

    def test_theme_package_and_accent_rules(self):
        from nebulix import config, themes
        c = config.apply_theme(config.validate({"accent": "magenta", "radius": 20}), "macos-dark")
        self.assertEqual((c["theme"], c["accent"], c["window_buttons"], c["topbar"], c["radius"]),
                         ("macos-dark", "auto", "mac", "translucent", 10))
        self.assertEqual(config.accent_hex(c), "#0A84FF")
        self.assertEqual(config.gnome_accent(c), "blue")
        config.validate(dict(c, accent="graphite"))
        with self.assertRaises(ValueError):
            config.validate(dict(c, accent="magenta"))  # a Nebulix-only accent name
        with self.assertRaises(ValueError):
            config.apply_theme(c, "nao-existe")
        self.assertEqual(themes.resolve("macos"), "macos-dark")
        self.assertEqual(config.apply_theme(c, "nebulix")["window_buttons"], "gnome")
        # each item stays adjustable after choosing a theme
        self.assertEqual(config.validate(dict(c, radius=18, window_buttons="gnome"))["radius"], 18)

    def test_light_themes_are_light(self):
        from nebulix import config, palette
        for th in ("macos-light", "nebulix-light"):
            _, t = palette.tokens(config.validate({"theme": th}))
            self.assertEqual(t["scheme"], "light")
            self.assertGreater(palette.lum(t["bg-1"]), palette.lum(t["fg-0"]))
        _, t = palette.tokens(config.validate({"theme": "macos-dark"}))
        self.assertEqual((t["bg-0"], t["fg-0"], t["purple"]), ("#161616", "#F5F5F7", "#0A84FF"))

    def test_templates_render_everywhere(self):
        from nebulix import config, palette, render, paths
        base = paths.data_dir() / "templates"
        for th, var, wb, bar, dock in product(config.CHOICES["theme"], ("dark", "darker"), ("gnome", "mac"), config.CHOICES["topbar"], ("macos", "ubuntu")):
            cfg = config.validate({"theme": th, "variant": var, "window_buttons": wb, "topbar": bar, "dock": dock, "radius": 20})
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


class TestThemes(Sandbox):
    def cfg(self, **kw):
        from nebulix import config
        base = {"wallpaper": "none"}
        base.update(kw)
        return config.validate(base)

    def render(self, **kw):
        from nebulix import config
        from nebulix.apply import render_all
        out = self.tmp / "out"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        render_all(config.apply_theme(self.cfg(), kw.pop("theme")), out)
        return out

    def test_light_theme_uses_light_stylesheets_and_editors(self):
        out = self.render(theme="macos-light")
        self.assertIn("gtk-contained.css", (out / "gtk-3.0/gtk.css").read_text())
        self.assertNotIn("gtk-contained-dark", (out / "gtk-3.0/gtk.css").read_text())
        self.assertIn("Default-light.css", (out / "gtk-4.0/gtk.css").read_text())
        self.assertIn("gnome-shell-light.css", (out / "gnome-shell/gnome-shell.css").read_text())
        self.assertIn("vim.o.background = 'light'", (out / "nvim/colors/nebulix.lua").read_text())
        pkg = json.loads((out / "vscode/nebulix-theme/package.json").read_text())
        self.assertEqual(pkg["contributes"]["themes"][0]["uiTheme"], "vs")
        ui = {t["label"]: t["uiTheme"] for t in pkg["contributes"]["themes"]}
        self.assertEqual(ui, {"Nebulix macOS Light": "vs", "Nebulix Dark": "vs-dark", "Nebulix macOS Dark": "vs-dark", "Nebulix Light": "vs"})
        for t in pkg["contributes"]["themes"]:
            self.assertTrue((out / "vscode/nebulix-theme" / t["path"]).exists())
        theme = json.loads((out / "vscode/nebulix-theme/themes/macos-light.json").read_text())
        self.assertEqual((theme["type"], theme["colors"]["editor.background"]), ("light", "#FFFFFF"))
        self.assertIn("#FFFFFF", (out / "btop/nebulix.theme").read_text())
        self.assertIn("Name=Nebulix-Light", (out / "index.theme").read_text())

    def test_dark_theme_keeps_dark_stylesheets(self):
        for th in ("nebulix", "macos-dark"):
            out = self.render(theme=th)
            self.assertIn("gtk-contained-dark.css", (out / "gtk-3.0/gtk.css").read_text())
            self.assertIn("gnome-shell-dark.css", (out / "gnome-shell/gnome-shell.css").read_text())
            self.assertIn("vim.o.background = 'dark'", (out / "nvim/colors/nebulix.lua").read_text())

    def test_macos_dark_colours_and_translucent_bar(self):
        out = self.render(theme="macos-dark")
        colors = (out / "gtk-4.0/colors.css").read_text()
        self.assertIn("@define-color window_bg_color #1E1E1E;", colors)
        self.assertIn("@define-color accent_bg_color #0065CC;", colors)  # blue darkened to keep 4.5:1 with white text
        self.assertIn("#0A84FF", (out / "gtk-4.0/tweaks.css").read_text() + (out / "gnome-shell/gnome-shell.css").read_text())
        shell = (out / "gnome-shell/gnome-shell.css").read_text()
        self.assertIn("rgba(30, 30, 30, 0.7) !important", shell)  # beats Yaru's #panel rule
        self.assertIn("windowcontrols button.close", (out / "gtk-4.0/tweaks.css").read_text())
        self.assertNotIn("radius-lg", shell)

    def test_apply_each_theme_then_undo(self):
        from nebulix import config
        from nebulix.apply import apply
        from nebulix.restore import restore
        (self.home / ".config").mkdir()
        before = self.snapshot()
        expect = {"nebulix": ("'prefer-dark'", "'Nebulix-Dark'"), "macos-dark": ("'prefer-dark'", "'Nebulix-Dark'"),
                  "macos-light": ("'prefer-light'", "'Nebulix-Light'"), "nebulix-light": ("'prefer-light'", "'Nebulix-Light'")}
        for th, (scheme, gtk) in expect.items():
            apply(config.apply_theme(self.cfg(), th), log=lambda *_: None)
            g = self.gs()
            self.assertEqual(g["org.gnome.desktop.interface|color-scheme"], scheme, th)
            self.assertEqual(g["org.gnome.desktop.interface|gtk-theme"], gtk, th)
            themes_dir = self.home / ".local/share/themes"
            self.assertEqual([p.name for p in themes_dir.iterdir()], [gtk.strip("'")], th)  # the other scheme's dir is gone
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.snapshot(), before)

    def test_macos_uses_plain_whitesur_and_nebulix_uses_overlay(self):
        from nebulix import config, icons
        from nebulix.apply import apply
        for n in ("WhiteSur-dark", "WhiteSur-light", "WhiteSur-purple-dark", "WhiteSur-purple-light"):
            (self.home / ".local/share/icons" / n).mkdir(parents=True)
        key = "org.gnome.desktop.interface|icon-theme"
        apply(config.apply_theme(self.cfg(), "macos-dark"), log=lambda *_: None)
        self.assertEqual(self.gs()[key], "'WhiteSur-dark'")
        apply(config.apply_theme(self.cfg(), "macos-light"), log=lambda *_: None)
        self.assertEqual(self.gs()[key], "'WhiteSur-light'")
        apply(config.apply_theme(self.cfg(), "nebulix-light"), log=lambda *_: None)
        self.assertEqual(self.gs()[key], "'Nebulix-Icons'")
        idx = (self.home / ".local/share/icons/Nebulix-Icons/index.theme").read_text()
        self.assertIn("Inherits=WhiteSur-purple-light", idx)
        self.assertEqual(icons.base_name("macos-dark"), "WhiteSur-dark")
        self.assertEqual(icons.whitesur_color("macos-dark"), "default")

    def test_whitesur_install_variant_is_passed_to_installer(self):
        from nebulix import icons
        self.assertEqual(icons.whitesur_color("nebulix"), "purple")
        self.assertEqual(icons.whitesur_color("macos-light"), "default")

    def test_font_follows_theme_only_when_installed(self):
        from unittest import mock
        from nebulix import config
        from nebulix.apply import apply
        key = "org.gnome.desktop.interface|font-name"
        with mock.patch("nebulix.apply.has_font", return_value=False):
            st = apply(config.apply_theme(self.cfg(), "macos-dark"), log=lambda *_: None)
        self.assertNotIn(key, self.gs())
        self.assertTrue(any("Inter" in m for m, _ in st.missing))
        with mock.patch("nebulix.apply.has_font", return_value=True):
            apply(config.apply_theme(self.cfg(), "macos-dark"), log=lambda *_: None)
            self.assertEqual(self.gs()[key], "'Inter 11'")
            apply(dict(config.apply_theme(self.cfg(), "macos-dark"), font="keep"), log=lambda *_: None)
            self.assertEqual(self.gs()[key], "'default'")  # released back to the original
            apply(config.apply_theme(self.cfg(), "nebulix"), log=lambda *_: None)

    def test_generated_wallpaper_of_light_theme_is_rendered_from_dark_tokens(self):
        from nebulix import config
        from nebulix.apply import apply
        apply(config.apply_theme(self.cfg(wallpaper="gen-horizon", wallpaper_size="1080p"), "macos-light"), log=lambda *_: None, only=["wallpaper"])
        self.assertTrue(list((self.home / ".local/share/backgrounds/nebulix").glob("nebulix-gen-horizon-*.png")))

    def test_gtk_css_parses_for_every_theme(self):
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            from gi.repository import Gtk
        except Exception:
            self.skipTest("GTK4 indisponível")
        from nebulix import config
        for th in config.CHOICES["theme"]:
            out = self.render(theme=th)
            for f in ("colors.css", "tweaks.css"):
                errs = []
                prov = Gtk.CssProvider()
                prov.connect("parsing-error", lambda _p, sec, e: errs.append(e.message))
                prov.load_from_string((out / "gtk-4.0" / f).read_text())
                self.assertEqual(errs, [], f"{th}/{f}")


class TestVscodeSetting(Sandbox):
    KEY = "workbench.colorTheme"

    def cfg(self, **kw):
        from nebulix import config
        base = {"wallpaper": "none", "vscode_theme": "follow"}
        base.update(kw)
        return config.validate(base)

    def settings(self, name="Code"):
        return self.home / ".config" / name / "User" / "settings.json"

    def run_apply(self, **kw):
        from nebulix.apply import apply
        apply(self.cfg(**kw), log=lambda *_: None, only=["vscode"])

    def test_editor_missing_touches_nothing(self):
        self.run_apply()
        self.assertFalse((self.home / ".config/Code").exists())

    def test_creates_file_and_undo_removes_it(self):
        from nebulix.restore import restore
        self.settings().parent.mkdir(parents=True)
        before = self.snapshot()
        self.run_apply()
        self.assertEqual(json.loads(self.settings().read_text()), {self.KEY: "Nebulix Dark"})
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.snapshot(), before)

    def test_jsonc_comments_and_other_keys_survive_the_cycle(self):
        from nebulix import vscode
        from nebulix.restore import restore
        orig = '// meu editor\n{\n    /* fonte */ "editor.fontSize": 14, // grande\n    "files.autoSave": "afterDelay",\n}\n'
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text(orig)
        self.run_apply(theme="macos-dark")
        txt = self.settings().read_text()
        self.assertEqual(vscode.get(txt), "Nebulix macOS Dark")
        for keep in ("// meu editor", "/* fonte */", "// grande", '"editor.fontSize": 14', '"files.autoSave": "afterDelay"'):
            self.assertIn(keep, txt)
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.settings().read_text(), orig.replace('"files.autoSave": "afterDelay",\n}', '"files.autoSave": "afterDelay",\n}'))

    def test_existing_key_restored_on_undo_removed_on_reset(self):
        from nebulix import vscode
        from nebulix.restore import restore
        orig = '{\n  "workbench.colorTheme": "Monokai", // meu\n  "a": 1\n}\n'
        for mode in ("undo", "reset"):
            self.settings().parent.mkdir(parents=True, exist_ok=True)
            self.settings().write_text(orig)
            self.run_apply()
            self.run_apply(theme="nebulix-light")  # re-apply must keep the ORIGINAL previous value
            self.assertEqual(vscode.get(self.settings().read_text()), "Nebulix Light")
            restore(mode, log=lambda *_: None)
            txt = self.settings().read_text()
            if mode == "undo":
                self.assertEqual(txt, orig)
            else:
                self.assertIsNone(vscode.get(txt))
                self.assertIn('"a": 1', txt)
            shutil.rmtree(self.home / ".local", ignore_errors=True)

    def test_specific_theme_and_keep_releases(self):
        from nebulix import vscode
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text('{"workbench.colorTheme": "Mine"}')
        self.run_apply(vscode_theme="macos-light")
        self.assertEqual(vscode.get(self.settings().read_text()), "Nebulix macOS Light")
        self.run_apply(vscode_theme="keep")
        self.assertEqual(vscode.get(self.settings().read_text()), "Mine")

    def test_insiders_and_codium_and_invalid_file(self):
        from nebulix import vscode
        for n in ("Code - Insiders", "VSCodium"):
            self.settings(n).parent.mkdir(parents=True)
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text("not json at all")
        self.run_apply()
        self.assertEqual(self.settings().read_text(), "not json at all")  # left alone
        self.assertEqual(vscode.get(self.settings("VSCodium").read_text()), "Nebulix Dark")
        self.assertEqual(vscode.get(self.settings("Code - Insiders").read_text()), "Nebulix Dark")

    def test_dry_run_and_empty_object_insert(self):
        from nebulix import vscode
        from nebulix.apply import apply
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text("{}")
        apply(self.cfg(), dry=True, log=lambda *_: None, only=["vscode"])
        self.assertEqual(self.settings().read_text(), "{}")
        self.assertEqual(json.loads(vscode.set_key("{}", "X")), {self.KEY: "X"})
        self.assertEqual(json.loads(vscode.set_key('{"a": 1}', "X")), {"a": 1, self.KEY: "X"})
        self.assertEqual(json.loads(vscode.remove_key('{"a": 1, "workbench.colorTheme": "X"}')), {"a": 1})


class TestCli(Sandbox):
    def test_theme_command(self):
        from nebulix import cli, config
        self.assertEqual(cli.main(["theme", "macos-dark", "--no-apply"]), 0)
        c = config.load()
        self.assertEqual((c["theme"], c["accent"], c["window_buttons"]), ("macos-dark", "auto", "mac"))
        self.assertEqual(cli.main(["theme", "claro", "--no-apply"]), 0)
        self.assertEqual(config.load()["theme"], "macos-light")
        self.assertEqual(cli.main(["theme", "xyz"]), 2)
        self.assertEqual(config.load()["theme"], "macos-light")
        self.assertEqual(cli.main(["theme"]), 0)
        c["wallpaper"] = "none"
        config.save(c)
        self.assertEqual(cli.main(["theme", "nebulix"]), 0)
        self.assertEqual(self.gs()["org.gnome.desktop.interface|gtk-theme"], "'Nebulix-Dark'")

    def test_old_config_without_theme_still_works(self):
        from nebulix import config
        f = self.home / ".config/nebulix/config.toml"
        f.parent.mkdir(parents=True)
        f.write_text('accent = "magenta"\nvariant = "darker"\nradius = 10\n')
        c = config.load()
        self.assertEqual((c["theme"], c["accent"]), ("nebulix", "magenta"))
        self.assertEqual(config.accent_hex(c), "#FF4FD8")

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
