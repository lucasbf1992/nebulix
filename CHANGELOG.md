# Changelog
## 0.3.0 (em desenvolvimento)
- **Sistema de temas:** nova chave `theme` (`nebulix`, `macos-dark`, `macos-light`, `nebulix-light`), `nebulix theme [NOME]` e seletor na aba Aparência. Escolher um tema aplica um pacote (destaque, botões da janela, barra, cantos, ícones, dock, fonte) e cada item continua ajustável. `accent = "auto"` usa o destaque padrão do tema.
- **macOS Dark:** cinzas neutros, azul `#0A84FF` (fundo de seleção escurecido para 4.5:1 com texto branco), semáforo à esquerda, barra translúcida (nova opção `topbar = translucent`), cantos 10 px, ícones WhiteSur azuis, Inter. Destaques macOS: azul, roxo, rosa, vermelho, laranja, amarelo, verde e grafite.
- **macOS Light e Nebulix Light:** `color-scheme = prefer-light`, GTK 3/4 e Shell com o stylesheet claro, tema instalado em `Nebulix-Light`; terminal, VS Code, Neovim, Starship, btop e fastfetch acompanham a paleta.
- Contraste WCAG checado para todas as combinações tema x destaque x variante (`build.py` e testes), inclusive cores `#RRGGBB` arbitrárias.
- Ícones WhiteSur passam a ter a variante (azul ou roxa) e o fundo (claro ou escuro) do tema; instalação continua pinada com sha256.
- Nova chave `font` (`auto`/`keep`): Inter nos temas macOS, quando instalada.
- fastfetch passa a seguir a cor de destaque. `nebulix undo` não deixa mais um `gtk.css` vazio quando ele não existia.
- Mínima mudança visual no tema roxo: botões de alternância do Shell e botão padrão dos diálogos usam as mesmas cores de destaque já usadas no resto.
## 0.2.0
- App de personalização (GTK4/libadwaita) e `nebulix config`: destaque, variante Darker OLED, raio dos cantos, botões da janela (GNOME ou semáforo macOS), barra flutuante ou sólida, dock.
- Dock estilo macOS (Ubuntu Dock): flutuante, centralizada, indicador no destaque.
- Ícones estilo macOS: WhiteSur roxo (baixado, versão fixa com sha256) + pastas squircle do Nebulix.
- Novos wallpapers (4 imagens prontas) e 4 gerados em código que seguem o destaque.
- `nebulix undo` e `nebulix reset`, também no app. Migra o estado da 0.1.
- Tema do Shell passa a incluir o stylesheet padrão extraído localmente (não depende de `@import`).
- Testes em sandbox (apply/undo/reset, migração, CSS de todas as combinações) e `nebulix doctor`.
## 0.1.0
- Primeira versão: paleta única, GTK 3/4, GNOME Shell, terminal, Starship, fastfetch, btop, VS Code, Neovim, wallpapers, instalador reversível, .tar.xz e .deb.
