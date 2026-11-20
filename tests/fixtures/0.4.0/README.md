Fixtures captured from the 0.4.0 code (commit 3436a5c) in a throw-away HOME; they are never regenerated.

- `configs/<tema>.toml`: the `config.toml` 0.4.0 writes for each theme (no keys from later versions).
- `goldens/<tema>/gs.json`: the fake gsettings state after `apply` (all components except wallpaper, WhiteSur folders
  already installed, fixed profile uuid, fonts present). Later versions may add keys; the old ones must keep their values.
- `goldens/<tema>/files/`: generated files under `~/.config`, the Ptyxis palette and the Nebulix-Icons overlay.
- `goldens/<tema>/terminal/`: the rendered terminal files (palette and GNOME Terminal dconf dump).
- `manifest/`: an install covering every manifest prefix of 0.4.0 (`gtkblock:`, `ptyxis:`, `gnt:`, `vscode:`,
  `vscext:`, `ext:` and plain paths, plus `flatpak`). `before/` is the HOME before apply, `home/` the HOME after it
  (state directory included), `gs-before.json` / `gs-after.json` the fake gsettings state. In the text `@HOME@` stands
  for the HOME path and in path names `@HOMEREL@` for the same path without the leading slash.
