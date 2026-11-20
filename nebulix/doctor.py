# SPDX-License-Identifier: GPL-3.0-or-later
"""Environment checks: returns [(level, message, fix_command)] with level in ok|warn|info."""
import shutil
import subprocess

from . import config, icons, vscode
from .apply import TESTED_GNOME, UT, gnome_major


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
        if not any("blur-my-shell" in e for e in lst):
            out.append(("info", "opcional: desfoque do fundo da dock/barra (Blur my Shell)", "gnome-extensions-app → Blur my Shell"))
    try:
        theme = config.load()["theme"]
    except Exception:  # broken config.toml: keep the checks that do not depend on it
        theme = "nebulix"
    out.append(("ok", "ícones WhiteSur instalados", "") if icons.has_theme(icons.base_name(theme))
               else ("warn", "ícones estilo macOS (WhiteSur) não instalados", "nebulix icons install"))
    if not icons.has_theme(icons.fallback_name(theme)):
        out.append(("info", f"{icons.fallback_name(theme)} ausente (fallback de ícones)", "sudo apt install papirus-icon-theme"))
    fonts = _run("fc-list") if shutil.which("fc-list") else ""
    if theme.startswith("macos") and "inter" not in fonts.lower():
        out.append(("info", "fonte Inter ausente (usada na interface dos temas macOS)", "sudo apt install fonts-inter"))
    if "JetBrainsMono" not in fonts.replace(" ", ""):
        out.append(("info", "fonte JetBrains Mono Nerd Font ausente", "https://www.nerdfonts.com/font-downloads (JetBrainsMono)"))
    eds = [f.parent.parent.name for f, _ in vscode.installed_editors()]
    if eds:
        out.append(("ok", f"editor encontrado: {', '.join(eds)}", ""))
    else:
        out.append(("info", "VS Code não encontrado (o tema do editor não será ativado)", "https://code.visualstudio.com"))
    for tool, hint in (("starship", "https://starship.rs"), ("fastfetch", "sudo apt install fastfetch")):
        out.append(("ok", f"{tool} instalado", "") if shutil.which(tool) else ("info", f"{tool} não instalado", hint))
    return out
