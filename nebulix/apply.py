# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the theme for a config and install it for the current user (reversible via restore.py)."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from . import __version__, config, gen, icons, paths, palette, render, themes, vscode, wallpapers
from .state import State, gs, lock, set_extension_enabled

UT = "user-theme@gnome-shell-extensions.gcampax.github.com"
UBUNTU_DOCK = "ubuntu-dock@ubuntu.com"
ZOOM = "nebulix-dock-zoom@nebulix.github.io"
DOCK = "org.gnome.shell.extensions.dash-to-dock"
IFACE = "org.gnome.desktop.interface"
TESTED_GNOME = ("50", "51")
TOUCHED_KEYS = [
    (IFACE, "color-scheme"), (IFACE, "accent-color"), (IFACE, "gtk-theme"), (IFACE, "icon-theme"), (IFACE, "font-name"),
    ("org.gnome.desktop.background", "picture-uri"), ("org.gnome.desktop.background", "picture-uri-dark"),
    ("org.gnome.desktop.screensaver", "picture-uri"), ("org.gnome.shell.extensions.user-theme", "name"),
    ("org.gnome.desktop.wm.preferences", "button-layout"),
] + [(DOCK, k) for k in ("dock-position", "extend-height", "dash-max-icon-size", "transparency-mode", "background-opacity",
                         "apply-custom-theme", "show-apps-at-top", "running-indicator-style",
                         "custom-theme-customize-running-dots", "custom-theme-running-dots-color", "click-action")]
PTYXIS = "org.gnome.Ptyxis"
GNT_LIST = "org.gnome.Terminal.ProfilesList"
PTYXIS_KEYS = ("profile-uuids", "default-profile-uuid", "cursor-shape", "font-name", "use-system-font", "disable-padding",
               "default-columns", "default-rows", "interface-style")
TOUCHED_KEYS += [(PTYXIS, k) for k in PTYXIS_KEYS] + [(GNT_LIST, "default")]
THEMES_DIRS = ("Nebulix-Dark", "Nebulix-Light")  # one directory per colour scheme


def q(s):
    return "'" + s + "'"


def render_all(cfg, out: Path, log=print):
    """Render templates/ + generated formats into `out`; returns tokens."""
    P, t = palette.tokens(cfg)
    base = paths.data_dir() / "templates"
    for f in sorted(base.rglob("*")):
        if not f.is_file():
            continue
        dest = out / f.relative_to(base)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_text(render.render(f.read_text(), t, cfg, str(f)))
        except UnicodeDecodeError:
            shutil.copy2(f, dest)
    others = [(i, *palette.tokens(dict(cfg, theme=i, accent="auto", variant="dark" if i != cfg["theme"] else cfg["variant"])))
              for i in config.CHOICES["theme"] if i != cfg["theme"]]
    gen.generate(P, t, out, cfg["theme"], others, dict(cfg, terminal_font_family=terminal_font(cfg)))
    return t


STOCK_IMPORT = re.compile(r'@import url\("resource:///org/gnome/shell/theme/gnome-shell-(dark|light)\.css"\);')
SHELL_GRESOURCE = "/usr/share/gnome-shell/gnome-shell-theme.gresource"


def inline_stock_shell_css(text):
    """Prepend the stock Shell stylesheet (dark or light), extracted locally from the installed gnome-shell.
    This keeps the theme working even if the Shell does not resolve @import of resources; nothing is redistributed."""
    m = STOCK_IMPORT.search(text)
    if m and shutil.which("gresource"):
        r = subprocess.run(["gresource", "extract", SHELL_GRESOURCE, f"/org/gnome/shell/theme/gnome-shell-{m.group(1)}.css"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            head = f"/* stock GNOME Shell {m.group(1)} stylesheet, extracted from your gnome-shell install (GPL-2.0-or-later) */\n"
            return text[:m.start()] + head + r.stdout + text[m.end():]
    return text


def _put_file(st: State, src: Path, dest: Path):
    st.log(f"→ {dest}")
    if st.dry:
        return
    st._backup(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    st.note(str(dest))


def _forget(st: State, pred, log=print):
    for e in list(st.manifest):
        if e.startswith("/") and pred(e):
            if not st.dry:
                shutil.rmtree(e, ignore_errors=True) if Path(e).is_dir() else Path(e).unlink(missing_ok=True)
            st.manifest.remove(e)


def gnome_major():
    if not shutil.which("gnome-shell"):
        return None
    m = re.search(r"(\d+)", subprocess.run(["gnome-shell", "--version"], capture_output=True, text=True).stdout)
    return m.group(1) if m else None


def apply(*a, **kw):
    with lock():
        return _apply(*a, **kw)


def _apply(cfg=None, dry=False, log=print, install_icons=False, only=None):
    cfg = config.validate(cfg or config.load())
    comps = set(only or cfg["components"])
    st = State(dry=dry, log=log)
    maj = gnome_major()
    if maj and maj not in TESTED_GNOME:
        log(f"! GNOME Shell {maj} não foi testado (testados: {', '.join(TESTED_GNOME)})")
    stage = Path(tempfile.mkdtemp(prefix="nebulix-"))
    try:
        t = render_all(cfg, stage, log)
        home, conf, data = paths.home(), paths.conf_home(), paths.data_home()
        acc = t["purple"]
        THEME = t["theme-name"]
        if "gtk" in comps or "shell" in comps:
            # switching between a dark and a light theme leaves the other directory behind: forget it
            _forget(st, lambda e: any(e.startswith(str(data / "themes" / d) + "/") for d in THEMES_DIRS if d != THEME))
            for d in THEMES_DIRS:
                if d != THEME and not st.dry:
                    try:
                        (data / "themes" / d).rmdir()  # only when empty
                    except OSError:
                        pass
            theme = data / "themes" / THEME
            st.put_text((stage / "index.theme").read_text(), theme / "index.theme")
        if "gtk" in comps:
            st.put_tree(stage / "gtk-3.0", data / "themes" / THEME / "gtk-3.0")
            st.put_tree(stage / "gtk-4.0", data / "themes" / THEME / "gtk-4.0")
            st.put_text((stage / "gtk-4.0/colors.css").read_text(), conf / "gtk-4.0/nebulix-colors.css")
            st.put_text((stage / "gtk-4.0/tweaks.css").read_text(), conf / "gtk-4.0/nebulix-tweaks.css")
            _gtk4_block(st, conf / "gtk-4.0/gtk.css")
            st.gs_set(IFACE, "color-scheme", "'prefer-dark'" if t["scheme"] == "dark" else "'prefer-light'")
            st.gs_set(IFACE, "accent-color", q(config.gnome_accent(cfg)))
            st.gs_set(IFACE, "gtk-theme", q(THEME))
            if shutil.which("flatpak") and not dry and "flatpak" not in st.manifest:
                r = subprocess.run(["flatpak", "override", "--user", "--filesystem=xdg-config/gtk-4.0:ro",
                                    "--filesystem=xdg-config/gtk-3.0:ro", "--filesystem=xdg-data/themes:ro"], capture_output=True)
                if r.returncode == 0:
                    st.note("flatpak")
            wm = "'close,minimize,maximize:appmenu'" if cfg["window_buttons"] == "mac" else "'appmenu:minimize,maximize,close'"
            st.gs_set("org.gnome.desktop.wm.preferences", "button-layout", wm)
            _font(st, cfg)
        if "shell" in comps:
            css = stage / "gnome-shell/gnome-shell.css"
            css.write_text(inline_stock_shell_css(css.read_text()))
            st.put_tree(stage / "gnome-shell", data / "themes" / THEME / "gnome-shell")
            _shell_enable(st, dry, log, THEME)
            _dock(st, cfg, acc)
            _dock_zoom(st, cfg, dry, log)
        if "terminal" in comps:
            _ptyxis(st, cfg, stage, dry, log)
            _gnome_terminal(st, stage, dry, log)
        if "starship" in comps:
            st.put_text((stage / "starship/starship.toml").read_text(), conf / "starship.toml")
        if "fastfetch" in comps:
            st.put_text((stage / "fastfetch/config.jsonc").read_text(), conf / "fastfetch/config.jsonc")
        if "btop" in comps:
            st.put_text((stage / "btop/nebulix.theme").read_text(), conf / "btop/themes/nebulix.theme")
        if "nvim" in comps:
            st.put_text((stage / "nvim/colors/nebulix.lua").read_text(), conf / "nvim/colors/nebulix.lua")
        if "vscode" in comps:
            new = home / ".vscode/extensions" / f"nebulix.nebulix-theme-{__version__}"
            _forget(st, lambda e: "/extensions/nebulix.nebulix-theme-" in e and not e.endswith(f"nebulix.nebulix-theme-{__version__}"))
            st.put_tree(stage / "vscode/nebulix-theme", new)
            vscode.register(st, home / ".vscode", new.name, __version__)
            for _f, ext in vscode.installed_editors():
                if ext != home / ".vscode":  # Insiders / VSCodium keep extensions elsewhere
                    st.put_tree(stage / "vscode/nebulix-theme", ext / "extensions" / new.name)
                    vscode.register(st, ext, new.name, __version__)
            _vscode_setting(st, cfg)
        if "wallpaper" in comps:
            _wallpaper(st, cfg, t, stage, dry, log)
        if "icons" in comps:
            _icons(st, cfg, t, stage, dry, install_icons, log)
        st.save()
        _report_missing(st, log, dry)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    log("ok" if not dry else "dry-run: nada foi alterado.")
    return st


def _report_missing(st, log, dry=False):
    if not st.missing:
        return
    log("")
    log("┌─ Requisitos faltando (o resto " + ("seria aplicado" if dry else "foi aplicado") + ") ─────────")
    for msg, fix in st.missing:
        log(f"│ ! {msg}")
        log(f"│   → {fix}")
    log("└───────────────────────────────────────────────────────────")


def _gtk4_block(st, g4: Path):
    st.log(f"→ bloco gerenciado em {g4}")
    if st.dry:
        return
    if g4.exists() and "NEBULIX-BEGIN" not in g4.read_text():
        st._backup(g4)
    old = g4.read_text() if g4.exists() else ""
    old = re.sub(r"/\* NEBULIX-BEGIN \*/.*?/\* NEBULIX-END \*/\n?", "", old, flags=re.S)
    g4.parent.mkdir(parents=True, exist_ok=True)
    g4.write_text(old + '/* NEBULIX-BEGIN */\n@import url("nebulix-colors.css");\n@import url("nebulix-tweaks.css");\n/* NEBULIX-END */\n')
    st.note(f"gtkblock:{g4}")


def _shell_enable(st, dry, log, theme_name):
    if not shutil.which("gnome-extensions"):
        return
    lst = subprocess.run(["gnome-extensions", "list"], capture_output=True, text=True).stdout.split()
    if UT not in lst:
        st.missing.append(("extensão User Themes ausente (necessária para o tema do Shell)", "sudo apt install gnome-shell-extensions"))
        return
    if dry:
        return
    en = subprocess.run(["gnome-extensions", "list", "--enabled"], capture_output=True, text=True).stdout.split()
    if UT not in en:
        subprocess.run(["gnome-extensions", "enable", UT], capture_output=True)
        st.note(f"ext:{UT}")
    # toggling the name makes the running Shell reload the stylesheet without a logout
    subprocess.run(["gsettings", "set", "org.gnome.shell.extensions.user-theme", "name", "''"], capture_output=True)
    st.gs_set("org.gnome.shell.extensions.user-theme", "name", q(theme_name))


DOCK_KEYS = [k for s, k in TOUCHED_KEYS if s == DOCK]


def _dock(st, cfg, acc):
    if cfg["dock"] != "macos":
        for k in DOCK_KEYS:
            st.gs_release(DOCK, k)
        return
    pos = q(cfg["dock_position"].upper())
    for k, v in (("dock-position", pos), ("extend-height", "false"), ("dash-max-icon-size", str(cfg["dock_icon_size"])),
                 ("transparency-mode", "'FIXED'"), ("background-opacity", f"{cfg['dock_opacity'] / 100:.2f}"),
                 ("apply-custom-theme", "false"), ("show-apps-at-top", "false"), ("running-indicator-style", "'DOTS'"),
                 ("custom-theme-customize-running-dots", "true"), ("custom-theme-running-dots-color", q(acc)),
                 ("click-action", "'minimize-or-previews'")):
        st.gs_set(DOCK, k, v)


def _dock_zoom(st, cfg, dry, log):
    """Optional macOS-style magnification: our own extension (extensions/nebulix-dock-zoom@...) running on top of the
    Ubuntu Dock. Off by default; turning it off disables the extension and removes its files."""
    ext_dir, conf = paths.ext_home() / ZOOM, paths.conf_home() / "nebulix/dock-zoom.json"
    if cfg["dock_zoom"] != "on":
        if f"ext:{ZOOM}" in st.manifest or str(ext_dir) in st.manifest:
            log("zoom da dock desligado")
            set_extension_enabled(ZOOM, False, dry)
            if not dry:
                _forget(st, lambda e: e in (str(ext_dir), str(conf)))
                if f"ext:{ZOOM}" in st.manifest:
                    st.manifest.remove(f"ext:{ZOOM}")
        return
    if shutil.which("gnome-extensions"):
        if UBUNTU_DOCK not in subprocess.run(["gnome-extensions", "list"], capture_output=True, text=True).stdout.split():
            st.missing.append(("zoom da dock precisa do Ubuntu Dock (ubuntu-dock@ubuntu.com), que não está instalado",
                               "sudo apt install gnome-shell-ubuntu-extensions"))
    st.put_tree(paths.data_dir() / "extensions" / ZOOM, ext_dir)
    st.put_text(json.dumps({"factor": cfg["dock_zoom_factor"] / 100}) + "\n", conf)
    if dry:
        return
    known = shutil.which("gnome-extensions") and ZOOM in subprocess.run(
        ["gnome-extensions", "list"], capture_output=True, text=True).stdout.split()
    set_extension_enabled(ZOOM, True)
    st.note(f"ext:{ZOOM}")
    if shutil.which("gnome-extensions") and not known:
        st.missing.append(("zoom da dock instalado, mas o GNOME só enxerga extensões novas ao iniciar a sessão",
                           "saia da sessão e entre de novo (o zoom liga sozinho)"))


def terminal_font(cfg):
    """Family for the terminal: JetBrainsMono Nerd Font, then JetBrains Mono; None keeps the system monospace font."""
    if cfg["terminal_font"] == "keep":
        return None
    return next((f for f in ("JetBrainsMono Nerd Font", "JetBrains Mono") if has_font(f)), None)


def _ptyxis(st, cfg, stage, dry, log):
    """Own 'Nebulix' profile (made the default) with the palette, opacity and line height; cursor, font, padding and
    window size are global settings in Ptyxis. Undo/reset remove the profile and put the globals back."""
    st.put_text((stage / "terminal/nebulix.palette").read_text(), paths.data_home() / "org.gnome.Ptyxis/palettes/nebulix.palette")
    if not shutil.which("gsettings") or gs("get", PTYXIS, "profile-uuids") is None:
        return  # Ptyxis not installed: only the palette file above
    ent = next((e for e in st.manifest if e.startswith("ptyxis:")), None)
    u = ent[7:] if ent else str(uuid.uuid4())
    lst = re.findall(r"'([^']+)'", gs("get", PTYXIS, "profile-uuids") or "")
    if u not in lst:
        st.gs_set(PTYXIS, "profile-uuids", "[" + ", ".join(q(x) for x in lst + [u]) + "]")
    if not dry:
        st.note(f"ptyxis:{u}")
    prof = f"{PTYXIS}.Profile:/org/gnome/Ptyxis/Profiles/{u}/"
    for k, v in (("label", q("Nebulix")), ("palette", q("nebulix")), ("opacity", f"{cfg['terminal_opacity'] / 100:.2f}"),
                 ("cell-height-scale", f"{cfg['terminal_line_height'] / 100:g}")):
        st.gs_set(prof, k, v)
    st.gs_set(PTYXIS, "default-profile-uuid", q(u))
    st.gs_set(PTYXIS, "interface-style", "'system'")  # the palette's [Dark]/[Light] section follows the system scheme
    st.gs_set(PTYXIS, "cursor-shape", q(cfg["terminal_cursor"]))
    st.gs_set(PTYXIS, "disable-padding", "true" if cfg["terminal_padding"] == "off" else "false")
    st.gs_set(PTYXIS, "default-columns", str(cfg["terminal_columns"]))
    st.gs_set(PTYXIS, "default-rows", str(cfg["terminal_rows"]))
    fam = terminal_font(cfg)
    if fam:
        st.gs_set(PTYXIS, "use-system-font", "false")
        st.gs_set(PTYXIS, "font-name", q(f"{fam} {cfg['terminal_font_size']}"))
    else:
        st.gs_release(PTYXIS, "use-system-font")
        st.gs_release(PTYXIS, "font-name")
    if not dry:
        log("perfil 'Nebulix' definido como padrão no Ptyxis")


def _gnome_terminal(st, stage, dry, log):
    """'Nebulix' profile of GNOME Terminal: created once, rewritten on every apply (so theme changes show up)."""
    if dry or not shutil.which("dconf"):
        return
    base = "/org/gnome/terminal/legacy/profiles:/"
    ent = next((e for e in st.manifest if e.startswith("gnt:")), None)
    if ent:
        u = ent[4:].split(":", 1)[0]
    else:
        # the key is unset until GNOME Terminal's preferences are touched: the schema default still lists the stock profile
        raw = subprocess.run(["dconf", "read", base + "list"], capture_output=True, text=True).stdout.strip()
        lst = re.findall(r"'([^']+)'", raw or gs("get", GNT_LIST, "list") or "")
        if not lst:
            return  # GNOME Terminal not installed
        u = str(uuid.uuid4())
        subprocess.run(["dconf", "write", base + "list", "[" + ", ".join(q(x) for x in lst + [u]) + "]"])
        st.note(f"gnt:{u}:{raw}")  # empty `raw`: the key was unset, undo resets it
    subprocess.run(["dconf", "load", f"{base}:{u}/"], input=(stage / "terminal/nebulix-gnome-terminal.dconf").read_text(), text=True)
    st.gs_set(GNT_LIST, "default", q(u))
    log("perfil 'Nebulix' definido como padrão no GNOME Terminal")


def _wallpaper(st, cfg, t, stage, dry, log):
    d = cfg["wallpaper"]
    wdir = paths.data_home() / "backgrounds" / "nebulix"
    if d == "none":
        for k in (("org.gnome.desktop.background", "picture-uri"), ("org.gnome.desktop.background", "picture-uri-dark"),
                  ("org.gnome.desktop.screensaver", "picture-uri")):
            st.gs_release(*k)
        return
    if d.startswith("gen-"):  # generated in code, follows the accent
        w, h = wallpapers.SIZES[cfg["wallpaper_size"]]
        wcfg = dict(cfg, theme=themes.get(cfg["theme"])["wallpaper_from"], accent=t["purple"])
        wt = palette.tokens(wcfg)[1]
        tag = hashlib.sha1(json.dumps([wt["purple"], wcfg["theme"], cfg["variant"], d, w, h]).encode()).hexdigest()[:8]
        name = f"nebulix-{d}-{tag}.png"
        dest = wdir / name
        if not dest.exists() and not dry:
            log(f"→ renderizando wallpaper {d} {w}x{h}")
            wallpapers.rasterize(wallpapers.svg(d[4:], w, h, wt), stage / name)
            src = stage / name
        else:
            src = dest if dest.exists() else None
    else:  # the artwork shipped in images/wallpapers
        name = f"nebulix-{d}.png"
        dest, src = wdir / name, paths.data_dir() / "images" / "wallpapers" / name
    _forget(st, lambda e: e.startswith(str(wdir) + "/nebulix-") and e != str(dest))
    if not dry and src and src != dest:
        _put_file(st, src, dest)
    elif dry:
        log(f"→ {dest}")
    uri = q(f"file://{dest}")
    st.gs_set("org.gnome.desktop.background", "picture-uri", uri)
    st.gs_set("org.gnome.desktop.background", "picture-uri-dark", uri)
    st.gs_set("org.gnome.desktop.screensaver", "picture-uri", uri)


def _vscode_setting(st, cfg):
    v = cfg["vscode_theme"]
    if v == "keep":
        vscode.release(st)
    else:
        vscode.apply_theme(st, gen.vscode_label(cfg["theme"] if v == "follow" else v))


def has_font(family):
    fc = shutil.which("fc-list")
    return bool(fc) and family.lower() in subprocess.run([fc], capture_output=True, text=True).stdout.lower()


def _font(st, cfg):
    """Interface font of the theme (Inter for the macOS themes), only when installed and not set to 'keep'."""
    font = themes.get(cfg["theme"]).get("font")
    if cfg["font"] == "keep" or not font:
        st.gs_release(IFACE, "font-name")
        return
    if not has_font(font.rsplit(" ", 1)[0]):
        st.gs_release(IFACE, "font-name")
        st.missing.append((f"fonte {font.rsplit(' ', 1)[0]} ausente (usada pelo tema {themes.get(cfg['theme'])['label']})", "sudo apt install fonts-inter"))
        return
    st.gs_set(IFACE, "font-name", q(font))


def _icons(st, cfg, t, stage, dry, install, log):
    mode, theme = cfg["icons"], cfg["theme"]
    fb = icons.fallback_name(theme)
    if mode == "keep":
        st.gs_release(IFACE, "icon-theme")
        return
    if mode == "papirus":
        if icons.has_theme(fb):
            st.gs_set(IFACE, "icon-theme", q(fb))
        else:
            st.missing.append((f"{fb} ausente", "sudo apt install papirus-icon-theme"))
        return
    entry, accent = icons.SETS[mode], cfg["accent"]
    wanted = icons.base_name(theme, mode, accent)
    if not icons.has_theme(wanted) and not dry and (install or icons.cached_tarball(mode)):
        try:  # a colour already in the cache installs without the network; the download needs the user's ask
            icons.ensure_set(mode, log, theme, accent)
        except Exception as e:  # network or checksum failure: fall back to what is installed, else Papirus
            log(f"! {entry['label']} indisponível ({e}); usando o que há instalado")
    base = icons.current_base(mode, theme, accent)
    if not icons.has_theme(wanted):
        cmd = f"nebulix icons install {mode}   (baixa ~{entry['size_mb']} MB, {entry['license']})"
        if icons.has_theme(base):
            st.missing.append((f"ícones {entry['label']} na cor do destaque ({wanted}) não instalados; usando {base}", cmd))
        else:
            st.missing.append((f"ícones {entry['label']} não instalados; usando Papirus por enquanto", cmd))
    if not icons.uses_overlay(theme):  # macOS themes: plain WhiteSur
        if icons.has_theme(base):
            st.gs_set(IFACE, "icon-theme", q(base))
        elif icons.has_theme(fb):
            st.gs_set(IFACE, "icon-theme", q(fb))
        return
    root = icons.write_overlay(t, stage / "icons" / icons.THEME_NAME, theme, mode, accent) if not dry else None
    if root:
        st.put_tree(root, paths.data_home() / "icons" / icons.THEME_NAME)
    st.gs_set(IFACE, "icon-theme", q(icons.THEME_NAME))
