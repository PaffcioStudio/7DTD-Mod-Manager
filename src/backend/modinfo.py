"""Parsing of the 7 Days to Die ModInfo.xml descriptor.

find_modinfo/parse_modinfo ported 1:1 from the legacy manager's modio.py -
the library stack's single source of ModInfo truth (every mod must ship a
ModInfo.xml; case-insensitive file name lookup, case-insensitive tags,
value taken from the ``value`` attribute or the element text).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

MODINFO_NAME = "ModInfo.xml"


def find_modinfo(folder: Path) -> Path | None:
    try:
        for item in folder.iterdir():
            if item.is_file() and item.name.lower() == MODINFO_NAME.lower():
                return item
    except OSError:
        return None
    return None


def _field(root: ET.Element, name: str) -> str:
    wanted = name.lower()
    for element in root.iter():
        tag = element.tag.split("}", 1)[-1].lower()
        if tag != wanted:
            continue
        value = element.attrib.get("value")
        if value is None:
            value = element.text
        return (value or "").strip()
    return ""


def parse_modinfo(path: Path) -> dict[str, str]:
    tree = ET.parse(path)
    root = tree.getroot()
    return {
        "display_name": _field(root, "DisplayName"),
        "mod_name": _field(root, "Name"),
        "description": _field(root, "Description"),
        "version": _field(root, "Version"),
        # NEW vs the legacy parse (stage 3): the legacy library model did
        # not carry the author; the new UI shows it on every mod card.
        "author": _field(root, "Author"),
    }


def parse_dependencies(path: Path) -> list[str]:
    """Czyta stabilne identyfikatory Name z sekcji Dependencies moda."""
    root = ET.parse(path).getroot()
    dependencies = []
    for parent in root.iter():
        if parent.tag.split("}", 1)[-1].lower() != "dependency":
            continue
        name = ""
        for child in parent.iter():
            if child is parent or child.tag.split("}", 1)[-1].lower() != "name":
                continue
            name = (child.attrib.get("value") or (child.text or "")).strip()
            if name:
                break
        if not name:
            name = (parent.attrib.get("value") or parent.attrib.get("name") or "").strip()
        if name and name.casefold() not in {item.casefold() for item in dependencies}:
            dependencies.append(name)
    return dependencies
