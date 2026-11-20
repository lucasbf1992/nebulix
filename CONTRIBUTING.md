# Contribuindo
- Cores: `palette.json` (base) + destaque/variante/raio vêm da config (`nebulix/palette.py`). Contraste é checado para todas as combinações em `build.py`.
- Templates ficam em `templates/` (`${token}`, `${token|a35}`, `${token|rgb}`); formatos especiais em `nebulix/gen.py`; condicionais com `/*@if chave=valor*/ ... /*@end*/`.
- Rode `python3 -m unittest discover -s tests`. Teste instaladores sempre com `HOME` descartável e `--dry-run`; nunca no seu ambiente real.
- Ao reportar app com visual quebrado, informe: versão do Ubuntu/GNOME, app (deb/snap/flatpak) e screenshot.
- Cada arquivo-fonte leva cabeçalho SPDX.
