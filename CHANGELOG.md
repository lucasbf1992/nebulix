# Changelog
## Não lançado
- Zoom dos ícones da dock ao passar o mouse (estilo macOS), opcional: `nebulix config set dock_zoom=on dock_zoom_factor=160` ou aba Aparência > Dock. Usa a extensão própria `nebulix-dock-zoom` por cima do Ubuntu Dock (que continua o padrão). Requer o Ubuntu Dock (`gnome-shell-ubuntu-extensions`); na primeira vez é preciso sair e entrar na sessão. `undo`/`reset` desligam e removem a extensão.
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
