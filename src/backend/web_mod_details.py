"""Szczegóły moda z 7daystodiemods.com przed pobraniem (etap 13).

QObject "WebDetails" wystawiony do QML: drawer na Odkrywaj woła
fetch(slug) i binduje się do ready/failed. Metadane z get_metadata
(opis, galeria, pliki, changelog) + cache w pamięci z TTL, żeby
klikanie w karty nie dharpało serwisu.

Wybór pliku: UI dostaje listę plików z identyfikatorami "hosted:<id>"
(pliki serwisu) albo "external:<url>" (linki zewnętrzne) i przekazuje
ten identyfikator z powrotem do Downloads.startModDownloadWithFile.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot

from backend.scraper_client import SevenDaysModsClient
from services.i18n_message import message as i18n_message
from models.mod import human_size

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


@dataclass(slots=True)
class _Pending:
    slug: str


class WebModDetails(QObject):
    """Detail karty web moda - wystawiony do QML jako ``WebDetails``."""

    busyChanged = Signal()
    ready = Signal(str, dict)     # slug, szczegóły
    failed = Signal(str, str)     # slug, komunikat

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._busy = False
        self._pending: _Pending | None = None
        self._generation = 0   # tylko najnowsze żądanie ma znaczenie

    # ------------------------------------------------------------------ #
    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot(str)
    def fetch(self, slug: str) -> None:
        slug = (slug or "").strip()
        if not slug:
            return
        with _lock:
            cached = _cache.get(slug)
            if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
                self.ready.emit(slug, dict(cached[1]))
                return
        if self._busy:
            self._pending = _Pending(slug)   # obsłuż po bieżącym
            return
        self._busy = True
        self.busyChanged.emit()
        self._generation += 1
        generation = self._generation

        def worker() -> None:
            try:
                client = SevenDaysModsClient()
                meta = client.get_metadata(slug)
                details = _map_details(slug, meta)
            except Exception as exc:  # noqa: BLE001 - komunikat na drawer
                logger.warning("Details for %s: %s", slug, exc)
                self.failed.emit(slug, str(exc))
            else:
                with _lock:
                    _cache[slug] = (time.monotonic(), details)
                self.ready.emit(slug, details)
            finally:
                if generation == self._generation:
                    self._busy = False
                    self.busyChanged.emit()
                    nxt = self._pending
                    self._pending = None
                    if nxt is not None:
                        self.fetch(nxt.slug)

        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def clearCache(self) -> None:
        with _lock:
            _cache.clear()


_MAX_GALLERY = 20


def _gallery_urls(meta: dict) -> list[str]:
    """Zrzuty ekranu moda: galeria z serwisu bez duplikatów.

    Gdy serwis nie ma galerii, pokazujemy miniaturę moda (jeśli jest),
    a w ostateczności obrazki wklejone w opis. Tylko adresy http(s) -
    reszta (np. data:/file:) nie ma po co trafiać do podglądu.
    """
    def clean(values) -> list[str]:
        out: list[str] = []
        for value in values or []:
            if not isinstance(value, str):
                continue
            url = value.strip()
            if url.startswith(("https://", "http://")) and url not in out:
                out.append(url)
        return out

    urls = clean(meta.get("gallery"))
    if not urls:
        urls = clean([meta.get("thumbnail")])
    if not urls:
        urls = clean(meta.get("description_images"))
    return urls[:_MAX_GALLERY]


def _map_details(slug: str, meta: dict) -> dict:
    """get_metadata -> płaski słownik gotowy dla QML (bool/int/str/listy)."""
    files = []
    for f in meta.get("files", []):
        files.append({
            "fileRef": f"hosted:{f.get('id', '')}",
            "label": f.get("label") or f.get("filename") or i18n_message("common.unnamed"),
            "version": f.get("version") or "",
            "sizeText": human_size(int(f.get("size_bytes") or 0)),
            "fileType": f.get("file_type") or "main",
            "verified": bool(f.get("verified")),
            "detectedGameVersions": list(f.get("detected_game_versions") or []),
        })
    for link in meta.get("external_links", []):
        files.append({
            "fileRef": f"external:{link.get('url', '')}",
            "label": link.get("label") or link.get("url") or i18n_message("web.file.external"),
            "version": link.get("version") or "",
            "sizeText": "",
            "fileType": "external",
            "verified": False,
            "detectedGameVersions": list(link.get("detected_game_versions") or []),
        })
    return {
        "slug": slug,
        "title": meta.get("title") or slug,
        "author": meta.get("author") or i18n_message("common.unknown"),
        "summary": meta.get("summary") or "",
        "description": meta.get("description") or "",
        "version": meta.get("current_version") or "",
        "categories": ", ".join(meta.get("categories") or []),
        "gameVersions": ", ".join(meta.get("game_versions") or []),
        "downloadCount": int(meta.get("download_count") or 0),
        "url": meta.get("url") or f"https://7daystodiemods.com/mods/{slug}",
        "thumbnail": meta.get("thumbnail") or "",
        "gallery": _gallery_urls(meta),
        "files": files,
        "changelog": [
            {
                "version": str(c.get("version") or ""),
                "date": str(c.get("date") or "")[:10],
                "changelog": str(c.get("changelog") or ""),
            }
            for c in (meta.get("changelog") or [])[:8]
        ],
    }
