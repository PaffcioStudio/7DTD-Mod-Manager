#!/usr/bin/env bash
# 7DTD Mod Manager - test, build, publish and install a release.
# Usage: ./release.sh 1.0.48
#        ./release.sh --current   (show local and installed versions)
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

fail() { printf '\n[BŁĄD] %s\n' "$*" >&2; exit 1; }
info() { printf '\n[INFO] %s\n' "$*"; }

read_app_version() {
    [[ -f src/services/app_info.py ]] || return 1
    sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/p' src/services/app_info.py | head -n 1
}

CURRENT="$(read_app_version)" || fail "Nie odczytano src/services/app_info.py. Umieść release.sh w katalogu głównym projektu."
[[ -n "$CURRENT" ]] || fail "Nie udało się odczytać APP_VERSION z src/services/app_info.py."
INSTALLED="$(dpkg-query -W -f='${Version}' 7dtd-mod-manager 2>/dev/null || true)"

printf '7DTD Mod Manager\n'
printf '  Wersja projektu:      %s\n' "$CURRENT"
printf '  Wersja zainstalowana: %s\n' "${INSTALLED:-brak pakietu DEB}"

usage() {
    printf '\nUżycie: ./release.sh WERSJA\n'
    printf 'Przykład: ./release.sh 1.0.48\n'
    printf 'Podgląd wersji: ./release.sh --current\n'
}

case "${1:-}" in
    --current|-c) [[ $# -eq 1 ]] || { usage; exit 2; }; exit 0 ;;
    --help|-h) usage; exit 0 ;;
    '') usage; exit 2 ;;
esac
[[ $# -eq 1 ]] || { usage; exit 2; }
TARGET="$1"
[[ "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "Niepoprawny numer wersji: $TARGET (np. 1.0.48)."
printf '  Wersja do wydania:   %s\n' "$TARGET"

# Guardrails before any build, cleanup or remote mutation.
[[ -f RELEASE_NOTES.md ]] || fail "Brak RELEASE_NOTES.md."
[[ "$(grep -c '^## (latest) ' RELEASE_NOTES.md || true)" == 1 ]] || fail "RELEASE_NOTES.md musi mieć dokładnie jeden nagłówek (latest)."
grep -Fxq "## (latest) $TARGET" RELEASE_NOTES.md || fail "Zaktualizuj nagłówek RELEASE_NOTES.md do '## (latest) $TARGET' przed publikacją."
for file in build.sh test.sh run.sh git-push.sh; do
    [[ -f "$file" ]] || fail "Brak $file."
done
for cmd in git gh mygit dpkg-deb dpkg-query sudo; do
    command -v "$cmd" >/dev/null 2>&1 || fail "Brak wymaganego polecenia: $cmd"
done
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "To nie jest repozytorium Git."
git symbolic-ref -q HEAD >/dev/null || fail "Repozytorium jest w detached HEAD."
git remote get-url origin >/dev/null 2>&1 || fail "Brak zdalnego repozytorium Git 'origin'."
gh auth status >/dev/null 2>&1 || fail "GitHub CLI wymaga zalogowania (gh auth login)."

# Avoid duplicate publishes from two terminals at once.
LOCK="$ROOT/.release.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    fail "Trwa już publikacja lub istnieje blokada $LOCK. Sprawdź proces, zanim usuniesz blokadę."
fi
cleanup() { rmdir "$LOCK" 2>/dev/null || true; }
trap cleanup EXIT
trap 'printf "\n[PRZERWANO] Etap: %s (wiersz %s). Dalsze etapy nie zostały uruchomione.\n" "$STEP" "$LINENO" >&2' ERR
STEP="Przygotowanie"

# Show changes and reset logs only after successful preflight.
chmod +x ./build.sh ./test.sh ./run.sh ./git-push.sh
mkdir -p "$HOME/.7dtd_modmanager/logs"
find "$HOME/.7dtd_modmanager/logs" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
if [[ -t 1 ]] && [[ -n "${TERM:-}" ]]; then clear || true; fi
printf 'Projekt: %s -> %s\n' "$CURRENT" "$TARGET"
mygit diff

# build.sh sets APP_VERSION/README, produces DEB + AppImage and normally prompts
# to install; answer no, as installation happens only after successful publish.
STEP="Budowanie"
info '1/7 Budowanie DEB oraz AppImage...'
printf 'n\n' | bash ./build.sh "$TARGET"
[[ "$(read_app_version)" == "$TARGET" ]] || fail "build.sh nie ustawił wersji $TARGET."
ARCH="$(dpkg --print-architecture)"
DEB="$ROOT/dist/7dtd-mod-manager_${TARGET}_${ARCH}.deb"
APPIMAGE="$ROOT/dist/7dtd-mod-manager-${TARGET}-x86_64.AppImage"
[[ -s "$DEB" && -s "$APPIMAGE" ]] || fail "Brakuje DEB lub AppImage dla wersji $TARGET."
[[ "$(dpkg-deb --field "$DEB" Version)" == "$TARGET" ]] || fail "Wersja wewnątrz DEB jest nieprawidłowa."

STEP="Testy"
info '2/7 Testy automatyczne...'
bash ./test.sh

STEP="Ręczny test GUI"
info '3/7 Sprawdź działanie aplikacji. Po jej zamknięciu publikacja ruszy automatycznie.'
bash ./run.sh

# Publish the exact tested assets. The existing git-release.sh deletes the
# previous GitHub release before creating a new one. Here we update it in place
# instead, so a temporary GitHub error will not erase the whole previous release.
STEP="Git push"
info '4/7 Zapis zmian i push do GitHuba...'
bash ./git-push.sh "Aktualizacja $TARGET."

STEP="GitHub Release"
info '5/7 Publikacja GitHub Release...'
TAG="release"
git tag -f "$TAG"
git push --force origin "refs/tags/$TAG:refs/tags/$TAG"
# gh release list failure is fatal; do not confuse a network error with absence.
PUBLISHED="$(gh release list --limit 500 --json tagName --jq '.[].tagName')"
if grep -Fxq "$TAG" <<< "$PUBLISHED"; then
    gh release upload "$TAG" "$DEB" "$APPIMAGE" --clobber
    gh release edit "$TAG" --title "$TARGET" --notes-file RELEASE_NOTES.md
    # Remove only outdated assets belonging to this app, after successful upload.
    ASSETS="$(gh release view "$TAG" --json assets --jq '.assets[].name')"
    while IFS= read -r asset; do
        [[ -n "$asset" ]] || continue
        case "$asset" in
            7dtd-mod-manager_*.deb|7dtd-mod-manager-*.AppImage)
                if [[ "$asset" != "$(basename "$DEB")" && "$asset" != "$(basename "$APPIMAGE")" ]]; then
                    gh release delete-asset "$TAG" "$asset" --yes
                fi
                ;;
        esac
    done <<< "$ASSETS"
else
    gh release create "$TAG" "$DEB" "$APPIMAGE" \
        --title "$TARGET" --notes-file RELEASE_NOTES.md --verify-tag
fi

STEP="Snapshot mygit"
info '6/7 Zapis snapshotu mygit...'
mygit save "Poprawiono i opublikowano wersję $TARGET."

STEP="Instalacja i mygit release"
info '7/7 Instalacja DEB i utworzenie mygit release...'
sudo apt install "$DEB"
mygit release --name "$TARGET"

printf '\n[OK] Wydanie %s ukończone.\n' "$TARGET"
printf 'DEB:      %s\n' "$DEB"
printf 'AppImage: %s\n' "$APPIMAGE"
