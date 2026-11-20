# Roadmap

Itens fora da 0.3.0, registrados para as próximas versões.

## 0.3.0: temas macOS Dark, macOS Light e Nebulix Light (lançada em 2026-11-20; temas, zoom da dock e tema do VS Code validados na sessão real)
Sistema de múltiplos temas (`theme`, `nebulix theme`), macOS Dark escuro e neutro, e dois temas claros (macOS Light e Nebulix Light, escolhidos em 2026-11-20). Escolha em `nebulix theme macos-dark` e no app.
- **Paleta:** fundos `#161616`, `#1E1E1E`, `#2A2A2C` e `#3A3A3C`; texto `#F5F5F7`, `#AEAEB2`, `#636366`; destaque azul `#0A84FF` (o fundo de seleção escurece para manter contraste 4.5:1 com texto branco); vermelho `#FF453A`, verde `#32D74B`, amarelo `#FFD60A`, rosa `#FF375F`, ciano `#64D2FF`. ANSI, terminal, VS Code, Neovim, Starship e btop seguem a paleta.
- **Pacote completo ajustável:** escolher o tema aplica um conjunto (destaque azul, botões semáforo à esquerda, barra superior translúcida, cantos de 10 px, ícones WhiteSur azuis, dock translúcida clara). Depois cada item continua ajustável. Nova chave `theme` e `accent = "auto"` (destaque padrão do tema); os destaques do macOS (azul, roxo, rosa, vermelho, laranja, amarelo, verde, grafite) entram na lista.
- **Desvio da paleta:** o texto terciário do macOS Dark é `#6C6C70` (não `#636366`) para atingir 3:1 sobre `#1E1E1E`.
- **Temas claros:** macOS Light (`#FFFFFF`/`#F5F5F7`, azul `#007AFF`) e Nebulix Light (brancos lilás, roxo `#6B3DD9`). Verde, amarelo e vermelho de texto são versões mais escuras que as do macOS para contraste; o semáforo mantém as cores clássicas.
- **Sem wallpaper próprio:** usa os wallpapers existentes.
- **Ícones:** WhiteSur na variante azul padrão (outra instalação pinada e verificada por sha256).
- **Fontes:** Inter na interface (a SF Pro da Apple não pode ser redistribuída).
- Mockup aprovado na conversa em 2026-11-20.

## Próximos passos
- Validar no Shell real nos temas claros: Atividades (o Shell mantém a visão geral escura), calendário, notificações e tela de bloqueio.
- Desfoque real da barra e da dock (extensão Blur my Shell) como opção.
- Zoom da dock: fundo da dock crescer com o zoom, cliques na parte ampliada, zoom em dock auto-ocultável, pulo ao abrir app.
- Conferir wallpaper, pastas dos ícones e terminal/editor em uso diário.

## Fora do escopo (decidido)
Tema Qt/KDE, cursor próprio, GRUB, Plymouth e distribuição ampla (PPA, gnome-look, marketplaces).
