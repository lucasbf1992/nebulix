# SPDX-License-Identifier: GPL-3.0-or-later
"""Round trip: whatever `apply` writes, `undo` and `reset` take away. The matrix grows with the features: every
family adds its keys to MATRIX and its leftovers to KEPT_ON_PURPOSE."""
import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import Sandbox, make_icon_tarball  # noqa: E402

ICON_THEME = "org.gnome.desktop.interface|icon-theme"
SET_FILES = {"whitesur": "WhiteSur", "mactahoe": "MacTahoe", "mcmojave": "McMojave-circle"}

# Icon family: every set (and the sets Nebulix does not download) with the folders from the set and from Nebulix.
MATRIX = [{"icons": s, "icon_folders": f} for s in ("whitesur", "mactahoe", "mcmojave") for f in ("nebulix", "conjunto")]
MATRIX += [{"icons": "papirus", "icon_folders": "nebulix"}, {"icons": "keep", "icon_folders": "conjunto"}]
# What stays on disk after an undo or a reset without the removal option: downloaded sets and their tarballs.
KEPT_ON_PURPOSE = (".local/share/icons/WhiteSur", ".local/share/icons/MacTahoe", ".local/share/icons/McMojave-circle", ".cache/nebulix/icons/")


class RoundTrip(Sandbox):
    def setUp(self):
        super().setUp()
        from nebulix import config, icons
        self.config, self.icons = config, icons
        self.src = self.tmp / "src"
        cm = self.no_network()
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        for sid, name in SET_FILES.items():
            entry = icons.SETS[sid]
            tb = make_icon_tarball(self.src, name, filename=entry["file"], colors=tuple(entry["colors"]))
            p = mock.patch.dict(entry, sha256=tb.sha256)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict("os.environ", {"NEBULIX_ICONS_SOURCE": str(self.src)})
        p.start()
        self.addCleanup(p.stop)
        self.mk_user_files()
        (self.home / ".local/share/icons/Papirus-Dark").mkdir(parents=True)
        (self.home / ".local/share/icons/Papirus-Dark/index.theme").write_text("[Icon Theme]\nName=Papirus-Dark\n")

    def mk_user_files(self):
        (self.home / ".config/gtk-4.0").mkdir(parents=True)
        (self.home / ".config/gtk-4.0/gtk.css").write_text("/* mine */\n")
        (self.home / ".config/starship.toml").write_text("# mine\n")
        (self.home / ".bashrc").write_text("# mine\n")

    def cfg(self, theme, **kw):
        return self.config.validate({**self.config.apply_theme(self.config.validate({}), theme), "wallpaper": "none", **kw})

    def apply(self, cfg):
        from nebulix.apply import apply
        apply(cfg, install_icons=True, log=lambda *_: None)

    def restore(self, mode, **kw):
        from nebulix.restore import restore
        restore(mode, log=lambda *_: None, **kw)

    def user_state(self):
        """Files of the HOME except what is kept on purpose, and the settings."""
        files = {k: v for k, v in self.snapshot().items() if not k.startswith(KEPT_ON_PURPOSE)
                 and k != ".config/nebulix/config.toml"}
        return files, self.gs()

    def folders(self):
        return [n for n in self.tree() if n != "Papirus-Dark"]


class TestIconFamily(RoundTrip):
    def test_apply_then_undo_gives_the_home_and_settings_back(self):  # every set x folders choice x theme
        for theme, extra in [("nebulix", m) for m in MATRIX] + [("macos-light", m) for m in MATRIX[1::2]]:
            with self.subTest(theme=theme, **extra):
                self.setUp_fresh()
                (self.tmp / "state/gs.json").write_text(json.dumps({ICON_THEME: "'Yaru'", "org.gnome.desktop.interface|text-scaling-factor": "1.0"}))
                before = self.user_state()
                self.apply(self.cfg(theme, **extra))
                self.assertNotEqual(self.user_state(), before)
                self.restore("undo")
                files, gs = self.user_state()
                self.assertEqual(files, before[0])
                self.assertEqual(gs[ICON_THEME], "'Yaru'")
                self.assertEqual(gs["org.gnome.desktop.interface|text-scaling-factor"], "1.0")
                self.assertTrue(all(v == "'default'" for k, v in gs.items() if k not in (ICON_THEME, "org.gnome.desktop.interface|text-scaling-factor")))
                self.assertNotIn("Nebulix-Icons", self.tree())

    def test_apply_then_reset_leaves_only_the_downloaded_sets(self):
        for extra in MATRIX:
            with self.subTest(**extra):
                self.setUp_fresh()
                before = self.user_state()
                self.apply(self.cfg("nebulix", **extra))
                self.restore("reset")
                self.assertEqual(self.user_state(), before)
                self.assertEqual(self.folders(), self.downloaded(extra["icons"]))

    def test_apply_then_reset_with_the_removal_option_leaves_nothing(self):
        for extra in MATRIX:
            with self.subTest(**extra):
                self.setUp_fresh()
                before = self.user_state()
                self.apply(self.cfg("nebulix", **extra))
                self.restore("reset", remove_icons=True)
                self.assertEqual(self.user_state(), before)
                self.assertEqual(self.tree(), ["Papirus-Dark"])
                self.assertFalse((self.home / ".cache/nebulix").exists())

    def test_two_applies_with_a_swap_undo_in_one_step(self):
        (self.tmp / "state/gs.json").write_text(json.dumps({ICON_THEME: "'Yaru'"}))
        before = self.user_state()
        self.apply(self.cfg("nebulix", icons="whitesur", icon_folders="conjunto"))
        self.apply(self.cfg("nebulix", icons="mactahoe", icon_folders="nebulix"))
        self.restore("undo")
        files, gs = self.user_state()
        self.assertEqual(files, before[0])
        self.assertEqual(gs[ICON_THEME], "'Yaru'")

    def downloaded(self, set_id):
        return [] if set_id in ("papirus", "keep") else [n for n in self.tree() if n.startswith(SET_FILES[set_id])]

    def setUp_fresh(self):
        """Back to an empty HOME between the cases of a matrix."""
        import shutil
        for p in list(self.home.iterdir()):
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        (self.tmp / "state/gs.json").unlink(missing_ok=True)
        self.mk_user_files()
        (self.home / ".local/share/icons/Papirus-Dark").mkdir(parents=True)
        (self.home / ".local/share/icons/Papirus-Dark/index.theme").write_text("[Icon Theme]\nName=Papirus-Dark\n")
