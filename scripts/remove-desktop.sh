#!/usr/bin/env bash
# ============================================================================
#  7 Days to Die - Mod Manager :: usunięcie skrótu z menu systemu
#  Odwrotność install-desktop.sh: kasuje wpis .desktop i ikonę z hicolor.
# ============================================================================
set -euo pipefail

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

removed=0
for f in "$APPS_DIR/7dtd-mod-manager.desktop" "$ICON_DIR/7dtd-mod-manager.png"; do
    if [ -f "$f" ]; then
        rm "$f"
        echo "usunięto: $f"
        removed=1
    fi
done

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

if [ "$removed" = 1 ]; then
    echo "✅ Skrót usunięty z menu aplikacji."
else
    echo "Skrótu nie było w systemie - nic do usunięcia."
fi
