# SPDX-License-Identifier: GPL-3.0-or-later
"""Nebulix settings app (GTK4 + libadwaita). Changes are saved and applied live (debounced)."""
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import __version__, config, doctor, icons, paths  # noqa: E402
from .apply import apply  # noqa: E402
from .restore import restore  # noqa: E402

APP_ID = "io.github.nebulix.Settings"
LABELS = {
    "variant": {"dark": "Dark", "darker": "Darker (preto OLED)"},
    "window_buttons": {"gnome": "GNOME (à direita)", "mac": "Semáforo macOS (à esquerda)"},
    "topbar": {"floating": "Flutuante (pílulas)", "solid": "Sólida"},
    "dock": {"macos": "Estilo macOS (flutuante, centralizada)", "ubuntu": "Não alterar (padrão do Ubuntu)"},
    "dock_position": {"bottom": "Embaixo", "left": "Esquerda", "right": "Direita"},
    "icons": {"whitesur": "Estilo macOS (WhiteSur + pastas Nebulix)", "papirus": "Papirus-Dark", "keep": "Não alterar"},
    "wallpaper": {"orbit": "Órbita", "horizon": "Horizonte", "circuit": "Circuito", "code": "Código", "gen-orbit": "Órbita (gerada, segue o destaque)", "gen-horizon": "Horizonte (gerado, segue o destaque)", "gen-circuit": "Circuito (gerado, segue o destaque)", "gen-code": "Código (gerado, segue o destaque)", "none": "Não alterar"},
    "wallpaper_size": {"1080p": "1080p", "1440p": "1440p", "4k": "4K", "ultrawide": "Ultrawide 21:9"},
}
COMP_LABELS = {"gtk": "Apps GTK e libadwaita", "shell": "GNOME Shell (barra, menus, dock)", "terminal": "Terminal (Ptyxis / GNOME Terminal)",
               "starship": "Prompt Starship", "fastfetch": "fastfetch", "btop": "btop", "vscode": "VS Code", "nvim": "Neovim",
               "wallpaper": "Wallpaper", "icons": "Ícones"}


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Nebulix", default_width=720, default_height=780, search_enabled=False)
        self.cfg = config.load()
        self._timer = None
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        css = "".join(f".nbx-{n} {{ background: {h}; border-radius: 99px; min-width: 26px; min-height: 26px; padding: 0; }}"
                      f".nbx-{n}:checked {{ box-shadow: 0 0 0 3px alpha(currentColor, .8); }}" for n, h in config.ACCENTS.items())
        self._css.load_from_string(css)
        self.status_row = Adw.ActionRow()
        self.apply_btn = Gtk.Button(label="Aplicar agora", valign=Gtk.Align.CENTER)
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", lambda _b: self._apply_now())
        self.status_row.add_suffix(self.apply_btn)
        self._refresh_status()
        self.add(self._page_look())
        self.add(self._page_icons())
        self.add(self._page_dev())
        self.add(self._page_restore())
        self.add(self._page_doctor())

    # ---------- plumbing ----------
    @staticmethod
    def installed():
        m = paths.state_dir() / "manifest"
        return m.exists() and bool(m.read_text().strip())

    def _refresh_status(self):
        on = self.installed()
        self.status_row.set_title("Tema aplicado" if on else "Tema não aplicado")
        self.status_row.set_subtitle("As opções abaixo são aplicadas ao mudar. Use o botão para reaplicar tudo." if on
                                     else "As configurações estão no padrão (ou foram restauradas). Escolha as opções e aplique.")
        self.apply_btn.set_label("Reaplicar" if on else "Aplicar agora")
        return False

    def toast(self, msg, persistent=False):
        t = Adw.Toast(title=msg)
        t.set_timeout(0 if persistent else 3)
        self.add_toast(t)
        return False

    def set(self, key, value):
        self.cfg[key] = value
        try:
            config.validate(self.cfg)
        except ValueError as e:
            self.add_toast(Adw.Toast(title=str(e)))
            return
        config.save(self.cfg)
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(500, self._apply_now)

    def _apply_now(self, only=None):
        self._timer = None
        cfg = dict(self.cfg)

        def work():
            err = None
            try:
                apply(cfg, only=only, log=lambda *_: None)
            except Exception as e:  # surface any failure to the user
                err = f"Erro ao aplicar: {e}"
            GLib.idle_add(self.toast, err or "Aplicado", bool(err))
            GLib.idle_add(self._refresh_status)
        threading.Thread(target=work, daemon=True).start()
        return False

    def combo(self, group, title, key, subtitle=None):
        opts = list(LABELS[key])
        row = Adw.ComboRow(title=title, subtitle=subtitle or "", model=Gtk.StringList.new([LABELS[key][o] for o in opts]))
        row.set_selected(opts.index(self.cfg[key]))
        row.connect("notify::selected", lambda r, _p: self.set(key, opts[r.get_selected()]))
        group.add(row)
        return row

    def spin(self, group, title, key, lo, hi, subtitle=""):
        row = Adw.SpinRow.new_with_range(lo, hi, 1)
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.set_value(self.cfg[key])
        row.connect("notify::value", lambda r, _p: self.set(key, int(r.get_value())))
        group.add(row)

    # ---------- pages ----------
    def _page_look(self):
        page = Adw.PreferencesPage(title="Aparência", icon_name="applications-graphics-symbolic")
        gs_ = Adw.PreferencesGroup()
        gs_.add(self.status_row)
        page.add(gs_)
        warns = [m for lvl, m, _f in doctor.check() if lvl == "warn"]
        if warns:
            gb = Adw.PreferencesGroup()
            gb.add(Adw.Banner(title=f"Requisitos faltando: {'; '.join(warns)}. Veja a aba Diagnóstico.", revealed=True))
            page.add(gb)
        g = Adw.PreferencesGroup(title="Cores")
        row = Adw.ActionRow(title="Destaque", subtitle="Cor principal de seleção, botões e foco")
        box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        first = None
        for name in config.ACCENTS:
            b = Gtk.ToggleButton(tooltip_text=name)
            b.add_css_class(f"nbx-{name}")
            if first:
                b.set_group(first)
            first = first or b
            b.set_active(self.cfg["accent"] == name)
            b.connect("toggled", lambda w, n=name: w.get_active() and self.set("accent", n))
            box.append(b)
        row.add_suffix(box)
        g.add(row)
        hexrow = Adw.EntryRow(title="Cor personalizada (#RRGGBB)")
        hexrow.set_text(self.cfg["accent"] if self.cfg["accent"].startswith("#") else "")
        hexrow.set_show_apply_button(True)
        hexrow.connect("apply", lambda r: self.set("accent", r.get_text().strip()))
        g.add(hexrow)
        self.combo(g, "Variante", "variant", "Darker usa fundo preto puro (telas OLED)")
        page.add(g)
        g2 = Adw.PreferencesGroup(title="Janelas e barra")
        self.combo(g2, "Botões da janela", "window_buttons")
        self.combo(g2, "Barra superior", "topbar")
        self.spin(g2, "Cantos arredondados", "radius", 6, 20, "em pixels")
        page.add(g2)
        g3 = Adw.PreferencesGroup(title="Dock", description="Requer o Ubuntu Dock (padrão do Ubuntu). O desfoque do fundo não existe como no macOS; o zoom é opcional.")
        self.combo(g3, "Estilo", "dock")
        self.combo(g3, "Posição", "dock_position")
        self.spin(g3, "Tamanho dos ícones", "dock_icon_size", 32, 64)
        self.spin(g3, "Opacidade do fundo", "dock_opacity", 20, 100, "em %")
        zr = Adw.SwitchRow(title="Zoom ao passar o mouse", subtitle="Estilo macOS. Instala a extensão nebulix-dock-zoom (precisa do Ubuntu Dock). Na primeira vez, saia da sessão e entre de novo.",
                           active=self.cfg["dock_zoom"] == "on")
        zr.connect("notify::active", lambda r, _p: self.set("dock_zoom", "on" if r.get_active() else "off"))
        g3.add(zr)
        self.spin(g3, "Intensidade do zoom", "dock_zoom_factor", 120, 200, "em % (160 = 1,6x)")
        page.add(g3)
        return page

    def _page_icons(self):
        page = Adw.PreferencesPage(title="Ícones e fundo", icon_name="image-x-generic-symbolic")
        g = Adw.PreferencesGroup(title="Ícones")
        self.combo(g, "Conjunto", "icons", "O estilo macOS usa o WhiteSur (GPL-3.0), baixado de uma versão fixa do GitHub")
        row = Adw.ActionRow(title="WhiteSur", subtitle="Instalado" if icons.has_theme(icons.BASE) else "Não instalado (~7 MB, verifica sha256)")
        btn = Gtk.Button(label="Instalar", valign=Gtk.Align.CENTER, sensitive=not icons.has_theme(icons.BASE))

        def install(_b):
            btn.set_sensitive(False)
            row.set_subtitle("Baixando…")

            def work():
                try:
                    icons.ensure_whitesur(lambda *_: None)
                    apply(dict(self.cfg), only=["icons"], log=lambda *_: None)
                    GLib.idle_add(lambda: row.set_subtitle("Instalado") or False)
                except Exception as e:
                    GLib.idle_add(lambda: (row.set_subtitle(f"Falhou: {e}"), btn.set_sensitive(True)) and False)
            threading.Thread(target=work, daemon=True).start()
        btn.connect("clicked", install)
        row.add_suffix(btn)
        g.add(row)
        page.add(g)
        g2 = Adw.PreferencesGroup(title="Papel de parede")
        self.combo(g2, "Imagem", "wallpaper", "As versões \"gerada\" usam a cor de destaque escolhida")
        self.combo(g2, "Tamanho (só para gerados)", "wallpaper_size")
        page.add(g2)
        return page

    def _page_dev(self):
        page = Adw.PreferencesPage(title="Componentes", icon_name="utilities-terminal-symbolic")
        g = Adw.PreferencesGroup(title="O que o Nebulix aplica", description="Desligar um item não desfaz o que já foi aplicado; use Restaurar para isso.")
        for c in config.COMPONENTS:
            r = Adw.SwitchRow(title=COMP_LABELS[c], active=c in self.cfg["components"])

            def toggled(row, _p, c=c):
                comps = [x for x in self.cfg["components"] if x != c] + ([c] if row.get_active() else [])
                self.set("components", [x for x in config.COMPONENTS if x in comps])
            r.connect("notify::active", toggled)
            g.add(r)
        page.add(g)
        return page

    def _confirm(self, heading, body, label, cb, destructive=True):
        d = Adw.AlertDialog(heading=heading, body=body)
        d.add_response("cancel", "Cancelar")
        d.add_response("ok", label)
        if destructive:
            d.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel")
        d.connect("response", lambda _d, r: r == "ok" and cb())
        d.present(self)

    def _page_restore(self):
        page = Adw.PreferencesPage(title="Restaurar", icon_name="edit-undo-symbolic")
        g = Adw.PreferencesGroup(title="Voltar ao padrão", description="Nenhuma das opções remove o pacote; para isso use: sudo apt remove nebulix")

        def run_restore(mode):
            def work():
                try:
                    restore(mode, log=lambda *_: None)
                    msg, bad = "Restaurado. Use \"Aplicar agora\" na aba Aparência para aplicar de novo.", False
                except Exception as e:
                    msg, bad = f"Erro ao restaurar: {e}", True
                GLib.idle_add(self.toast, msg, bad)
                GLib.idle_add(self._refresh_status)
            threading.Thread(target=work, daemon=True).start()
        r1 = Adw.ActionRow(title="Desfazer minhas mudanças", subtitle="Volta ao que estava antes de instalar o Nebulix (usa o backup)")
        b1 = Gtk.Button(label="Desfazer", valign=Gtk.Align.CENTER)
        b1.connect("clicked", lambda _b: self._confirm("Desfazer as mudanças do Nebulix?", "Temas, ícones, wallpaper e dock voltam aos valores de antes.", "Desfazer", lambda: run_restore("undo")))
        r1.add_suffix(b1)
        r2 = Adw.ActionRow(title="Padrão de fábrica do Ubuntu", subtitle="Reseta as configurações para os valores do Ubuntu (Yaru, wallpaper padrão, dock lateral)")
        b2 = Gtk.Button(label="Restaurar padrão", valign=Gtk.Align.CENTER)
        b2.add_css_class("destructive-action")
        b2.connect("clicked", lambda _b: self._confirm("Restaurar o padrão do Ubuntu?", "Isso ignora o que você tinha antes e usa os valores originais do sistema.", "Restaurar padrão", lambda: run_restore("reset")))
        r2.add_suffix(b2)
        g.add(r1)
        g.add(r2)
        page.add(g)
        return page

    def _page_doctor(self):
        page = Adw.PreferencesPage(title="Diagnóstico", icon_name="emblem-system-symbolic")
        g = Adw.PreferencesGroup(title="Dependências", description=f"Nebulix {__version__}")
        for lvl, msg, fix in doctor.check():
            r = Adw.ActionRow(title=msg, subtitle=fix, subtitle_selectable=True)
            r.add_prefix(Gtk.Image.new_from_icon_name({"ok": "emblem-ok-symbolic", "warn": "dialog-warning-symbolic", "info": "dialog-information-symbolic"}[lvl]))
            if fix:
                cp = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Copiar comando")
                cp.add_css_class("flat")
                cp.connect("clicked", lambda _b, f=fix: self.get_clipboard().set(f))
                r.add_suffix(cp)
            g.add(r)
        page.add(g)
        return page


def run():
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: (a.props.active_window or SettingsWindow(a)).present())
    return app.run(None)
