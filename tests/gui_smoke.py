# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds the settings window (run with a sandbox HOME!) and renders every page to a PNG. Needs a display."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Graphene, GLib, Gtk  # noqa: E402

from nebulix import gui  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
app = Adw.Application(application_id="io.github.nebulix.SmokeTest")


def pages(w):
    res = []

    def walk(x):
        if isinstance(x, Adw.PreferencesPage):
            res.append(x)
        c = x.get_first_child()
        while c:
            walk(c)
            c = c.get_next_sibling()
    walk(w)
    return res


def shot(win, name):
    w, h = win.get_width(), win.get_height()
    snap = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
    tex = win.get_native().get_renderer().render_texture(snap.to_node(), Graphene.Rect().init(0, 0, w, h))
    tex.save_to_png(str(out / f"{name}.png"))


def go(a):
    win = gui.SettingsWindow(a)
    win.set_default_size(720, 900)
    win.present()
    pl = pages(win)
    state = {"i": 0}

    def step():
        i = state["i"]
        if i > 0:
            shot(win, f"page{i}-{pl[i-1].get_title()}")
        if i >= len(pl):
            a.quit()
            return False
        win.set_visible_page(pl[i])
        state["i"] += 1
        return True
    GLib.timeout_add(1000, step)


app.connect("activate", go)
app.run(None)
