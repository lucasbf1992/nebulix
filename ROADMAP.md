# Roadmap

Itens fora da 0.2.0, registrados para as próximas versões.

## 0.3.0: tema macOS Dark (decidido)
Segundo tema, escuro e neutro, próximo ao macOS, ao lado do Nebulix roxo. Escolha em `nebulix theme macos` e no app.
- **Paleta:** fundos `#161616`, `#1E1E1E`, `#2A2A2C` e `#3A3A3C`; texto `#F5F5F7`, `#AEAEB2`, `#636366`; destaque azul `#0A84FF` (o fundo de seleção escurece para manter contraste 4.5:1 com texto branco); vermelho `#FF453A`, verde `#32D74B`, amarelo `#FFD60A`, rosa `#FF375F`, ciano `#64D2FF`. ANSI, terminal, VS Code, Neovim, Starship e btop seguem a paleta.
- **Pacote completo ajustável:** escolher o tema aplica um conjunto (destaque azul, botões semáforo à esquerda, barra superior translúcida, cantos de 10 px, ícones WhiteSur azuis, dock translúcida clara). Depois cada item continua ajustável. Nova chave `theme` e `accent = "auto"` (destaque padrão do tema); os destaques do macOS (azul, roxo, rosa, vermelho, laranja, amarelo, verde, grafite) entram na lista.
- **Sem wallpaper próprio:** usa os wallpapers existentes.
- **Ícones:** WhiteSur na variante azul padrão (outra instalação pinada e verificada por sha256).
- **Fontes:** Inter na interface (a SF Pro da Apple não pode ser redistribuída).
- Mockup aprovado na conversa em 2026-11-20.

## Próximos passos
- **Zoom dos ícones da dock ao passar o mouse (estilo macOS).** Implementado como extensão própria `nebulix-dock-zoom` sobre o Ubuntu Dock (opcional, `dock_zoom=on`). Falta validar na sessão real. Ideias seguintes: fundo da dock crescer com o zoom, cliques na parte ampliada, zoom em dock auto-ocultável, pulo ao abrir app.
- Validar no Shell real: Atividades, calendário, notificações, tela de bloqueio.
- Passos de validação pendentes: ícones WhiteSur, wallpaper e terminal/editor na sessão real.
- Release `v0.2.0` no GitHub (com `.deb`, `.tar.xz` e `SHA256SUMS`) depois da validação.

## Fora do escopo (decidido)
Tema Qt/KDE, cursor próprio, GRUB, Plymouth e distribuição ampla (PPA, gnome-look, marketplaces).
