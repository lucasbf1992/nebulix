#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds release/nebulix-VERSION.tar.xz and release/nebulix_VERSION_all.deb
set -euo pipefail
cd "$(dirname "$0")"
V="$(python3 -c 'from nebulix import __version__ as v; print(v)')"
REV="${DEB_REV:-2}"   # Debian revision: bump it so apt upgrades a rebuilt package of the same version
DV="$V-$REV"
python3 -m unittest discover -s tests >/dev/null
python3 build.py >/dev/null
rm -rf release && mkdir -p release
SHIP=(nebulix templates palette.json images/wallpapers images/logo)
# ---- tarball ----
T="release/nebulix-$V"; mkdir -p "$T/images"
cp -r nebulix templates palette.json install.sh uninstall.sh LICENSE LICENSE-ART README.md CREDITS.md CHANGELOG.md "$T/"
cp -r images/wallpapers images/logo "$T/images/"
find "$T" -name __pycache__ -prune -exec rm -rf {} +
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-01-01' -C release -cJf "release/nebulix-$V.tar.xz" "nebulix-$V"
rm -rf "$T"
# ---- .deb ----
D="$(mktemp -d)"; trap 'rm -rf "$D"' EXIT
S="$D/usr/share"
mkdir -p "$D/DEBIAN" "$D/usr/bin" "$D/usr/lib/python3/dist-packages" "$S/nebulix/images" "$S/themes/Nebulix-Dark" \
  "$S/backgrounds/nebulix" "$S/gnome-background-properties" "$S/doc/nebulix" "$S/applications" "$S/icons/hicolor/scalable/apps"
cp -r nebulix "$D/usr/lib/python3/dist-packages/nebulix"
find "$D" -name __pycache__ -prune -exec rm -rf {} +
cp -r templates palette.json "$S/nebulix/"; cp -r images/wallpapers images/logo "$S/nebulix/images/"
install -m755 packaging/nebulix "$D/usr/bin/nebulix"
cp packaging/io.github.nebulix.Settings.desktop "$S/applications/"
cp dist/logo/nebulix.svg "$S/icons/hicolor/scalable/apps/io.github.nebulix.Settings.svg"
# system-wide selectable theme (default look); `nebulix apply` renders the customised one per user
cp dist/index.theme "$S/themes/Nebulix-Dark/"; cp -r dist/gtk-3.0 dist/gtk-4.0 dist/gnome-shell "$S/themes/Nebulix-Dark/"
cp images/wallpapers/*.png "$S/backgrounds/nebulix/"
{
  echo '<?xml version="1.0"?>'; echo '<!DOCTYPE wallpapers SYSTEM "gnome-wp-list.dtd">'; echo '<wallpapers>'
  for n in orbit horizon circuit code; do
    echo "  <wallpaper deleted=\"false\"><name>Nebulix $n</name><filename>/usr/share/backgrounds/nebulix/nebulix-$n.png</filename>"
    echo "    <filename-dark>/usr/share/backgrounds/nebulix/nebulix-$n.png</filename-dark><options>zoom</options><pcolor>#0B0812</pcolor><scolor>#0B0812</scolor></wallpaper>"
  done; echo '</wallpapers>'
} >"$S/gnome-background-properties/nebulix.xml"
cp LICENSE LICENSE-ART CREDITS.md "$S/doc/nebulix/"
cat >"$S/doc/nebulix/copyright" <<X
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: nebulix

Files: *
Copyright: Nebulix contributors
License: GPL-3.0+
 On Debian systems the full text is in /usr/share/common-licenses/GPL-3.

Files: usr/share/backgrounds/* usr/share/nebulix/images/* usr/share/icons/*
Copyright: Nebulix contributors
License: CC-BY-SA-4.0
 See /usr/share/doc/nebulix/LICENSE-ART.
X
cat >"$D/DEBIAN/postinst" <<'X'
#!/bin/sh
set -e
if [ "$1" = configure ] && command -v py3compile >/dev/null 2>&1; then py3compile -p nebulix || true; fi
if [ "$1" = configure ]; then
  cat >&2 <<'MSG'

Nebulix instalado. Nada foi alterado na sua sessão ainda:
  nebulix apply --dry-run   mostra o que mudaria
  nebulix apply             aplica o tema ao seu usuário
  nebulix doctor            mostra requisitos e como instalar
  nebulix reset             volta ao padrão do Ubuntu (rode ANTES de remover o pacote)
MSG
fi
exit 0
X
cat >"$D/DEBIAN/prerm" <<'X'
#!/bin/sh
set -e
if command -v py3clean >/dev/null 2>&1; then py3clean -p nebulix || true; fi
exit 0
X
cat >"$D/DEBIAN/postrm" <<'X'
#!/bin/sh
set -e
if [ "$1" = remove ]; then
  echo "Nebulix removido. Se o tema ainda estiver ativo na sua sessão, rode 'nebulix reset' ANTES de remover o pacote (ou use gsettings reset)." >&2
fi
exit 0
X
chmod 755 "$D/DEBIAN/postinst" "$D/DEBIAN/prerm" "$D/DEBIAN/postrm"
SIZE=$(du -sk "$D/usr" | cut -f1)
cat >"$D/DEBIAN/control" <<X
Package: nebulix
Version: $DV
Architecture: all
Maintainer: Lucas <lucasbf1992@users.noreply.github.com>
Section: gnome
Priority: optional
Installed-Size: $SIZE
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gnome-shell (>= 50~), gnome-shell-extensions
Recommends: papirus-icon-theme, librsvg2-common
Suggests: starship, fastfetch, fonts-inter
Homepage: https://github.com/lucasbf1992/nebulix
Description: Nebulix - customizable dark purple theme for GNOME
 GTK 3/4 and GNOME Shell themes, macOS-style dock and icons, wallpapers, and a
 settings app ('nebulix') to change accent colour, variant, window buttons,
 corner radius and dock live. Applies terminal, Starship, fastfetch, btop,
 VS Code and Neovim themes too. Fully reversible: 'nebulix undo' (back to
 before) or 'nebulix reset' (Ubuntu defaults).
X
find "$D" -type d -exec chmod 755 {} +; find "$D/usr" -type f -exec chmod 644 {} +
chmod 755 "$D/usr/bin/nebulix"
fakeroot dpkg-deb --build -Zxz "$D" "release/nebulix_${DV}_all.deb" >/dev/null
( cd release && sha256sum * > SHA256SUMS )
ls -lh release
