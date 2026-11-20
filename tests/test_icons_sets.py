# SPDX-License-Identifier: GPL-3.0-or-later
"""Icon set registry and download (S1/S2): everything runs against fake tarballs, never the network."""
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
        return self.icons.ensure_whitesur(self.log.append, theme)


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
