# SPDX-License-Identifier: GPL-3.0-or-later
"""Environment checks: returns [(level, message, fix_command)] with level in ok|warn|info."""
import shutil
import subprocess

from . import config, icons, vscode
from .apply import TESTED_GNOME, UBUNTU_DOCK, UT, ZOOM, gnome_major, terminal_font


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
    try:
        icfg = config.load()
        theme = icfg["theme"]
    except Exception:  # broken config.toml: keep the checks that do not depend on it
        icfg, theme = None, "nebulix"
    for sid, entry in icons.SETS.items():
        out.append(("ok", f"ícones {entry['label']} instalados", "") if icons.installed(sid)
                   else ("warn" if sid == "whitesur" else "info", f"ícones {entry['label']} não instalados (~{entry['size_mb']} MB)",
                         f"nebulix icons install {sid}"))
    if icfg and icfg["icons"] in icons.SETS and icons.installed(icfg["icons"]):
        want = icons.base_name(theme, icfg["icons"], icfg["accent"])
        if not icons.has_theme(want):
            out.append(("warn", f"a cor de ícones do destaque falta ({want}); usando {icons.current_base(icfg['icons'], theme, icfg['accent'])}",
                        f"nebulix icons install {icfg['icons']}"))
    if not icons.has_theme(icons.fallback_name(theme)):
        out.append(("info", f"{icons.fallback_name(theme)} ausente (fallback de ícones)", "sudo apt install papirus-icon-theme"))
    fonts = _run("fc-list") if shutil.which("fc-list") else ""
    if theme.startswith("macos") and "inter" not in fonts.lower():
        out.append(("info", "fonte Inter ausente (usada na interface dos temas macOS)", "sudo apt install fonts-inter"))
    try:
        tcfg = config.load()
    except Exception:
        tcfg = config.validate({})
    fam = terminal_font(tcfg)
    if fam:
        out.append(("ok", f"fonte do terminal: {fam}", ""))
    elif tcfg["terminal_font"] == "auto":
        out.append(("info", "fonte JetBrains Mono ausente (o terminal usa a fonte monoespaçada do sistema)", "sudo apt install fonts-jetbrains-mono"))
    if "nerd" not in fonts.lower():
        out.append(("info", "opcional: Nerd Font para os ícones do prompt Starship", "https://www.nerdfonts.com/font-downloads (JetBrainsMono)"))
    if not any(shutil.which(x) for x in ("ptyxis", "gnome-terminal")):
        out.append(("info", "Ptyxis e GNOME Terminal não encontrados (o tema do terminal não terá efeito)", "sudo apt install ptyxis"))
    eds = [f.parent.parent.name for f, _ in vscode.installed_editors()]
    if eds:
        out.append(("ok", f"editor encontrado: {', '.join(eds)}", ""))
    else:
        out.append(("info", "VS Code não encontrado (o tema do editor não será ativado)", "https://code.visualstudio.com"))
    for tool, hint in (("starship", "https://starship.rs"), ("fastfetch", "sudo apt install fastfetch")):
        out.append(("ok", f"{tool} instalado", "") if shutil.which(tool) else ("info", f"{tool} não instalado", hint))
    return out
