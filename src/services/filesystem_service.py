"""Filesystem paths and JSON helpers - the single source of storage locations.

All app data lives under ``~/.7dtd_modmanager`` - the SAME root the legacy
PyQt6 manager uses (decision 19.09.2026, stage 1 of the migration plan).
Pliki tej aplikacji mają normalne nazwy (settings.json, library.json,
instances.json, ...) - decyzja 28.09.2026: stary menedżer został wycofany,
katalog użytkownik sprząta ręcznie.

Files created by earlier builds of this UI live in the XDG config dir
(``~/.config/7dtd-mod-manager``); :func:`read_json_migrated` picks them up
once and callers persist them at the new path on their next save.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DATA_DIR_NAME = ".7dtd_modmanager"
# previous home of THIS UI's files (XDG) - read-only fallback
LEGACY_UI_DIR_NAME = "7dtd-mod-manager"


def home_dir() -> Path:
    return Path.home()


def data_dir() -> Path:
    """Shared data root: ~/.7dtd_modmanager."""
    root = Path.home() / DATA_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_dir() -> Path:
    """Cache metadanych z 7daystodiemods.com (D9, etap 9). Odtworzenie
    = tanie zapytania API, więc TTL może być agresywniejszy niż pobierania."""
    root = data_dir() / "cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def logs_dir() -> Path:
    return data_dir() / "logs"


def downloads_dir() -> Path:
    """Pobrane archiwa modów/modpacków (D9, etap 9). DOMYŚLNIE nic tu
    nie jest kasowane automatycznie - transfer jest limitowany, dysk nie."""
    root = data_dir() / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def staging_dir() -> Path:
    """Katalog roboczy pobierania/wypakowywania (``mm-dl-*``, ``mm-mod-*``).

    Leży pod katalogiem danych aplikacji (a NIE w systemowym /tmp), bo:
    - /tmp bywa tmpfs-em (RAM) albo małą partycją systemową - wielogigabajtowy
      ZIP overhaulu (np. Undead Legacy ~7,5 GB + wypakowana kopia) tam nie
      mieści się i kończył się ``[Errno 28] No space left on device``;
    - ten sam system plików co downloads/ i instances/ pozwala PRZENOSIĆ
      (rename, bez kopiowania) archiwum i wypakowane mody zamiast kopiować.
    """
    root = data_dir() / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_mods_dir() -> Path:
    """Default user mods folder - same location the legacy manager uses."""
    return data_dir() / "mods"


def library_root() -> Path:
    """Mod library CONTENT dir (LibraryModEntry folders)."""
    return data_dir() / "library"


def instances_root() -> Path:
    """Default parent dir for instance DATA dirs (suggested at instance
    creation; the user may pick any location)."""
    return data_dir() / "instances"


def backups_root() -> Path:
    """Parent dir for instance backup folders (one folder per instance id)."""
    return data_dir() / "backups"


def legacy_modpacks_root() -> Path:
    """Pre-v31 location of the backup folders (they were called "modpacks").

    Only used by the one-time migration into :func:`backups_root`.
    """
    return data_dir() / "modpacks"


def profiles_dir() -> Path:
    """Centralna biblioteka profili 7DTD (Presets/*.xml)."""
    root = data_dir() / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


# --------------------------------------------------------------------- #
# files owned by this app                                                #
# --------------------------------------------------------------------- #
def settings_path() -> Path:
    return data_dir() / "settings.json"


def profiles_path() -> Path:
    return data_dir() / "profiles.json"


def mod_state_path() -> Path:
    return data_dir() / "state.json"


def library_metadata_path() -> Path:
    """Stage 3 of the migration plan (biblioteka modów)."""
    return data_dir() / "library.json"


def activation_state_path() -> Path:
    """Stage 3 of the migration plan (aktywacja)."""
    return data_dir() / "activation.json"


def instances_path() -> Path:
    """Stage 5 of the migration plan (instancje)."""
    return data_dir() / "instances.json"


def modpacks_path() -> Path:
    """Stage 7 of the migration plan (modpacki)."""
    return data_dir() / "modpacks.json"


def downloads_queue_path() -> Path:
    """Stages 4/9 of the migration plan (kolejka pobierania)."""
    return data_dir() / "downloads.json"


def profile_state_path() -> Path:
    """Stan przypisania centralnych profili do instancji."""
    return data_dir() / "profile-state.json"


def installed_archives_path() -> Path:
    """Rejestr archiwów z downloads/ zainstalowanych do Biblioteki
    (etap 9 krok B, D9) - baza dla auto-czyszczenia "tylko zainstalowane"."""
    return data_dir() / "installed-archives.json"


def thumbs_dir() -> Path:
    """Miniatury ikon modów z 7daystodiemods.com (etap 17) - pliki
    <library_id>.<ext> w cache/thumbs; obecność pliku = ikona jest."""
    return cache_dir() / "thumbs"


# --------------------------------------------------------------------- #
# legacy locations of this UI (read-only fallbacks)                     #
# --------------------------------------------------------------------- #
def legacy_ui_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else home_dir() / ".config"
    return root / LEGACY_UI_DIR_NAME


def legacy_settings_path() -> Path:
    return legacy_ui_dir() / "settings.json"


def old_manager_settings_path() -> Path:
    """Config STAREGO menedżera (~/.7dtd_modmanager/settings.json, snake_case)
    - ŻYWE dane starego projektu we wspólnym katalogu; wyłącznie DO ODCZYTU
    (leniwy import wartości, moduł 10). Nigdy nie zapisywać."""
    return data_dir() / "settings.json"


def legacy_profiles_path() -> Path:
    return legacy_ui_dir() / "profiles.json"


def legacy_mod_state_path() -> Path:
    return legacy_ui_dir() / "state.json"


def read_json_migrated(path: Path, legacy_path: Path, default=None):
    """read_json(path), falling back to legacy_path when path is missing.

    Lets files written by earlier builds (XDG dir) survive the move to the
    shared root; callers persist the value at ``path`` on their next save.
    """
    data = read_json(path, None)
    if data is not None:
        return data
    return read_json(legacy_path, default)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload) -> bool:
    try:
        ensure_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        tmp.replace(path)
        return True
    except OSError:
        return False


def path_exists(path: str) -> bool:
    try:
        return bool(path) and Path(path).exists()
    except OSError:
        return False


def display_path(path: str) -> str:
    try:
        p = Path(path).expanduser()
        home = Path.home()
        if p == home:
            return "~"
        if str(p).startswith(str(home) + "/"):
            return "~" + str(p)[len(str(home)):]
        return str(p)
    except Exception:
        return path or ""
