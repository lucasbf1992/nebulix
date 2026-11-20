# SPDX-License-Identifier: GPL-3.0-or-later
"""The colour of the icons follows the accent: the mapping, the dark/light variant, and what apply does when the
folder of that colour is missing. Everything runs against fake tarballs and folders, never the network."""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_icons_sets as base  # noqa: E402

# What the accent of each theme gets in each set (reference hues from the upstream sets).
EXPECTED = {
    "whitesur": {
        "nebulix": {"nebulix": "purple", "magenta": "pink", "cyan": "default", "blue": "default", "green": "green", "amber": "yellow"},
        "nebulix-light": {"nebulix": "purple", "magenta": "pink", "cyan": "default", "blue": "default", "green": "green", "amber": "yellow"},
        "macos-dark": {"blue": "default", "purple": "purple", "pink": "pink", "red": "red", "orange": "orange", "yellow": "yellow",
                       "green": "green", "graphite": "grey"},
    },
    "mactahoe": {
        "nebulix": {"nebulix": "purple", "magenta": "purple", "cyan": "blue", "blue": "blue", "green": "green", "amber": "yellow"},
        "macos-dark": {"blue": "blue", "purple": "purple", "pink": "red", "red": "red", "orange": "orange", "yellow": "yellow",
                       "green": "green", "graphite": "grey"},  # MacTahoe has no pink: the closest hue
    },
    "mcmojave": {
        "nebulix": {"nebulix": "purple", "magenta": "pink", "cyan": "blue", "blue": "blue", "green": "green", "amber": "yellow"},
        "macos-dark": {"blue": "blue", "purple": "purple", "pink": "pink", "red": "red", "orange": "orange", "yellow": "yellow",
                       "green": "green", "graphite": "grey"},
    },
}
FIXED = {"whitesur": {"cyan": "default", "amber": "yellow", "graphite": "grey"},
         "mactahoe": {"cyan": "blue", "amber": "yellow", "graphite": "grey"},
         "mcmojave": {"cyan": "blue", "amber": "yellow", "graphite": "grey"}}
# an accent name of each theme that stands for cyan / amber / graphite
FIXED_ACCENT = {"cyan": ("nebulix", "cyan"), "amber": ("nebulix", "amber"), "graphite": ("macos-dark", "graphite")}


class IconColor(base.MultiSet):
    def install_all(self, set_id):
        """Every colour and variant folder of a set, as if the whole set were installed."""
        e = self.icons.SETS[set_id]
        for c in e["colors"]:
            for v in ("dark", "light"):
                (self.home / ".local/share/icons" / self.icons.folder_name(set_id, c, v)).mkdir(parents=True, exist_ok=True)

    def install_folders(self, set_id, colors, schemes=("dark", "light")):
        for c in colors:
            for v in schemes:
                (self.home / ".local/share/icons" / self.icons.folder_name(set_id, c, v)).mkdir(parents=True, exist_ok=True)

    def apply(self, set_id, theme, accent="auto", install=False):
        from nebulix import config
        from nebulix.apply import apply
        cfg = dict(config.apply_theme(config.validate({}), theme), icons=set_id, accent=accent)
        lines = []
        st = apply(cfg, only=["icons"], install_icons=install, log=lines.append)
        return st, lines

    def shown_base(self):
        """The set folder the desktop ends up showing: the icon theme itself, or what the Nebulix overlay inherits."""
        name = self.icon_theme().strip("'")
        if name == self.icons.THEME_NAME:
            idx = (self.home / ".local/share/icons" / name / "index.theme").read_text()
            return next(ln for ln in idx.splitlines() if ln.startswith("Inherits=")).split("=", 1)[1].split(",")[0]
        return name


class TestMapping(IconColor):
    def test_the_mapping_is_per_set_and_per_accent(self):  # every set x theme x accent
        for sid, themes in EXPECTED.items():
            self.install_all(sid)
            prefix = self.icons.SETS[sid]["prefix"]
            for theme, accents in themes.items():
                from nebulix import themes as T
                scheme = T.get(theme)["scheme"]
                for accent, color in accents.items():
                    with self.subTest(set=sid, theme=theme, accent=accent):
                        self.apply(sid, theme, accent)
                        want = prefix + ("" if color == "default" else f"-{color}") + f"-{scheme}"
                        self.assertEqual(self.shown_base(), want)

    def test_an_accent_gets_the_colour_of_the_same_name_when_the_set_has_it(self):  # FR-10
        from nebulix import themes
        for sid in self.icons.SETS:
            colors = self.icons.SETS[sid]["colors"]
            for theme in ("macos-dark", "macos-light", "nebulix", "nebulix-light"):
                for accent in themes.get(theme)["accents"]:
                    if accent in colors and accent not in ("nord", "black"):
                        with self.subTest(set=sid, theme=theme, accent=accent):
                            self.assertEqual(self.icons.accent_color(sid, theme, accent), accent)
        self.assertEqual(self.icons.accent_color("whitesur", "macos-dark", "pink"), "pink")
        self.assertEqual(self.icons.accent_color("whitesur", "macos-light", "orange"), "orange")
        self.assertEqual(self.icons.accent_color("whitesur", "nebulix-light", "green"), "green")
        self.assertEqual(self.icons.accent_color("whitesur", "macos-dark", "blue"), "default")  # the set's own blue
        self.assertEqual(self.icons.accent_color("mactahoe", "macos-dark", "pink"), "red")  # no pink: closest hue

    def test_fixed_cases_cyan_amber_graphite(self):
        from nebulix import themes
        for sid, cases in FIXED.items():
            for name, color in cases.items():
                theme, accent = FIXED_ACCENT[name]
                with self.subTest(set=sid, accent=name):
                    self.assertEqual(self.icons.set_color(sid, themes.accent_hex(theme, accent)), color)

    def test_light_and_dark_follow_the_scheme_of_the_theme(self):
        for sid in self.icons.SETS:
            self.install_all(sid)
            for theme, scheme in (("nebulix", "dark"), ("nebulix-light", "light"), ("macos-dark", "dark"), ("macos-light", "light")):
                with self.subTest(set=sid, theme=theme):
                    self.apply(sid, theme)
                    self.assertTrue(self.shown_base().endswith(f"-{scheme}"), self.shown_base())

    def test_auto_keeps_the_colours_of_the_previous_release(self):  # compatibility golden
        self.install_all("whitesur")
        for theme, want in (("nebulix", "WhiteSur-purple-dark"), ("nebulix-light", "WhiteSur-purple-light"),
                            ("macos-dark", "WhiteSur-dark"), ("macos-light", "WhiteSur-light")):
            with self.subTest(theme=theme):
                self.apply("whitesur", theme, "auto")
                self.assertEqual(self.shown_base(), want)

    def test_custom_hex_accents(self):
        from nebulix import themes
        self.assertEqual(self.icons.set_color("whitesur", "#808080"), "grey")  # no saturation
        self.assertEqual(self.icons.set_color("mactahoe", "#FF0000"), "red")
        self.assertEqual(self.icons.set_color("mcmojave", "#00FF00"), "green")
        self.assertEqual(themes.accent_hex("nebulix", "#12abef"), "#12ABEF")
        self.install_all("mactahoe")
        self.apply("mactahoe", "nebulix", "#12abef")
        self.assertEqual(self.shown_base(), "MacTahoe-blue-dark")

    def test_low_saturation_goes_to_grey_and_the_edge_is_0_15(self):
        grey_ish = "#%02X%02X%02X" % (200, 190, 200 - 30)  # saturation (200-170)/200 = 0.15
        below = "#%02X%02X%02X" % (200, 195, 200 - 29)  # 29/200 = 0.145
        self.assertEqual(self.icons.set_color("mactahoe", below), "grey")
        self.assertNotEqual(self.icons.set_color("mactahoe", grey_ish), "grey")

    def test_a_set_without_grey_falls_back_to_its_default_colour(self):
        entry = dict(self.icons.SETS["mactahoe"], colors={"blue": "#006EFD", "red": "#FE342C"})
        entry.pop("neutral")
        with mock.patch.dict(self.icons.SETS, {"fake": entry}):
            self.assertEqual(self.icons.set_color("fake", "#989898"), "blue")
            self.assertEqual(self.icons.set_color("fake", "#FF0000"), "red")

    def test_the_theme_catalogue_no_longer_carries_an_icon_colour(self):
        from nebulix import themes
        for t in themes.ids():
            self.assertNotIn("color", themes.get(t)["icons"])


class TestMissingColour(IconColor):
    def serve_all(self, set_id="whitesur"):
        return self.serve_set(set_id, colors=tuple(self.icons.SETS[set_id]["colors"]))

    def test_a_cached_colour_installs_without_the_network(self):
        self.serve_all()
        self.apply("whitesur", "nebulix", "nebulix", install=True)  # purple: downloads once, keeps the tarball
        self.assertEqual(self.downloads(), 1)
        del os.environ["NEBULIX_ICONS_SOURCE"]  # from here on the network (and the source) is gone
        st, _ = self.apply("whitesur", "nebulix", "green")  # no ask for a download: the cache is enough
        self.assertEqual(self.shown_base(), "WhiteSur-green-dark")
        self.assertEqual(len(self.installer_runs()), 2)
        self.assertEqual(st.missing, [])
        self.assertIn("WhiteSur-green-dark", self.tree())
        self.assertIn("WhiteSur-purple-dark", self.tree())  # the first colour stays

    def test_a_missing_colour_without_cache_uses_the_closest_installed_one(self):
        self.install_folders("whitesur", ("default", "purple"))
        st, _ = self.apply("whitesur", "nebulix", "green")  # green is closer to the blue than to the purple
        self.assertEqual(self.shown_base(), "WhiteSur-dark")
        self.assertEqual(self.installer_runs(), [])
        self.assertEqual(self.cache_files(), [])
        self.assertTrue(any("WhiteSur-green-dark" in m and "WhiteSur-dark" in m for m, _ in st.missing), st.missing)
        self.assertTrue(any("nebulix icons install whitesur" in fix for _m, fix in st.missing))

    def test_the_closest_colour_is_taken_in_the_same_variant_and_set(self):
        self.install_folders("whitesur", ("purple",), schemes=("light",))
        self.install_folders("mactahoe", ("green",))
        self.apply("whitesur", "nebulix", "magenta")
        self.assertNotIn("WhiteSur", self.icon_theme())  # no dark folder of the set: Papirus, not the light one
        self.assertNotIn("MacTahoe", self.shown_base())

    def test_nothing_installed_and_no_ask_means_papirus_and_no_download(self):
        (self.home / ".local/share/icons/Papirus-Dark").mkdir(parents=True)
        st, _ = self.apply("whitesur", "nebulix", "green")
        self.assertEqual(self.icon_theme(), "'Nebulix-Icons'")
        self.assertEqual(self.installer_runs(), [])
        self.assertTrue(st.missing)

    def test_asking_to_install_downloads_the_colour_of_the_accent(self):
        self.serve_all()
        self.install_folders("whitesur", ("purple",))
        self.apply("whitesur", "nebulix", "amber", install=True)
        self.assertEqual(self.shown_base(), "WhiteSur-yellow-dark")
        self.assertEqual(self.downloads(), 1)
        self.assertRegex(self.installer_runs()[-1], r"-t yellow$")

    def test_changing_the_accent_twice_does_not_install_again(self):
        self.serve_all()
        self.apply("whitesur", "nebulix", "green", install=True)
        self.apply("whitesur", "nebulix", "green")
        self.assertEqual(len(self.installer_runs()), 1)

    def test_doctor_names_the_missing_colour_of_the_accent(self):
        from nebulix import config, doctor
        self.install_folders("whitesur", ("default",))
        config.save(dict(config.validate({}), accent="green"))
        found = [(lvl, m, fix) for lvl, m, fix in doctor.check() if "WhiteSur-green-dark" in m]
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][0], "warn")
        self.assertEqual(found[0][2], "nebulix icons install whitesur")

    def test_doctor_is_quiet_when_the_colour_of_the_accent_is_there(self):
        from nebulix import config, doctor
        self.install_folders("whitesur", ("default", "green"))
        config.save(dict(config.validate({}), accent="green"))
        self.assertEqual([m for _l, m, _f in doctor.check() if "WhiteSur-green-dark" in m], [])
