"""Browse the site's Nuxt catalog using the existing scraper parser."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Property, Signal, Slot

from backend.nuxtdata import build_all, extract_payload
from backend.scraper_client import BASE_URL, USER_AGENT
from backend.undead_legacy import fetch_latest_release
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)
CACHE_TTL = 900

# dołączony do aplikacji katalog overhauli (assets/manifests/) - provider
# "GitHub" w Odkrywaj; plik jest bundlowany do .deb/.AppImage razem z resztą.
# Wyjątkiem są wpisy z dynamicznym źródłem wersji (obecnie Undead Legacy),
# dla których odświeżamy metadane z oficjalnej strony.
MANIFEST_DIR = Path(__file__).resolve().parents[2] / "assets" / "manifests"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "overhaul"


def fetch_local_catalog(query: str = "", refresh: bool = False) -> dict:
    """Katalog z manifest_overhaul.json. Filtruje po nazwie,
    autorze i opisie; zwraca ten sam kształt wyniku co fetch_catalog."""
    items = []
    try:
        data = json.loads((MANIFEST_DIR / "manifest_overhaul.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Local overhaul manifest missing or invalid: %s",
                       MANIFEST_DIR / "manifest_overhaul.json")
        data = {}
    default_game_version = str(data.get("game_version", "")).strip()
    dynamic_failed = False
    needle = query.strip().lower()
    for entry in data.get("overhauls", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        author = str(entry.get("author", "")).strip()
        description = str(entry.get("description", "")).strip()
        # opcjonalne tłumaczenie EN; QML wybiera pole wg języka UI
        description_en = str(entry.get("description_en", "")).strip()
        thumbnail = str(entry.get("thumbnail", "")).strip()
        entry_game_version = str(entry.get("game_version") or default_game_version).strip()
        entry_version = str(entry.get("version", "")).strip()
        entry_download_url = str(entry.get("download_url", "")).strip()
        if entry.get("dynamic_source") == "undead_legacy" or name.casefold() == "undead legacy":
            try:
                latest = fetch_latest_release(refresh=refresh)
                entry_version = latest["version"]
                entry_game_version = latest["game_version"]
                entry_download_url = latest["download_url"]
            except Exception:
                dynamic_failed = True
                logger.warning("Could not refresh Undead Legacy metadata", exc_info=True)
        if needle and needle not in name.lower() \
                and needle not in author.lower() \
                and needle not in description.lower() \
                and needle not in description_en.lower():
            continue
        items.append({
            "slug": _slugify(name),
            "title": name or i18n_message("common.unnamed"),
            "summary": description,
            "summaryEn": description_en,
            "author": author or i18n_message("common.unknown"),
            "thumbnail": thumbnail if thumbnail.startswith("https://") else "",
            "thumbCrop": bool(entry.get("thumbnail_crop", False)),
            "category": "Overhaul",
            "versions": entry_game_version,
            "game_version": entry_game_version,
            "version": entry_version,
            "downloads": 0,
            "url": entry_download_url,
        })
    return {"items": items, "total": len(items), "page": 1, "pages": 1,
            "categories": [], "versions": [], "offline": dynamic_failed}


def parse_catalog(html: str, category: str = "", version: str = "") -> dict:
    # Keep the selected game-version branch attached to each discovered item.
    # The download path may later delegate to the web scraper, so the branch
    # must survive that hand-off instead of being inferred again from the URL.
    game_version = str(version or "").strip()
    values = build_all(extract_payload(html))
    data = next((v for v in values if isinstance(v, dict) and "mods-list" in v), {})
    listing = data.get("mods-list")
    metadata = next((v for v in values if isinstance(v, dict)
                     and "gameVersions" in v and "categories" in v), {})
    if not isinstance(listing, dict) or not isinstance(listing.get("items"), list):
        raise ValueError("Catalog response has an unsupported structure")
    entries = []
    seen = set()
    for mod in listing["items"]:
        slug = mod.get("slug", "")
        if not re.fullmatch(r"[a-zA-Z0-9-]+", slug) or slug in seen:
            continue
        categories = mod.get("categories") or []
        versions = mod.get("game_versions") or []
        # The old discover scanner also checked the actual categories: the
        # server has previously returned unrelated results for a filter.
        if category and category not in [c.get("slug") for c in categories]:
            continue
        if version and version not in [v.get("slug") for v in versions]:
            continue
        seen.add(slug)
        author = mod.get("author") or {}
        thumbnail = (mod.get("thumbnail") or {}).get("url", "")
        entries.append({
            "slug": slug, "title": mod.get("title") or slug,
            "summary": mod.get("summary") or "",
            "author": author.get("display_name") or author.get("username") or i18n_message("common.unknown"),
            "thumbnail": thumbnail if thumbnail.startswith("https://") else "",
            "category": ", ".join(c.get("name", "") for c in categories),
            "versions": ", ".join(v.get("name", "") for v in versions),
            "game_version": game_version,
            "version": mod.get("current_version") or "",
            "downloads": int(mod.get("download_count") or 0),
            "url": f"{BASE_URL}/mods/{slug}",
        })
    def options(key):
        return [{"value": v["slug"], "label": v["name"]}
                for v in metadata.get(key, []) if v.get("slug") and v.get("name")]
    return {"items": entries, "total": int(listing.get("total", 0)),
            "page": max(1, int(listing.get("page", 1))),
            "pages": max(1, int(listing.get("total_pages", 1))),
            "categories": options("categories"), "versions": options("gameVersions")}


def fetch_catalog(query="", category="", version="", page=1, refresh=False,
                 created_after="", include_adult=False):
    params = {"q": query.strip(), "category": category, "game_version": version,
              "sort": "newest", "page": max(1, page)}
    if created_after in {"7d", "30d", "365d"}:
        params["created_after"] = created_after
    if include_adult:
        params["include_adult"] = "true"
    url = requests.Request("GET", BASE_URL + "/discover", params=params).prepare().url
    path = fs.cache_dir() / ("discover-" + hashlib.sha256(url.encode()).hexdigest() + ".json")
    cached = fs.read_json(path, None)
    valid_cache = (isinstance(cached, dict) and isinstance(cached.get("data"), dict)
                   and isinstance(cached["data"].get("items"), list)
                   and isinstance(cached.get("time"), (int, float)))
    if valid_cache and not refresh and time.time() - cached["time"] < CACHE_TTL:
        return dict(cached["data"], offline=False)
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(5, 20))
        response.raise_for_status()
        result = parse_catalog(response.text, category, version)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        if valid_cache:
            return dict(cached["data"], offline=True)
        raise
    try:
        fs.write_json(path, {"time": time.time(), "data": result})
    except OSError:
        logger.warning("Could not cache catalog", exc_info=True)
    return dict(result, offline=False)


class DiscoverManager(QObject):
    changed = Signal()
    ready = Signal(int, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._categories = [{"value": "", "label": ""}]
        self._versions = [{"value": "", "label": ""}]
        self._busy = False
        self._error = ""
        self._offline = False
        self._page = self._pages = 1
        self._total = 0
        self._generation = 0
        self._pending = None
        self._thread = None
        self._closed = False
        self._request = ("", "", "", 1, False, "", False)
        self._provider = "web"      # "web" (7D2D Mods) | "local" (GitHub)
        self.ready.connect(self._finish)

    @Property("QVariantList", notify=changed)
    def items(self):
        return self._items

    @Property(str, notify=changed)
    def provider(self):
        return self._provider

    @provider.setter
    def provider(self, value: str) -> None:
        value = "local" if value == "local" else "web"
        if value == self._provider:
            return
        self._provider = value
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def categories(self):
        return self._categories

    @Property("QVariantList", notify=changed)
    def versions(self):
        return self._versions

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def offline(self):
        return self._offline

    @Property(int, notify=changed)
    def page(self):
        return self._page

    @Property(int, notify=changed)
    def pages(self):
        return self._pages

    @Property(int, notify=changed)
    def total(self):
        return self._total

    @Slot(str, str, str, int, bool, str, bool)
    def search(self, query, category, version, page, refresh, created_after="", include_adult=False):
        if self._closed:
            return
        self._generation += 1
        self._request = (query, category, version, max(1, page), refresh, created_after, bool(include_adult))
        self._pending = (self._generation, self._request)
        self._busy = True
        self._error = ""
        self._items = []
        self._offline = False
        self.changed.emit()
        if self._thread is None:
            self._start_pending()

    def _start_pending(self):
        generation, request = self._pending
        self._pending = None
        provider = self._provider
        def worker():
            try:
                if provider == "local":
                    self.ready.emit(generation, fetch_local_catalog(request[0], refresh=request[4]), "")
                else:
                    self.ready.emit(generation, fetch_catalog(*request), "")
            except Exception as exc:
                logger.warning("Catalog request failed: %s", exc)
                self.ready.emit(generation, None, "discover.error.fetchFailed")
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    @Slot(int, object, str)
    def _finish(self, generation, result, error):
        self._thread.join()
        self._thread = None
        if self._closed:
            return
        if self._pending is not None:
            self._start_pending()
            return
        if generation != self._generation:
            return
        self._busy = False
        self._error = error
        if result is not None:
            self._items = result["items"]
            self._page, self._pages, self._total = result["page"], result["pages"], result["total"]
            self._offline = result["offline"]
            # kategorie/wersje pochodzą z serwisu - katalog lokalny ich nie
            # definiuje, więc nie nadpisujemy listy zebraną z web
            if self._provider == "web":
                self._categories = self._categories[:1] + result["categories"]
                self._versions = self._versions[:1] + result["versions"]
        self.changed.emit()

    def shutdown(self):
        self._closed = True
        self._pending = None
        if self._thread is not None:
            self._thread.join()
