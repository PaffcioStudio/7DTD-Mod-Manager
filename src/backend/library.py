"""Model danych Biblioteki modów - port 1:1 ze starego projektu
(7dtd-mod-manager/library.py, etap 3 migracji), z podmienioną warstwą
zapisu na filesystem_service (atomiczne *.json w wspólnym root).

Model A: Biblioteka jest JEDYNYM trwałym miejscem przechowywania zawartości
modów. Dwie osobne struktury danych, dwa osobne pliki JSON:
- library.json (LibraryModEntry) - CO jest w Bibliotece: metadane,
  checksuma, skąd pochodzi. Zmienia się rzadko (dodanie/usunięcie moda).
- activation.json (ActivationState) - CO jest WŁĄCZONE, globalnie i per
  instancja. Zmienia się często (włącz/wyłącz przy każdej sesji). Rozdzielenie
  pozwala odtworzyć stan aktywacji bez re-skanowania zawartości Biblioteki.

Zawartość (folder library/) jest świadomie IZOLOWANA od żywej biblioteki
starego menedżera (decyzja użytkownika, etap 3) - scalenie należy do etapu
migracji starych lokalizacji.
"""
from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.modinfo import find_modinfo, parse_modinfo
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message

# Domyślna nazwa instancji, dopóki etap 6 nie wprowadzi realnego modelu
# Instance. Aktywacja jest już projektowana pod wiele instancji (stąd
# instance_id jako parametr wszędzie niżej), ale cała aplikacja operuje
# na dokładnie jednej, tej instancji.
DEFAULT_INSTANCE_ID = "main"

# Zapisy rejestru są atomowe (tmp+replace), ale sekwencje
# read-modify-write ("dociągnij listę, dopisz wpis, zapisz") przy dwóch
# równoległych pisarzach (np. import z folderu + kończące się pobieranie
# z URL) potrafiłyby zgubić wpis - ostatni zapis wygrywa. Wszystkie RMW
# po stronie library.py/library_ops.py trzymają więc tę blokadę (RLock,
# bo operacje się zagnieżdżają: import -> set_global_enabled).
LIBRARY_LOCK = threading.RLock()

_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MiB - balans między liczbą syscalli a zużyciem pamięci


# --- Metadane modów w Bibliotece ---

@dataclass(slots=True)
class LibraryModEntry:
    """Jeden mod w Bibliotece. library_id jest stabilnym identyfikatorem
    NIEZALEŻNYM od folder_name - przy migracji ze starych lokalizacji nazwa
    folderu mogła zostać zmieniona z powodu konfliktu (dwa różne mody o tej
    samej nazwie folderu), a library_id musi pozostać stabilne mimo to, żeby
    aktywacja (referencjonująca po library_id) nie "zgubiła" moda."""

    library_id: str
    folder_name: str
    display_name: str
    mod_name: str
    author: str = ""
    version: str = ""
    description: str = ""
    content_hash: str = ""
    source: str = ""  # skąd pochodzi (np. "main_location", "import", ścieżka)
    added_at: str = ""
    web_slug: str = ""  # slug na 7daystodiemods.com (sprawdzanie aktualizacji)
    game_version: str = ""  # wersja gry modu wg katalogu (slug, np. "v3"); "" = nieznana

    @property
    def path(self) -> Path:
        return fs.library_root() / self.folder_name

    @property
    def title(self) -> str:
        return self.display_name or self.folder_name


def compute_content_hash(folder: Path) -> str:
    """SHA-256 po zawartości WSZYSTKICH plików w folderze moda (nazwa
    względna + bajty), posortowanych deterministycznie po ścieżce
    względnej. Celowo NIE po (rozmiar, mtime) - te są zawodne przy
    migracji między systemami plików (kopiowanie zwykle resetuje mtime),
    więc dwie bit-identyczne kopie tego samego moda na różnych dyskach
    mogłyby dostać różny "odcisk" mimo identycznej zawartości.

    Deterministyczne niezależnie od kolejności zwracanej przez system
    plików (sortowanie) i od maszyny/OS (normalizacja separatora do "/")."""
    if not folder.is_dir():
        raise NotADirectoryError(i18n_message("library.error.notDirectory", {"path": str(folder)}))

    hasher = hashlib.sha256()
    files = sorted(
        (p for p in folder.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(folder).as_posix(),
    )
    for file_path in files:
        rel = file_path.relative_to(folder).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\x00")  # separator, żeby "ab"+"c" nie kolidowało z "a"+"bc"
        with file_path.open("rb") as f:
            while True:
                chunk = f.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def load_library_entries() -> list[LibraryModEntry]:
    data = fs.read_json(fs.library_metadata_path(), None)
    if not isinstance(data, dict):
        return []
    items = data.get("entries", [])
    entries: list[LibraryModEntry] = []
    if not isinstance(items, list):
        return entries
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(
                LibraryModEntry(
                    library_id=str(item.get("library_id", "")),
                    folder_name=str(item.get("folder_name", "")),
                    display_name=str(item.get("display_name", "")),
                    mod_name=str(item.get("mod_name", "")),
                    author=str(item.get("author", "")),
                    version=str(item.get("version", "")),
                    description=str(item.get("description", "")),
                    content_hash=str(item.get("content_hash", "")),
                    source=str(item.get("source", "")),
                    added_at=str(item.get("added_at", "")),
                    web_slug=str(item.get("web_slug", "")),
                    game_version=str(item.get("game_version", "")),
                )
            )
        except Exception:
            continue
    return entries


def save_library_entries(entries: list[LibraryModEntry]) -> None:
    with LIBRARY_LOCK:
        payload = {
            "entries": [
                {
                    "library_id": e.library_id,
                    "folder_name": e.folder_name,
                    "display_name": e.display_name,
                    "mod_name": e.mod_name,
                    "author": e.author,
                    "version": e.version,
                    "description": e.description,
                    "content_hash": e.content_hash,
                    "source": e.source,
                    "added_at": e.added_at,
                    "web_slug": e.web_slug,
                    "game_version": e.game_version,
                }
                for e in entries
            ]
        }
        fs.write_json(fs.library_metadata_path(), payload)


def find_by_content_hash(entries: list[LibraryModEntry], content_hash: str) -> LibraryModEntry | None:
    """Do wykrywania duplikatów: czy Biblioteka ma już mod o identycznej
    zawartości (niezależnie od nazwy folderu czy metadanych ModInfo)."""
    for entry in entries:
        if entry.content_hash == content_hash:
            return entry
    return None


def find_by_library_id(entries: list[LibraryModEntry], library_id: str) -> LibraryModEntry | None:
    for entry in entries:
        if entry.library_id == library_id:
            return entry
    return None


def register_folder_in_library(
    folder: Path,
    *,
    source: str,
    from_datetime,
) -> LibraryModEntry:
    """Buduje LibraryModEntry z folderu moda (musi zawierać modinfo.xml).
    Nie kopiuje ani nie przenosi żadnych plików - to WYŁĄCZNIE budowa
    metadanych z folderu, który wołający już umieścił pod library_root().

    from_datetime: wstrzykiwane wywołanie (zwykle datetime.now) zamiast
    zaimportowanego bezpośrednio - żeby testy mogły podać deterministyczny
    czas bez patchowania modułu datetime."""
    modinfo = find_modinfo(folder)
    if modinfo is None:
        raise FileNotFoundError(i18n_message("library.error.modInfoMissing", {"path": str(folder)}))

    data = parse_modinfo(modinfo)
    content_hash = compute_content_hash(folder)

    return LibraryModEntry(
        library_id=str(uuid.uuid4()),
        folder_name=folder.name,
        display_name=data.get("display_name", ""),
        mod_name=data.get("mod_name", ""),
        author=data.get("author", ""),
        version=data.get("version", ""),
        description=data.get("description", ""),
        content_hash=content_hash,
        source=source,
        added_at=from_datetime().isoformat(timespec="seconds"),
    )


# --- Stan aktywacji: globalna lista + wykluczenia per instancja ---

@dataclass(slots=True)
class ActivationState:
    """Globalna lista włączonych modów (global_enabled) + per-instancja
    wykluczenia (instance_exclusions) I włączenia (instance_inclusions).
    Każda instancja domyślnie dziedziczy cały global_enabled; wykluczenie
    w danej instancji wyłącza konkretny mod TYLKO dla niej, bez ruszania
    ustawień globalnych ani innych instancji.

    ROZSZERZONE 29.08.2026 w starym projekcie (ustalenia z użytkownikiem):
    "ulubione" mody - te celowo wyłączone globalnie - muszą dać się włączyć
    PUNKTOWO dla jednej instancji, bez włączania ich globalnie. Efektywny
    stan dla pary (mod, instancja) to cztery przypadki:
      - globalnie włączony, BEZ wykluczenia  → włączony
      - globalnie włączony, Z wykluczeniem   → wyłączony
      - globalnie wyłączony, BEZ włączenia   → wyłączony (domyślny stan
        "ulubionego" moda - instancja rodzi się "czysta")
      - globalnie wyłączony, Z włączeniem    → włączony (świadomy wybór)
    instance_exclusions i instance_inclusions dla tej samej pary są
    WZAJEMNIE WYKLUCZAJĄCE - set_*() pilnuje tego przy każdej zmianie.

    Przechowywane jako set[str] z library_id modów (nie folder_name -
    stabilność przy zmianie nazwy folderu, zob. LibraryModEntry)."""

    global_enabled: set[str] = field(default_factory=set)
    instance_exclusions: dict[str, set[str]] = field(default_factory=dict)
    instance_inclusions: dict[str, set[str]] = field(default_factory=dict)

    def is_enabled_for(self, library_id: str, instance_id: str = DEFAULT_INSTANCE_ID) -> bool:
        if library_id in self.global_enabled:
            excluded = self.instance_exclusions.get(instance_id, set())
            return library_id not in excluded
        included = self.instance_inclusions.get(instance_id, set())
        return library_id in included

    def enabled_for_instance(self, instance_id: str = DEFAULT_INSTANCE_ID) -> set[str]:
        """Zbiór library_id efektywnie włączonych dla instancji:
        (global_enabled pomniejszony o wykluczenia) PLUS punktowe włączenia."""
        excluded = self.instance_exclusions.get(instance_id, set())
        included = self.instance_inclusions.get(instance_id, set())
        return (self.global_enabled - excluded) | included

    def set_global_enabled(self, library_id: str, enabled: bool) -> None:
        if enabled:
            self.global_enabled.add(library_id)
            # Włączenie globalne czyni punktowe włączenia zbędnymi - sprzątamy,
            # żeby instance_inclusions nie rosło martwymi wpisami.
            for instance_id in list(self.instance_inclusions.keys()):
                self._discard_from_bucket(self.instance_inclusions, instance_id, library_id)
        else:
            self.global_enabled.discard(library_id)
            # Wyłączenie globalne czyni wykluczenia per-instancja zbędnymi.
            for instance_id in list(self.instance_exclusions.keys()):
                self._discard_from_bucket(self.instance_exclusions, instance_id, library_id)

    def set_instance_exclusion(self, library_id: str, instance_id: str, excluded: bool) -> None:
        bucket = self.instance_exclusions.setdefault(instance_id, set())
        if excluded:
            bucket.add(library_id)
            # Wykluczenie i punktowe włączenie tej samej pary są sprzeczne -
            # nie mogą współistnieć (zabezpieczenie spójności).
            self._discard_from_bucket(self.instance_inclusions, instance_id, library_id)
        else:
            bucket.discard(library_id)
            if not bucket:
                del self.instance_exclusions[instance_id]

    def set_instance_inclusion(self, library_id: str, instance_id: str, included: bool) -> None:
        """Włącza (albo cofa) moda PUNKTOWO dla jednej instancji, niezależnie
        od stanu globalnego. Ma efekt tylko dla modów WYŁĄCZONYCH globalnie;
        wołanie dla już włączonego jest nieszkodliwe."""
        bucket = self.instance_inclusions.setdefault(instance_id, set())
        if included:
            bucket.add(library_id)
            self._discard_from_bucket(self.instance_exclusions, instance_id, library_id)
        else:
            bucket.discard(library_id)
            if not bucket:
                del self.instance_inclusions[instance_id]

    @staticmethod
    def _discard_from_bucket(
        buckets: dict[str, set[str]], instance_id: str, library_id: str
    ) -> None:
        """Usuwa library_id z buckets[instance_id] i sprząta klucz instance_id,
        jeśli bucket opustoszał - inaczej zostaje martwy pusty set() w słowniku
        (bug znaleziony testem 29.08.2026: discard() nie usuwa pustego bucketa)."""
        bucket = buckets.get(instance_id)
        if bucket is None:
            return
        bucket.discard(library_id)
        if not bucket:
            del buckets[instance_id]

    def remove_instance(self, instance_id: str) -> None:
        """Sprząta wykluczenia I włączenia instancji usuniętej z rejestru -
        żeby plik aktywacji nie trzymał martwych wpisów."""
        self.instance_exclusions.pop(instance_id, None)
        self.instance_inclusions.pop(instance_id, None)

    def remove_library_id(self, library_id: str) -> None:
        """Sprząta wszystkie ślady po modzie usuniętym z Biblioteki."""
        self.global_enabled.discard(library_id)
        for buckets in (self.instance_exclusions, self.instance_inclusions):
            for instance_id in list(buckets.keys()):
                self._discard_from_bucket(buckets, instance_id, library_id)


def load_activation_state() -> ActivationState:
    data = fs.read_json(fs.activation_state_path(), None)
    if not isinstance(data, dict):
        return ActivationState()

    global_enabled = set(
        str(x) for x in data.get("global_enabled", []) if isinstance(x, str)
    )
    instance_exclusions: dict[str, set[str]] = {}
    raw_exclusions = data.get("instance_exclusions", {})
    if isinstance(raw_exclusions, dict):
        for instance_id, ids in raw_exclusions.items():
            if isinstance(ids, list):
                instance_exclusions[str(instance_id)] = set(
                    str(x) for x in ids if isinstance(x, str)
                )

    # instance_inclusions: klucz NOWY w starym projekcie (29.08.2026) - brak
    # w starszych plikach jest oczekiwany, .get(..., {}) daje pusty słownik.
    instance_inclusions: dict[str, set[str]] = {}
    raw_inclusions = data.get("instance_inclusions", {})
    if isinstance(raw_inclusions, dict):
        for instance_id, ids in raw_inclusions.items():
            if isinstance(ids, list):
                instance_inclusions[str(instance_id)] = set(
                    str(x) for x in ids if isinstance(x, str)
                )

    return ActivationState(
        global_enabled=global_enabled,
        instance_exclusions=instance_exclusions,
        instance_inclusions=instance_inclusions,
    )


def save_activation_state(state: ActivationState) -> None:
    with LIBRARY_LOCK:
        payload = {
            "global_enabled": sorted(state.global_enabled),
            "instance_exclusions": {
                instance_id: sorted(ids)
                for instance_id, ids in state.instance_exclusions.items()
                if ids  # nie zapisuj pustych wpisów, żeby plik się nie zaśmiecał
            },
            "instance_inclusions": {
                instance_id: sorted(ids)
                for instance_id, ids in state.instance_inclusions.items()
                if ids
            },
        }
        fs.write_json(fs.activation_state_path(), payload)
