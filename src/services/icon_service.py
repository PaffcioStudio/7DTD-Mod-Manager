"""SVG icon service.

All icons live as plain SVG files in ``assets/icons``.  Each file uses
``currentColor`` as its stroke/fill token.  This service loads them once,
substitutes the requested color and returns a base64 data-URL which QML
``Image`` elements can consume directly - which keeps the icon set crisp,
theme-aware and hover-recolorable without any shader effects.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Slot

logger = logging.getLogger(__name__)


def _normalize_hex(color: str) -> str:
    """QML colors stringify as '#rrggbb' or '#aarrggbb'."""
    text = str(color or "#FFFFFF").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 8:      # drop alpha part
        text = text[2:]
    if len(text) != 6:
        return "#FFFFFF"
    try:
        int(text, 16)
    except ValueError:
        return "#FFFFFF"
    return f"#{text.upper()}"


class IconService(QObject):
    """Exposed to QML as ``Icons``."""

    def __init__(self, icons_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._icons_dir = Path(icons_dir)
        self._svgs: dict[str, str] = {}
        self._cache: dict[tuple[str, str], str] = {}
        self._missing: set[str] = set()
        self._load_all()

    # ------------------------------------------------------------------ #
    def _load_all(self) -> None:
        if not self._icons_dir.is_dir():
            logger.warning("Icons directory not found: %s", self._icons_dir)
            return
        for path in sorted(self._icons_dir.glob("*.svg")):
            try:
                self._svgs[path.stem] = path.read_text(encoding="utf-8")
            except OSError:
                continue
        logger.info("Loaded %d SVG icons from %s", len(self._svgs), self._icons_dir)

    # ------------------------------------------------------------------ #
    @Slot(str, str, result=str)
    def url(self, name: str, color: str) -> str:
        """Return a data-URL for ``name`` recolored to ``color``."""
        hex_color = _normalize_hex(color)
        key = (name, hex_color)
        cached = self._cache.get(key)
        if cached:
            return cached

        svg = self._svgs.get(name)
        if svg is None:
            if name and name not in self._missing:
                self._missing.add(name)
                logger.warning("Missing icon: %s", name)
            svg = self._svgs.get("package", "<svg/>")
            if not svg:
                return ""

        colored = svg.replace("currentColor", hex_color)
        payload = base64.b64encode(colored.encode("utf-8")).decode("ascii")
        result = f"data:image/svg+xml;base64,{payload}"
        self._cache[key] = result
        return result
