"""Operacje plikowo-rejestrowe na Bibliotece modów - port 1:1 ze starego
projektu (7dtd-mod-manager/library_ops.py, etap 3 migracji). Warstwa NAD
modelem danych z library.py: tu dzieje się kopiowanie na dysk, deduplikacja
po zawartości i sprzątanie aktywacji.

Operacje:
- import_mod_to_library() - jeden folder moda -> kopia do library_root(),
  wpis do library.json, opcjonalne włączenie do globalnego zestawu.
  Deduplikacja PO ZAWARTOŚCI (compute_content_hash): bit-identyczny mod już
  obecny w Bibliotece nie jest kopiowany drugi raz - zwracany jest istniejący
  wpis (import jest bezpieczny do powtarzania). Konflikt NAZW (inna
  zawartość, ta sama nazwa folderu) rozwiązywany sufiksem "-2", "-3"...
- import_mods_to_library() - wersja wsadowa (drag&drop, stare lokalizacje).
- install_modpack_to_library() - pobrany modpack (folder Mods z downloadu)
  -> każdy podfolder z ModInfo.xml importowany do Biblioteki.
- remove_mods_from_library() - usunięcie modów: pliki z library_root(),
  wpisy z library.json i CAŁY stan aktywacji tych modów.
- find_orphaned_library_folders()/register_orphaned_folder(s) - foldery
  wrzucone ręcznie bezpośrednio do library_root(), nieuwidzione w rejestrze.

Wszystkie funkcje wielomodowe przyjmują progress_cb/cancel_event zgodnie
z kontraktem workerów (zob. fileops.py).
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from services.i18n_message import message as i18n_message

from backend.fileops import (
    OperationCancelled,
    ProgressCallback,
    check_cancel,
    copy_tree_with_progress,
    remove_tree_with_progress,
)
from backend.game_process import is_game_running
from backend import library
from backend.library import (
    LibraryModEntry,
    compute_content_hash,
    find_by_content_hash,
    load_activation_state,
    load_library_entries,
    save_activation_state,
    save_library_entries,
)
from backend.modinfo import find_modinfo, parse_modinfo
from services import install_log
from services import filesystem_service as fs


class LibraryOperationError(Exception):
    """Błąd operacji na Bibliotece (walidacja, konflikt, IO)."""


@dataclass(slots=True)
class ImportReport:
    """Podsumowanie importu wsadowego/modpacka - do komunikatu w UI."""

    imported: list[LibraryModEntry] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)  # nazwy folderów źródłowych
    errors: list[str] = field(default_factory=list)

    @property
    def anything_done(self) -> bool:
        return bool(self.imported) or bool(self.already_present)


def _unique_folder_name(root: Path, desired: str) -> str:
    """Zwraca desired, albo desired-2, desired-3... - pierwszą wolną nazwę
    w root. Konieczne przy imporcie moda, którego nazwa folderu koliduje
    z innym modem o INNEJ zawartości (identyczna zawartość jest wyłapywana
    wcześniej po content_hash, więc tu trafiają tylko realne konflikty)."""
    candidate = desired
    counter = 2
    while (root / candidate).exists():
        candidate = f"{desired}-{counter}"
        counter += 1
    return candidate


def _register_entry(
    folder_in_library: Path,
    *,
    folder_name: str,
    content_hash: str,
    modinfo_data: dict[str, str],
    source: str,
    from_datetime,
    game_version: str = "",
) -> LibraryModEntry:
    """Buduje wpis LibraryModEntry dla folderu JUŻ skopiowanego do Biblioteki.
    Celowo NIE liczy content_hash od nowu na kopii (hash policzony na źródle
    jest równoważny - kopia jest bit-identyczna, a hashowanie dużego moda
    dwa razy to podwójny koszt przy każdym imporcie)."""
    return LibraryModEntry(
        library_id=str(uuid.uuid4()),
        folder_name=folder_name,
        display_name=modinfo_data.get("display_name", ""),
        mod_name=modinfo_data.get("mod_name", ""),
        author=modinfo_data.get("author", ""),
        version=modinfo_data.get("version", ""),
        description=modinfo_data.get("description", ""),
        content_hash=content_hash,
        source=source,
        added_at=from_datetime().isoformat(timespec="seconds"),
        game_version=game_version,
    )


def set_global_enabled(library_id: str, enabled: bool) -> None:
    """Modyfikuje globalny stan aktywacji jednego moda (load-modify-save
    pod LIBRARY_LOCK). Świeży odczyt przed każdą modyfikacją gwarantuje,
    że równolegli pisarze (import z URL, druga operacja UI) nie nadpiszą
    swoich zmian nawzajem."""
    with library.LIBRARY_LOCK:
        state = load_activation_state()
        state.set_global_enabled(library_id, enabled)
        save_activation_state(state)


# alias dla wewnętrznych wywołań (stara nazwa)
_set_global_enabled = set_global_enabled


def _import_one_to_library(
    source_folder: str | Path,
    *,
    source: str,
    enable: bool,
    from_datetime,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    game_version: str = "",
) -> tuple[LibraryModEntry, bool]:
    """Rdzeń importu pojedynczego moda - zwraca (wpis, czy_był_nowy).
    Publiczne funkcje opakowują to w wygodniejsze sygnatury."""
    src = Path(source_folder).expanduser().resolve(strict=False)
    if not src.is_dir():
        raise NotADirectoryError(i18n_message("library.error.notModDirectory", {"path": str(src)}))
    modinfo = find_modinfo(src)
    if modinfo is None:
        raise FileNotFoundError(i18n_message("library.error.modInfoMissing", {"path": str(src)}))

    name = src.name.strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise LibraryOperationError(i18n_message("library.error.invalidModFolder", {"path": str(src)}))

    content_hash = compute_content_hash(src)

    entries = load_library_entries()
    existing = find_by_content_hash(entries, content_hash)
    if existing is not None:
        # Bit-identyczna zawartość już w Bibliotece - import to no-op
        # (poza ewentualnym dociągnięciem do globalnego zestawu: enable
        # traktujemy addytywnie, cofnięcie go dla istniejącego wpisu NIE
        # wyłącza moda).
        if enable and existing.library_id not in load_activation_state().global_enabled:
            _set_global_enabled(existing.library_id, True)
        return existing, False

    root = fs.library_root()
    folder_name = _unique_folder_name(root, name)
    dest = root / folder_name
    copy_tree_with_progress(src, dest, progress_cb=progress_cb, cancel_event=cancel_event)

    entry = _register_entry(
        dest,
        folder_name=folder_name,
        content_hash=content_hash,
        modinfo_data=parse_modinfo(modinfo),
        source=source,
        from_datetime=from_datetime or datetime.now,
        game_version=game_version,
    )
    # Zapis do rejestru dopiero PO udanej kopii - przerwany import
    # (cancel/błąd IO) nie zostawia wpisu wskazującego nieistniejący folder.
    # Read-modify-write pod blokadą: równoległy pisarz (np. drugi import)
    # nie może zgubić naszego wpisu (i odwrotnie).
    with library.LIBRARY_LOCK:
        save_library_entries(load_library_entries() + [entry])
    if enable:
        _set_global_enabled(entry.library_id, True)
    return entry, True


def discover_mod_folders(root_folder: str | Path, *, max_depth: int = 6) -> list[Path]:
    """Znajduje wszystkie foldery zawierające ModInfo.xml pod wskazanym katalogiem.

    Jeśli wskazany katalog sam jest modem, zwracany jest tylko on. W pozostałych
    przypadkach skanowanie schodzi w głąb do ``max_depth`` poziomów i zatrzymuje
    się na znalezionym modem, dzięki czemu jego podkatalogi nie są traktowane
    jako kolejne mody.
    """
    root = Path(root_folder).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise NotADirectoryError(i18n_message("library.error.notDirectory", {"path": str(root)}))
    if find_modinfo(root) is not None:
        return [root]

    ignored_names = {
        ".git", ".hg", ".svn", "__pycache__", "node_modules",
        "build", "dist", ".cache", ".venv", "venv",
    }
    found: list[Path] = []
    visited: set[Path] = {root}
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack:
        current, depth = stack.pop()
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for child in children:
            try:
                if not child.is_dir() or child.is_symlink():
                    continue
                if child.name in ignored_names:
                    continue
                resolved = child.resolve(strict=False)
                if resolved in visited:
                    continue
                visited.add(resolved)
                if find_modinfo(child) is not None:
                    found.append(resolved)
                    continue
                stack.append((resolved, depth + 1))
            except OSError:
                continue

    return sorted(found, key=lambda p: str(p).lower())


def import_mod_to_library(
    source_folder: str | Path,
    *,
    source: str = "import",
    enable: bool = False,
    from_datetime=None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> LibraryModEntry:
    """Importuje jeden folder moda do Biblioteki. Zwraca wpis Biblioteki -
    istniejący (gdy identyczna zawartość już tam jest) albo nowo utworzony.

    source: etykieta pochodzenia zapisywana w LibraryModEntry.source
    (np. "download:<nazwa>", "import", "main_location").

    enable: czy od razu włączyć mod do globalnego zestawu aktywnego (używane
    przez pobieranie modpacków - tam intencją jest "chcę w to grać"; przy
    ręcznym imporcie drag&drop domyślnie nie).

    Rzuca FileNotFoundError (brak ModInfo.xml), NotADirectoryError,
    LibraryOperationError (pusta/nieprawidłowa nazwa folderu)."""
    entry, _was_new = _import_one_to_library(
        source_folder,
        source=source,
        enable=enable,
        from_datetime=from_datetime,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
    )
    return entry


def import_mods_to_library(
    source_folders: list[str | Path],
    *,
    source: str = "import",
    enable: bool = False,
    from_datetime=None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    game_version: str = "",
) -> ImportReport:
    """Wersja wsadowa importu (drag&drop, import wielu zaznaczonych folderów).
    Błędy pojedynczych folderów lądują w raporcie, reszta importuje się
    dalej - jeden zły folder nie zatrzymuje całej paczki."""
    report = ImportReport()
    total = len(source_folders)
    for index, folder in enumerate(source_folders):
        check_cancel(cancel_event)
        label = Path(folder).name
        try:
            entry, was_new = _import_one_to_library(
                folder,
                source=source,
                enable=enable,
                from_datetime=from_datetime,
                progress_cb=progress_cb,
                cancel_event=cancel_event,
                game_version=game_version,
            )
            if was_new:
                report.imported.append(entry)
            else:
                report.already_present.append(label)
        except OperationCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - pojedynczy zły folder nie zatrzymuje paczki
            report.errors.append(f"{label}: {exc}")
            install_log.error("LIBRARY import error: %s (%s)", label, exc)
        if progress_cb:
            progress_cb(index + 1, total, label)
    install_log.info(
        "LIBRARY import done (source=%s): %d imported, %d already present, %d errors",
        source, len(report.imported), len(report.already_present), len(report.errors))
    for entry in report.imported:
        install_log.info("LIBRARY imported: %s (%s) -> %s",
                         entry.title, entry.version or "?", entry.path)
    return report


def install_modpack_to_library(
    mods_root: str | Path,
    *,
    source: str = "download",
    enable: bool = True,
    from_datetime=None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    game_version: str = "",
) -> ImportReport:
    """Importuje CAŁY folder Mods pobranego modpacka do Biblioteki - każdy
    podfolder z ModInfo.xml to osobny mod. Zawartość bez ModInfo.xml jest po
    cichu pomijana - to nie mody; błąd pada tylko, gdy w folderze Mods nie ma
    ANI JEDNEGO moda. Import jest ADDYTYWNY - nie usuwa ani nie nadpisuje
    niczego, co już jest w Bibliotece (identyczna zawartość = dedup, konflikt
    nazw = sufiks). enable=True domyślnie: pobranie modpacka to intencja
    "chcę w to grać"."""
    root = Path(mods_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise NotADirectoryError(i18n_message("library.error.notModsDirectory", {"path": str(root)}))

    mod_folders: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and find_modinfo(child) is not None:
            mod_folders.append(child)
    if not mod_folders:
        raise LibraryOperationError(i18n_message("library.error.noModsInPack", {"path": str(root)}))

    install_log.info("LIBRARY install_modpack: root=%s, %d mod folders",
                     root, len(mod_folders))
    return import_mods_to_library(
        mod_folders,
        source=source,
        enable=enable,
        from_datetime=from_datetime,
        progress_cb=progress_cb,
        cancel_event=cancel_event,
        game_version=game_version,
    )


def remove_mods_from_library(
    entries: list[LibraryModEntry],
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> tuple[list[LibraryModEntry], list[str]]:
    """Usuwa mody z Biblioteki: foldery z library_root(), wpisy z rejestru
    i cały ich stan aktywacji (globalny + per instancja - ActivationState.
    remove_library_id sprząta oba naraz).

    Bezpiecznik: usuwać wolno wyłącznie ścieżki FIZYCZNIE leżące wewnątrz
    library_root() - sfałszowany/uszkodzony wpis nie pozwoli skasować
    niczego poza Biblioteką.

    Folder Mods instancji, który ma symlink do usuniętego moda, zostanie
    posprzątany przy następnym budowaniu (build_mods_folder czyta
    nieaktualne wpisy ze znacznika - zob. mod_activation.py)."""
    root = fs.library_root().resolve(strict=False)
    remaining_entries = load_library_entries()
    activation = load_activation_state()

    removed: list[LibraryModEntry] = []
    errors: list[str] = []
    to_delete: list[Path] = []

    for entry in entries:
        try:
            path = entry.path.resolve(strict=False)
            if root not in path.parents:
                raise ValueError(i18n_message("library.error.outsideRoot", {"path": str(path)}))
            if not path.exists():
                errors.append(i18n_message("library.error.folderMissing", {"title": entry.title, "path": str(path)}))
            else:
                to_delete.append(path)
            remaining_entries = [e for e in remaining_entries if e.library_id != entry.library_id]
            activation.remove_library_id(entry.library_id)
            removed.append(entry)
        except Exception as exc:  # noqa: BLE001 - pojedynczy wpis nie zatrzymuje reszty
            errors.append(f"{entry.title}: {exc}")

    for index, path in enumerate(to_delete):
        check_cancel(cancel_event)
        if progress_cb:
            progress_cb(index, len(to_delete), path.name)
        remove_tree_with_progress(path, cancel_event=cancel_event)

    if removed:
        with library.LIBRARY_LOCK:
            # rejestry czytane na początku mogły się zmienić w międzyczasie
            # (inny pisarz) - usuwamy z FRESH stanu, żeby nie przywrócić
            # cudzych wpisów
            remaining_entries = load_library_entries()
            for entry_ in removed:
                remaining_entries = [e for e in remaining_entries if e.library_id != entry_.library_id]
                activation.remove_library_id(entry_.library_id)
            save_library_entries(remaining_entries)
            save_activation_state(activation)
    if progress_cb:
        progress_cb(len(to_delete), len(to_delete), i18n_message("fileops.done"))
    return removed, errors


def is_game_modifying_library_content() -> bool:
    """True, gdy gra działa - wołane przez UI przed operacjami, które NIE
    mogą się wykonać podczas gry (usuwanie z Biblioteki: pliki Biblioteki są
    czytane przez grę przez symlinki folderów Mods instancji). Aktywacja
    (JSON) i import (addytywny) są bezpieczne i dozwolone."""
    return is_game_running()


def find_orphaned_library_folders() -> list[Path]:
    """Foldery fizycznie leżące w library_root() z ModInfo.xml, które NIE
    mają odpowiadającego wpisu w rejestrze (użytkownik wrzucił pliki ręcznie,
    przez menedżer plików). Rejestr, nie sama obecność plików na dysku, jest
    źródłem prawdy o tym, co jest w Bibliotece - ta funkcja pozwala jednym
    kliknięciem wciągnąć takie foldery do rejestru BEZ ponownego kopiowania
    (są już we właściwym miejscu).

    Dopasowanie po NAZWIE FOLDERU (nie po library_id - osierocony folder z
    definicji nie ma jeszcze żadnego), więc folder o nazwie identycznej z
    już zarejestrowanym wpisem NIE jest zgłaszany jako osierocony, żeby
    uniknąć dwuznaczności przy imporcie."""
    root = fs.library_root()
    if not root.is_dir():
        return []

    registered_folder_names = {entry.folder_name for entry in load_library_entries()}
    orphans: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name in registered_folder_names:
            continue
        if find_modinfo(child) is None:
            continue
        orphans.append(child)

    return orphans


def register_orphaned_folder(
    folder: Path, *, source: str, enable: bool, from_datetime=None,
) -> LibraryModEntry:
    """Rejestruje folder JUŻ leżący w library_root() w rejestrze - BEZ
    kopiowania plików (w odróżnieniu od import_mod_to_library(), który zawsze
    kopiuje z zewnętrznej lokalizacji - tutaj to byłoby kopiowanie folderu
    do samego siebie).

    Deduplikacja PO ZAWARTOŚCI wciąż obowiązuje - jeśli osierocony folder
    ma identyczną zawartość co mod już zarejestrowany pod inną nazwą
    folderu, zwracany jest istniejący wpis, a fizyczny duplikat NIE jest
    kasowany automatycznie (oba foldery są już W Bibliotece - automatyczne
    kasowanie byłoby zbyt inwazyjne; UI powinno poinformować osobno)."""
    modinfo = find_modinfo(folder)
    if modinfo is None:
        raise LibraryOperationError(i18n_message("library.error.modInfoMissing", {"path": str(folder)}))

    content_hash = compute_content_hash(folder)
    existing_entries = load_library_entries()
    duplicate = find_by_content_hash(existing_entries, content_hash)
    if duplicate is not None:
        return duplicate

    modinfo_data = parse_modinfo(modinfo)
    entry = _register_entry(
        folder,
        folder_name=folder.name,
        content_hash=content_hash,
        modinfo_data=modinfo_data,
        source=source,
        from_datetime=from_datetime or datetime.now,
    )
    with library.LIBRARY_LOCK:
        existing_entries.append(entry)
        save_library_entries(existing_entries)
    if enable:
        set_global_enabled(entry.library_id, True)
    return entry


def register_orphaned_folders(
    folders: list[Path],
    *,
    source: str = "import",
    enable: bool = False,
    from_datetime=None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> ImportReport:
    """Wersja wsadowa register_orphaned_folder() - ten sam wzorzec obsługi
    błędów co import_mods_to_library() (jeden zły folder nie zatrzymuje
    reszty paczki, trafia do report.errors)."""
    report = ImportReport()
    total = len(folders)
    for index, folder in enumerate(folders):
        check_cancel(cancel_event)
        label = folder.name
        try:
            entry = register_orphaned_folder(folder, source=source, enable=enable, from_datetime=from_datetime)
            report.imported.append(entry)
        except Exception as exc:  # noqa: BLE001 - pojedynczy zły folder nie zatrzymuje paczki
            report.errors.append(f"{label}: {exc}")
        if progress_cb:
            progress_cb(index + 1, total, label)
    return report


def update_entry_content(
    library_id: str,
    new_source_folder: str | Path,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> tuple[LibraryModEntry, bool]:
    """Aktualizacja moda W MIEJSCU (etap 11): nowa zawartość zastępuje
    zawartość istniejącego wpisu, a library_id, nazwa folderu i źródło
    zostają NIEZMIENNE.

    Dzięki temu stan aktywacji (globalny zestaw + wykluczenia/włączenia
    per instancja) i symlinki w folderach Mods instancji pozostają ważne
    bez żadnych przenosin - symlink wskazuje na ŚCIEŻKĘ folderu, więc
    podmiana zawartości pod tą ścieżką jest dla niego niewidoczna.

    Przebieg: nowa zawartość kopiowana do katalogu staging obok folderu,
    stary folder przemianowany na .update-*.old, staging wchodzi na jego
    miejsce, rejestr dostaje nowe metadane ModInfo + nowy content_hash.
    Awaria w środku = stary folder wraca na miejsce.

    Zwraca (zaktualizowany_wpis, czy_zawartość_się_zmieniła). Identyczna
    zawartość (content_hash) = bez operacji na dysku, (wpis, False)."""
    root = fs.library_root()
    new_source = Path(new_source_folder).expanduser().resolve(strict=False)
    if not new_source.is_dir():
        raise NotADirectoryError(i18n_message("library.error.notDirectory", {"path": str(new_source)}))
    if find_modinfo(new_source) is None:
        raise LibraryOperationError(i18n_message("library.error.modInfoMissing", {"path": str(new_source)}))

    with library.LIBRARY_LOCK:
        entries = load_library_entries()
        entry = library.find_by_library_id(entries, library_id)
        if entry is None:
            raise KeyError(i18n_message("library.error.entryMissing", {"id": library_id}))

        new_hash = compute_content_hash(new_source)
        if new_hash == entry.content_hash:
            return entry, False

        target = root / entry.folder_name
        staged = root / f".update-{entry.folder_name}.new"
        old = root / f".update-{entry.folder_name}.old"
        _fs_safe_rmtree(staged)
        _fs_safe_rmtree(old)

        try:
            copy_tree_with_progress(new_source, staged,
                                    progress_cb=progress_cb,
                                    cancel_event=cancel_event)
            if not target.exists():
                # stan uszkodzony (pliki zniknęły) - po prostu wstaw nowe
                staged.rename(target)
            else:
                target.rename(old)
                staged.rename(target)
        except (OperationCancelled, Exception):
            # anulowanie albo awaria kopiowania/przemianowania - przywróć
            # stary folder ZANIM cokolwiek posprzątamy (inaczej anulowanie
            # tuż po target.rename(old) skasowałoby oryginalnego moda)
            _restore_after_failed_update(staged, old, target)
            raise
        _fs_safe_rmtree(old)

        data = parse_modinfo(find_modinfo(target))
        entry.display_name = data.get("display_name", entry.display_name)
        entry.mod_name = data.get("mod_name", entry.mod_name)
        entry.author = data.get("author", entry.author)
        entry.version = data.get("version", entry.version)
        entry.description = data.get("description", entry.description)
        entry.content_hash = new_hash
        save_library_entries(entries)
        return entry, True


def _restore_after_failed_update(staged: Path, old: Path, target: Path) -> None:
    """Sprząta po nieudanej/anulowanej aktualizacji w miejscu: jeśli stary
    folder został już odsunięty do .old, wraca na miejsce target (a
    ewentualny częściowo wstawiony staging pod target znika). Dopiero
    potem usuwany jest katalog staging."""
    if old.exists():
        if target.exists():
            # staging zdążył wejść pod target, ale operacja i tak przerwana -
            # oryginał z .old ma pierwszeństwo
            _fs_safe_rmtree(target)
        if not target.exists():
            try:
                old.rename(target)
            except OSError as exc:  # pragma: no cover - nietypowe uprawnienia
                import logging
                logging.getLogger(__name__).error(
                    "Failed to restore %s -> %s: %s", old, target, exc)
                return   # zostaw .old nietknięte, żeby nie stracić moda
    _fs_safe_rmtree(staged)


def _fs_safe_rmtree(path: Path) -> None:
    """Usuwa katalog roboczy aktualizacji; best-effort, bez rzucania."""
    import shutil
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError as exc:  # pragma: no cover - nietypowe uprawnienia
        import logging
        logging.getLogger(__name__).warning(
            "Failed to remove %s: %s", path, exc)
