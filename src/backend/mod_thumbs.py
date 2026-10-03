"""Miniatury ikon modów z 7daystodiemods.com (etap 17).

Czysta logika, bez Qt. Plik miniatury zapisywany jest w
cache/thumbs/<library_id>.<ext> - OBECNOŚĆ PLIKU = ikona jest,
brak = przy następnym uruchomieniu program spróbuje ponownie.

Dopasowanie modu Biblioteki do strony: wyszukiwanie po nazwie
(dokładnie → prefiks na granicy słowa, ta sama heurystyka co przy
aktualizacjach - zob. mod_updates.match_items_slug). Z wyniku
wyszukiwania bierzemy OD RAZU URL miniatury, więc jeden mod kosztuje
jedno zapytanie o stronę listy + jedno pobranie obrazka.
"""
from __future__ import annotations

import logging
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from backend import discover
from backend.mod_updates import match_items_slug
from backend.modinfo import find_modinfo
from services import filesystem_service as fs

logger = logging.getLogger(__name__)

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def thumb_path(library_id: str) -> Path | None:
    """Ścieżka istniejącej miniatury dla wpisu (dowolne rozszerzenie)."""
    stem = library_id
    try:
        for f in fs.thumbs_dir().iterdir():
            if f.is_file() and f.stem == stem:
                return f
    except OSError:
        pass
    return None


def preload_urls() -> dict[str, str]:
    """{library_id: file:// URL} istniejących miniatur - do zasilenia
    modelu przy starcie aplikacji (QML Image czyta file://)."""
    out: dict[str, str] = {}
    try:
        for f in fs.thumbs_dir().iterdir():
            if f.is_file():
                out[f.stem] = "file://" + str(f.resolve())
    except OSError:
        pass
    return out


def has_thumb(library_id: str) -> bool:
    return thumb_path(library_id) is not None


def search_thumb_url(name: str) -> tuple[str, str] | None:
    """(slug, url_miniatury) dla nazwy moda albo None bez pewnego trafienia."""
    try:
        result = discover.fetch_catalog(query=name)
    except Exception as exc:  # noqa: BLE001 - sieć/parsowanie: brak wyniku
        logger.warning("Thumbnail lookup for %r failed: %s", name, exc)
        return None
    wanted = (name or "").strip().casefold()
    if not wanted:
        return None
    items = result.get("items", [])
    slug = match_items_slug(items, name)
    if not slug:
        return None
    for item in items:
        if item.get("slug") == slug:
            url = item.get("thumbnail") or ""
            return (slug, url) if url.startswith("https://") else None
    return None


def download_thumb(url: str, library_id: str) -> Path | None:
    """Pobiera obrazek do cache/thumbs/<library_id>.<ext> (atomowo:
    najpierw .part, potem replace). None = nie udało się."""
    ext = ".jpg"
    m = re.search(r"\.(jpe?g|png|webp)(?:[?#]|$)", url, re.I)
    if m:
        ext = "." + m.group(1).lower()
    dest = fs.thumbs_dir() / f"{library_id}{ext}"
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        fs.thumbs_dir().mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(part, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
        part.replace(dest)
    except OSError as exc:
        logger.warning("Thumbnail %s: write error: %s", library_id, exc)
        part.unlink(missing_ok=True)
        return None
    except Exception as exc:  # noqa: BLE001 - sieciowe: brak miniatury
        logger.warning("Thumbnail %s: %s", library_id, exc)
        part.unlink(missing_ok=True)
        return None
    return dest


def local_banner(mod_folder: str | Path) -> Path | None:
    """PRIORYTET 1 (zero sieci): Banner/Icon z ModInfo.xml zainstalowanego
    moda (ścieżka względna do folderu moda, np. Misc/Logo.png). Wymaga,
    żeby plik istniał i leżał WEWNĄTRZ folderu moda (ModInfo z kontrolowanego
    źródła, ale ostrożność nigdy nie zawadzi)."""
    folder = Path(mod_folder)
    info = find_modinfo(folder)
    if info is None:
        return None
    try:
        root = ET.parse(info).getroot()
    except (OSError, ET.ParseError):
        return None
    try:
        folder_resolved = folder.resolve(strict=False)
        for tag in ("Banner", "Icon"):
            el = root.find(f".//{tag}")
            if el is None:
                continue
            raw = (el.get("value") or el.text or "").strip()
            if not raw:
                continue
            candidate = (folder / raw).resolve(strict=False)
            if candidate.suffix.lower() not in _ALLOWED_EXT:
                continue
            if not candidate.is_file():
                continue
            if folder_resolved not in candidate.parents:
                continue   # ucieczka poza folder moda - ignorujemy
            return candidate
    except OSError:
        return None
    return None


def cache_banner(source: Path, library_id: str) -> Path:
    """Kopiuje lokalną grafikę do cache/thumbs/<library_id><ext>."""
    dest = fs.thumbs_dir() / (library_id + source.suffix.lower())
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest


def resolve_and_download(name: str, library_id: str) -> Path | None:
    """Pełny cykl dla jednego wpisu: wyszukaj → pobierz miniaturę.
    Zwraca ścieżkę albo None (brak dopasowania / błąd sieci)."""
    found = search_thumb_url(name)
    if not found:
        return None
    _slug, url = found
    return download_thumb(url, library_id)
