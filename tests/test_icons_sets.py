# SPDX-License-Identifier: GPL-3.0-or-later
"""Icon set registry, download, cache and install command: everything runs against fake tarballs, never the network."""
import contextlib
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import Sandbox, make_icon_tarball  # noqa: E402

SOURCE_FILE = "v2025-02-10.tar.gz"


class IconsSets(Sandbox):
    def setUp(self):
        super().setUp()
        from nebulix import icons
        self.icons = icons
        self.src = self.tmp / "src"
        self.log = []
        self.enter(self.no_network())

    def enter(self, cm):
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def serve(self, **kw):
        """Put a fake WhiteSur tarball in the source directory and make the registry point at it."""
        kw.setdefault("colors", ("default", "purple"))
        tb = make_icon_tarball(self.src, "WhiteSur", filename=SOURCE_FILE, **kw)
        self.enter(mock.patch.dict("os.environ", {"NEBULIX_ICONS_SOURCE": str(self.src)}))
        self.enter(mock.patch.dict(self.icons.SETS["whitesur"], sha256=tb.sha256))
        return tb

    def ensure(self, theme="macos-dark"):
        return self.icons.ensure_set("whitesur", self.log.append, theme)


class TestSetsTable(IconsSets):
    def test_whitesur_entry_keeps_the_pinned_values(self):  # S2
        ws = self.icons.SETS["whitesur"]
        self.assertEqual(ws["tag"], "v2025-02-10")
        self.assertTrue(ws["url"].endswith(f"/{SOURCE_FILE}"))
        self.assertEqual(ws["file"], SOURCE_FILE)
        self.assertRegex(ws["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(ws["size_mb"], 7)

    def test_table_is_patchable_for_a_new_set(self):  # S2, AC-7
        entry = dict(self.icons.SETS["whitesur"], label="Fake")
        with mock.patch.dict(self.icons.SETS, {"fake": entry}):
            self.assertIn("fake", self.icons.SETS)
        self.assertNotIn("fake", self.icons.SETS)

    def test_fetch_without_source_goes_to_the_url(self):  # S1
        with mock.patch.dict("os.environ"):
            os.environ.pop("NEBULIX_ICONS_SOURCE", None)
            with self.assertRaises(AssertionError):  # the network block of no_network() fired
                self.icons.fetch_tarball("whitesur", self.tmp / "out.tgz")

    def test_fetch_from_source_copies_the_file(self):  # S1
        tb = self.serve()
        self.icons.fetch_tarball("whitesur", self.tmp / "out.tgz")
        self.assertEqual((self.tmp / "out.tgz").read_bytes(), tb.path.read_bytes())


class TestDownload(IconsSets):
    def test_download_through_the_fake_tarball_installs(self):  # S1, S2, S3
        self.serve()
        self.assertTrue(self.ensure("macos-dark"))
        self.assertEqual(self.tree(), ["WhiteSur-dark", "WhiteSur-light"])
        self.assertEqual(self.downloads(), 1)
        argv = self.installer_runs()[0]
        self.assertRegex(argv, r"ARGV=-d \S+/\.local/share/icons -t default$")
        self.assertIn("baixando WhiteSur v2025-02-10 (~7 MB, GPL-3.0)", self.log)

    def test_nebulix_theme_asks_for_the_purple_variant(self):
        self.serve()
        self.assertTrue(self.ensure("nebulix"))
        self.assertTrue(self.installer_runs()[0].endswith("-t purple"))
        self.assertIn("WhiteSur-purple-dark", self.tree())

    def test_installed_theme_is_not_downloaded_again(self):
        self.serve()
        self.ensure("macos-dark")
        self.ensure("macos-dark")
        self.assertEqual(self.downloads(), 1)

    def test_sha_mismatch_does_not_run_the_installer(self):  # TC-15
        self.serve()
        with mock.patch.dict(self.icons.SETS["whitesur"], sha256="0" * 64):
            with self.assertRaisesRegex(RuntimeError, "sha256"):
                self.ensure()
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.tree(), [])

    def test_tarball_with_a_changed_byte_is_rejected(self):  # TC-15
        tb = self.serve()
        data = bytearray(tb.path.read_bytes())
        data[-5] ^= 0xFF  # the registry still holds the sha256 of the original
        tb.path.write_bytes(bytes(data))
        with self.assertRaises(Exception):
            self.ensure()
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.tree(), [])

    def test_members_outside_the_destination_do_not_escape(self):  # TC-16
        self.serve(evil=True)
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        self.enter(mock.patch.object(tempfile, "tempdir", str(scratch)))
        with self.assertRaises(tarfile.TarError):  # filter="data" refuses ../ members
            self.ensure()
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.tree(), [])
        self.assertEqual([p.name for p in self.tmp.rglob("evil.txt")], [])
        self.assertEqual(list(scratch.iterdir()), [])  # temporary directory cleaned up

    def test_apply_falls_back_when_the_download_is_refused(self):  # TC-15, TC-16 through apply
        from nebulix import config
        from nebulix.apply import apply
        for name, kw, sha in (("evil member", {"evil": True}, None), ("wrong sha", {}, "0" * 64)):
            with self.subTest(name):
                self.serve(**kw)
                if sha:
                    self.enter(mock.patch.dict(self.icons.SETS["whitesur"], sha256=sha))
                lines = []
                apply(config.apply_theme(config.validate({}), "macos-dark"), only=["icons"], install_icons=True,
                      log=lines.append)
                self.assertTrue(any("WhiteSur indisponível" in ln for ln in lines), lines)
                self.assertEqual(self.installer_runs(), [])
                self.assertEqual(self.tree(), [])
                self.assertNotIn("WhiteSur", self.gs().get("org.gnome.desktop.interface|icon-theme", ""))

    def test_missing_source_file_counts_as_network_down(self):
        from nebulix import config
        from nebulix.apply import apply
        self.src.mkdir()
        self.enter(mock.patch.dict("os.environ", {"NEBULIX_ICONS_SOURCE": str(self.src)}))
        lines = []
        apply(config.apply_theme(config.validate({}), "macos-dark"), only=["icons"], install_icons=True, log=lines.append)
        self.assertTrue(any("WhiteSur indisponível" in ln for ln in lines), lines)
        self.assertEqual(self.tree(), [])


SET_FILES = {"whitesur": ("WhiteSur", "v2025-02-10.tar.gz"), "mactahoe": ("MacTahoe", "2026-09-10.tar.gz"),
             "mcmojave": ("McMojave-circle", "2025-08-07.tar.gz")}


class MultiSet(IconsSets):
    def serve_set(self, set_id, colors=("default", "purple", "blue"), **kw):
        name, filename = SET_FILES[set_id]
        self.assertEqual(self.icons.SETS[set_id]["file"], filename)
        tb = make_icon_tarball(self.src, name, filename=filename, colors=colors, **kw)
        os.environ["NEBULIX_ICONS_SOURCE"] = str(self.src)
        self.enter(mock.patch.dict(self.icons.SETS[set_id], sha256=tb.sha256))
        return tb

    def run_cli(self, *argv, stdin=None):
        from nebulix import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            if stdin is None:
                code = cli.main(list(argv))
            else:
                with mock.patch("builtins.input", side_effect=stdin if isinstance(stdin, BaseException) else lambda: stdin):
                    code = cli.main(list(argv))
        return code, out.getvalue()

    def apply_icons(self, set_id, theme="macos-dark", install=True):
        from nebulix import config
        from nebulix.apply import apply
        cfg = dict(config.apply_theme(config.validate({}), theme), icons=set_id)
        lines = []
        apply(cfg, only=["icons"], install_icons=install, log=lines.append)
        return lines

    def icon_theme(self):
        return self.gs().get("org.gnome.desktop.interface|icon-theme", "")

    def cache_files(self):
        d = self.home / ".cache/nebulix/icons"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


class TestSetsRegistry(MultiSet):
    def test_every_entry_is_pinned_and_complete(self):  # AC-5, AC-6
        for sid, e in self.icons.SETS.items():
            with self.subTest(sid):
                self.assertRegex(e["sha256"], r"^[0-9a-f]{64}$")
                self.assertIn(e["tag"], e["url"])
                self.assertTrue(e["url"].endswith("/" + e["file"]))
                self.assertEqual(e["license"], "GPL-3.0")
                self.assertIn(e["default_color"], e["colors"])
                self.assertIn(e["neutral"], e["colors"])
        self.assertEqual(list(self.icons.SETS), ["whitesur", "mactahoe", "mcmojave"])

    def test_folder_names_omit_the_default_colour(self):
        f = self.icons.folder_name
        self.assertEqual(f("whitesur", "default", "dark"), "WhiteSur-dark")
        self.assertEqual(f("whitesur", "purple", "light"), "WhiteSur-purple-light")
        self.assertEqual(f("mactahoe", "blue", "dark"), "MacTahoe-blue-dark")

    def test_blue_is_the_default_colour_of_the_new_sets(self):
        self.assertEqual(self.icons.base_name("macos-dark", "mactahoe"), "MacTahoe-blue-dark")
        self.assertEqual(self.icons.base_name("macos-light", "mcmojave"), "McMojave-circle-blue-light")
        self.assertEqual(self.icons.base_name("nebulix", "mactahoe"), "MacTahoe-purple-dark")
        self.assertEqual(self.icons.base_name("nebulix", "whitesur"), "WhiteSur-purple-dark")
        self.assertEqual(self.icons.base_name("macos-dark", "whitesur"), "WhiteSur-dark")

    def test_config_accepts_the_sets_and_rejects_typos(self):  # TC-4, AC-5
        from nebulix import config
        for v in ("whitesur", "mactahoe", "mcmojave", "papirus", "keep"):
            self.assertEqual(config.validate({"icons": v})["icons"], v)
        with self.assertRaisesRegex(ValueError, "icons inválido: 'wh1tesur'"):
            config.validate({"icons": "wh1tesur"})

    def test_config_accepts_a_set_added_to_the_table(self):  # TC-11
        from nebulix import config
        with mock.patch.dict(self.icons.SETS, {"fake": dict(self.icons.SETS["whitesur"])}):
            self.assertEqual(config.validate({"icons": "fake"})["icons"], "fake")
        with self.assertRaises(ValueError):
            config.validate({"icons": "fake"})


class TestInstallPerSet(MultiSet):
    def test_each_set_installs_only_the_colour_of_the_theme(self):  # TC-12 (one colour), AC-8
        for sid, (name, _f) in SET_FILES.items():
            with self.subTest(sid):
                self.serve_set(sid)
                before = self.downloads()
                self.assertTrue(self.icons.ensure_set(sid, self.log.append, "macos-dark"))
                self.assertEqual(self.downloads(), before + 1)
                mine = [t for t in self.tree() if t.startswith(name)]
                col = "" if sid == "whitesur" else "-blue"
                self.assertEqual(mine, [f"{name}{col}-dark", f"{name}{col}-light"])
                self.assertNotIn("-t all", self.installer_runs()[-1])

    def test_installer_arguments_are_built_per_set(self):
        for sid, tail in (("whitesur", "-t default"), ("mactahoe", "-t blue"), ("mcmojave", "-c -t blue")):
            with self.subTest(sid):
                self.serve_set(sid)
                self.icons.ensure_set(sid, self.log.append, "macos-dark")
                self.assertRegex(self.installer_runs()[-1], rf"ARGV=-d \S+/\.local/share/icons {tail}$")

    def test_dest_is_a_directory_that_exists_before_the_installer(self):  # McMojave-circle needs it
        self.serve_set("mcmojave")
        self.assertFalse((self.home / ".local/share/icons").exists())
        self.assertTrue(self.icons.ensure_set("mcmojave", self.log.append, "macos-dark"))

    def test_apply_activates_each_set(self):  # TC-9
        expect = {"whitesur": "'WhiteSur-dark'", "mactahoe": "'MacTahoe-blue-dark'", "mcmojave": "'McMojave-circle-blue-dark'"}
        for sid, want in expect.items():
            with self.subTest(sid):
                self.serve_set(sid)
                self.apply_icons(sid)
                self.assertEqual(self.icon_theme(), want)

    def test_apply_without_install_flag_does_not_download(self):
        self.serve_set("mactahoe")
        lines = self.apply_icons("mactahoe", install=False)
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.tree(), [])
        self.assertEqual(self.cache_files(), [])

    def test_a_set_added_to_the_table_installs_without_code_changes(self):  # TC-11
        e = dict(self.icons.SETS["whitesur"], label="Ficticio", prefix="Ficticio", file="fake.tar.gz",
                 colors={"roxo": "#800080", "azul": "#0000FF"}, default_color="azul", neutral="roxo")
        tb = make_icon_tarball(self.src, "Ficticio", filename="fake.tar.gz", colors=("roxo", "azul"))
        e["sha256"] = tb.sha256
        os.environ["NEBULIX_ICONS_SOURCE"] = str(self.src)
        with mock.patch.dict(self.icons.SETS, {"fake": e}):
            self.apply_icons("fake")
        self.assertEqual(self.downloads(), 1)
        self.assertEqual(self.tree(), ["Ficticio-azul-dark", "Ficticio-azul-light"])
        self.assertEqual(self.icon_theme(), "'Ficticio-azul-dark'")


class TestCache(MultiSet):
    def test_verified_tarball_is_kept_in_the_cache(self):
        tb = self.serve_set("whitesur")
        self.ensure("macos-dark")
        self.assertEqual(self.cache_files(), [SOURCE_FILE])
        self.assertEqual((self.home / ".cache/nebulix/icons" / SOURCE_FILE).read_bytes(), tb.path.read_bytes())

    def test_another_colour_installs_from_the_cache_without_network(self):  # TC-13, AC-9
        self.serve_set("whitesur")
        self.ensure("macos-dark")
        (self.src / SOURCE_FILE).unlink()  # source gone and no_network() is active
        self.assertTrue(self.ensure("nebulix"))
        self.assertEqual(self.tree(), ["WhiteSur-dark", "WhiteSur-light", "WhiteSur-purple-dark", "WhiteSur-purple-light"])
        self.assertEqual(len(self.installer_runs()), 2)
        self.assertTrue(any("guardado" in ln for ln in self.log))

    def test_same_colour_again_neither_downloads_nor_reinstalls(self):  # AC-9
        self.serve_set("mactahoe")
        self.apply_icons("mactahoe")
        (self.src / SET_FILES["mactahoe"][1]).unlink()
        self.apply_icons("mactahoe")
        self.assertEqual(len(self.installer_runs()), 1)

    def test_cached_file_with_a_wrong_sha_is_ignored_and_fetched_again(self):
        self.serve_set("whitesur")
        cache = self.home / ".cache/nebulix/icons"
        cache.mkdir(parents=True)
        (cache / SOURCE_FILE).write_bytes(b"corrupted")
        self.assertTrue(self.ensure("macos-dark"))
        self.assertTrue(any("baixando" in ln for ln in self.log))
        self.assertNotEqual((cache / SOURCE_FILE).read_bytes(), b"corrupted")

    def test_refused_tarball_is_not_cached(self):  # TC-15
        self.serve_set("whitesur")
        with mock.patch.dict(self.icons.SETS["whitesur"], sha256="0" * 64):
            with self.assertRaises(RuntimeError):
                self.ensure()
        self.assertEqual(self.cache_files(), [])

    def test_xdg_cache_home_is_honoured(self):
        self.serve_set("whitesur")
        os.environ["XDG_CACHE_HOME"] = str(self.tmp / "xdg-cache")
        self.ensure("macos-dark")
        self.assertEqual(sorted(p.name for p in (self.tmp / "xdg-cache/nebulix/icons").iterdir()), [SOURCE_FILE])

    def test_switching_set_and_back_needs_no_network(self):  # TC-25, AC-17
        self.serve_set("whitesur")
        self.serve_set("mactahoe")
        self.apply_icons("whitesur")
        self.apply_icons("mactahoe")
        for f in self.src.iterdir():
            f.unlink()
        self.apply_icons("whitesur", install=False)
        self.assertEqual(self.icon_theme(), "'WhiteSur-dark'")
        self.apply_icons("mactahoe", install=False)
        self.assertEqual(self.icon_theme(), "'MacTahoe-blue-dark'")
        self.assertEqual(len(self.installer_runs()), 2)


class TestFailures(MultiSet):
    def test_failing_installer_leaves_none_of_its_folders(self):  # TC-18 (c), AC-12
        self.serve_set("mactahoe", installer_ok=False)
        keep = self.home / ".local/share/icons/Yaru-custom"
        keep.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "falhou"):
            self.icons.ensure_set("mactahoe", self.log.append, "macos-dark")
        self.assertEqual(len(self.installer_runs()), 1)
        self.assertEqual(self.tree(), ["Yaru-custom"])

    def test_cleanup_after_a_failure_keeps_the_overlay_written_meanwhile(self):  # F-2
        self.serve_set("mactahoe", installer_ok=False)
        icons_dir = self.home / ".local/share/icons"
        icons_dir.mkdir(parents=True)
        real = self.icons.subprocess.run

        def run(*a, **kw):  # an apply writes the overlay while the installer runs
            (icons_dir / "Nebulix-Icons").mkdir()
            return real(*a, **kw)
        with mock.patch.object(self.icons.subprocess, "run", side_effect=run), self.assertRaisesRegex(RuntimeError, "falhou"):
            self.icons.ensure_set("mactahoe", self.log.append, "macos-dark")
        self.assertEqual(self.tree(), ["Nebulix-Icons"])

    def test_apply_falls_back_to_papirus_when_the_installer_fails(self):  # TC-18
        self.serve_set("mcmojave", installer_ok=False)
        (self.home / ".local/share/icons/Papirus-Dark").mkdir(parents=True)
        lines = self.apply_icons("mcmojave")
        self.assertTrue(any("McMojave-circle indisponível" in ln for ln in lines), lines)
        self.assertEqual(self.tree(), ["Papirus-Dark"])
        self.assertEqual(self.icon_theme(), "'Papirus-Dark'")

    def test_truncated_tarball_is_refused(self):  # TC-18 (d)
        tb = self.serve_set("whitesur")
        data = tb.path.read_bytes()
        tb.path.write_bytes(data[:len(data) // 2])
        with self.assertRaises(RuntimeError):
            self.ensure()
        self.assertEqual(self.tree(), [])
        self.assertEqual(self.cache_files(), [])

    def test_missing_installer_note_is_reported_without_a_partial_folder(self):
        self.serve_set("whitesur", installer_ok=False)
        with self.assertRaises(RuntimeError):
            self.ensure()
        self.assertEqual(self.tree(), [])


class TestIconsInstallCommand(MultiSet):
    def test_size_is_shown_and_refusal_downloads_nothing(self):  # TC-17, AC-11
        self.serve_set("whitesur")
        n = self.icons.SETS["whitesur"]["size_mb"]
        code, out = self.run_cli("icons", "install", stdin="n")
        self.assertEqual(code, 0)
        self.assertIn(f"~{n} MB", out)
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.tree(), [])
        self.assertEqual(self.cache_files(), [])

    def test_eof_counts_as_no(self):  # D5
        self.serve_set("whitesur")
        code, _ = self.run_cli("icons", "install", stdin=EOFError())
        self.assertEqual(code, 0)
        self.assertEqual(self.installer_runs(), [])

    def test_acceptance_installs_and_activates(self):  # TC-17
        self.serve_set("whitesur")
        code, out = self.run_cli("icons", "install", stdin="s")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.downloads(), 1)
        self.assertEqual(self.icon_theme(), "'Nebulix-Icons'")  # the Nebulix theme keeps its folder overlay
        self.assertIn("Inherits=WhiteSur-purple-dark", (self.home / ".local/share/icons/Nebulix-Icons/index.theme").read_text())
        self.assertEqual(self.installer_runs()[0].split("ARGV=")[1].split()[-1], "purple")

    def test_configured_set_is_used_without_an_argument(self):  # TC-29, AC-21
        from nebulix import config
        for sid in SET_FILES:
            self.serve_set(sid)
        c = config.load()
        c["icons"] = "mactahoe"
        config.save(c)
        code, out = self.run_cli("icons", "install", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.installer_runs()), 1)
        self.assertEqual([t for t in self.tree() if t != "Nebulix-Icons" and not t.startswith("MacTahoe")], [])
        self.assertIn("MacTahoe-purple-dark", self.tree())

    def test_named_set_is_installed_and_saved(self):  # D5
        from nebulix import config
        self.serve_set("mcmojave")
        code, out = self.run_cli("icons", "install", "mcmojave", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(config.load()["icons"], "mcmojave")
        self.assertEqual([t for t in self.tree() if t != "Nebulix-Icons"], ["McMojave-circle-purple-dark", "McMojave-circle-purple-light"])
        self.assertIn("Inherits=McMojave-circle-purple-dark", (self.home / ".local/share/icons/Nebulix-Icons/index.theme").read_text())

    def test_yes_does_not_ask(self):
        self.serve_set("whitesur")
        code, out = self.run_cli("icons", "install", "whitesur", "--yes", stdin=AssertionError("asked"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("[s/N]", out)

    def test_papirus_and_keep_have_nothing_to_download(self):  # TC-29, AC-21
        from nebulix import config
        for v in ("papirus", "keep"):
            with self.subTest(v):
                c = config.load()
                c["icons"] = v
                config.save(c)
                code, out = self.run_cli("icons", "install")
                self.assertEqual(code, 0)
                self.assertIn("nada para baixar", out)
                self.assertEqual(self.installer_runs(), [])

    def test_unknown_set_is_an_error(self):
        code, out = self.run_cli("icons", "install", "wh1tesur", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("conjunto desconhecido", out)
        self.assertEqual(self.installer_runs(), [])

    def test_failure_returns_1_and_keeps_the_config(self):
        from nebulix import config
        self.serve_set("mactahoe", installer_ok=False)
        code, out = self.run_cli("icons", "install", "mactahoe", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("MacTahoe indisponível", out)
        self.assertEqual(config.load()["icons"], "whitesur")
        self.assertEqual(self.tree(), [])

    def test_installed_set_is_not_asked_about_again(self):
        self.serve_set("whitesur")
        self.run_cli("icons", "install", "whitesur", "--yes")
        code, out = self.run_cli("icons", "install", "whitesur", stdin=AssertionError("asked"))
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.installer_runs()), 1)

    def test_help_lists_the_sets(self):
        _, out = self.run_cli("--help")
        self.assertIn("icons install [CONJUNTO]", out)
        self.assertIn("mactahoe", out)


class TestDoctor(MultiSet):
    def lines(self):
        from nebulix import doctor
        labels = [e["label"] for e in self.icons.SETS.values()]
        return [m for lvl, m, fix in doctor.check() if "ícones" in m and any(lb in m for lb in labels)]

    def test_one_line_per_set(self):  # TC-28, AC-20
        lines = self.lines()
        for e in self.icons.SETS.values():
            self.assertEqual(len([ln for ln in lines if e["label"] in ln]), 1, lines)
        self.assertTrue(all("não instalados" in ln for ln in lines), lines)

    def test_installed_set_is_reported_as_installed(self):  # TC-28
        (self.home / ".local/share/icons/WhiteSur-blue-dark").mkdir(parents=True)
        (self.home / ".local/share/icons/WhiteSur-blue-light").mkdir()
        lines = self.lines()
        self.assertIn("ícones WhiteSur instalados", lines)
        self.assertTrue(any("MacTahoe não instalados" in ln for ln in lines), lines)
        self.assertTrue(any("McMojave-circle não instalados" in ln for ln in lines), lines)

    def test_the_fix_command_names_the_set(self):
        from nebulix import doctor
        fixes = {m: fix for lvl, m, fix in doctor.check()}
        self.assertEqual(fixes["ícones MacTahoe não instalados (~10 MB)"], "nebulix icons install mactahoe")

    def test_a_prefix_of_another_set_is_not_a_match(self):
        (self.home / ".local/share/icons/WhiteSurX").mkdir(parents=True)
        self.assertFalse(self.icons.installed("whitesur"))
