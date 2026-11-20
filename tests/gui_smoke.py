# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds the settings window (run with a sandbox HOME!) and renders every page to a PNG. Needs a display."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Graphene, GLib, Gtk  # noqa: E402

from nebulix import gui, icons  # noqa: E402

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
    node = snap.to_node()
    if node is None:  # nothing drawn yet: skip the PNG instead of raising inside the timer
        print("aviso: sem conteúdo para", name, file=sys.stderr)
        return
    tex = win.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w, h))
    tex.save_to_png(str(out / f"{name}.png"))


failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("FALHOU:", msg, file=sys.stderr)


def widgets(root):
    yield root
    c = root.get_first_child()
    while c:
        yield from widgets(c)
        c = c.get_next_sibling()


def strings(row):
    m = row.get_model()
    return [m.get_string(i) for i in range(m.get_n_items())]


def check_icons_page(win):
    """The icons page: the five sets, the folders control, the preview and (set not installed) the download button."""
    check(strings(win.rows["icons"][0]) == list(gui.LABELS["icons"].values()), "seletor de conjuntos sem os rótulos de LABELS")
    check(strings(win.rows["icons"][0]) == ["Estilo macOS (WhiteSur, variante do tema)", "MacTahoe (estilo macOS recente)", "McMojave-circle (ícones redondos)",
                                            "Papirus (claro ou escuro, conforme o tema)", "Não alterar"], "rótulos dos 5 conjuntos")
    check(strings(win.rows["icon_folders"][0]) == list(gui.LABELS["icon_folders"].values()), "controle icon_folders sem os 3 rótulos")
    check(len([w for w in widgets(win) if isinstance(w, Gtk.Image) and w.get_tooltip_text() in gui.SettingsWindow.PREVIEW_ICONS]) == 8, "prévia sem 8 ícones")
    for mode in icons.SETS:
        win.cfg["icons"] = mode
        win._update_icons_view()
        want = not icons.has_theme(icons.base_name(win.cfg["theme"], mode, win.cfg["accent"]))
        check(win.dl_row.get_visible() == want, f"botão de baixar em {mode}: visível deveria ser {want}")
        if want:
            check(win.dl_btn.get_label() == f"Baixar (~{icons.SETS[mode]['size_mb']} MB)", f"rótulo do botão em {mode}: {win.dl_btn.get_label()}")
    for mode in ("papirus", "keep"):
        win.cfg["icons"] = mode
        win._update_icons_view()
        check(not win.dl_row.get_visible(), f"botão de baixar não deve aparecer em {mode}")
    win.cfg["icons"] = "whitesur"
    win._update_icons_view()


def go(a):
    win = gui.SettingsWindow(a)
    win.set_default_size(720, 900)
    win.present()
    try:
        check_icons_page(win)
    except Exception as e:
        check(False, f"check_icons_page: {e!r}")
    pl = pages(win)
    state = {"i": 0}

    def step():
        try:
            i = state["i"]
            if i > 0:
                shot(win, f"page{i}-{pl[i-1].get_title()}")
            if i >= len(pl):
                a.quit()
                return False
            win.set_visible_page(pl[i])
            state["i"] += 1
            return True
        except Exception as e:  # never leave the app running: record it and quit
            check(False, f"erro no passo da captura: {e!r}")
            a.quit()
            return False
    GLib.timeout_add(1000, step)


app.connect("activate", go)
app.run(None)
sys.exit(1 if failures else 0)
