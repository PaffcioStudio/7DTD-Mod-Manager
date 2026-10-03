"""Model danych instancji gry - port 1:1 ze starego projektu
(7dtd-mod-manager/instances.py, etap 6 migracji), z zapisem przez
filesystem_service (instances.json, atomiczne).

Instancja to wyłącznie mechanizm IZOLACJI DANYCH użytkownika gry: osobny
katalog, do którego gra (przez argument startowy -UserDataFolder=Z:/...)
kieruje Saves/, Mods/, datastorage/ i cache - uruchamiana bez ryzyka
nadpisania danych innej instancji. Instancja NIE jest overhaulem ani
modpackiem.

Trzy warstwy:
1. MODEL + STORAGE (Instance, instances.json) - nazwa, ścieżka danych,
   flagi startowe jako pola bool (checkboxy w UI, nie ręczny tekst).
2. URUCHAMIANIE (launch_instance_via_steam) - delegacja do
   game_process.launch_game_via_steam() z danymi instancji; tu wchodzi
   konwersja unix->Wine (build_launch_args -> to_wine_path).
   Instancja bez game_branch używa `steam -applaunch`; instancja z
   game_branch uruchamia pobraną kopię Windows przez Proton z aktywnym
   klientem Steam.
3. MODY PER INSTANCJA (build_mods_for_instance) - folder Mods/ instancji
   jest GENEROWANY z Biblioteki wg stanu aktywacji
   (ActivationState.enabled_for_instance).

Instancja DOMYŚLNA ("Główna"): data_dir == "" = brak -UserDataFolder -
gra używa swojej domyślnej lokalizacji danych (zachowanie jak bez
menedżera). Jest nieusuwalna (punkt odniesienia). build_mods_for_instance
dla niej odmawia - jej mody zarządza zakładka Mody (globalna aktywacja).

Identyfikatory: instance_id to stabilny UUID niezależny od nazwy;
pierwsza, automatyczna instancja dostaje id "main" - równe
DEFAULT_INSTANCE_ID z library.py, żeby wykluczenia z pliku aktywacji
od razu odnosiły się do tej instancji.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.game_process import (
    GameProcessInfo,
    build_launch_args,
    find_game_processes,
    format_launch_args_for_steam,
    launch_game_via_steam,
)
from backend.library import (
    DEFAULT_INSTANCE_ID,
    ActivationState,
    LibraryModEntry,
    load_activation_state,
    save_activation_state,
)
from backend.mod_activation import (
    ActivationEntry,
    BuildResult,
    build_mods_folder,
)
from backend.fileops import remove_tree_with_progress
from backend.wine_paths import to_wine_path
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message

DEFAULT_INSTANCE_NAME = "Główna"

# Podstawowa transliteracja PL -> ASCII do domyślnej propozycji ścieżki
# instancji z jej nazwy ("Overhaul Ciężki" -> "overhaul-ciezki").
_PL_TRANSLIT = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
})


class InstanceError(Exception):
    """Błąd operacji na rejestrze instancji (walidacja, usuwanie)."""


# --- Model ---

@dataclass(slots=True)
class Instance:
    """Jedna instancja gry. data_dir == "" to instancja DOMYŚLNA (bez
    izolacji danych), każda inna wartość - bezwzględna ścieżka unixowa
    katalogu danych. Flagi jako osobne pola bool (checkboxy w UI, nie
    ręcznie wpisywany tekst - literówka we fladze nie wywoła błędu gry)."""

    instance_id: str
    name: str
    data_dir: str = ""
    flag_noeos: bool = True
    flag_skip_news_screen: bool = True
    flag_skip_intro: bool = True
    created_at: str = ""
    # flag_noeac na KOŃCU listy pól (lekcja ze starego projektu: wstawienie
    # pola w środku przesunęło semantykę pozycyjnych konstruktorów) -
    # domyślnie False, czyli EAC włączony.
    flag_noeac: bool = False
    # description: DODANE w tym projekcie (etap 6, analogia do pola author
    # w mm-library.json) - stary schemat go nie miał; na końcu listy.
    description: str = ""
    # game_branch: DODANE (pobieranie wersji gry przez DepotDownloader) -
    # przypisana wersja gry (branch Steam, np. "v2.6"); "" = bez przypisania
    # (instalacja ze Steam / branch publiczny). Na końcu listy pól.
    game_branch: str = ""
    # ulubiona instancja: zawsze pokazywana na górze i chroniona przed usunięciem
    favorite: bool = False

    @property
    def is_default(self) -> bool:
        """Czy instancja bez izolacji danych (brak -UserDataFolder)."""
        return not self.data_dir.strip()

    @property
    def data_path(self) -> Path | None:
        if self.is_default:
            return None
        return Path(self.data_dir).expanduser()

    @property
    def mods_dir(self) -> Path | None:
        """Folder Mods/ tej instancji; None dla domyślnej."""
        data = self.data_path
        return data / "Mods" if data is not None else None

    @property
    def is_overhaul(self) -> bool:
        """Czy instancja została utworzona automatycznie dla Overhaul."""
        return self.description.strip().casefold().startswith("overhaul ")

    def launch_args(self) -> list[str]:
        """Argumenty startowe gry tej instancji (konwersja unix->Wine w
        build_launch_args)."""
        return build_launch_args(
            None if self.is_default else self.data_dir,
            noeos=self.flag_noeos,
            noeac=self.flag_noeac,
            skip_news_screen=self.flag_skip_news_screen,
            skip_intro=self.flag_skip_intro,
        )

    def launch_command_preview(self) -> str:
        """Czytelny podgląd celu uruchomienia instancji.

        Dla przypisanego game_branch pokazujemy konkretną kopię, bo nie jest
        ona uruchamiana przez `steam -applaunch`."""
        if self.game_branch:
            return (
                f"Pobrana kopia: ~/.7dtd_modmanager/game-versions/{self.game_branch}/"
                "7DaysToDie.exe (Proton)"
            )
        args = self.launch_args()
        if not args:
            return "%command%"
        return "%command% " + format_launch_args_for_steam(args)

    def flags_summary(self) -> list[str]:
        """Aktywne flagi jako teksty (podgląd w UI)."""
        flags: list[str] = []
        if self.flag_noeos:
            flags.append("-noeos")
        if self.flag_noeac:
            flags.append("-noeac")
        if self.flag_skip_news_screen:
            flags.append("-skipnewsscreen=true")
        if self.flag_skip_intro:
            flags.append("-skipintro")
        return flags


# --- Storage (instances.json) ---

def _instance_to_dict(instance: Instance) -> dict:
    return {
        "instance_id": instance.instance_id,
        "name": instance.name,
        "description": instance.description,
        "data_dir": instance.data_dir,
        "flags": {
            "noeos": instance.flag_noeos,
            "noeac": instance.flag_noeac,
            "skip_news_screen": instance.flag_skip_news_screen,
            "skip_intro": instance.flag_skip_intro,
        },
        "created_at": instance.created_at,
        "game_branch": instance.game_branch,
        "favorite": instance.favorite,
    }


def _instance_from_dict(item: dict) -> Instance:
    # Flagi zapisane płasko (nadzbiór) albo w pod-słowniku "flags" -
    # czytanie odporne na obie formy, zapis używa "flags".
    flags = item.get("flags", {})
    if not isinstance(flags, dict):
        flags = {}
    description = str(item.get("description", ""))
    game_branch = str(item.get("game_branch", ""))
    imported_pack = description.strip().casefold().startswith(("overhaul ", "zestaw "))
    return Instance(
        instance_id=str(item.get("instance_id", "")),
        name=str(item.get("name", "")),
        data_dir=str(item.get("data_dir", "")),
        flag_noeos=(True if imported_pack else bool(item.get("noeos", flags.get("noeos", False)))),
        # Importowane Overhaule/zestawy mają bezpieczne flagi zawsze włączone:
        # nie ma sensu uruchamiać ich z EOS/EAC.
        flag_noeac=(True if imported_pack else bool(item.get("noeac", flags.get("noeac", False)))),
        flag_skip_news_screen=bool(
            item.get("skip_news_screen", flags.get("skip_news_screen", False))
        ),
        flag_skip_intro=bool(item.get("skip_intro", flags.get("skip_intro", False))),
        created_at=str(item.get("created_at", "")),
        description=description,
        game_branch=game_branch,
        favorite=bool(item.get("favorite", False)),
    )


def load_instances() -> list[Instance]:
    """Wczytuje rejestr z instances.json; odporny na brak pliku i
    uszkodzony JSON. SAM SIĘ NAPRAWIA: pusty rejestr dopisuje instancję
    domyślną "Główna" (id "main") - każdy czytelnik dostaje zawsze co
    najmniej jedną sensowną instancję."""
    data = fs.read_json(fs.instances_path(), None)
    instances: list[Instance] = []
    if isinstance(data, dict):
        items = data.get("instances", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    instances.append(_instance_from_dict(item))

    if not instances:
        instances = [make_default_instance()]
        try:
            save_instances(instances)
        except OSError:
            pass

    # Ulubione zawsze na górze; sortowanie jest stabilne, więc kolejność
    # pozostałych instancji nie przeskakuje bez potrzeby.
    instances = sorted(instances, key=lambda i: not i.favorite)
    return instances


def save_instances(instances: list[Instance]) -> None:
    """Zapisuje rejestr (pełny overwrite, atomicznie przez fs)."""
    payload = {"instances": [_instance_to_dict(i) for i in instances]}
    fs.write_json(fs.instances_path(), payload)


def make_default_instance(from_datetime=None) -> Instance:
    """Instancja domyślna: "Główna", data_dir="", flagi domyślnie
    WŁĄCZONE - wzorzec komendy referencyjnej użytkownika
    ("-noeos -skipnewsscreen=true -skipintro %command%"). instance_id
    celowo = DEFAULT_INSTANCE_ID z library.py (kompatybilność aktywacji)."""
    now_fn = from_datetime or datetime.now
    return Instance(
        instance_id=DEFAULT_INSTANCE_ID,
        name=DEFAULT_INSTANCE_NAME,
        data_dir="",
        flag_noeos=True,
        flag_skip_news_screen=True,
        flag_skip_intro=True,
        created_at=now_fn().isoformat(timespec="seconds"),
    )


# --- Walidacja (przed zapisem do rejestru) ---

def normalize_data_dir(value: str) -> str:
    """expanduser + resolve (bez wymagania istnienia) - żeby dwie formy
    tej samej ścieżki nie założyły dwóch instancji na ten sam katalog.
    Puste wejście -> puste wyjście (instancja domyślna)."""
    stripped = (value or "").strip()
    if not stripped:
        return ""
    return str(Path(stripped).expanduser().resolve(strict=False))


def validate_instance_name(
    name: str, instances: list[Instance], *, current_id: str | None = None,
) -> str | None:
    """Komunikat błędu albo None. current_id = id edytowanej instancji
    (jej własna nazwa nie liczy się do konfliktu)."""
    stripped = (name or "").strip()
    if not stripped:
        return i18n_message("instances.nameEmpty")
    folded = stripped.casefold()
    for other in instances:
        if other.instance_id == current_id:
            continue
        if other.name.casefold() == folded:
            return i18n_message("instances.nameDuplicate", {"name": stripped})
    return None


def validate_instance_data_dir(
    data_dir: str, instances: list[Instance], *, current_id: str | None = None,
) -> str | None:
    """Komunikat błędu albo None. Wymogi: bezwzględna (to_wine_path rzuciłby
    ValueError - wolimy czytelny komunikat teraz niż wyjątek przy starcie
    gry), nie root, nie duplikat innej instancji i - przy tworzeniu nowej
    instancji - nie wskazuje już istniejącego katalogu. Bezwzględność sprawdzana
    PRZED normalizacją (resolve zamieniłby względną na absolutną względem
    CWD i sprawdzenie po normalizacji byłoby martwe). Przy edycji istniejąca
    ścieżka bieżącej instancji pozostaje dozwolona; zmiana na obcy istniejący
    katalog jest blokowana jako zabezpieczenie przed przypadkowym użyciem
    cudzych danych.
    """
    stripped = (data_dir or "").strip()
    if not stripped:
        return None  # pusta ścieżka = domyślna lokalizacja
    if not Path(stripped).is_absolute():
        return i18n_message("instances.dataPathAbsolute")
    normalized = normalize_data_dir(stripped)
    if normalized == "/":
        return i18n_message("instances.dataPathRoot")
    for other in instances:
        if other.instance_id == current_id:
            continue
        if normalize_data_dir(other.data_dir) == normalized:
            return i18n_message("instances.dataPathDuplicate", {"name": other.name})

    path = Path(normalized)
    if path.exists():
        if current_id is None:
            return i18n_message("instances.dataPathExists", {"path": str(path)})
        current = find_instance(instances, current_id)
        current_path = normalize_data_dir(current.data_dir) if current else ""
        if current_path != normalized:
            return i18n_message("instances.targetExists", {"path": str(path)})
    return None


def suggest_data_dir_for_name(name: str) -> Path:
    """Domyślna propozycja ścieżki nowej instancji z jej nazwy:
    <root>/instances/<slug>. Slug zachowuje kropki w środku, więc np.
    ``15.5`` trafia do ``instances/15.5`` zamiast ``instances/15-5``.
    Kropki na początku są usuwane, aby nazwa typu ``.fajnagierka`` nie
    tworzyła ukrytego katalogu. Pozostałe znaki poza [a-z0-9._-] są
    zamieniane na "-"."""
    slug = (name or "").strip().lower().translate(_PL_TRANSLIT)
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug)
    slug = slug.lstrip(".").strip("-")
    if not slug:
        slug = "instancja"
    return fs.instances_root() / slug


# --- Operacje na rejestrze ---

def create_instance(
    name: str,
    data_dir: str,
    *,
    noeos: bool = True,
    noeac: bool = False,
    skip_news_screen: bool = True,
    skip_intro: bool = True,
    description: str = "",
    game_branch: str = "",
    instances: list[Instance] | None = None,
    from_datetime=None,
) -> Instance:
    """Buduje nową instancję po walidacji nazwy i ścieżki. Rzuca
    InstanceError z komunikatem do pokazania w UI."""
    registry = instances if instances is not None else load_instances()
    error = validate_instance_name(name, registry)
    if error:
        raise InstanceError(error)
    error = validate_instance_data_dir(data_dir, registry)
    if error:
        raise InstanceError(error)

    now = from_datetime or datetime.now
    return Instance(
        instance_id=str(uuid.uuid4()),
        name=name.strip(),
        data_dir=normalize_data_dir(data_dir),
        flag_noeos=noeos,
        flag_noeac=noeac,
        flag_skip_news_screen=skip_news_screen,
        flag_skip_intro=skip_intro,
        description=description,
        game_branch=(game_branch or "").strip()[:40],
        created_at=now().isoformat(timespec="seconds"),
    )


def find_instance(instances: list[Instance], instance_id: str) -> Instance | None:
    for instance in instances:
        if instance.instance_id == instance_id:
            return instance
    return None


def default_instance(instances: list[Instance]) -> Instance | None:
    """Pierwsza instancja bez izolacji danych (data_dir == "")."""
    for instance in instances:
        if instance.is_default:
            return instance
    return None


def delete_instance(
    instances: list[Instance],
    instance_id: str,
    *,
    remove_data: bool = False,
    progress_cb=None,
    cancel_event=None,
) -> list[Instance]:
    """Usuwa instancję z rejestru. Celowo NIE rusza plików katalogu danych
    (Saves itd. zostają - ich usuwanie to decyzja użytkownika w dialogu).
    Czyści wykluczenia/włączenia instancji z pliku aktywacji. Instancja
    domyślna jest nieusuwalna. Zwraca nową listę (bez mutacji wejściowej).

    TWARDY ZABEZPIECZENIE: usuwanie (nawet samego wpisu z rejestru) jest
    zablokowane, gdy gra działa - instancja może być w użyciu przez proces
    gry (folder danych, symlinki Mods)."""
    if find_game_processes():
        raise InstanceError(i18n_message("instances.delete.running"))
    target = find_instance(instances, instance_id)
    if target is None:
        raise InstanceError(i18n_message("instances.delete.notFound"))
    if target.is_default:
        raise InstanceError(i18n_message("instances.delete.default"))

    # opcjonalne usuniecie folderu danych - jawna decyzja uzytkownika
    # (checkbox w dialogu usuwania); bezpiecznik sciezki jak w modpacks.py
    if remove_data:
        data_path = target.data_path
        if data_path is None:
            raise InstanceError(i18n_message("instances.delete.defaultData"))
        resolved = data_path.resolve(strict=False)
        home = Path.home().resolve(strict=False)
        if resolved in {Path("/").resolve(strict=False), home} or len(resolved.parts) < 3:
            raise InstanceError(i18n_message("instances.delete.denied", {"path": str(resolved)}))
        remove_tree_with_progress(resolved, progress_cb=progress_cb, cancel_event=cancel_event)

    remaining = [i for i in instances if i.instance_id != instance_id]
    save_instances(remaining)

    try:
        state = load_activation_state()
        if instance_id in state.instance_exclusions or instance_id in state.instance_inclusions:
            state.remove_instance(instance_id)
            save_activation_state(state)
    except OSError:
        pass
    return remaining


# --- Uruchamianie ---

def launch_instance_via_steam(instance: Instance) -> bool:
    """Uruchamia instancję.

    Bez game_branch: `steam -applaunch` dla zainstalowanej wersji Steam.
    Z game_branch: bezpośrednia kopia pobrana przez DepotDownloader uruchomiona
    przez Proton, z aktywnym klientem Steam i osobnym prefixem Wine.
    """
    return launch_game_via_steam(
        None if instance.is_default else instance.data_dir,
        noeos=instance.flag_noeos,
        noeac=instance.flag_noeac,
        skip_news_screen=instance.flag_skip_news_screen,
        skip_intro=instance.flag_skip_intro,
        game_branch=instance.game_branch,
    )


# --- Folder Mods instancji (Model A: generowany z Biblioteki) ---

def build_mods_for_instance(
    instance: Instance,
    library_entries: list[LibraryModEntry],
    activation_state: ActivationState,
    *,
    progress_cb=None,
    cancel_event=None,
) -> BuildResult:
    """Buduje/odświeża folder Mods/ instancji z izolowanym katalogiem na
    podstawie Biblioteki i stanu aktywacji: symlink z fallbackiem do kopii,
    atomowo, idempotentnie (mod_activation.py). Katalog danych instancji
    jest tworzony, jeśli jeszcze nie istnieje.

    Instancja domyślna podnosi ValueError: jej mody to globalna aktywacja
    zarządzana zakładką Mody (build Mods = zdublowany mechanizm)."""
    if instance.is_default:
        raise ValueError(i18n_message("instances.mods.default"))

    mods_dir = instance.mods_dir
    assert mods_dir is not None
    mods_dir.parent.mkdir(parents=True, exist_ok=True)

    enabled = activation_state.enabled_for_instance(instance.instance_id)
    entries = [
        ActivationEntry(entry.folder_name, entry.path)
        for entry in library_entries
        if entry.library_id in enabled
    ]
    return build_mods_folder(entries, mods_dir)


# --- Wykrywanie działającej instancji ---

def normalize_user_data_folder_value(value: str | None) -> str:
    """Normalizuje wartość -UserDataFolder= do postaci porównywalnej:
    bez cudzysłowów, backslashe -> "/", case-insensitive, bez końcowego
    ukośnika. Żyje w JEDNYM miejscu, bo oba kierunki porównania muszą
    przechodzić identyczną obróbkę."""
    if not value:
        return ""
    normalized = value.replace("\\", "/").strip().strip('"').strip()
    while normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized.casefold()


def _instance_user_data_folder_candidates(instance: Instance) -> set[str]:
    """Znormalizowane postacie ścieżki danych instancji: forma Wine (Z:),
    surowa unixowa (gra uruchomiona natywnie ręcznie) i warianty z
    rozwiniętymi symlinkami (resolve)."""
    raw = instance.data_dir.strip()
    if not raw:
        return set()

    candidates: set[str] = set()
    path = Path(raw).expanduser()
    for variant in (path, path.resolve(strict=False)):
        as_str = str(variant)
        candidates.add(normalize_user_data_folder_value(to_wine_path(as_str)))
        candidates.add(normalize_user_data_folder_value(as_str))
    candidates.discard("")
    return candidates


def match_instance_by_user_data_folder(
    value: str | None, instances: list[Instance],
) -> Instance | None:
    """Dopasowuje surową wartość -UserDataFolder= do instancji. None, gdy
    pusta albo nie pasuje do żadnej (gra uruchomiona ręcznie z własną
    ścieżką danych)."""
    normalized = normalize_user_data_folder_value(value)
    if not normalized:
        return None
    for instance in instances:
        if instance.is_default:
            continue
        if normalized in _instance_user_data_folder_candidates(instance):
            return instance
    return None


@dataclass(slots=True)
class RunningGameInfo:
    """Wynik wykrycia działającej gry. instance == None + user_data_folder
    != None = gra działa z niepasującą do żadnej instancji ścieżką (uruchomiona
    ręcznie); instance == None + user_data_folder is None = brak instancji
    domyślnej w rejestrze, a gra działa bez flagi (de facto na domyślnej
    lokalizacji)."""

    processes: list[GameProcessInfo]
    instance: Instance | None
    user_data_folder: str | None

    @property
    def primary_process(self) -> GameProcessInfo | None:
        """Reprezentatywny proces: pierwszy z -UserDataFolder (na nim opiera
        się rozpoznanie instancji), w razie braku - pierwszy dopasowany."""
        for process in self.processes:
            if process.user_data_folder:
                return process
        return self.processes[0] if self.processes else None


def detect_running_game(instances: list[Instance]) -> RunningGameInfo | None:
    """Skanuje procesy i rozpoznaje, KTÓRA instancja działa: wartość
    -UserDataFolder= procesu wskazuje instancję o tej ścieżce danych; jej
    BRAK = domyślna lokalizacja danych = instancja domyślna. Zwraca None,
    gdy gra nie działa. Świadome ograniczenie: przy wielu procesach z różnymi
    flagami rozpoznajemy pierwszą wartość (Steam i tak uruchamia jedną kopię
    na AppID)."""
    processes = find_game_processes()
    if not processes:
        return None

    with_folder = [p for p in processes if p.user_data_folder]
    if not with_folder:
        return RunningGameInfo(
            processes=processes,
            instance=default_instance(instances),
            user_data_folder=None,
        )

    value = with_folder[0].user_data_folder
    return RunningGameInfo(
        processes=processes,
        instance=match_instance_by_user_data_folder(value, instances),
        user_data_folder=value,
    )
