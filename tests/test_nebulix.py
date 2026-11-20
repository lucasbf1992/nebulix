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

    def test_extension_is_registered_and_old_entry_replaced(self):
        from nebulix import __version__
        from nebulix.restore import restore
        ext = self.home / ".vscode/extensions"
        ext.mkdir(parents=True)
        (ext / "extensions.json").write_text(json.dumps([
            {"identifier": {"id": "other.thing"}, "version": "1", "relativeLocation": "other.thing-1"},
            {"identifier": {"id": "nebulix.nebulix-theme"}, "version": "0.2.0", "relativeLocation": "nebulix.nebulix-theme-0.2.0"}]))
        (ext / ".obsolete").write_text(json.dumps({"nebulix.nebulix-theme-%s" % __version__: True, "x.y-1": True}))
        self.run_apply()
        reg = json.loads((ext / "extensions.json").read_text())
        ours = [e for e in reg if e["identifier"]["id"] == "nebulix.nebulix-theme"]
        self.assertEqual([e["version"] for e in ours], [__version__])
        self.assertEqual(ours[0]["relativeLocation"], f"nebulix.nebulix-theme-{__version__}")
        self.assertTrue(Path(ours[0]["location"]["fsPath"]).is_dir())
        self.assertEqual(json.loads((ext / ".obsolete").read_text()), {"x.y-1": True})
        restore("undo", log=lambda *_: None)
        reg = json.loads((ext / "extensions.json").read_text())
        self.assertEqual([e["identifier"]["id"] for e in reg], ["other.thing"])

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


FAKE_EXT = '''#!/usr/bin/env bash
# lists the Ubuntu Dock and User Themes; the zoom extension only appears once FAKE_ZOOM_KNOWN exists
if [ "$1" = list ] && [ -z "$2" ]; then
  echo ubuntu-dock@ubuntu.com; echo user-theme@gnome-shell-extensions.gcampax.github.com
  [ -e "$FAKE_STATE/zoom_known" ] && echo nebulix-dock-zoom@nebulix.github.io
fi
exit 0
'''
ZOOM_UUID = "nebulix-dock-zoom@nebulix.github.io"


class TestDockZoom(Sandbox):
    def setUp(self):
        super().setUp()
        (self.tmp / "bin/gnome-extensions").write_text(FAKE_EXT)

    def cfg(self, **kw):
        from nebulix import config
        base = {"wallpaper": "none", "dock_zoom": "on", "dock_zoom_factor": 150}
        base.update(kw)
        return config.validate(base)

    def enabled(self):
        import re
        return re.findall(r"'([^']+)'", self.gs().get("org.gnome.shell|enabled-extensions", ""))

    def test_config_validation(self):
        from nebulix import config
        self.assertEqual(config.validate({})["dock_zoom"], "off")
        for bad in ({"dock_zoom": "maybe"}, {"dock_zoom_factor": 50}, {"dock_zoom_factor": 300}):
            with self.assertRaises(ValueError):
                config.validate(bad)

    def test_off_by_default_installs_nothing(self):
        from nebulix.apply import apply
        apply(self.cfg(dock_zoom="off"), log=lambda *_: None)
        self.assertFalse((self.home / ".local/share/gnome-shell/extensions" / ZOOM_UUID).exists())
        self.assertNotIn(ZOOM_UUID, self.enabled())

    def test_on_installs_enables_and_asks_relogin_once(self):
        import json
        from nebulix.apply import apply
        st = apply(self.cfg(), log=lambda *_: None)
        d = self.home / ".local/share/gnome-shell/extensions" / ZOOM_UUID
        self.assertTrue((d / "extension.js").exists() and (d / "metadata.json").exists())
        self.assertEqual(json.loads((self.home / ".config/nebulix/dock-zoom.json").read_text()), {"factor": 1.5})
        self.assertIn(ZOOM_UUID, self.enabled())
        self.assertTrue(any("sair" in f or "saia" in f for _m, f in st.missing))
        (self.tmp / "state/zoom_known").write_text("")
        st = apply(self.cfg(dock_zoom_factor=180), log=lambda *_: None)
        self.assertEqual([m for m, _f in st.missing if "zoom" in m], [])
        self.assertEqual(json.loads((self.home / ".config/nebulix/dock-zoom.json").read_text()), {"factor": 1.8})
        self.assertEqual(self.enabled().count(ZOOM_UUID), 1)

    def test_turning_off_removes_everything(self):
        from nebulix.apply import apply
        apply(self.cfg(), log=lambda *_: None)
        apply(self.cfg(dock_zoom="off"), log=lambda *_: None)
        self.assertFalse((self.home / ".local/share/gnome-shell/extensions" / ZOOM_UUID).exists())
        self.assertFalse((self.home / ".config/nebulix/dock-zoom.json").exists())
        self.assertNotIn(ZOOM_UUID, self.enabled())

    def test_undo_and_reset_disable_and_remove(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        for mode in ("undo", "reset"):
            apply(self.cfg(), log=lambda *_: None)
            self.assertIn(ZOOM_UUID, self.enabled())
            restore(mode, log=lambda *_: None)
            self.assertNotIn(ZOOM_UUID, self.enabled())
            self.assertFalse(list(self.home.rglob("nebulix-dock-zoom*")), mode)
            self.assertFalse((self.home / ".config/nebulix/dock-zoom.json").exists())

    def test_keeps_other_enabled_extensions(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        (self.tmp / "state/gs.json").write_text(json.dumps({"org.gnome.shell|enabled-extensions": "['a@b', 'c@d']"}))
        apply(self.cfg(), log=lambda *_: None)
        self.assertEqual(self.enabled(), ["a@b", "c@d", ZOOM_UUID])
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.enabled(), ["a@b", "c@d"])

    def test_missing_ubuntu_dock_is_reported(self):
        from nebulix.apply import apply
        (self.tmp / "bin/gnome-extensions").write_text("#!/bin/sh\nexit 0\n")
        st = apply(self.cfg(), log=lambda *_: None)
        self.assertTrue(any("Ubuntu Dock" in m for m, _ in st.missing))

    def test_doctor_reports_zoom_state(self):
        from nebulix import config, doctor
        config.save(self.cfg())
        msgs = [m for _l, m, _f in doctor.check()]
        self.assertTrue(any("nebulix-dock-zoom" in m for m in msgs), msgs)

    def test_extension_files_are_valid(self):
        import json
        d = ROOT / "extensions" / ZOOM_UUID
        meta = json.loads((d / "metadata.json").read_text())
        self.assertEqual(meta["uuid"], ZOOM_UUID)
        self.assertIn("50", meta["shell-version"])
        self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", (d / "extension.js").read_text())



FAKE_DCONF = '''#!/usr/bin/env python3
import json, os, sys
f = os.path.join(os.environ["FAKE_STATE"], "dconf.json")
d = json.load(open(f)) if os.path.exists(f) else {}
a = sys.argv[1:]
if a[0] == "read": print(d.get(a[1], ""))
elif a[0] == "write": d[a[1]] = a[2]
elif a[0] == "load": d["load:" + a[1]] = sys.stdin.read()
elif a[0] == "reset":
    for k in [k for k in d if k.endswith(a[-1]) or k == "load:" + a[-1]]:
        d.pop(k)
json.dump(d, open(f, "w"))
'''


class TestTerminal(Sandbox):
    PT = "org.gnome.Ptyxis"

    def setUp(self):
        super().setUp()
        (self.tmp / "bin/dconf").write_text(FAKE_DCONF)
        (self.tmp / "bin/dconf").chmod(0o755)
        (self.tmp / "state/gs.json").write_text(json.dumps({f"{self.PT}|profile-uuids": "@as []", f"{self.PT}|default-profile-uuid": "''"}))

    def cfg(self, theme="nebulix", **kw):
        from nebulix import config
        return config.validate({**config.apply_theme(config.validate({}), theme), "wallpaper": "none", **kw})

    def dconf(self):
        f = self.tmp / "state/dconf.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def profile(self, key):
        u = [k for k in self.gs() if k.startswith(f"{self.PT}.Profile:/")]
        self.assertTrue(u, "no profile written")
        return self.gs()[f"{u[0].split('|')[0]}|{key}"]

    def test_theme_defaults_for_opacity_and_cursor(self):
        from nebulix import config
        got = {th: (c["terminal_opacity"], c["terminal_cursor"]) for th in config.CHOICES["theme"]
               for c in [config.apply_theme(config.validate({}), th)]}
        self.assertEqual(got, {"nebulix": (90, "block"), "macos-dark": (95, "ibeam"),
                               "macos-light": (100, "ibeam"), "nebulix-light": (100, "block")})
        for bad in ({"terminal_opacity": 50}, {"terminal_cursor": "x"}, {"terminal_rows": 5}, {"terminal_padding": "maybe"}):
            with self.assertRaises(ValueError):
                config.validate(bad)

    def test_palette_has_dark_and_light_twin_for_every_theme(self):
        import re
        from nebulix import config, palette, themes
        from nebulix.apply import render_all
        for th in config.CHOICES["theme"]:
            out = self.tmp / f"out-{th}"
            cfg = self.cfg(theme=th)
            render_all(cfg, out, log=lambda *_: None)
            txt = (out / "terminal/nebulix.palette").read_text()
            sec = {m.group(1): m.group(2) for m in re.finditer(r"\[(Dark|Light)\]\n(.*?)(?=\n\[|\Z)", txt, re.S)}
            self.assertEqual(set(sec), {"Dark", "Light"})
            for scheme, theme_id in (("Dark", th if themes.get(th)["scheme"] == "dark" else themes.pair(th)),
                                     ("Light", th if themes.get(th)["scheme"] == "light" else themes.pair(th))):
                _, t = palette.tokens(config.validate({"theme": theme_id}))
                self.assertIn(f"Background={t['bg-0']}", sec[scheme])
                self.assertIn(f"Foreground={t['fg-0']}", sec[scheme])
                self.assertIn(f"Cursor={t['purple']}", sec[scheme])
                self.assertEqual(sec[scheme].count("Color"), 16)

    def test_ptyxis_profile_created_made_default_and_undone(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        before = self.snapshot()
        apply(self.cfg(theme="macos-dark"), only=["terminal"], log=lambda *_: None)
        g = self.gs()
        u = g[f"{self.PT}|default-profile-uuid"].strip("'")
        self.assertIn(u, g[f"{self.PT}|profile-uuids"])
        self.assertEqual(self.profile("palette"), "'nebulix'")
        self.assertEqual(self.profile("opacity"), "0.95")
        self.assertEqual(g[f"{self.PT}|cursor-shape"], "'ibeam'")
        self.assertEqual(g[f"{self.PT}|interface-style"], "'system'")
        self.assertEqual(g[f"{self.PT}|default-columns"], "80")
        # re-applying with another theme reuses the same profile
        apply(self.cfg(theme="nebulix", terminal_opacity=80), only=["terminal"], log=lambda *_: None)
        g = self.gs()
        self.assertEqual(g[f"{self.PT}|default-profile-uuid"].strip("'"), u)
        self.assertEqual(g[f"{self.PT}|profile-uuids"].count(u), 1)
        self.assertEqual(self.profile("opacity"), "0.80")
        self.assertEqual(g[f"{self.PT}|cursor-shape"], "'block'")
        restore("undo", log=lambda *_: None)
        g = self.gs()
        self.assertEqual(g[f"{self.PT}|profile-uuids"], "@as []")
        self.assertEqual(g[f"{self.PT}|default-profile-uuid"], "''")
        self.assertEqual(self.snapshot(), before)

    def test_reset_clears_the_ptyxis_keys(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        apply(self.cfg(), only=["terminal"], log=lambda *_: None)
        restore("reset", log=lambda *_: None)
        self.assertEqual(self.gs(), {})

    def test_font_follows_what_is_installed_and_keep_leaves_it(self):
        from unittest import mock
        from nebulix import apply as ap
        for installed, want in (({"JetBrainsMono Nerd Font"}, "JetBrainsMono Nerd Font"), ({"JetBrains Mono"}, "JetBrains Mono"), (set(), None)):
            with mock.patch.object(ap, "has_font", lambda f, i=installed: f in i):
                self.assertEqual(ap.terminal_font(self.cfg()), want)
                self.assertIsNone(ap.terminal_font(self.cfg(terminal_font="keep")))
        with mock.patch.object(ap, "has_font", lambda f: f == "JetBrains Mono"):
            ap.apply(self.cfg(terminal_font_size=13), only=["terminal"], log=lambda *_: None)
            self.assertEqual(self.gs()[f"{self.PT}|font-name"], "'JetBrains Mono 13'")
            ap.apply(self.cfg(terminal_font="keep"), only=["terminal"], log=lambda *_: None)
            self.assertEqual(self.gs()[f"{self.PT}|font-name"], "'default'")  # back to what it was

    def test_gnome_terminal_profile_is_rewritten_when_the_theme_changes(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        (self.tmp / "state/dconf.json").write_text(json.dumps({"/org/gnome/terminal/legacy/profiles:/list": "['abc']"}))
        apply(self.cfg(theme="nebulix"), only=["terminal"], log=lambda *_: None)
        loads = [v for k, v in self.dconf().items() if k.startswith("load:")]
        self.assertEqual(len(loads), 1)
        self.assertIn("background-transparency-percent=10", loads[0])
        self.assertIn("use-transparent-background=true", loads[0])
        self.assertIn("cursor-shape='block'", loads[0])
        apply(self.cfg(theme="macos-light"), only=["terminal"], log=lambda *_: None)
        loads = [v for k, v in self.dconf().items() if k.startswith("load:")]
        self.assertEqual(len(loads), 1)  # same profile, new content
        self.assertIn("background-color='#FFFFFF'", loads[0])
        self.assertIn("use-transparent-background=false", loads[0])
        self.assertIn("cursor-shape='ibeam'", loads[0])
        self.assertIn("org.gnome.Terminal.ProfilesList|default", self.gs())
        restore("undo", log=lambda *_: None)
        self.assertEqual(self.dconf().get("/org/gnome/terminal/legacy/profiles:/list"), "['abc']")
        self.assertNotIn("org.gnome.Terminal.ProfilesList|default", {k: v for k, v in self.gs().items() if v != "'default'"})

    def test_gnome_terminal_with_unset_profile_list_uses_the_schema_default(self):
        from nebulix.apply import apply
        from nebulix.restore import restore
        g = self.gs()
        g["org.gnome.Terminal.ProfilesList|list"] = "['stock']"
        (self.tmp / "state/gs.json").write_text(json.dumps(g))
        apply(self.cfg(), only=["terminal"], log=lambda *_: None)
        lst = self.dconf()["/org/gnome/terminal/legacy/profiles:/list"]
        self.assertTrue(lst.startswith("['stock', '") and lst.endswith("']"))
        self.assertTrue([k for k in self.dconf() if k.startswith("load:")])
        restore("undo", log=lambda *_: None)
        self.assertNotIn("/org/gnome/terminal/legacy/profiles:/list", self.dconf())  # unset again

    def test_contrast_stays_readable_at_the_lowest_opacity(self):
        from nebulix import config, palette
        for th in config.CHOICES["theme"]:
            self.assertGreaterEqual(palette.terminal_contrast(config.validate({"theme": th})), 4.5, th)


class TestConcurrentApply(Sandbox):
    def test_parallel_applies_do_not_collide(self):
        import threading
        from nebulix import config
        from nebulix.apply import apply
        errs = []

        def run(theme):
            try:
                cfg = config.apply_theme(config.validate({"wallpaper": "none", "icons": "papirus"}), theme)
                apply(cfg, log=lambda *_: None)
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))
        ths = [threading.Thread(target=run, args=(x,)) for x in ("nebulix-light", "macos-dark", "nebulix-light", "macos-light")]
        [x.start() for x in ths]
        [x.join() for x in ths]
        self.assertEqual(errs, [])

    def test_existing_backup_target_is_not_an_error(self):
        from nebulix.state import State
        st = State(log=lambda *_: None)
        dest = self.home / ".local/share/gnome-shell/extensions/x"
        dest.mkdir(parents=True)
        (dest / "a").write_text("1")
        tgt = st.bk / str(dest).lstrip("/")
        tgt.mkdir(parents=True)
        (tgt / "a").write_text("original")
        st._backup(dest)
        self.assertEqual((tgt / "a").read_text(), "original")
