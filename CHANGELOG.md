# Changelog
## 0.5.0 (2026-11-20)
- **Conjuntos de ícones:** nova chave `icons` com `whitesur`, `mactahoe` (MacTahoe), `mcmojave` (McMojave-circle), `papirus` e `keep`. Os conjuntos são baixados sob demanda (tarball fixado por versão, com sha256) para `~/.local/share/icons`; `nebulix icons install [CONJUNTO]` baixa e `nebulix config set icons=mactahoe` troca e aplica.
- **A cor dos ícones agora segue o destaque:** cada conjunto tem a sua lista de cores e o Nebulix instala a mais próxima do destaque do tema (cinza para destaques sem cor), nas variantes escura e clara. Sem a cor exata, usa a mais parecida já instalada e o `nebulix doctor` indica o comando que baixa a certa.
- **Pastas:** nova chave `icon_folders` (`auto`, `nebulix`, `conjunto`) escolhe quem desenha as pastas: squircle do Nebulix (camada `Nebulix-Icons`) ou as do próprio conjunto; `auto` segue o tema.
- **Aba Ícones no app** (título "Ícones e fundo"): seletor do conjunto e do estilo das pastas, prévia de ícones do conjunto escolhido e botão **Baixar** (com o tamanho) quando o conjunto não está instalado.
- **`nebulix reset --remove-icons`:** apaga também os conjuntos baixados, a camada `Nebulix-Icons` e o cache; `undo` e `reset` comuns devolvem o tema de ícones anterior e deixam os conjuntos no disco.
- **Cache** do tarball verificado em `~/.cache/nebulix/icons`: voltar a um conjunto já baixado não precisa de rede.
- Correções: downloads de ícones travados contra execuções concorrentes, remoção de ícones tolerante a arquivos ausentes e mapeamento de cores de mesmo nome.
## 0.4.0 (2026-11-20)
- **Terminal por tema:** transparência, cursor, fonte e cores adequados a cada tema. Opacidade padrão 90% (Nebulix), 95% (macOS Dark) e 100% (temas claros), cursor bloco/barra. Novas chaves `terminal_opacity`, `terminal_cursor`, `terminal_font`, `terminal_font_size`, `terminal_padding`, `terminal_line_height`, `terminal_columns`, `terminal_rows`; opacidade e cursor fazem parte do pacote do tema.
- Nova aba **Terminal** no app, com prévia (fundo translúcido, prompt, as 16 cores ANSI e o cursor).
- **Ptyxis:** a paleta agora é de fato usada: o Nebulix cria o perfil "Nebulix" e o torna o padrão (antes, sem perfil existente, a paleta nunca era selecionada). A paleta traz `[Dark]` e `[Light]` do par do tema e `interface-style` fica em `system`. `undo`/`reset` removem o perfil e restauram o padrão anterior.
- **GNOME Terminal:** o perfil "Nebulix" passa a ser reescrito a cada aplicação (antes, trocar de tema não atualizava as cores) e vira o padrão.
- Fonte do terminal: JetBrainsMono Nerd Font, JetBrains Mono ou a do sistema, conforme instalada; `nebulix doctor` sugere `fonts-jetbrains-mono`.
- `build.py` e os testes checam o contraste do texto com o fundo na opacidade mínima.
## 0.3.0 (2026-11-20)
- **Correções do primeiro teste real:** trocar de tema várias vezes seguidas no app não gera mais "Arquivo existe" (applies serializados e travados por usuário; o app junta pedidos rápidos); os ícones da dock não ficam mais invisíveis ao trocar o tema com o zoom ligado (a extensão restaura os ícones quando o Shell os recria); a extensão do VS Code é registrada em `extensions.json` (antes o VS Code a marcava como removida/incompatível), e `undo`/`reset` removem o registro.
- **Sistema de temas:** nova chave `theme` (`nebulix`, `macos-dark`, `macos-light`, `nebulix-light`), `nebulix theme [NOME]` e seletor na aba Aparência. Escolher um tema aplica um pacote (destaque, botões da janela, barra, cantos, ícones, dock, fonte) e cada item continua ajustável. `accent = "auto"` usa o destaque padrão do tema.
- **macOS Dark:** cinzas neutros, azul `#0A84FF` (fundo de seleção escurecido para 4.5:1 com texto branco), semáforo à esquerda, barra translúcida (nova opção `topbar = translucent`), cantos 10 px, ícones WhiteSur azuis, Inter. Destaques macOS: azul, roxo, rosa, vermelho, laranja, amarelo, verde e grafite.
- **macOS Light e Nebulix Light:** `color-scheme = prefer-light`, GTK 3/4 e Shell com o stylesheet claro, tema instalado em `Nebulix-Light`; terminal, VS Code, Neovim, Starship, btop e fastfetch acompanham a paleta.
- Contraste WCAG checado para todas as combinações tema x destaque x variante (`build.py` e testes), inclusive cores `#RRGGBB` arbitrárias.
- Ícones WhiteSur passam a ter a variante (azul ou roxa) e o fundo (claro ou escuro) do tema; instalação continua pinada com sha256.
- **Tema do VS Code:** a extensão traz um tema por tema do Nebulix (`uiTheme` vs-dark ou vs) e a nova chave `vscode_theme` (`keep`, `follow` ou um tema) define `workbench.colorTheme` no `settings.json` do Code, Insiders e VSCodium com edição pontual (JSONC preservado), restaurável por `undo`/`reset`. Opção no app (aba Componentes) e `nebulix doctor` avisa se o editor não existe.
- Nova chave `font` (`auto`/`keep`): Inter nos temas macOS, quando instalada.
- fastfetch passa a seguir a cor de destaque. `nebulix undo` não deixa mais um `gtk.css` vazio quando ele não existia.
- Mínima mudança visual no tema roxo: botões de alternância do Shell e botão padrão dos diálogos usam as mesmas cores de destaque já usadas no resto.
- **Zoom da dock:** zoom dos ícones da dock ao passar o mouse (estilo macOS), opcional: `nebulix config set dock_zoom=on dock_zoom_factor=160` ou aba Aparência > Dock. Usa a extensão própria `nebulix-dock-zoom` por cima do Ubuntu Dock (que continua o padrão). Requer o Ubuntu Dock (`gnome-shell-ubuntu-extensions`); na primeira vez é preciso sair e entrar na sessão. `undo`/`reset` desligam e removem a extensão.
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
