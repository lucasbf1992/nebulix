# SPDX-License-Identifier: GPL-3.0-or-later
"""Nebulix settings app (GTK4 + libadwaita). Changes are saved and applied live (debounced)."""
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import __version__, config, doctor, gen, icons, palette, paths, themes  # noqa: E402
from .apply import apply, terminal_font  # noqa: E402
from .restore import restore  # noqa: E402

APP_ID = "io.github.nebulix.Settings"
LABELS = {
    "theme": {tid: themes.get(tid)["label"] for tid in config.CHOICES["theme"]},
    "variant": {"dark": "Dark", "darker": "Darker (preto OLED)"},
    "window_buttons": {"gnome": "GNOME (à direita)", "mac": "Semáforo macOS (à esquerda)"},
    "topbar": {"floating": "Flutuante (pílulas)", "solid": "Sólida", "translucent": "Translúcida (largura total)"},
    "dock": {"macos": "Estilo macOS (flutuante, centralizada)", "ubuntu": "Não alterar (padrão do Ubuntu)"},
    "dock_position": {"bottom": "Embaixo", "left": "Esquerda", "right": "Direita"},
    "icons": {"whitesur": "Estilo macOS (WhiteSur, variante do tema)", "mactahoe": "MacTahoe (estilo macOS recente)", "mcmojave": "McMojave-circle (ícones redondos)", "papirus": "Papirus (claro ou escuro, conforme o tema)", "keep": "Não alterar"},
    "icon_folders": {"auto": "Automático (conforme o tema)", "nebulix": "Pastas Nebulix", "conjunto": "Pastas do conjunto"},
    "vscode_theme": {"keep": "Não alterar", "follow": "Seguir o tema do Nebulix", **{t: gen.vscode_label(t) for t in config.CHOICES["theme"]}},
    "font": {"auto": "Do tema (Inter nos temas macOS, se instalada)", "keep": "Não alterar"},
    "terminal_cursor": {"block": "Bloco", "ibeam": "Barra", "underline": "Sublinhado"},
    "terminal_font": {"auto": "Auto (JetBrains Mono)", "keep": "Não alterar"},
    "terminal_padding": {"on": "Com margem interna", "off": "Sem margem"},
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
        self._running, self._pending, self._qlock = False, None, threading.Lock()
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.rows = {}  # config key -> (row, options) so a theme change can refresh every control
        self._syncing = False
        self.status_row = Adw.ActionRow()
        self.apply_btn = Gtk.Button(label="Aplicar agora", valign=Gtk.Align.CENTER)
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", lambda _b: self._apply_now())
        self.status_row.add_suffix(self.apply_btn)
        self._refresh_status()
        self.add(self._page_look())
        self.add(self._page_terminal())
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
        if key == "theme":  # a theme brings a whole package of values
            try:
                self.cfg = config.apply_theme(self.cfg, value)
            except ValueError as e:
                self.add_toast(Adw.Toast(title=str(e)))
                return
            self._sync()
        else:
            self.cfg[key] = value
            try:
                config.validate(self.cfg)
            except ValueError as e:
                self.add_toast(Adw.Toast(title=str(e)))
                return
            if key == "accent":
                self._mark_accent()
        self._update_preview()
        self._update_icons_view()
        config.save(self.cfg)
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(500, self._apply_now)

    def _apply_now(self, only=None):
        """Applies never overlap: while one runs, only the most recent request is kept and runs right after."""
        self._timer = None
        with self._qlock:
            prev = self._pending
            if prev and (prev[1] is None or only is None):
                only = None  # a full apply that is still queued must not shrink to a partial one
            elif prev:
                only = sorted({*prev[1], *only})
            self._pending = (dict(self.cfg), only)
            if self._running:
                return False
            self._running = True

        def work():
            while True:
                with self._qlock:
                    cfg, only_ = self._pending
                    self._pending = None
                err = None
                try:
                    apply(cfg, only=only_, log=lambda *_: None)
                except Exception as e:  # surface any failure to the user
                    err = f"Erro ao aplicar: {e}"
                with self._qlock:
                    done = self._pending is None
                    if done:
                        self._running = False
                if done:
                    GLib.idle_add(self.toast, err or "Aplicado", bool(err))
                    GLib.idle_add(self._refresh_status)
                    return
        threading.Thread(target=work, daemon=True).start()
        return False

    def combo(self, group, title, key, subtitle=None):
        opts = list(LABELS[key])
        row = Adw.ComboRow(title=title, subtitle=subtitle or "", model=Gtk.StringList.new([LABELS[key][o] for o in opts]))
        row.set_selected(opts.index(self.cfg[key]))
        row.connect("notify::selected", lambda r, _p: not self._syncing and self.set(key, opts[r.get_selected()]))
        group.add(row)
        self.rows[key] = (row, opts)
        return row

    def spin(self, group, title, key, lo, hi, subtitle=""):
        row = Adw.SpinRow.new_with_range(lo, hi, 1)
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.set_value(self.cfg[key])
        row.connect("notify::value", lambda r, _p: not self._syncing and self.set(key, int(r.get_value())))
        group.add(row)
        self.rows[key] = (row, None)

    def _sync(self):
        """Refresh every control after the config changed under it (theme package)."""
        self._syncing = True
        try:
            for key, (row, opts) in self.rows.items():
                if opts is None:
                    row.set_value(self.cfg[key])
                else:
                    row.set_selected(opts.index(self.cfg[key]))
            self._fill_accents()
            self._update_icons_view()
            if "variant" in self.rows:
                self.rows["variant"][0].set_visible(themes.get(self.cfg["theme"])["scheme"] == "dark")
        finally:
            self._syncing = False

    def _fill_accents(self):
        th = self.cfg["theme"]
        box = self.accent_box
        while (c := box.get_first_child()):
            box.remove(c)
        self._css.load_from_string("".join(
            f".nbx-{n} {{ background: {a['hex']}; border-radius: 99px; min-width: 26px; min-height: 26px; padding: 0; }}"
            f".nbx-{n}:checked {{ box-shadow: 0 0 0 3px alpha(currentColor, .8); }}" for n, a in themes.get(th)["accents"].items()))
        self._swatches, first = {}, None
        for name in themes.accent_names(th):
            b = Gtk.ToggleButton(tooltip_text=name)
            b.add_css_class(f"nbx-{name}")
            if first:
                b.set_group(first)
            first = first or b
            b.connect("toggled", lambda w, n=name: w.get_active() and not self._syncing and self.set("accent", n))
            box.append(b)
            self._swatches[name] = b
        self._mark_accent()

    def _mark_accent(self):
        was, self._syncing = self._syncing, True
        a = self.cfg["accent"]
        if a == "auto":
            a = themes.get(self.cfg["theme"])["default_accent"]
        for n, b in self._swatches.items():
            b.set_active(n == a)
        if hasattr(self, "hexrow"):
            self.hexrow.set_text(self.cfg["accent"] if self.cfg["accent"].startswith("#") else "")
        self._syncing = was

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
        gt = Adw.PreferencesGroup(title="Tema", description="Escolher um tema aplica um pacote (destaque, botões da janela, barra, cantos, ícones, dock). Depois cada item abaixo continua ajustável.")
        self.combo(gt, "Tema", "theme")
        page.add(gt)
        g = Adw.PreferencesGroup(title="Cores")
        row = Adw.ActionRow(title="Destaque", subtitle="Cor principal de seleção, botões e foco")
        self.accent_box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        row.add_suffix(self.accent_box)
        g.add(row)
        self.hexrow = Adw.EntryRow(title="Cor personalizada (#RRGGBB)")
        self.hexrow.set_show_apply_button(True)
        self.hexrow.connect("apply", lambda r: self.set("accent", r.get_text().strip()))
        g.add(self.hexrow)
        self._fill_accents()
        self.combo(g, "Variante", "variant", "Darker usa fundo preto puro (telas OLED); só nos temas escuros")
        self.rows["variant"][0].set_visible(themes.get(self.cfg["theme"])["scheme"] == "dark")
        page.add(g)
        g2 = Adw.PreferencesGroup(title="Janelas e barra")
        self.combo(g2, "Botões da janela", "window_buttons")
        self.combo(g2, "Barra superior", "topbar")
        self.spin(g2, "Cantos arredondados", "radius", 6, 20, "em pixels")
        self.combo(g2, "Fonte da interface", "font", "O Inter precisa estar instalado (sudo apt install fonts-inter)")
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

    def _page_terminal(self):
        page = Adw.PreferencesPage(title="Terminal", icon_name="utilities-terminal-symbolic")
        gp = Adw.PreferencesGroup(title="Prévia", description="Como o terminal fica com o tema escolhido (a transparência aparece sobre o fundo).")
        self._term_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._term_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        back = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        back.add_css_class("nbx-term-back")
        self._term_label = Gtk.Label(xalign=0, selectable=False)
        self._term_label.add_css_class("nbx-term")
        self._term_label.set_margin_start(24)
        self._term_label.set_margin_end(24)
        self._term_label.set_margin_top(20)
        self._term_label.set_margin_bottom(20)
        win = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_start=28, margin_end=28, margin_top=20, margin_bottom=20)
        win.add_css_class("nbx-term-win")
        win.append(self._term_label)
        back.append(win)
        gp.add(back)
        page.add(gp)
        g = Adw.PreferencesGroup(title="Visual", description="Vale para o Ptyxis e o GNOME Terminal. Cada tema traz o seu padrão de transparência e cursor.")
        self.spin(g, "Opacidade do fundo", "terminal_opacity", 70, 100, "em % (100 = opaco)")
        self.combo(g, "Cursor", "terminal_cursor")
        self.combo(g, "Fonte", "terminal_font", "Usa JetBrainsMono Nerd Font ou JetBrains Mono, o que estiver instalado (sudo apt install fonts-jetbrains-mono)")
        self.spin(g, "Tamanho da fonte", "terminal_font_size", 8, 20)
        page.add(g)
        g2 = Adw.PreferencesGroup(title="Espaçamento e janela")
        self.combo(g2, "Margem interna", "terminal_padding")
        self.spin(g2, "Altura da linha", "terminal_line_height", 100, 140, "em %")
        self.spin(g2, "Colunas iniciais", "terminal_columns", 80, 240)
        self.spin(g2, "Linhas iniciais", "terminal_rows", 24, 80)
        page.add(g2)
        self._update_preview()
        return page

    def _update_preview(self):
        if not hasattr(self, "_term_label"):
            return
        try:
            cfg = config.validate(self.cfg)
        except ValueError:
            return
        P, t = palette.tokens(cfg)
        r, g, b = palette.rgb(t["bg-0"])
        self._term_css.load_from_string(
            f".nbx-term-back {{ background: linear-gradient(135deg, {t['purple-dim']}, {t['bg-2']} 55%, {t['purple']}); border-radius: 12px; }}"
            f".nbx-term-win {{ background: rgba({r}, {g}, {b}, {cfg['terminal_opacity'] / 100:g}); border-radius: 10px; }}"
            f".nbx-term {{ font-family: 'JetBrains Mono', monospace; font-size: {cfg['terminal_font_size']}pt; color: {t['fg-0']}; }}")
        ansi = P["ansi"]["normal"] + P["ansi"]["bright"]
        cur = {"block": "█", "ibeam": "▏", "underline": "▁"}[cfg["terminal_cursor"]]
        sw = lambda cs: "".join(f'<span background="{c}">  </span>' for c in cs)  # noqa: E731
        esc = GLib.markup_escape_text
        fam = terminal_font(cfg) or "do sistema"
        self._term_label.set_markup(
            f'<span foreground="{t["accent-text"]}">~/nebulix</span> <span foreground="{t["green"]}">main</span>\n'
            f'<span foreground="{t["accent-text"]}">❯</span> nebulix theme {esc(cfg["theme"])}<span foreground="{t["purple"]}">{cur}</span>\n'
            f'{sw(ansi[:8])}\n{sw(ansi[8:])}\n'
            f'<span foreground="{t["fg-2"]}" size="small">fonte: {esc(fam)} {cfg["terminal_font_size"]} · opacidade {cfg["terminal_opacity"]}%</span>')

    PREVIEW_ICONS = ("folder", "utilities-terminal", "web-browser", "preferences-system", "system-file-manager", "user-trash", "user-home", "text-x-generic")

    def _page_icons(self):
        page = Adw.PreferencesPage(title="Ícones e fundo", icon_name="image-x-generic-symbolic")
        g = Adw.PreferencesGroup(title="Ícones")
        self.combo(g, "Conjunto", "icons", "Os conjuntos macOS são de terceiros (GPL-3.0): o Nebulix não os inclui e só baixa quando você pedir")
        self.combo(g, "Pastas", "icon_folders", "As pastas Nebulix (quadradas arredondadas) ou as do próprio conjunto; no automático, vale a escolha do tema")
        self.dl_row = Adw.ActionRow()
        self.dl_btn = Gtk.Button(valign=Gtk.Align.CENTER)
        self.dl_btn.add_css_class("suggested-action")
        self.dl_btn.connect("clicked", lambda _b: self._download_set())
        self.dl_row.add_suffix(self.dl_btn)
        g.add(self.dl_row)
        page.add(g)
        gp = Adw.PreferencesGroup(title="Prévia", description="Desenhada a partir dos arquivos do conjunto instalado.")
        self._icon_theme = Gtk.IconTheme()
        self._icon_flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8, min_children_per_line=4,
                                      homogeneous=True, column_spacing=6, row_spacing=6, margin_top=6, margin_bottom=6)
        self._icon_imgs = []
        for name in self.PREVIEW_ICONS:
            img = Gtk.Image(pixel_size=48, tooltip_text=name)
            self._icon_imgs.append(img)
            self._icon_flow.append(img)
        gp.add(self._icon_flow)
        self._icon_note = Gtk.Label(xalign=0, wrap=True, margin_top=6)
        self._icon_note.add_css_class("dim-label")
        gp.add(self._icon_note)
        page.add(gp)
        g2 = Adw.PreferencesGroup(title="Papel de parede")
        self.combo(g2, "Imagem", "wallpaper", "As versões \"gerada\" usam a cor de destaque escolhida")
        self.combo(g2, "Tamanho (só para gerados)", "wallpaper_size")
        page.add(g2)
        self._update_icons_view()
        return page

    def _icon_theme_name(self):
        """Folder of the chosen set that the preview draws from (None: nothing to draw, the set is left alone)."""
        mode, theme = self.cfg["icons"], self.cfg["theme"]
        if mode == "keep":
            return None
        if mode in icons.SETS:
            name = icons.current_base(mode, theme, self.cfg["accent"])
            if icons.has_theme(name):
                return name
        fb = icons.fallback_name(theme)
        return fb if icons.has_theme(fb) else None

    def _update_icons_view(self):
        if not hasattr(self, "dl_row"):
            return
        mode = self.cfg["icons"]
        name = self._icon_theme_name()
        if name:
            self._icon_theme.set_search_path([str(d) for d in icons.icon_dirs()])
            self._icon_theme.set_theme_name(name)
        for img, icon in zip(self._icon_imgs, self.PREVIEW_ICONS):
            if name:
                img.set_from_paintable(self._icon_theme.lookup_icon(icon, None, 48, self.get_scale_factor(), Gtk.TextDirection.NONE, 0))
            else:
                img.clear()
        self._icon_flow.set_visible(bool(name))
        if mode == "keep":
            self._icon_note.set_label("Os ícones do sistema ficam como estão.")
        elif mode == "papirus" and not name:
            self._icon_note.set_label("O Papirus não está instalado (sudo apt install papirus-icon-theme).")
        elif name:
            fallback = mode in icons.SETS and not name.startswith(icons.SETS[mode]["prefix"])
            self._icon_note.set_label(f"Tema de ícones: {name}" + (" (o conjunto escolhido ainda não está instalado)" if fallback else ""))
        else:
            self._icon_note.set_label("")
        missing = mode in icons.SETS and not icons.has_theme(icons.base_name(self.cfg["theme"], mode, self.cfg["accent"]))
        busy = getattr(self, "_dl_busy", False)
        self.dl_row.set_visible(missing or busy)
        if mode in icons.SETS and not busy:
            entry = icons.SETS[mode]
            self.dl_row.set_title(f"{entry['label']} não instalado na cor do destaque" if name and name.startswith(entry["prefix"])
                                  else f"{entry['label']} não instalado")
            self.dl_row.set_subtitle(f"Baixa de uma versão fixa do GitHub e confere o sha256 ({entry['license']}).")
            self.dl_btn.set_label(f"Baixar (~{entry['size_mb']} MB)")
            self.dl_btn.set_sensitive(True)

    def _download_set(self):
        mode, theme, accent = self.cfg["icons"], self.cfg["theme"], self.cfg["accent"]
        if mode not in icons.SETS or getattr(self, "_dl_busy", False):
            return
        self._dl_busy = True
        self.dl_btn.set_sensitive(False)
        self.dl_row.set_subtitle("Baixando…")
        cfg = dict(self.cfg)

        def done(err):
            self._dl_busy = False
            self._update_icons_view()
            if err:
                self.dl_row.set_visible(True)
                self.dl_row.set_subtitle(f"Falhou: {err}")
            self.toast(f"Falhou: {err}" if err else "Ícones instalados e aplicados", bool(err))
            return False

        def work():
            err = None
            try:
                icons.ensure_set(mode, lambda *_: None, theme, accent)
                apply(cfg, only=["icons"], log=lambda *_: None)
            except Exception as e:  # network, checksum or installer failure
                err = str(e)
            GLib.idle_add(done, err)
        threading.Thread(target=work, daemon=True).start()

    def _page_dev(self):
        page = Adw.PreferencesPage(title="Componentes", icon_name="preferences-other-symbolic")
        g = Adw.PreferencesGroup(title="O que o Nebulix aplica", description="Desligar um item não desfaz o que já foi aplicado; use Restaurar para isso.")
        for c in config.COMPONENTS:
            r = Adw.SwitchRow(title=COMP_LABELS[c], active=c in self.cfg["components"])

            def toggled(row, _p, c=c):
                comps = [x for x in self.cfg["components"] if x != c] + ([c] if row.get_active() else [])
                self.set("components", [x for x in config.COMPONENTS if x in comps])
            r.connect("notify::active", toggled)
            g.add(r)
        page.add(g)
        gv = Adw.PreferencesGroup(title="VS Code", description="Ativa o tema no editor (workbench.colorTheme em settings.json, só essa chave; o desfazer restaura o valor anterior). Requer o componente VS Code ligado.")
        self.combo(gv, "Tema do VS Code", "vscode_theme")
        page.add(gv)
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
