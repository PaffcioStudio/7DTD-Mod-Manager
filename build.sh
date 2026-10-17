#!/usr/bin/env bash
# ============================================================================
#  7 Days to Die - Mod Manager :: build
#  Builds .deb and .AppImage into ./dist/ (bundles .venv - the app runs standalone).
#
#  Steps:
#    1. dist/ exists? no = create it, yes = clear its contents
#    2. verify the environment (.venv - calls ./venv.sh if it is missing)
#    3. collect the project payload into .build/opt/7dtd-mod-manager
#    4. package the .deb (dpkg-deb)
#    5. package the .AppImage (appimagetool, downloaded into .build on demand)
#    6. clean up build leftovers
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[i]${NC} $1"; }
ok()      { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
fail()    { echo -e "${RED}[✗]${NC} $1"; }

APP_ID="7dtd-mod-manager"
DIST="$PROJECT_DIR/dist"
BUILD="$PROJECT_DIR/.build"
RELEASE_NOTES="$PROJECT_DIR/RELEASE_NOTES.md"
DEFAULT_RELEASE_NOTES="If you run into any problems or bugs, please open an issue on GitHub. Include your app version, your Linux distro, and the relevant log from ~/.7dtd_modmanager/logs/."

# RELEASE_NOTES.md is part of every source tree and every release.
# Create the minimal file automatically when a local checkout is missing it;
# the repository hygiene test still fails so the omission is visible in CI/tests.
if [ ! -f "$RELEASE_NOTES" ]; then
    printf '%s\n' "$DEFAULT_RELEASE_NOTES" > "$RELEASE_NOTES"
    warn "Brak RELEASE_NOTES.md - utworzono domyślny plik"
fi

# Usage: ./build.sh [VERSION] [--install|-i]
#   VERSION       e.g. 1.0.43 - written to src/services/app_info.py (and to
#                 README.md and tests/test_app_info.py) and used in package names.
#                 Without it, APP_VERSION from app_info.py is used.
#   --install/-i  installs/updates the built .deb without asking.
INSTALL_DEB=false
NEW_VERSION=""
for arg in "$@"; do
    case "$arg" in
        --install|-i)
            INSTALL_DEB=true
            ;;
        v[0-9]*|[0-9]*)
            NEW_VERSION="${arg#v}"
            if ! [[ "$NEW_VERSION" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
                fail "Niepoprawna wersja: $arg (oczekiwane np. 1.0.43)"
                exit 2
            fi
            ;;
        *)
            fail "Nieznany argument: $arg"
            echo "Użycie: $0 [WERSJA] [--install|-i]" >&2
            exit 2
            ;;
    esac
done

# ----------------------------------------------------------------------------
# 0. host tools
# ----------------------------------------------------------------------------
for tool in rsync dpkg-deb curl python3; do
    command -v "$tool" >/dev/null 2>&1 || { fail "Brak wymaganego narzędzia: $tool"; exit 1; }
done

# ----------------------------------------------------------------------------
# 1. dist/ - create or clear it (it must contain ONLY the newest files)
# ----------------------------------------------------------------------------
mkdir -p "$DIST"
find "$DIST" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
ok "dist/ wyczyszczony"

# ----------------------------------------------------------------------------
# 2. environment (.venv) - same as venv.sh; if missing, build it on the fly
# ----------------------------------------------------------------------------
if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
    warn ".venv nie istnieje - tworzę środowisko przez ./venv.sh"
    "$PROJECT_DIR/venv.sh"
fi
[ -f "$PROJECT_DIR/requirements.txt" ] || { fail "Brak requirements.txt"; exit 1; }
"$PROJECT_DIR/.venv/bin/python" -c "import PySide6, requests" 2>/dev/null || {
    warn "Zależności w .venv są niekompletne - doinstalowuję"
    "$PROJECT_DIR/.venv/bin/python" -m pip install -r requirements.txt --quiet
}
ok "Środowisko .venv gotowe"

# ----------------------------------------------------------------------------
# 3. version + build working directory
# ----------------------------------------------------------------------------
if [ -n "$NEW_VERSION" ]; then
    # app_info.py is the single source of truth; keep README and the test in sync
    sed -i "s/^APP_VERSION = \".*\"/APP_VERSION = \"$NEW_VERSION\"/" src/services/app_info.py
    sed -i "s/^\*\*Current version:\*\* .*/**Current version:** $NEW_VERSION  /" README.md
    sed -i "s/assert APP_VERSION == \".*\"/assert APP_VERSION == \"$NEW_VERSION\"/" tests/test_app_info.py
    ok "Wersja ustawiona na $NEW_VERSION (app_info.py, README.md, tests/test_app_info.py)"
fi
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' src/services/app_info.py | head -1)"
[ -n "$VERSION" ] || { fail "Nie udało się odczytać APP_VERSION"; exit 1; }
ARCH="$(dpkg --print-architecture)"
info "Wersja $VERSION ($ARCH)"

rm -rf "$BUILD"
mkdir -p "$BUILD"
PAYLOAD="$BUILD/opt/$APP_ID"

# project payload (without dev files and the environment - handled separately)
mkdir -p "$PAYLOAD"
rsync -a \
    --exclude '.venv/' --exclude '.git/' --exclude '.build/' --exclude 'dist/' \
    --exclude '.claude/' --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '*.pyc' --exclude '*.zip' \
    --include '/README.md' --exclude '*.md' \
    --exclude '.mygit*' --exclude 'shots/' \
    "$PROJECT_DIR/" "$PAYLOAD/"
# the whole environment (the app then runs without any system dependencies)
# note: the trailing slash on the source = copy its CONTENTS into .venv (no nesting)
rsync -a "$PROJECT_DIR/.venv/" "$PAYLOAD/.venv"
# slimming down: strip the Qt modules the app does NOT use (the app = QML/Quick,
# Network, Svg) - WebEngine is a whole Chromium (~240 MB), Multimedia/ffmpeg
# ~40 MB, Pdf/Quick3D a dozen or so MB; everything QML needs stays
VENV_SP="$PAYLOAD/.venv/lib/python3.12/site-packages/PySide6"
for junk in \
    "$VENV_SP/Qt/lib/libQt6WebEngine"*.so* \
    "$VENV_SP/Qt/lib/libQt6Pdf"*.so* \
    "$VENV_SP/Qt/lib/libQt6Multimedia"*.so* \
    "$VENV_SP/Qt/lib/libQt6Quick3D"*.so* \
    "$VENV_SP/Qt/lib/libQt6SpatialAudio"*.so* \
    "$VENV_SP/Qt/lib/libQt6Charts"*.so* \
    "$VENV_SP/Qt/lib/libQt6DataVisualization"*.so* \
    "$VENV_SP/Qt/lib/libQt6VirtualKeyboard"*.so* \
    "$VENV_SP/Qt/lib/libavcodec"*.so* \
    "$VENV_SP/Qt/lib/libavformat"*.so* \
    "$VENV_SP/Qt/lib/libavutil"*.so* \
    "$VENV_SP/Qt/lib/libswresample"*.so* \
    "$VENV_SP/Qt/lib/libswscale"*.so* \
    "$VENV_SP/Qt/translations/qtwebengine_locales" \
    "$VENV_SP/Qt/resources" \
    "$VENV_SP/Qt/metatypes" \
    "$VENV_SP/Qt/qml/QtMultimedia" \
    "$VENV_SP/Qt/qml/QtPdf" \
    "$VENV_SP/Qt/qml/QtQuick3D" \
    "$VENV_SP/Qt/qml/QtCharts" \
    "$VENV_SP/PySide6/QtWebEngineWidgets.pyi" \
    "$VENV_SP/PySide6/QtWebEngineCore.pyi" \
    "$VENV_SP/PySide6/QtWebEngineQuick.pyi" ; do
    rm -rf $junk
done
ok "Payload zebrany: $(du -sh "$PAYLOAD" | cut -f1)"

# ----------------------------------------------------------------------------
# 4. shared files (desktop entry + icon + launcher)
# ----------------------------------------------------------------------------
write_desktop() {  # $1 = Exec
    cat <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=7DTD Mod Manager
Name[pl]=7DTD - Menedżer modów
Comment=Library, instances and downloads for 7 Days to Die
Comment[pl]=Biblioteka modów, instancje i pobieranie dla 7 Days to Die
Exec=$1
Icon=7dtd-mod-manager
Terminal=false
Categories=Utility;
Keywords=7 days to die;7dtd;mody;mods;modpacki;
StartupNotify=true
EOF
}

WRAPPER="/usr/bin/$APP_ID"
PAYLOAD_REL="opt/$APP_ID"
# AppStream identifier (reverse-DNS format) - the .desktop and .appdata.xml files
# MUST be named exactly like the <id>, otherwise validate-tree fails
APPSTREAM_ID="io.github.paffciostudio.$APP_ID"

write_appdata() {  # AppStream metainfo (removes the appimagetool WARNING; version is dynamic)
    local date_today
    date_today="$(date +%F)"
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>$APPSTREAM_ID</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LicenseRef-Proprietary</project_license>
  <developer>
    <name>7DTD Mod Manager</name>
  </developer>
  <name>7DTD Mod Manager</name>
  <summary>Biblioteka modów, instancje i pobieranie dla 7 Days to Die</summary>
  <description>
    <p>Menedżer modów do 7 Days to Die: biblioteka z deduplikacją zawartości,
    izolowane instancje gry (osobne katalogi danych i zestawy modów),
    pobieranie z 7daystodiemods.com oraz modpacków z repozytoriów Git,
    wydań GitHub i archiwów .zip, kopie zapasowe instancji.</p>
    <p>Aplikacja PySide6 + QML z wbudowanym środowiskiem Python - nie wymaga
    zależności systemowych poza libc.</p>
  </description>
  <launchable type="desktop-id">$APPSTREAM_ID.desktop</launchable>
  <url type="homepage">https://github.com/paffciostudio</url>
  <provides>
    <binary>$APP_ID</binary>
  </provides>
  <releases>
    <release version="$VERSION" date="$date_today"/>
  </releases>
  <content_rating type="oars-1.1"/>
</component>
EOF
}

# ----------------------------------------------------------------------------
# 5a. .deb
# ----------------------------------------------------------------------------
info "Pakowanie .deb ..."
DEB_STAGE="$BUILD/deb"
rm -rf "$DEB_STAGE"
mkdir -p "$DEB_STAGE/DEBIAN" \
         "$DEB_STAGE/usr/bin" \
         "$DEB_STAGE/usr/share/applications" \
         "$DEB_STAGE/usr/share/metainfo" \
         "$DEB_STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$DEB_STAGE/opt"

cp -a "$PAYLOAD" "$DEB_STAGE/$PAYLOAD_REL"
write_desktop "/usr/bin/$APP_ID" > "$DEB_STAGE/usr/share/applications/$APPSTREAM_ID.desktop"
write_appdata > "$DEB_STAGE/usr/share/metainfo/$APPSTREAM_ID.appdata.xml"
cp "$PROJECT_DIR/assets/icons/app-icon-256.png" \
   "$DEB_STAGE/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"

cat > "$DEB_STAGE/usr/bin/$APP_ID" <<EOF
#!/bin/bash
exec /opt/$APP_ID/run.sh "\$@"
EOF
chmod 755 "$DEB_STAGE/usr/bin/$APP_ID"

INSTALLED_KB="$(du -sk "$DEB_STAGE" | cut -f1)"
cat > "$DEB_STAGE/DEBIAN/control" <<EOF
Package: $APP_ID
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_KB
Maintainer: 7DTD Mod Manager
Description: Menedżer modów do 7 Days to Die
 Biblioteka modów z deduplikacją, izolowane instancje gry, pobieranie
 z 7daystodiemods.com i modpacki. Aplikacja PySide6 + QML z wbudowanym
 środowiskiem Python (nie wymaga zależności systemowych poza libc).
EOF

cat > "$DEB_STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -qtf /usr/share/icons/hicolor || true
EOF
chmod 755 "$DEB_STAGE/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$DEB_STAGE" \
    "$DIST/${APP_ID}_${VERSION}_${ARCH}.deb" >/dev/null
ok ".deb zbudowany"

# ----------------------------------------------------------------------------
# 5b. .AppImage
# ----------------------------------------------------------------------------
info "Pakowanie .AppImage ..."
APPDIR="$BUILD/AppDir"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/metainfo" "$APPDIR/opt"

cp -a "$PAYLOAD" "$APPDIR/$PAYLOAD_REL"
# desktop file in the AppDir root (for appimagetool) AND in usr/share/applications
# (appstreamcli validate-tree only looks in the FHS location)
write_desktop "AppRun" > "$APPDIR/$APPSTREAM_ID.desktop"
write_desktop "AppRun" > "$APPDIR/usr/share/applications/$APPSTREAM_ID.desktop"
write_appdata > "$APPDIR/usr/share/metainfo/$APPSTREAM_ID.appdata.xml"
cp "$PROJECT_DIR/assets/icons/app-icon-256.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
cp "$PROJECT_DIR/assets/icons/app-icon-256.png" "$APPDIR/$APP_ID.png"

cat > "$APPDIR/AppRun" <<EOF
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${BASH_SOURCE[0]}")")"
unset QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
exec "\$HERE/$PAYLOAD_REL/.venv/bin/python" "\$HERE/$PAYLOAD_REL/src/main.py" "\$@"
EOF
chmod 755 "$APPDIR/AppRun"

APPIMAGETOOL="$BUILD/appimagetool-x86_64.AppImage"
if [ ! -x "$APPIMAGETOOL" ]; then
    info "Pobieram appimagetool (jednorazowo, ląduje w .build/) ..."
    curl -fL --retry 3 -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# FUSE may be unavailable - extract-and-run works around it
"$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" \
    "$DIST/${APP_ID}-${VERSION}-x86_64.AppImage" >/dev/null
ok ".AppImage zbudowany"

# ----------------------------------------------------------------------------
# 6. clean up build leftovers
# ----------------------------------------------------------------------------
rm -rf "$BUILD"
find "$PROJECT_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$PROJECT_DIR/squashfs-root" 2>/dev/null || true

# ----------------------------------------------------------------------------
# .deb installation (optional, on request) - version and architecture
# come from the build variables, so it also works for future versions
# ----------------------------------------------------------------------------
DEB_FILE="$DIST/${APP_ID}_${VERSION}_${ARCH}.deb"
APPIMAGE_FILE="$DIST/${APP_ID}-${VERSION}-x86_64.AppImage"
echo ""
if [ "$INSTALL_DEB" = true ]; then
    info "--install: automatycznie instaluję/aktualizuję $DEB_FILE przez dpkg ..."
    sudo dpkg --install "$DEB_FILE"
    ok "Zainstalowano: $DEB_FILE"
else
    read -r -p "Zainstalować/aktualizować teraz $DEB_FILE przez dpkg? [t/N] " answer || true
    if [[ "${answer:-}" =~ ^[tTyY] ]]; then
        sudo dpkg --install "$DEB_FILE"
        ok "Zainstalowano: $DEB_FILE"
    else
        info "Instalacja pominięta. Ręcznie:  sudo dpkg --install \"$DEB_FILE\""
    fi
fi

# ----------------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------------
echo ""
ok "Gotowe - dist/ zawiera:"
ls -lh "$DIST" | tail -n +2
echo ""
echo -e "Instalacja .deb:        ${BOLD}sudo apt install ./${DIST#$PROJECT_DIR/}/${APP_ID}_${VERSION}_${ARCH}.deb${NC}"
echo -e "AppImage:               ${BOLD}./dist/${APP_ID}-${VERSION}-x86_64.AppImage${NC}"
echo ""
