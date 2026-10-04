"""Dynamic metadata and download resolution for the Undead Legacy overhaul.

The project's public download page is the stable source of truth for the
current release.  The manifest intentionally stores the stable mirror URL
(``/dl?v=mirror``), while this module reads the current version from the
v2.6 row and resolves the mirror redirect only when a download actually
starts.  This avoids pinning the app to a signed/temporary Dropbox URL.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

logger = logging.getLogger(__name__)

DOWNLOAD_PAGE_URL = "https://ul.subquake.com/download"
MIRROR_URL = "https://ul.subquake.com/dl?v=mirror"
GAME_VERSION = "v2.6"
DEFAULT_VERSION = "2.7.40"
CACHE_TTL = 900
TIMEOUT = (5, 20)
USER_AGENT = "7DTD-Mod-Manager/1.0 (+Undead Legacy dynamic source)"

_VERSION_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")


class _RowParser(HTMLParser):
    """Small HTML parser that records table rows and anchor URLs/text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._tr_depth = 0
        self._cell_depth = 0
        self._cell_tag = ""
        self._current_cell: dict | None = None
        self._current_row: list[dict] | None = None
        self._anchor_depth = 0
        self._anchor: dict | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag == "tr" and self._tr_depth == 0:
            self._tr_depth = 1
            self._current_row = []
            return
        if self._tr_depth == 0:
            return
        if tag == "tr":
            self._tr_depth += 1
            return
        if tag in {"td", "th"} and self._cell_depth == 0:
            self._cell_tag = tag
            self._cell_depth = 1
            self._current_cell = {"text": [], "links": []}
            return
        if self._cell_depth:
            if tag in {"td", "th"}:
                self._cell_depth += 1
                return
            if tag == "a" and self._anchor_depth == 0:
                self._anchor_depth = 1
                self._anchor = {
                    "href": str(attrs_dict.get("href") or "").strip(),
                    "title": str(attrs_dict.get("title") or "").strip(),
                    "text": [],
                }

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._tr_depth == 0:
            return
        if tag == "a" and self._anchor_depth:
            anchor = self._anchor or {"href": "", "title": "", "text": []}
            anchor["text"] = " ".join(anchor["text"]).strip()
            if self._current_cell is not None:
                self._current_cell["links"].append(anchor)
            self._anchor = None
            self._anchor_depth = 0
            return
        if tag in {"td", "th"} and self._cell_depth:
            self._cell_depth -= 1
            if self._cell_depth == 0:
                cell = self._current_cell or {"text": [], "links": []}
                cell["text"] = " ".join(cell["text"]).strip()
                if self._current_row is not None:
                    self._current_row.append(cell)
                self._current_cell = None
            return
        if tag == "tr" and self._tr_depth:
            if self._tr_depth == 1:
                self.rows.append({"cells": self._current_row or []})
                self._current_row = None
                self._tr_depth = 0
            else:
                self._tr_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell_depth and self._current_cell is not None:
            text = " ".join(str(data).split())
            if text:
                self._current_cell["text"].append(text)
            if self._anchor_depth and self._anchor is not None and text:
                self._anchor["text"].append(text)


def _is_mirror_link(href: str) -> bool:
    if not href:
        return False
    absolute = urljoin(DOWNLOAD_PAGE_URL, href)
    try:
        parsed = urlsplit(absolute)
        query = parse_qs(parsed.query)
    except ValueError:
        return False
    return (
        parsed.netloc.lower() == "ul.subquake.com"
        and parsed.path.rstrip("/") == "/dl"
        and query.get("v", [""])[0].lower() == "mirror"
    )


def _extract_latest_version(row: dict) -> str | None:
    cells = row.get("cells") or []
    if len(cells) < 2:
        return None
    text = str(cells[1].get("text") or "").strip()
    matches = _VERSION_RE.findall(text)
    return matches[-1] if matches else None


_cache_lock = threading.Lock()
_cache_at = 0.0
_cache_value: dict | None = None


def fetch_latest_release(*, refresh: bool = False) -> dict:
    """Read the current v2.6 release row from the official download page.

    Returns ``version``, ``game_version``, ``release_date`` and the stable
    ``download_url``.  A small cache prevents repeated searches in the same UI
    session from hammering the site; ``refresh=True`` bypasses it.
    """
    global _cache_at, _cache_value
    now = time.time()
    with _cache_lock:
        if _cache_value is not None and not refresh and now - _cache_at < CACHE_TTL:
            return dict(_cache_value)

    response = requests.get(
        DOWNLOAD_PAGE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    parser = _RowParser()
    parser.feed(response.text)

    for row in parser.rows:
        cells = row.get("cells") or []
        if not cells:
            continue
        row_game_version = str(cells[0].get("text") or "").strip()
        if row_game_version != GAME_VERSION:
            continue
        links = []
        for cell in cells:
            links.extend(cell.get("links") or [])
        mirror = next((link for link in links if _is_mirror_link(link.get("href", ""))), None)
        if mirror is None:
            continue
        version = _extract_latest_version(row)
        if not version:
            raise ValueError("Undead Legacy mirror row has no recognizable version")
        date_match = re.search(r"\b(\d{4}\.\d{2}\.\d{2})\b", str(cells[1].get("text") or ""))
        value = {
            "version": version,
            "game_version": GAME_VERSION,
            "release_date": date_match.group(1) if date_match else "",
            "download_url": urljoin(DOWNLOAD_PAGE_URL, mirror.get("href") or MIRROR_URL),
        }
        with _cache_lock:
            _cache_at = now
            _cache_value = dict(value)
        return value

    raise ValueError("Undead Legacy v2.6 mirror row was not found on the official download page")


def resolve_mirror_url(url: str = MIRROR_URL) -> str:
    """Resolve the stable Undead Legacy mirror to the current archive URL.

    The response body is never consumed: a streamed GET is enough to obtain
    the final redirect target while keeping the actual ZIP download for the
    normal resumable downloader.
    """
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Referer": "https://ul.subquake.com/",
        },
        timeout=TIMEOUT,
        allow_redirects=True,
        stream=True,
    )
    try:
        response.raise_for_status()
        final_url = str(response.url or "").strip()
    finally:
        response.close()
    if not final_url:
        raise ValueError("Undead Legacy mirror did not resolve to a downloadable URL")
    return final_url
