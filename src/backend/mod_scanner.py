"""Scanner for a real 7 Days to Die ``Mods`` directory.

7DTD mods live in sub-folders of the game's Mods directory and ship a
``ModInfo.xml`` descriptor:

    <xml>
      <Name value="Better Loot"/>
      <Author value="Snufkin"/>
      <Version value="1.93"/>
      <Description value="..."/>
    </xml>

The scan runs in a worker thread and reports back through a Qt signal so the
UI thread never blocks.
"""

from __future__ import annotations

import logging
import re
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from models.mod import Mod
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)

_VALUE_RE = re.compile(r'value\s*=\s*"([^"]*)"')


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _read_value(path: Path) -> dict[str, str]:
    """Extract Name/Author/Version/Description from a ModInfo.xml."""
    result: dict[str, str] = {}
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        # fall back to a forgiving regex scan of the raw file
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return result
        for key in ("Name", "Author", "Version", "Description"):
            match = re.search(rf"<{key}\b[^>]*>", text)
            if match:
                value = _VALUE_RE.search(match.group(0))
                if value:
                    result[key.lower()] = value.group(1)
        return result

    for element in tree.iter():
        tag = _strip_ns(element.tag)
        if tag in ("Name", "Author", "Version", "Description"):
            value = element.get("value") or (element.text or "").strip()
            if value:
                result[tag.lower()] = value.strip()
    return result


def scan_mods_directory(mods_dir: str | Path) -> list[Mod]:
    """Synchronously scan ``mods_dir`` - call from a worker thread."""
    root = Path(mods_dir)
    if not root.is_dir():
        return []

    mods: list[Mod] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        info = folder / "ModInfo.xml"
        if not info.is_file():
            continue
        values = _read_value(info)
        if not values.get("name"):
            continue
        try:
            size = sum(
                f.stat().st_size for f in folder.rglob("*") if f.is_file()
            )
        except OSError:
            size = 0
        mods.append(
            Mod(
                id=folder.name,
                name=values.get("name", folder.name),
                author=values.get("author") or i18n_message("common.unknown"),
                category="Gameplay",
                version=values.get("version", "?"),
                new_version="",
                enabled=True,
                description=values.get("description", ""),
                size_bytes=size,
                downloads=0,
                rating=0.0,
                tags=[],
                dependencies=[],
                modified_files=[],
            )
        )
    return mods


class ModScanner(QObject):
    """Threaded wrapper around :func:`scan_mods_directory`."""

    scanFinished = Signal(list)      # list[Mod]
    scanFailed = Signal(str)

    def scan_async(self, mods_dir: str) -> None:
        if not mods_dir:
            self.scanFailed.emit("No mods directory configured")
            return

        def worker() -> None:
            try:
                mods = scan_mods_directory(mods_dir)
                self.scanFinished.emit(mods)
            except Exception as exc:  # pragma: no cover - safety net
                logger.exception("Mod scan failed")
                self.scanFailed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()
