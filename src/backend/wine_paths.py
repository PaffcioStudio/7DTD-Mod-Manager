"""Konwersja ścieżek między konwencją Unix a konwencją Wine/Windows.

Port 1:1 ze starego projektu (7dtd-mod-manager/wine_paths.py, etap 6).

Kontekst: 7 Days to Die (i ogólnie dowolna gra uruchomiona pod Wine/Proton)
interpretuje argumenty startowe w konwencji Windows. Ścieżka unixowa
przekazana z wiodącym "/" NIE jest rozpoznawana jako bezwzględna - silnik
dokleja ją do katalogu instalacji gry zamiast potraktować jako osobną,
niezależną lokalizację. Potwierdzone eksperymentalnie w starym projekcie
przy testach -UserDataFolder.

Rozwiązanie: Wine domyślnie mapuje dysk Z:\\ na root "/" systemu hosta,
więc dowolna ścieżka unixowa ma swój odpowiednik pod Z:/<ta sama ścieżka
bez wiodącego /> - i właśnie to Wine rozpoznaje jako ścieżkę bezwzględną.

Ten moduł MUSI być używany wszędzie, gdzie budowana jest komenda
uruchomieniowa gry przekazująca dowolną ścieżkę systemu plików jako
argument startowy (obecnie: -UserDataFolder=) - łatwo o regresję (gra
startująca z danymi w złym miejscu, bez żadnego komunikatu) jeśli
konwersję się pominie.
"""
from __future__ import annotations

from services.i18n_message import message as i18n_message

from pathlib import Path, PureWindowsPath

# Litera dysku, na którą Wine domyślnie mapuje root "/" systemu hosta
# (prefiks domyślny ~/.wine i analogiczne prefiksy Proton).
WINE_ROOT_DRIVE = "Z:"


def to_wine_path(unix_path: str | Path) -> str:
    """Konwertuje bezwzględną ścieżkę unixową na odpowiednik Wine/Windows.

    Przykład: "/home/u/Eksperyment" -> "Z:/home/u/Eksperyment".
    Względna ścieżka rzuca ValueError od razu (Wine dokleiłaby ją do
    katalogu instalacji gry - ciche złe zachowanie). Zachowuje separator
    "/" (Wine akceptuje oba, "/" jest czytelniejszy i nie wymaga
    escapowania). Nie rozwiązuje symlinków i nie wymaga istnienia ścieżki
    - celowo, bo może dotyczyć katalogu, który dopiero powstanie."""
    path = Path(unix_path)
    if not path.is_absolute():
        raise ValueError(i18n_message("paths.error.absolute", {"path": str(unix_path)}))

    posix = path.as_posix()
    without_leading_slash = posix.lstrip("/")
    return f"{WINE_ROOT_DRIVE}/{without_leading_slash}"


def to_unix_path(wine_path: str) -> Path:
    """Konwertuje ścieżkę Wine ("Z:/home/..." lub "Z:\\\\home\\\\...") z
    powrotem na unixową. Rozpoznaje WYŁĄCZNIE prefiks Z: - ścieżka z innym
    dyskiem nie ma jednoznacznego odpowiednika bez znajomości konkretnego
    prefiksu Wine, więc rzuca ValueError zamiast zgadywać."""
    normalized = wine_path.replace("\\", "/")
    win_path = PureWindowsPath(normalized)

    drive = win_path.drive
    if drive.upper() != WINE_ROOT_DRIVE.upper():
        raise ValueError(i18n_message("paths.error.wineDrive", {"drive": drive, "path": wine_path}))

    remaining_parts = win_path.parts[1:]
    return Path("/", *remaining_parts)
