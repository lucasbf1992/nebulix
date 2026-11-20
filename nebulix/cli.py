# SPDX-License-Identifier: GPL-3.0-or-later
"""nebulix command line."""
import argparse
import sys

from . import __version__, config, doctor, paths, themes
from .apply import apply
from .restore import restore

HELP = """nebulix {v} — temas para GNOME (Nebulix, macOS Dark, macOS Light, Nebulix Light)

  nebulix                      abre o app de personalização
  nebulix apply [--dry-run]    aplica a configuração atual   (alias: install)
  nebulix theme [NOME]         lista os temas ou aplica um (nebulix | macos-dark | macos-light | nebulix-light)
  nebulix config list|get K|set K=V ...   ver/alterar (aplica ao salvar, use --no-apply p/ não aplicar)
  nebulix status               mostra config e o que está instalado
  nebulix undo [--dry-run]     volta ao que era antes do Nebulix        (alias: uninstall)
  nebulix reset [--dry-run]    padrão de fábrica do Ubuntu (gsettings reset)
  nebulix icons install [CONJUNTO] [--yes]   baixa e ativa um conjunto de ícones (whitesur | mactahoe | mcmojave; padrão: o configurado)
  nebulix doctor               checa dependências e mostra como instalar
  nebulix wallpaper NOME       orbit | horizon | circuit | code | none

Zoom da dock (opcional, precisa do Ubuntu Dock): nebulix config set dock_zoom=on dock_zoom_factor=160
Terminal: nebulix config set terminal_opacity=85 terminal_cursor=ibeam terminal_font_size=12
"""


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        return gui()
    cmd, rest = a[0], a[1:]
    dry = "--dry-run" in rest
    rest = [x for x in rest if x != "--dry-run"]
    if cmd in ("-h", "--help", "help"):
        print(HELP.format(v=__version__))
    elif cmd in ("version", "--version"):
        print(f"nebulix {__version__}")
    elif cmd in ("apply", "install"):
        only = [r[2:] for r in rest if r.startswith("--") and r[2:] in config.COMPONENTS] or None
        apply(config.load(), dry=dry, only=only, install_icons="--icons" in rest or "--yes" in rest)
    elif cmd in ("undo", "uninstall"):
        restore("undo", dry=dry)
    elif cmd == "reset":
        restore("reset", dry=dry, remove_icons="--remove-icons" in rest)
    elif cmd == "config":
        return _config(rest, dry)
    elif cmd == "theme":
        return _theme(rest, dry)
    elif cmd == "wallpaper":
        return _config([f"set", f"wallpaper={rest[0]}"] if rest else ["get", "wallpaper"], dry)
    elif cmd == "status":
        _status()
    elif cmd == "doctor":
        for lvl, msg, fix in doctor.check():
            print({"ok": "✓", "warn": "!", "info": "·"}[lvl], msg + (f"\n    → {fix}" if fix else ""))
    elif cmd == "icons" and rest[:1] == ["install"]:
        return _icons_install(rest[1:])
    elif cmd == "gui":
        return gui()
    else:
        print(HELP.format(v=__version__))
        return 2
    return 0


def _icons_install(rest):
    from . import icons
    yes = "--yes" in rest or "-y" in rest
    names = [r for r in rest if not r.startswith("-")]
    c = config.load()
    sid = names[0] if names else c["icons"]
    if names and sid not in icons.SETS and sid not in config.CHOICES["icons"]:
        print(f"conjunto desconhecido: {sid} (use {', '.join(icons.SETS)})", file=sys.stderr)
        return 2
    if sid not in icons.SETS:
        print(f"icons = {sid}: não há nada para baixar (o conjunto vem do sistema)")
        return 0
    entry = icons.SETS[sid]
    base = icons.base_name(c["theme"], sid)
    if not icons.has_theme(base) and not icons.cached_tarball(sid) and not yes:
        print(f"Baixar ~{entry['size_mb']} MB ({entry['label']} {entry['tag']}, {entry['license']})? [s/N] ", end="", flush=True)
        try:
            ans = input()
        except EOFError:
            ans = ""
        if ans.strip().lower() not in ("s", "sim", "y", "yes"):
            print("cancelado: nada foi baixado")
            return 0
    try:
        icons.ensure_set(sid, print, c["theme"])
    except Exception as e:
        print(f"erro: {entry['label']} indisponível ({e})", file=sys.stderr)
        return 1
    c["icons"] = sid
    config.save(c)
    apply(c, only=["icons"])
    return 0


def _config(rest, dry):
    no_apply = "--no-apply" in rest
    rest = [r for r in rest if r != "--no-apply"]
    cfg = config.load()
    if not rest or rest[0] == "list":
        for k in config.DEFAULTS:
            print(f"{k} = {cfg[k]}")
        return 0
    if rest[0] == "get":
        print(cfg[rest[1]])
        return 0
    if rest[0] == "set":
        for kv in rest[1:]:
            k, _, v = kv.partition("=")
            if k not in config.DEFAULTS:
                print(f"chave desconhecida: {k}", file=sys.stderr)
                return 2
            cfg[k] = config.parse_value(k, v)
        try:
            cfg = config.validate(cfg)
        except ValueError as e:
            print(f"erro: {e}", file=sys.stderr)
            return 2
        if not dry:
            config.save(cfg)
        if not no_apply:
            apply(cfg, dry=dry)
        return 0
    print("uso: nebulix config list | get CHAVE | set CHAVE=VALOR ...", file=sys.stderr)
    return 2


def _theme(rest, dry):
    no_apply = "--no-apply" in rest
    rest = [r for r in rest if r != "--no-apply"]
    cfg = config.load()
    if not rest:
        for tid in themes.ids():
            th = themes.get(tid)
            print(f"{'*' if tid == cfg['theme'] else ' '} {tid:14s} {th['label']}")
        return 0
    try:
        new = config.apply_theme(cfg, rest[0])
    except ValueError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    if not dry:
        config.save(new)
    if not no_apply:
        apply(new, dry=dry)
    return 0


def _status():
    cfg = config.load()
    print(f"Nebulix {__version__}  (config: {paths.config_file()})")
    for k in config.DEFAULTS:
        print(f"  {k:15s} {cfg[k]}")
    sd = paths.state_dir()
    n = len((sd / "manifest").read_text().splitlines()) if (sd / "manifest").exists() else 0
    print(f"instalado: {'sim' if n else 'não'} ({n} entradas em {sd})")


def gui():
    try:
        from .gui import run
    except Exception as e:
        print(f"app gráfico indisponível ({e}); use `nebulix --help`", file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
