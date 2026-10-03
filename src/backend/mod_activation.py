"""Mechanizm aktywacji modów: buduje folder Mods/ dla danej lokalizacji
(instalacja gry, główna lokalizacja, przyszła instancja - etap 6) na
podstawie listy aktywnych modów z Biblioteki. Port 1:1 ze starego projektu
(7dtd-mod-manager/mod_activation.py, etap 3 migracji).

Strategia: symlink z fallbackiem do kopii. Każdy aktywny mod staje się
jednym top-level wpisem w folderze docelowym Mods/, o nazwie równej
folder_name z LibraryModEntry (zob. library.py), wskazującym (symlink)
lub będącym kopią zawartości library_root() / folder_name.

Operacja jest IDEMPOTENTNA (build_mods_folder można wołać wielokrotnie,
bezpiecznie) i wykonywana ATOMOWO WZGLĘDEM WIDOKU Z ZEWNĄTRZ: cała nowa
zawartość budowana jest w katalogu tymczasowym obok celu, a podmiana na
docelowy folder następuje jedną operacją os.replace() na katalog - więc
w razie błędu w trakcie budowania (dysk pełny, plik zablokowany)
ISTNIEJĄCY folder Mods/ pozostaje nietknięty, zamiast zostać w stanie
połowicznym. To dotyczy jedynie WIDOCZNEGO efektu końcowego (stary folder
albo nowy folder, nigdy pół-zbudowany), nie przetrwania awarii zasilania
w trakcie samego os.replace().

Rozpoznawanie "czyich" wpisów dotyczy operacja (żeby czyszczenie
nieaktualnych wpisów przy kolejnym wywołaniu nie ruszało plików, które
użytkownik mógł wrzucić do Mods/ ręcznie, poza tym mechanizmem): plik
MANAGED_MARKER_FILENAME wewnątrz folderu Mods/, zawierający listę nazw
wpisów utworzonych przez ten mechanizm przy ostatnim budowaniu. Wpisy
spoza tej listy są zostawiane w spokoju.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)

# Plik-znacznik wewnątrz folderu Mods/, wskazujący które wpisy są zarządzane
# przez ten mechanizm (symlink/kopia z Biblioteki), a które użytkownik mógł
# umieścić tam ręcznie - te drugie nigdy nie są ruszane przez
# build_mods_folder/clean_managed_entries.
MANAGED_MARKER_FILENAME = ".7dtd_managed.json"


class ActivationError(Exception):
    """Błąd podczas budowania folderu Mods/ - dysk pełny, plik zablokowany,
    brak uprawnień nawet do fallbacku kopii, itp. Podnoszony PO próbie
    posprzątania katalogu tymczasowego, więc nie zostawia śmieci na dysku
    (poza samym docelowym folderem Mods/, który w razie błędu zostaje
    nietknięty - zob. docstring modułu)."""


@dataclass(slots=True)
class ActivationEntry:
    """Jedna pozycja do aktywacji: nazwa wpisu w Mods/ (zwykle folder_name
    moda) + ścieżka źródłowa w Bibliotece, którą ten wpis ma reprezentować."""

    entry_name: str
    source_path: Path


@dataclass(slots=True)
class BuildResult:
    """Podsumowanie jednego wywołania build_mods_folder - do wyświetlenia
    w UI albo do logowania."""

    symlinked: list[str] = field(default_factory=list)
    copied: list[str] = field(default_factory=list)  # fallback z powodu błędu symlinka
    removed_stale: list[str] = field(default_factory=list)
    total_entries: int = 0

    @property
    def used_copy_fallback(self) -> bool:
        return len(self.copied) > 0


def _read_managed_marker(mods_dir: Path) -> set[str]:
    marker = mods_dir / MANAGED_MARKER_FILENAME
    if not marker.exists():
        return set()
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        entries = data.get("managed_entries", [])
        if isinstance(entries, list):
            return {str(e) for e in entries}
    except Exception:
        pass
    return set()


def _write_managed_marker(mods_dir: Path, entry_names: set[str]) -> None:
    marker = mods_dir / MANAGED_MARKER_FILENAME
    payload = {"managed_entries": sorted(entry_names)}
    marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _create_entry(entry: ActivationEntry, target_dir: Path) -> tuple[Path, bool]:
    """Tworzy jeden wpis (entry.entry_name) w target_dir, wskazujący na
    entry.source_path. Najpierw próbuje symlinka; jeśli się nie uda
    z jakiegokolwiek powodu (brak uprawnień, system plików bez wsparcia
    symlinków jak niektóre montowania FAT, limit liczby dowiązań), przechodzi
    na pełną kopię drzewa katalogów.

    Zwraca (ścieżkę_do_utworzonego_wpisu, czy_użyto_fallbacku_kopii)."""
    dest = target_dir / entry.entry_name

    try:
        os.symlink(entry.source_path, dest, target_is_directory=entry.source_path.is_dir())
        return dest, False
    except OSError as exc:
        logger.info(
            "Symlink failed for %s -> %s (%s), falling back to copy",
            dest, entry.source_path, exc,
        )
        # Symlink mógł się częściowo utworzyć zanim rzucił - sprzątamy
        # przed próbą kopii, żeby copytree nie natrafiło na istniejącą ścieżkę.
        if dest.is_symlink() or dest.exists():
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()

        try:
            if entry.source_path.is_dir():
                shutil.copytree(entry.source_path, dest, symlinks=False)
            else:
                shutil.copy2(entry.source_path, dest)
        except OSError as copy_exc:
            raise ActivationError(i18n_message("activation.error.entry", {
                "name": entry.entry_name,
                "error": str(copy_exc),
            })) from copy_exc

        return dest, True


def build_mods_folder(entries: list[ActivationEntry], target_dir: Path | str) -> BuildResult:
    """Buduje folder Mods/ pod target_dir zawierający dokładnie podane
    entries - idempotentnie, bezpiecznie do wielokrotnego wywołania.

    Przebieg:
    1. Buduje CAŁĄ nową zawartość w katalogu tymczasowym obok target_dir
       (na tym samym systemie plików, żeby finalny os.replace() na katalog
       był operacją atomową, nie kopiowaniem między dyskami).
    2. Kopiuje do niego niezarządzane wpisy z istniejącego target_dir
       (te SPOZA znacznika poprzedniego budowania) - żeby nic, co użytkownik
       tam ręcznie umieścił, nie zniknęło.
    3. Tworzy nowe zarządzane wpisy (symlink z fallbackiem do kopii).
    4. Zapisuje nowy znacznik z aktualną listą zarządzanych wpisów.
    5. Podmienia stary target_dir na nowo zbudowany (os.replace na katalog).

    W razie błędu w dowolnym momencie kroków 2-4: katalog tymczasowy jest
    usuwany, wyjątek propagowany jako ActivationError, a ISTNIEJĄCY
    target_dir pozostaje kompletnie nietknięty (krok 5 nigdy się nie
    wykonuje)."""
    target_dir = Path(target_dir)
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)

    result = BuildResult(total_entries=len(entries))
    new_managed_names = {e.entry_name for e in entries}

    # Krok 1: katalog tymczasowy NA TYM SAMYM POZIOMIE co target_dir (nie
    # w systemowym /tmp), żeby finalny os.replace() nie musiał kopiować
    # między różnymi systemami plików (co przestałoby być atomowe i mogłoby
    # zawieść w połowie przy dużych bibliotekach modów).
    tmp_dir = Path(tempfile.mkdtemp(prefix=".mods_build_", dir=parent))

    try:
        # Krok 2: przenieś niezarządzane wpisy z istniejącego target_dir.
        if target_dir.exists():
            previously_managed = _read_managed_marker(target_dir)
            for child in target_dir.iterdir():
                if child.name == MANAGED_MARKER_FILENAME:
                    continue
                if child.name in previously_managed:
                    continue  # to nasz stary zarządzany wpis - pomijamy, zbudujemy na nowo
                # Wpis obcy (ręcznie dodany przez użytkownika) - zachowaj.
                dest = tmp_dir / child.name
                if child.is_symlink():
                    linkto = os.readlink(child)
                    os.symlink(linkto, dest)
                elif child.is_dir():
                    shutil.copytree(child, dest, symlinks=True)
                else:
                    shutil.copy2(child, dest)

        # Krok 3: utwórz nowe zarządzane wpisy.
        for entry in entries:
            _created_path, used_copy = _create_entry(entry, tmp_dir)
            if used_copy:
                result.copied.append(entry.entry_name)
            else:
                result.symlinked.append(entry.entry_name)

        # Krok 4: znacznik.
        _write_managed_marker(tmp_dir, new_managed_names)

        # Policz, które zarządzane wpisy zniknęły względem poprzedniego stanu
        # (do BuildResult - informacyjnie, sam fakt "nie skopiowaliśmy ich do
        # tmp_dir w kroku 2" już je usunął z efektywnego wyniku).
        if target_dir.exists():
            previously_managed = _read_managed_marker(target_dir)
            result.removed_stale = sorted(previously_managed - new_managed_names)

    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if isinstance(exc, ActivationError):
            raise
        raise ActivationError(i18n_message("activation.error.build", {"error": str(exc)})) from exc

    # Krok 5: atomowa podmiana. os.replace() na katalog działa jako
    # pojedyncza operacja rename() w obrębie tego samego systemu plików
    # (stąd wymóg, żeby tmp_dir leżał w parent, nie w /tmp) - nie ma stanu
    # pośredniego widocznego z zewnątrz: albo stary katalog, albo nowy.
    if target_dir.exists():
        # os.replace nie potrafi bezpośrednio zastąpić niepustego katalogu
        # na wszystkich platformach - usuwamy stary DOPIERO gdy nowy jest
        # już w pełni gotowy (tmp_dir), więc to wciąż nie zostawia okna, w
        # którym target_dir by nie istniał z żadną sensowną zawartością
        # dłużej niż trwa pojedyncza operacja systemowa.
        backup_dir = Path(tempfile.mkdtemp(prefix=".mods_old_", dir=parent))
        backup_dir.rmdir()  # potrzebujemy tylko unikalnej nazwy, nie istniejącego katalogu
        os.replace(target_dir, backup_dir)
        try:
            os.replace(tmp_dir, target_dir)
        except Exception:
            # Nie powinno się zdarzyć (tmp_dir i target_dir w tym samym
            # katalogu nadrzędnym), ale w razie czego przywracamy stary stan
            # zamiast zostawić target_dir usunięty.
            os.replace(backup_dir, target_dir)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ActivationError(i18n_message("activation.error.replace")) from None
        shutil.rmtree(backup_dir, ignore_errors=True)
    else:
        os.replace(tmp_dir, target_dir)

    return result


def clean_managed_entries(target_dir: Path | str) -> list[str]:
    """Usuwa WSZYSTKIE zarządzane wpisy z target_dir (te wymienione w
    znaczniku), zostawiając nietknięte wpisy obce - odpowiednik
    build_mods_folder([], target_dir) bez konieczności znać pełną listę
    entries, przydatne np. przy dezaktywacji całej instancji. Zwraca listę
    nazw usuniętych wpisów.

    Bezpieczne wywołanie na folderze bez znacznika (nic nie robi, zwraca
    pustą listę) - nie ma tam nic, co ten mechanizm kiedykolwiek stworzył."""
    target_dir = Path(target_dir)
    if not target_dir.exists():
        return []

    managed = _read_managed_marker(target_dir)
    removed: list[str] = []
    for name in managed:
        child = target_dir / name
        if child.is_symlink():
            child.unlink()
            removed.append(name)
        elif child.is_dir():
            shutil.rmtree(child)
            removed.append(name)
        elif child.exists():
            child.unlink()
            removed.append(name)

    marker = target_dir / MANAGED_MARKER_FILENAME
    if marker.exists():
        marker.unlink()

    return removed
