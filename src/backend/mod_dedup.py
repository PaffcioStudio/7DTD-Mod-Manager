"""Disable game-directory duplicates while keeping the modpack's versions.

Only ModInfo.xml is moved, outside Mods; DLLs and hard-coded resource paths
stay intact. Backups survive crashes and are restored on the next launcher
start that does not need the instance copy. Never overwrite either copy.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.modinfo import find_modinfo, parse_modinfo

logger = logging.getLogger(__name__)
BACKUP_DIR = ".modmanager-disabled-mods"


def _keys(folder: Path, descriptor: Path) -> set[str]:
    keys = {"folder:" + folder.name.casefold()}
    try:
        name = parse_modinfo(descriptor)["mod_name"]
        if name:
            keys.add("name:" + name.casefold())
    except ET.ParseError:
        logger.warning("Invalid mod descriptor: %s", descriptor)
    # Harmony packs sometimes rename both the folder and the descriptor name.
    if (folder / "0Harmony.dll").is_file() and (folder / "TfpHarmony.dll").is_file():
        keys.add("tfp-harmony-wrapper")
    return keys


def _mods(root: Path) -> list[tuple[Path, Path]]:
    if not root.exists():
        return []
    result = []
    for folder in sorted(root.iterdir()):
        if folder.is_dir():
            descriptor = next((p for p in folder.iterdir()
                               if p.name.casefold() == "modinfo.xml" and p.is_file()), None)
            if descriptor is not None:
                result.append((folder, descriptor))
    return result


def sync_game_dir(game_dir: Path | str, instance_data_dir: Path | str | None) -> list[str]:
    """Reconcile duplicates before launch; raise on unsafe/unreadable state.

    A failed preparation must block launch. Renames are rolled back on failure.
    Matching uses folder names, ModInfo Name and the TFP Harmony wrapper.
    Symlinked library mods are read only; their descriptors are never moved.
    """
    game_dir = Path(game_dir).expanduser()
    mods = game_dir / "Mods"
    backup = game_dir / BACKUP_DIR
    if backup.is_symlink():
        raise OSError(f"Mod backup directory must not be a symlink: {backup}")
    instance_mods = Path(instance_data_dir).expanduser() / "Mods" if instance_data_dir else None
    keys: set[str] = set()
    if instance_mods is not None and instance_mods.resolve() != mods.resolve():
        for folder, descriptor in _mods(instance_mods):
            keys.update(_keys(folder, descriptor))

    moves: list[tuple[Path, Path]] = []
    disabled: list[str] = []
    try:
        for folder, descriptor in _mods(backup):
            if folder.is_symlink() or descriptor.is_symlink():
                raise OSError(f"Mod backup must not contain symlinks: {descriptor}")
            original_folder = mods / folder.name
            if keys & _keys(original_folder, descriptor):
                if find_modinfo(original_folder) is not None:
                    raise FileExistsError(f"Mod descriptor recreated while disabled: {original_folder}")
                disabled.append(folder.name)
                continue
            target = original_folder / descriptor.name
            if mods.is_symlink() or original_folder.is_symlink():
                raise OSError(f"Cannot restore a mod through a symlink: {target}")
            if find_modinfo(original_folder) is not None or target.exists() or target.is_symlink():
                raise FileExistsError(f"Cannot restore mod without overwriting: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor.rename(target)
            moves.append((descriptor, target))

        for folder, descriptor in _mods(mods):
            if not keys.intersection(_keys(folder, descriptor)):
                continue
            # Moving through a symlink would change the shared library source.
            if mods.is_symlink() or folder.is_symlink() or descriptor.is_symlink():
                raise OSError(f"Cannot safely disable a symlinked game mod: {folder}")
            target = backup / folder.name / descriptor.name
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"Mod backup already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor.rename(target)
            moves.append((descriptor, target))
            disabled.append(folder.name)
    except Exception:
        for source, target in reversed(moves):
            target.rename(source)
        raise
    for name in disabled:
        logger.info("Disabled duplicate game mod %s in %s; using instance %s", name, game_dir, instance_data_dir)
    return disabled
