# SPDX-License-Identifier: GPL-3.0-or-later
"""nebulix command line."""
import argparse
import sys

from . import __version__, config, doctor, paths
from .apply import apply
from .restore import restore

HELP = """nebulix {v} — tema roxo escuro para GNOME

  nebulix                      abre o app de personalização
  nebulix apply [--dry-run]    aplica a configuração atual   (alias: install)
  nebulix config list|get K|set K=V ...   ver/alterar (aplica ao salvar, use --no-apply p/ não aplicar)
  nebulix status               mostra config e o que está instalado
  nebulix undo [--dry-run]     volta ao que era antes do Nebulix        (alias: uninstall)
  nebulix reset [--dry-run]    padrão de fábrica do Ubuntu (gsettings reset)
  nebulix icons install        baixa o WhiteSur (~7 MB) e ativa os ícones estilo macOS
  nebulix doctor               checa dependências e mostra como instalar
  nebulix wallpaper NOME       orbit | horizon | circuit | code | none

Zoom da dock (opcional, precisa do Ubuntu Dock): nebulix config set dock_zoom=on dock_zoom_factor=160
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
    elif cmd == "wallpaper":
        return _config([f"set", f"wallpaper={rest[0]}"] if rest else ["get", "wallpaper"], dry)
    elif cmd == "status":
        _status()
    elif cmd == "doctor":
        for lvl, msg, fix in doctor.check():
            print({"ok": "✓", "warn": "!", "info": "·"}[lvl], msg + (f"\n    → {fix}" if fix else ""))
    elif cmd == "icons" and rest[:1] == ["install"]:
        from . import icons
        icons.ensure_whitesur(print)
        c = config.load()
        c["icons"] = "whitesur"
        config.save(c)
        apply(c, only=["icons"])
    elif cmd == "gui":
        return gui()
    else:
        print(HELP.format(v=__version__))
        return 2
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
