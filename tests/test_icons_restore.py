# SPDX-License-Identifier: GPL-3.0-or-later
"""Taking icons away: `reset --remove-icons` deletes exactly the folders the sets generate (and the overlay, and the
tarball cache) and nothing else; `undo` hands back the icon theme the user had."""
import contextlib
import io
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import Sandbox, make_icon_tarball  # noqa: E402

ICON_THEME = "org.gnome.desktop.interface|icon-theme"
SET_FILES = {"whitesur": "WhiteSur", "mactahoe": "MacTahoe", "mcmojave": "McMojave-circle"}
OLD_WHITESUR = ("WhiteSur-purple", "WhiteSur-purple-dark", "WhiteSur-purple-light", "WhiteSur", "WhiteSur-dark", "WhiteSur-light")
THIRD_PARTY = ("Papirus", "Papirus-Dark", "Yaru-custom", "WhiteSur-custom", "WhiteSurfer", "MacTahoe-extra-theme", "Adwaita")


class Restore(Sandbox):
    def setUp(self):
        super().setUp()
        from nebulix import config, icons
        self.config, self.icons = config, icons
        self.src = self.tmp / "src"
        cm = self.no_network()
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def serve_all(self):
        """Fake tarballs for the three sets (every colour of each), pinned by sha256."""
        for sid, name in SET_FILES.items():
            entry = self.icons.SETS[sid]
            tb = make_icon_tarball(self.src, name, filename=entry["file"], colors=tuple(entry["colors"]))
            p = mock.patch.dict(entry, sha256=tb.sha256)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict("os.environ", {"NEBULIX_ICONS_SOURCE": str(self.src)})
        p.start()
        self.addCleanup(p.stop)

    def mk(self, *names):
        for n in names:
            (self.home / ".local/share/icons" / n).mkdir(parents=True, exist_ok=True)
            (self.home / ".local/share/icons" / n / "index.theme").write_text(f"[Icon Theme]\nName={n}\n")

    def cfg(self, theme="nebulix", **kw):
        return self.config.validate({**self.config.apply_theme(self.config.validate({}), theme), "wallpaper": "none", **kw})

    def apply(self, cfg, only=None, install=True):
        from nebulix.apply import apply
        apply(cfg, only=only, install_icons=install, log=lambda *_: None)

    def cli(self, *argv):
        from nebulix import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def cache(self):
        d = self.home / ".cache/nebulix/icons"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def every_generated_folder(self):
        """The names the sets can create, built here from the table (colour x dark/light, plus the names without colour)."""
        names = []
        for sid, e in self.icons.SETS.items():
            for color in e["colors"]:
                names += [self.icons.folder_name(sid, color, s) for s in ("dark", "light")]
                names.append(e["prefix"] if color == "default" else f"{e['prefix']}-{color}")  # what the installer makes without a variant
            names += [e["prefix"], f"{e['prefix']}-dark", f"{e['prefix']}-light"]
        return names


class TestRemoveIcons(Restore):
    def test_removes_every_generated_folder_and_the_overlay(self):
        self.mk(*self.every_generated_folder(), *OLD_WHITESUR, *THIRD_PARTY)
        self.apply(self.cfg(icons="mactahoe"), only=["icons"], install=False)  # leaves the overlay and a manifest
        self.assertIn("Nebulix-Icons", self.tree())
        code, _ = self.cli("reset", "--remove-icons")
        self.assertEqual(code or 0, 0)
        left = self.tree()
        self.assertEqual(left, sorted(THIRD_PARTY))
        for n in left:
            self.assertTrue((self.home / ".local/share/icons" / n / "index.theme").exists(), n)

    def test_the_six_names_the_old_release_made_go_too(self):
        self.mk(*OLD_WHITESUR, "Papirus", "Yaru-custom")
        self.apply(self.cfg(icons="whitesur"), only=["icons"], install=False)
        self.cli("reset", "--remove-icons")
        self.assertEqual(self.tree(), ["Papirus", "Yaru-custom"])

    def test_the_removal_list_is_the_table(self):
        names = set(self.icons.owned_folders())
        self.assertEqual(names, set(self.every_generated_folder()) | set(OLD_WHITESUR) | {"Nebulix-Icons"})
        self.assertFalse(names & set(THIRD_PARTY))
        with mock.patch.dict(self.icons.SETS, {"fake": dict(self.icons.SETS["mactahoe"], prefix="Fake", colors={"blue": "#0000FF"})}):
            self.assertIn("Fake-blue-dark", self.icons.owned_folders())

    def test_without_the_option_the_sets_stay_and_the_icon_theme_goes_back(self):
        self.serve_all()
        (self.tmp / "state/gs.json").write_text('{"%s": "\'Yaru\'"}' % ICON_THEME)
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        self.assertEqual(self.tree(), ["MacTahoe-purple-dark", "MacTahoe-purple-light", "Nebulix-Icons"])
        self.cli("reset")
        self.assertEqual(self.tree(), ["MacTahoe-purple-dark", "MacTahoe-purple-light"])  # only the overlay is Nebulix's own
        self.assertNotIn(ICON_THEME, self.gs())
        self.assertEqual(self.cache(), ["2026-09-10.tar.gz"])

    def test_the_cache_of_tarballs_goes_with_the_option(self):
        self.serve_all()
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        self.apply(self.cfg(icons="whitesur"), only=["icons"])
        self.assertEqual(self.cache(), ["2026-09-10.tar.gz", "v2025-02-10.tar.gz"])
        self.mk("Papirus")
        self.cli("reset", "--remove-icons")
        self.assertEqual(self.cache(), [])
        self.assertEqual(self.tree(), ["Papirus"])
        self.assertFalse((self.home / ".cache/nebulix").exists())

    def test_other_files_in_the_cache_parent_are_kept(self):
        self.serve_all()
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        (self.home / ".cache/nebulix/other.txt").write_text("x")
        self.cli("reset", "--remove-icons")
        self.assertEqual(self.cache(), [])
        self.assertTrue((self.home / ".cache/nebulix/other.txt").exists())

    def test_dry_run_changes_nothing(self):
        self.serve_all()
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        before, cache = self.snapshot(), self.cache()
        self.cli("reset", "--remove-icons", "--dry-run")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.cache(), cache)

    def test_a_set_installed_by_hand_with_the_same_names_is_removed_too(self):
        self.mk("WhiteSur-dark", "WhiteSur-light", "WhiteSur-pink-dark")
        self.apply(self.cfg(icons="keep"), only=["icons"], install=False)
        self.cli("reset", "--remove-icons")
        self.assertEqual(self.tree(), [])

    def test_a_symlinked_folder_is_unlinked_not_followed(self):
        target = self.tmp / "elsewhere"
        target.mkdir()
        (target / "keep.txt").write_text("x")
        d = self.home / ".local/share/icons"
        d.mkdir(parents=True)
        (d / "WhiteSur-dark").symlink_to(target, target_is_directory=True)
        self.apply(self.cfg(icons="keep"), only=["icons"], install=False)
        self.cli("reset", "--remove-icons")
        self.assertFalse((d / "WhiteSur-dark").is_symlink())
        self.assertTrue((target / "keep.txt").exists())

    def test_nothing_to_remove_is_not_an_error(self):
        self.apply(self.cfg(icons="papirus"), only=["icons"], install=False)
        self.cli("reset", "--remove-icons")
        self.assertEqual(self.tree(), [])


class TestUndoGivesTheIconThemeBack(Restore):
    def seed(self, value="'Yaru'"):
        (self.tmp / "state/gs.json").write_text('{"%s": "%s"}' % (ICON_THEME, value))

    def test_undo_after_an_icon_set_restores_the_previous_icon_theme(self):
        self.serve_all()
        self.seed()
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        self.assertNotEqual(self.gs()[ICON_THEME], "'Yaru'")
        self.cli("undo")
        self.assertEqual(self.gs()[ICON_THEME], "'Yaru'")

    def test_a_set_swap_in_between_still_undoes_to_what_the_user_had(self):
        self.serve_all()
        self.seed()
        self.apply(self.cfg(icons="whitesur", icon_folders="conjunto"), only=["icons"])
        first = self.gs()[ICON_THEME]
        self.apply(self.cfg(icons="mactahoe", icon_folders="conjunto"), only=["icons"])
        self.assertNotEqual(self.gs()[ICON_THEME], first)
        self.cli("undo")
        self.assertEqual(self.gs()[ICON_THEME], "'Yaru'")

    def test_undo_keeps_the_downloaded_sets_on_disk(self):
        self.serve_all()
        self.seed()
        self.apply(self.cfg(icons="mactahoe"), only=["icons"])
        self.cli("undo")
        self.assertIn("MacTahoe-purple-dark", self.tree())
        self.assertNotIn("Nebulix-Icons", self.tree())

    def test_papirus_and_keep_leave_the_icon_theme_where_it_was(self):
        for mode in ("papirus", "keep"):
            with self.subTest(mode):
                self.mk("Papirus-Dark")
                self.seed()
                self.apply(self.cfg(icons=mode), only=["icons"], install=False)
                self.cli("undo")
                self.assertEqual(self.gs()[ICON_THEME], "'Yaru'")
