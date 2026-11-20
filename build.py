#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Dev/CI build: checks contrast for every theme x accent x variant, renders the default theme into dist/."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from nebulix import config, palette, themes  # noqa: E402
from nebulix.apply import render_all  # noqa: E402


def main():
    bad = 0
    n = 0
    for th in config.CHOICES["theme"]:
        variants = config.CHOICES["variant"] if themes.get(th)["scheme"] == "dark" else ("dark",)
        for acc in ("auto", *themes.accent_names(th)):
            for var in variants:
                n += 1
                cfg = config.validate({"theme": th, "accent": acc, "variant": var})
                for a, b, c, need in palette.contrast_report(cfg):
                    if c < need:
                        bad += 1
                        print(f"contraste {th}/{acc}/{var}: {a} sobre {b} = {c:.2f} (< {need})")
    for th in config.CHOICES["theme"]:
        c = palette.terminal_contrast(config.validate({"theme": th}))
        if c < 4.5:
            bad += 1
            print(f"terminal translúcido a 70% em {th}: texto = {c:.2f} (< 4.5)")
    if bad:
        sys.exit(f"{bad} combinações abaixo do contraste mínimo")
    print(f"contraste ok em {n} combinações de tema x destaque x variante")
    dist = ROOT / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir()
    cfg = config.validate({})
    t = render_all(cfg, dist)
    shutil.copytree(ROOT / "images" / "wallpapers", dist / "wallpapers")
    print("ok")


if __name__ == "__main__":
    main()
