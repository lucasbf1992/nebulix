# SPDX-License-Identifier: GPL-3.0-or-later
"""Architecture guards: stdlib-only core, license headers, no package manager calls, GUI labels for every value."""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import ROOT, Sandbox  # noqa: E402

PKG = ROOT / "nebulix"
SPDX = "# SPDX-License-Identifier: "  # any license: the art generators (wallpapers.py) are CC-BY-SA-4.0
# CHOICES keys that the GUI shows as a switch or spin row instead of a combo with labels
NO_COMBO = {"dock_zoom"}
# the one place outside gui.py that touches gi: wallpapers.rasterize imports GdkPixbuf lazily, inside the function
LAZY_GI = {"wallpapers.py"}
# first words of the calls apply/undo must never make; `flatpak override` is allowed, install/remote-add are not
PKG_MANAGERS = ("apt", "apt-get", "pip", "pip3")


def sources():
    return sorted(PKG.glob("*.py"))


class TestArchitecture(Sandbox):
    def test_core_imports_only_the_stdlib(self):  # TC-89
        bad = []
        for f in sources():
            if f.name == "gui.py":  # the only module allowed to import gi
                continue
            for node in ast.walk(ast.parse(f.read_text(), str(f))):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module]
                else:
                    continue
                bad += [f"{f.name}: {m}" for m in mods if m.split(".")[0] not in sys.stdlib_module_names
                        and not (m.split(".")[0] == "gi" and f.name in LAZY_GI)]
        self.assertEqual(bad, [], "third-party imports outside gui.py")

    def test_every_module_starts_with_the_spdx_line(self):  # TC-89
        self.assertTrue(sources())
        bad = [f.name for f in sources() if not f.read_text().startswith(SPDX)]
        self.assertEqual(bad, [], "SPDX-License-Identifier missing on line 1")


class TestNoPackageManagers(Sandbox):
    def run_everything(self):
        from nebulix import config
        from nebulix.apply import apply
        from nebulix.restore import restore
        cfg = config.validate({"wallpaper": "none"})
        apply(cfg, log=lambda *_: None)
        apply(cfg, log=lambda *_: None)
        restore("undo", log=lambda *_: None)
        apply(cfg, log=lambda *_: None)
        restore("reset", log=lambda *_: None, remove_icons=True)

    def test_apply_and_undo_never_install_packages(self):  # TC-5 (base)
        for n in (*PKG_MANAGERS,):
            self.fake(n)
        self.run_everything()
        calls = self.calls()
        flatpak = [c for c in calls if c.startswith("flatpak")]
        self.assertTrue(flatpak, "the flatpak override call was expected (sanity check of the log)")
        for c in flatpak:
            self.assertTrue(c.startswith("flatpak override "), c)
        self.assertFalse([c for c in calls if c.split()[0] in PKG_MANAGERS], calls)
        self.assertFalse([c for c in calls if "install" in c.split() or "remote-add" in c.split()], calls)

    def test_without_the_tools_nothing_is_installed_either(self):  # TC-5 (base)
        (self.tmp / "bin/flatpak").unlink()
        self.restrict_path()
        self.run_everything()
        self.assertEqual([c for c in self.calls() if not c.startswith("gsettings")], [])


class TestLabels(Sandbox):
    """GUI labels read from the source with ast, so the check needs no display or GTK."""

    @staticmethod
    def literal_labels():
        """(LABELS: key -> (set of literal value names, has_computed_part), COMP_LABELS: set of names)."""
        labels, comp = {}, set()
        for node in ast.parse((PKG / "gui.py").read_text()).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name == "COMP_LABELS":
                comp = {k.value for k in node.value.keys}
            elif name == "LABELS":
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(v, ast.DictComp):  # derived from config.CHOICES: nothing literal to check
                        labels[k.value] = (set(), True)
                        continue
                    names = {x.value for x in v.keys if isinstance(x, ast.Constant)}
                    computed = any(x is None for x in v.keys)  # `**{...}` spread
                    labels[k.value] = (names, computed)
        return labels, comp

    def test_every_choice_has_a_label(self):  # TC-31 (base)
        from nebulix import config
        labels, comp = self.literal_labels()
        self.assertTrue(labels and comp)
        missing = []
        for key, values in config.CHOICES.items():
            if key in NO_COMBO:
                continue
            names, computed = labels.get(key, (set(), False))
            if key not in labels:
                missing.append(f"LABELS[{key!r}]")
            elif not computed:
                missing += [f"LABELS[{key!r}][{v!r}]" for v in values if v not in names]
        missing += [f"COMP_LABELS[{c!r}]" for c in config.COMPONENTS if c not in comp]
        self.assertEqual(missing, [])

    def test_icon_pickers_label_exactly_the_accepted_values(self):  # TC-31
        from nebulix import config, icons
        labels, _comp = self.literal_labels()
        shown = {"whitesur", "mactahoe", "mcmojave", "papirus", "keep"}
        self.assertEqual(labels["icons"], (shown, False))
        self.assertEqual(set(config.CHOICES["icons"]), shown)
        self.assertEqual(set(icons.SETS) | {"papirus", "keep"}, shown)
        self.assertEqual(labels["icon_folders"], (set(config.CHOICES["icon_folders"]), False))

    def test_no_label_for_a_value_that_does_not_exist(self):
        from nebulix import config
        labels, comp = self.literal_labels()
        stale = [f"LABELS[{k!r}][{v!r}]" for k, (names, _c) in labels.items()
                 for v in names if v not in config.CHOICES.get(k, ())]
        stale += [f"COMP_LABELS[{c!r}]" for c in comp if c not in config.COMPONENTS]
        self.assertEqual(stale, [])
