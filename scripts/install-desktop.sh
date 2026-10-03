#!/usr/bin/env bash
# ============================================================================
#  7 Days to Die - Mod Manager :: instalacja skrótu w menu systemu
#  Tworzy ~/.local/share/applications/7dtd-mod-manager.desktop z
#  bezwzględnymi ścieżkami do TEGO katalogu projektu + kopiuje ikonę
#  do hicolor. Odinstalowanie: usuń oba pliki (patrz komunikat na końcu).
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

if [ ! -x "$PROJECT_DIR/run.sh" ]; then
    echo "BŁĄD: nie znaleziono run.sh w $PROJECT_DIR" >&2
    exit 1
fi

mkdir -p "$APPS_DIR" "$ICON_DIR"
cp "$PROJECT_DIR/assets/icons/app-icon-256.png" "$ICON_DIR/7dtd-mod-manager.png"

cat > "$APPS_DIR/7dtd-mod-manager.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=7DTD Mod Manager
Name[pl]=7DTD - Menedżer modów
GenericName=Mod Manager
GenericName[pl]=Menedżer modów
Comment=Library, instances, downloads for 7 Days to Die
Comment[pl]=Biblioteka modów, instancje i pobieranie dla 7 Days to Die
Exec=$PROJECT_DIR/run.sh
TryExec=$PROJECT_DIR/run.sh
Path=$PROJECT_DIR
Icon=7dtd-mod-manager
Terminal=false
Categories=Utility;
Keywords=7 days to die;7dtd;mody;mods;modpacki;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo ""
echo "✅ Skrót zainstalowany: $APPS_DIR/7dtd-mod-manager.desktop"
echo "   Ikona:               $ICON_DIR/7dtd-mod-manager.png"
echo ""
echo "Odinstalowanie:"
echo "  rm \"$APPS_DIR/7dtd-mod-manager.desktop\" \"$ICON_DIR/7dtd-mod-manager.png\""
