#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Dev/CI build: renders the default theme into dist/ and checks contrast for every accent x variant."""
import shutil
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from nebulix import config, palette  # noqa: E402
from nebulix.apply import render_all  # noqa: E402


def main():
    bad = 0
    for acc, var in product(config.ACCENTS, config.CHOICES["variant"]):
        cfg = config.validate({"accent": acc, "variant": var})
        for a, b, c, need in palette.contrast_report(cfg):
            if c < need:
                bad += 1
                print(f"contraste {acc}/{var}: {a} sobre {b} = {c:.2f} (< {need})")
    if bad:
        sys.exit(f"{bad} combinações abaixo do contraste mínimo")
    print("contraste ok para todos os destaques e variantes")
    dist = ROOT / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir()
    cfg = config.validate({})
    t = render_all(cfg, dist)
    shutil.copytree(ROOT / "images" / "wallpapers", dist / "wallpapers")
    print("ok")


if __name__ == "__main__":
    main()
