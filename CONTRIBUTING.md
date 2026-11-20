# Contribuindo
- Cores: `palette.json` define cada tema (base, ANSI, destaques e o pacote de valores); destaque/variante/raio vêm da config (`nebulix/palette.py`). Para um tema novo, adicione-o em `palette.json` e em `config.CHOICES["theme"]`. Contraste é checado para todas as combinações tema x destaque x variante em `build.py`. Nos templates use `${on-red}`, `${accent-solid}`/`${on-solid}`, `${ink-dark}` etc. em vez de `${bg-0}` como cor de texto (os temas claros invertem o fundo), e `/*@if scheme=dark*/` para o que só vale no escuro.
- Templates ficam em `templates/` (`${token}`, `${token|a35}`, `${token|rgb}`); formatos especiais em `nebulix/gen.py`; condicionais com `/*@if chave=valor*/ ... /*@end*/`.
- Rode `python3 -m unittest discover -s tests`. Teste instaladores sempre com `HOME` descartável e `--dry-run`; nunca no seu ambiente real.
- Ao reportar app com visual quebrado, informe: versão do Ubuntu/GNOME, app (deb/snap/flatpak) e screenshot.
- Cada arquivo-fonte leva cabeçalho SPDX.
