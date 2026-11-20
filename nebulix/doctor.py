# SPDX-License-Identifier: GPL-3.0-or-later
"""Environment checks: returns [(level, message, fix_command)] with level in ok|warn|info."""
import shutil
import subprocess

from . import config, icons
from .apply import TESTED_GNOME, UBUNTU_DOCK, UT, ZOOM, gnome_major


def _run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def check():
    out = []
    g = gnome_major()
    if g:
        out.append(("ok" if g in TESTED_GNOME else "warn", f"GNOME Shell {g}" + ("" if g in TESTED_GNOME else " (não testado)"), ""))
    else:
        out.append(("warn", "gnome-shell não encontrado", ""))
    if shutil.which("gnome-extensions"):
        lst = _run("gnome-extensions", "list").split()
        if UT not in lst:
            out.append(("warn", "extensão User Themes ausente (necessária para o tema do Shell)", "sudo apt install gnome-shell-extensions"))
        else:
            out.append(("ok", "extensão User Themes instalada", ""))
        try:
            zoom_on = config.load()["dock_zoom"] == "on"
        except Exception:
            zoom_on = False
        if zoom_on:
            if UBUNTU_DOCK not in lst:
                out.append(("warn", "zoom da dock ligado, mas o Ubuntu Dock não está instalado", "sudo apt install gnome-shell-ubuntu-extensions"))
            elif ZOOM not in lst:
                out.append(("warn", "zoom da dock ligado, mas a extensão nebulix-dock-zoom ainda não foi detectada pelo GNOME",
                            "rode `nebulix apply` e depois saia da sessão e entre de novo"))
            else:
                en = _run("gnome-extensions", "list", "--enabled").split()
                out.append(("ok", "zoom da dock ativo (nebulix-dock-zoom)", "") if ZOOM in en
                           else ("warn", "extensão nebulix-dock-zoom instalada, mas desativada", "nebulix apply"))
        if not any("blur-my-shell" in e for e in lst):
            out.append(("info", "opcional: desfoque do fundo da dock/barra (Blur my Shell)", "gnome-extensions-app → Blur my Shell"))
    out.append(("ok", "ícones WhiteSur instalados", "") if icons.has_theme(icons.BASE)
               else ("warn", "ícones estilo macOS (WhiteSur) não instalados", "nebulix icons install"))
    if not icons.has_theme("Papirus-Dark"):
        out.append(("info", "Papirus-Dark ausente (fallback de ícones)", "sudo apt install papirus-icon-theme"))
    fonts = _run("fc-list") if shutil.which("fc-list") else ""
    if "JetBrainsMono" not in fonts.replace(" ", ""):
        out.append(("info", "fonte JetBrains Mono Nerd Font ausente", "https://www.nerdfonts.com/font-downloads (JetBrainsMono)"))
    for tool, hint in (("starship", "https://starship.rs"), ("fastfetch", "sudo apt install fastfetch")):
        out.append(("ok", f"{tool} instalado", "") if shutil.which(tool) else ("info", f"{tool} não instalado", hint))
    return out
