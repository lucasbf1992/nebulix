# SPDX-License-Identifier: GPL-3.0-or-later
"""Release consistency (TC-87) and, opt-in, the real package build (TC-88)."""
import json
import os
import subprocess
import tarfile
import unittest
from pathlib import Path

import nebulix

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_VERSION = "0.5.0"


class TestRelease(unittest.TestCase):
    def test_version_is_consistent(self):  # TC-87
        self.assertEqual(nebulix.__version__, EXPECTED_VERSION)
        self.assertEqual(json.loads((ROOT / "palette.json").read_text())["version"], EXPECTED_VERSION)
        self.assertIn(f"## {EXPECTED_VERSION} (", (ROOT / "CHANGELOG.md").read_text())

    @unittest.skipUnless(os.environ.get("NEBULIX_RUN_PACKAGE_TEST") == "1", "set NEBULIX_RUN_PACKAGE_TEST=1")
    def test_package_builds(self):  # TC-88
        # package.sh runs the whole suite: switch this test off in the child or it would recurse forever
        env = dict(os.environ, NEBULIX_RUN_PACKAGE_TEST="0")
        subprocess.run(["./package.sh"], cwd=ROOT, check=True, capture_output=True, env=env)
        tar = ROOT / f"release/nebulix-{EXPECTED_VERSION}.tar.xz"
        deb = ROOT / f"release/nebulix_{EXPECTED_VERSION}-1_all.deb"
        self.assertTrue(tar.is_file() and deb.is_file())
        with tarfile.open(tar) as t:
            names = t.getnames()
        self.assertIn(f"nebulix-{EXPECTED_VERSION}/palette.json", names)
        self.assertIn(f"nebulix-{EXPECTED_VERSION}/nebulix/__init__.py", names)
        self.assertTrue((ROOT / "release/SHA256SUMS").is_file())
