"""Loader BepInEx + Unity Doorstop dostarczany z overhaulami (np. Undead Legacy).

Paczka Undead Legacy oprócz klasycznego ``Mods/`` zawiera pliki startowe
BepInExa, bez których jego część kodowa (patchery/pluginy Harmony) w ogóle
się nie załaduje:

    winhttp.dll, doorstop_config.ini, BepInEx/ (core, patchers, config)

Gra jest uruchamiana przez Proton jako ``7DaysToDie.exe``, więc liczy się
wariant WINDOWSOWY (``winhttp.dll`` = proxy-DLL Doorstopa wczytywany z
katalogu exe, wymaga ``WINEDLLOVERRIDES=winhttp=n,b``). Pliki natywnego
Linuksa/macOS z tej samej paczki (``run_bepinex*.sh``, ``libdoorstop_*.so``,
``libdoorstop.dylib``) pod Protonem nie są używane i nie są kopiowane.

Katalog gry (``game-versions/<branch>/``) jest WSPÓLNY dla wszystkich
instancji danej wersji, a loader ma działać tylko w instancji, która go
potrzebuje. Dlatego:

1. przy instalacji overhaula loader jest odkładany do instancji
   (``<data_dir>/.modmanager-loader/``),
2. przy KAŻDYM starcie gry :func:`sync_game_dir` wdraża loader instancji do
   katalogu gry (albo sprząta po poprzedniej instancji, jeśli ta go nie ma),
   zapisując listę wdrożonych plików w ``.modmanager-loader.json``,
3. ``[MultiFolderLoader] baseDir`` w ``doorstop_config.ini`` jest przepisywany
   na folder ``Mods/`` TEJ instancji (domyślne ``Mods/`` wskazywałoby na
   pusty ``Mods/`` w katalogu gry).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path

from backend.wine_paths import to_wine_path

logger = logging.getLogger(__name__)

LOADER_DIRNAME = ".modmanager-loader"
MANIFEST_NAME = ".modmanager-loader.json"
BACKUP_SUFFIX = ".modmanager-backup"
DLL_OVERRIDE = "winhttp=n,b"

# Co kopiujemy z paczki (wariant Windows/Proton). Nazwy porównujemy bez
# względu na wielkość liter - paczki z Windowsa bywają "WinHttp.dll".
_LOADER_FILES = ("winhttp.dll", "doorstop_config.ini")
_LOADER_DIRS = ("BepInEx",)

# Podfoldery modow, ktore overhaul adresuje SZTYWNO wzgledem katalogu gry
# (np. "#Mods/UndeadLegacy/Resources/x.ulm" albo
# "Data/Bundles/Standalone/../../../Mods/UndeadLegacy/Resources/x.ulm").
# Mody instancji leza w <instancja>/Mods, wiec bez dowiazania gra konczy z
# "Loading AssetBundle ... failed: Parent folder not found!". Linkujemy TYLKO
# te zasoby (nie ModInfo.xml/Config/DLL), zeby mod nie zaladowal sie drugi raz
# z <gra>/Mods obok <instancja>/Mods.
_GAME_RELATIVE_MOD_DIRS = ("Resources",)


def _child(directory: Path, name: str) -> Path | None:
    """Element katalogu o danej nazwie, ignorując wielkość liter."""
    try:
        for entry in directory.iterdir():
            if entry.name.casefold() == name.casefold():
                return entry
    except OSError:
        pass
    return None


def is_loader_root(directory: Path) -> bool:
    """Czy katalog zawiera komplet plików startowych BepInExa (Windows)."""
    directory = Path(directory)
    if not directory.is_dir():
        return False
    dll = _child(directory, "winhttp.dll")
    ini = _child(directory, "doorstop_config.ini")
    core = _child(directory, "BepInEx")
    return bool(dll and dll.is_file() and ini and ini.is_file() and core and core.is_dir())


def find_loader_root(extracted_dir: Path, mods_root: Path | None = None) -> Path | None:
    """Szuka loadera w wypakowanej paczce: obok folderu Mods, w korzeniu
    paczki albo poziom niżej (zipball GitHub dodaje folder ``repo-branch``)."""
    candidates: list[Path] = []
    if mods_root is not None:
        candidates.append(Path(mods_root).parent)
    extracted_dir = Path(extracted_dir)
    candidates.append(extracted_dir)
    try:
        candidates.extend(sorted(c for c in extracted_dir.iterdir() if c.is_dir()))
    except OSError:
        pass
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if is_loader_root(candidate):
            return candidate
    return None


def loader_dir_for(instance_data_dir: Path | str) -> Path:
    return Path(instance_data_dir).expanduser() / LOADER_DIRNAME


def has_loader(instance_data_dir: Path | str | None) -> bool:
    if not instance_data_dir:
        return False
    return is_loader_root(loader_dir_for(instance_data_dir))


def stash_loader(loader_root: Path, instance_data_dir: Path | str) -> Path:
    """Kopiuje pliki startowe BepInExa z paczki do katalogu instancji.
    Zwraca katalog docelowy. Pomija pliki natywnego Linuksa/macOS."""
    loader_root = Path(loader_root)
    target = loader_dir_for(instance_data_dir)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in _LOADER_FILES:
        src = _child(loader_root, name)
        if src is not None and src.is_file():
            shutil.copy2(src, target / name.lower() if name.endswith(".dll") else target / name)
    for name in _LOADER_DIRS:
        src = _child(loader_root, name)
        if src is not None and src.is_dir():
            shutil.copytree(src, target / name, symlinks=True)
    logger.info("BepInEx loader stored for instance: %s", target)
    return target


# --- doorstop_config.ini -----------------------------------------------------

_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
_BASEDIR_RE = re.compile(r"^(\s*baseDir\s*=).*$", re.IGNORECASE)


def rewrite_base_dir(ini_text: str, base_dir: str) -> str:
    """Ustawia ``baseDir`` w sekcji ``[MultiFolderLoader]`` (reszta pliku -
    komentarze, kolejność, końce linii - bez zmian). Brak sekcji/klucza =
    zostaną dopisane."""
    newline = "\r\n" if "\r\n" in ini_text else "\n"
    lines = ini_text.splitlines()
    in_section = False
    section_found = False
    replaced = False
    out: list[str] = []
    for line in lines:
        match = _SECTION_RE.match(line)
        if match:
            if in_section and not replaced:
                out.append(f"baseDir = {base_dir}")
                replaced = True
            in_section = match.group("name").strip().casefold() == "multifolderloader"
            section_found = section_found or in_section
        elif in_section and not replaced:
            key = _BASEDIR_RE.match(line)
            if key:
                line = f"{key.group(1)} {base_dir}"
                replaced = True
        out.append(line)
    if not section_found:
        out.extend(["", "[MultiFolderLoader]", f"baseDir = {base_dir}"])
    elif not replaced:
        out.append(f"baseDir = {base_dir}")
    return newline.join(out) + newline


# --- wdrażanie do katalogu gry -----------------------------------------------


def _read_manifest(game_dir: Path) -> list[str]:
    try:
        data = json.loads((game_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        return [str(p) for p in data.get("files", [])]
    except (OSError, ValueError, AttributeError):
        return []


def _safe_rel(game_dir: Path, rel: str) -> Path | None:
    """Ścieżka z manifestu musi zostać wewnątrz katalogu gry."""
    target = (game_dir / rel)
    try:
        # rozwiazujemy RODZICA, nie sam wpis: dowiazanie symboliczne (zasoby
        # modow) wskazuje poza katalog gry, a mimo to jest naszym plikiem
        (target.parent.resolve(strict=False) / target.name).relative_to(
            game_dir.resolve(strict=False))
    except ValueError:
        return None
    return target


def _prune_empty_parents(game_dir: Path, path: Path) -> None:
    parent = path.parent
    while parent != game_dir and game_dir in parent.parents:
        if parent == game_dir / "Mods":
            return  # katalog Mods nalezy do gry, nie do nas
        try:
            parent.rmdir()
        except OSError:
            return
        parent = parent.parent


def _restore_backup(target: Path) -> None:
    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if backup.exists() and not target.exists():
        backup.replace(target)


def remove_deployed(game_dir: Path) -> int:
    """Usuwa z katalogu gry WYŁĄCZNIE pliki wdrożone wcześniej przez launcher
    (lista w manifeście) i przywraca ewentualne kopie zapasowe."""
    game_dir = Path(game_dir)
    removed = 0
    for rel in _read_manifest(game_dir):
        target = _safe_rel(game_dir, rel)
        if target is None:
            continue
        try:
            if target.is_symlink() or target.is_file():
                target.unlink()
                removed += 1
            _restore_backup(target)
            _prune_empty_parents(game_dir, target)
        except OSError:
            logger.warning("Could not remove deployed loader file: %s", target, exc_info=True)
    try:
        (game_dir / MANIFEST_NAME).unlink()
    except OSError:
        pass
    return removed


def _link_game_relative_mod_dirs(game_dir: Path, mods_dir: Path) -> list[str]:
    """Dowiazuje <gra>/Mods/<mod>/Resources -> <instancja>/Mods/<mod>/Resources.
    Zwraca sciezki wzgledne (do manifestu, zeby sprzatanie je usunelo)."""
    created: list[str] = []
    try:
        mods = sorted(p for p in mods_dir.iterdir() if p.is_dir())
    except OSError:
        return created
    for mod in mods:
        for wanted in _GAME_RELATIVE_MOD_DIRS:
            res = _child(mod, wanted)
            if res is None or not res.is_dir():
                continue
            link = game_dir / "Mods" / mod.name / res.name
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                continue  # prawdziwy folder (reczna instalacja) zostaje nietkniety
            try:
                link.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(res.resolve(strict=False), link, target_is_directory=True)
            except OSError:
                logger.warning("Could not link mod resources into the game dir: %s", link, exc_info=True)
                continue
            created.append(link.relative_to(game_dir).as_posix())
    return created


def sync_game_dir(game_dir: Path | str, instance_data_dir: Path | str | None) -> bool:
    """Doprowadza katalog gry do stanu właściwego dla uruchamianej instancji.

    Zwraca True, gdy loader BepInEx jest aktywny dla tej instancji (wtedy
    wołający MUSI ustawić ``WINEDLLOVERRIDES`` - zob. :func:`apply_dll_override`).
    False = instancja bez loadera, a katalog gry jest czysty.
    """
    game_dir = Path(game_dir)
    remove_deployed(game_dir)  # zawsze: sprzątnij po poprzedniej instancji
    if not has_loader(instance_data_dir):
        return False

    source = loader_dir_for(instance_data_dir)
    mods_dir = Path(instance_data_dir).expanduser() / "Mods"
    deployed: list[str] = []
    for src in sorted(source.rglob("*")):
        if not src.is_file() and not src.is_symlink():
            continue
        rel = src.relative_to(source)
        target = game_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if (target.exists() or target.is_symlink()) and not target.is_dir():
            backup = target.with_name(target.name + BACKUP_SUFFIX)
            if not backup.exists():
                target.replace(backup)  # nie nadpisujemy cudzego pliku bez śladu
            else:
                target.unlink()
        shutil.copy2(src, target, follow_symlinks=False)
        deployed.append(rel.as_posix())

    deployed.extend(_link_game_relative_mod_dirs(game_dir, mods_dir))

    ini = game_dir / "doorstop_config.ini"
    if ini.is_file():
        base_dir = to_wine_path(mods_dir.resolve(strict=False)).rstrip("/") + "/"
        ini.write_text(
            rewrite_base_dir(ini.read_text(encoding="utf-8", errors="replace"), base_dir),
            encoding="utf-8",
        )
    (game_dir / MANIFEST_NAME).write_text(
        json.dumps({"files": deployed}, indent=2), encoding="utf-8")
    logger.info("BepInEx loader deployed to %s (%d files, mods=%s)", game_dir, len(deployed), mods_dir)
    return True


def apply_dll_override(env: dict[str, str]) -> None:
    """Dokleja ``winhttp=n,b`` do WINEDLLOVERRIDES (nie gubi istniejących)."""
    existing = (env.get("WINEDLLOVERRIDES") or "").strip().strip(";")
    if DLL_OVERRIDE in existing.split(";"):
        return
    env["WINEDLLOVERRIDES"] = f"{existing};{DLL_OVERRIDE}" if existing else DLL_OVERRIDE
