"""Convert standalone 7DTD POI prefab ZIPs into installable modlets.

Some catalog downloads contain exported prefab files (XML + TTS), not a
ModInfo.xml. They are valid ZIPs but cannot be imported into the mod library
as-is. A small generated modlet keeps these POIs under normal library and
instance activation instead of modifying the game's Data/Prefabs directly.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.modinfo import find_modinfo

logger = logging.getLogger(__name__)

# Known files written by the game's prefab editor. Do not include executable
# files, scripts or unrelated XML/config files when converting a prefab ZIP.
_PREFAB_SUFFIXES = {".tts", ".xml", ".mesh", ".nim", ".ins", ".jpg", ".jpeg", ".png"}
_MAX_SCAN_FILES = 10000


def _base_name(path: Path) -> str:
    """E.g. foo.blocks.nim, foo.tts and foo.xml all belong to foo."""
    name = path.name.casefold()
    return name[:-11] if name.endswith(".blocks.nim") else path.stem.casefold()


def _prefab_root_for(files: list[Path], extracted_root: Path) -> Path:
    """Use the directory after Prefabs/POIs, or their common parent."""
    poi_roots: list[Path] = []
    for path in files:
        parents = list(path.parents)
        for parent in parents:
            if parent == extracted_root or extracted_root not in parent.parents:
                break
            if parent.name.casefold() == "pois" and parent.parent.name.casefold() == "prefabs":
                poi_roots.append(parent)
                break
    if len(poi_roots) == len(files) and len(set(poi_roots)) == 1:
        return poi_roots[0]
    # Common *parent* keeps distinct POIs in distinct subdirectories.
    import os
    return Path(os.path.commonpath([str(path.parent) for path in files]))


def prepare_loose_prefab_mod(
    extracted_root: Path,
    *,
    slug: str,
    title: str,
    author: str = "",
    version: str = "",
) -> Path | None:
    """Return a new Mods-root with one generated prefab modlet, or None.

    Only accept real prefabs containing paired .xml + .tts filenames in the
    same directory. Existing ModInfo.xml mods are deliberately not rewritten.
    The extracted files and the downloaded ZIP remain untouched.
    """
    extracted_root = Path(extracted_root)
    if not extracted_root.is_dir():
        return None

    all_files: list[Path] = []
    for index, path in enumerate(extracted_root.rglob("*")):
        if index > _MAX_SCAN_FILES:
            logger.warning("Prefab conversion skipped: extracted tree exceeds %d entries", _MAX_SCAN_FILES)
            return None
        if path.is_symlink():
            return None
        if path.is_file():
            if path.name.casefold() == "modinfo.xml":
                return None
            all_files.append(path)

    # Distinguish prefab POIs from ordinary XML-only mods and random ZIPs.
    all_by_parent: dict[Path, set[str]] = {}
    for path in all_files:
        all_by_parent.setdefault(path.parent, set()).add(path.name.casefold())
    tts_files = [
        path for path in all_files
        if path.suffix.casefold() == ".tts"
        and path.with_suffix(".xml").name.casefold() in all_by_parent[path.parent]
    ]
    if not tts_files:
        return None

    source_root = _prefab_root_for(tts_files, extracted_root)
    stems_by_dir: dict[Path, set[str]] = {}
    for path in tts_files:
        stems_by_dir.setdefault(path.parent, set()).add(path.stem.casefold())
    companions = [
        path for path in all_files
        if path.parent in stems_by_dir
        and path.suffix.casefold() in _PREFAB_SUFFIXES
        and _base_name(path) in stems_by_dir[path.parent]
    ]
    if not companions:
        return None

    safe_slug = re.sub(r"[^A-Za-z0-9_-]", "_", slug).strip("_-") or "Prefab"
    name = ("MM_Prefab_" + safe_slug)[:110]
    safe_title = (title or slug or "Prefab").strip()[:180]
    # 7DTD ModInfo v2 needs at least major.minor, not an arbitrary text label.
    match = re.search(r"\d+(?:\.\d+){0,3}", version or "")
    numeric_version = match.group(0) if match else "1.0"
    if "." not in numeric_version:
        numeric_version += ".0"

    # Unique staging location avoids colliding with user-supplied ZIP paths.
    staging = Path(tempfile.mkdtemp(prefix=".mm-prefab-", dir=extracted_root))
    try:
        mods_root = staging / "Mods"
        mod_dir = mods_root / name
        dst_root = mod_dir / "Prefabs" / "POIs"
        for path in companions:
            rel_path = path.relative_to(source_root)
            dest = dst_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

        root = ET.Element("xml")
        for tag, value in (
            ("Name", name),
            ("DisplayName", safe_title),
            ("Version", numeric_version),
            ("Author", (author or "Unknown")[:180]),
            ("Description", "Standalone POI prefab packaged for 7DTD Mod Manager."),
        ):
            ET.SubElement(root, tag, value=value)
        ET.ElementTree(root).write(mod_dir / "ModInfo.xml", encoding="utf-8", xml_declaration=True)
        assert find_modinfo(mod_dir) is not None
        logger.info("Prepared standalone POI prefab as %s (%d asset files)", name, len(companions))
        return mods_root
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
