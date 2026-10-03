"""Sprawdzanie aktualizacji modów na 7daystodiemods.com (etap 11).

Czysta logika, bez Qt. Kontroler (ModManager) woła to z wątku roboczego.

Zasady:
- Aktualizacje NIGDY nie dzieją się same z siebie na tym poziomie - here
  tylko "sprawdź" i "porównaj". Automatyczna instalacja to decyzja UI
  (Ustawienia: autoUpdateMods, domyślnie WYŁĄCZONE - modyfikacja biblioteki
  bez wiedzy użytkownika może zepsuć zapisy gry).
- Powiązanie wpisu Biblioteki ze stroną: slug z pola source ("web:<slug>",
  mody pobrane przez scraper) albo z zapisanego web_slug, a dla modów bez
  żadnego śladu - WYSZUKIWANIE po nazwie (dokładne, case-insensitive).
  Wynik wyszukiwania jest zapisywany z powrotem do wpisu (web_slug), więc
  kosztowne szukanie dzieje się raz na mod.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from backend import discover
from backend.library import LibraryModEntry
from backend.scraper_client import SevenDaysModsClient

logger = logging.getLogger(__name__)

# wynik get_mod dla tego samego sluga trzymamy chwilę w pamięci - "sprawdź
# wszystkie" po restarcie + kolejne kliknięcia nie powinny dharpać serwisu.
# Cache trzyma WYŁĄCZNIE dane ze strony (tytuł, wersja) - has_update zależy
# od wersji LOKALNEJ wpisu, więc liczone jest świeżo przy każdym porównaniu.
_CHECK_TTL_SECONDS = 600
_check_cache: dict[str, tuple[float, tuple[str, str]]] = {}


@dataclass
class UpdateInfo:
    """Wynik porównania wersji jednego moda."""

    library_id: str
    slug: str
    site_title: str = ""
    site_version: str = ""
    local_version: str = ""
    has_update: bool = False


def slug_from_source(source: str) -> str | None:
    """slug zapisany w polu source wpisu ("web:<slug>" z scrapera)."""
    if isinstance(source, str) and source.startswith("web:"):
        slug = source[4:].strip()
        return slug or None
    return None


def version_tuple(text: str | None) -> tuple[int, ...] | None:
    """Wersja jako krotka liczb do porównania ("Version 3.2.9.1" -> (3,2,9,1)).
    None, gdy w tekście nie ma żadnej liczby (nie da się porównać)."""
    nums = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in nums) if nums else None


def is_newer(site_version: str | None, local_version: str | None) -> bool:
    """True tylko gdy wersja ze strony jest NUMERYCZNIE nowa od lokalnej.
    Równo (po normalizacji długości) albo brak liczb = brak aktualizacji -
    propozycja DOWNGRADE-u (np. 3.0 -> 1.0) nigdy nie przechodzi."""
    s = version_tuple(site_version)
    l = version_tuple(local_version)
    if not s or not l:
        return False
    width = max(len(s), len(l))
    s += (0,) * (width - len(s))
    l += (0,) * (width - len(l))
    return s > l


def resolve_slug(entry: LibraryModEntry, client: SevenDaysModsClient) -> str | None:
    """Slug moda na stronie: source -> web_slug -> wyszukanie po nazwie.
    Zapisuje znaleziony slug z powrotem do rejestru (web_slug)."""
    slug = slug_from_source(entry.source) or (entry.web_slug or None)
    if slug:
        return slug

    for name in filter(None, (entry.display_name, entry.mod_name)):
        slug = _search_slug(name, client)
        if slug:
            _persist_web_slug(entry.library_id, slug)
            return slug
    return None


def _search_slug(name: str, client: SevenDaysModsClient) -> str | None:
    """Dopasowanie tytułu w wyszukiwarce serwisu: najpierw dokładne,
    potem prefiksowe na granicy słowa. Serwis wplata wersję w tytuł
    ("The Winchester - V3.2 b9"), więc samo == jest za ostre. Świadomie
    BEZ dalszych zgadywań - brak trafienia = brak sluga (mod bez
    aktualizacji), bo fałszywe powiązanie podmieniłoby zawartość złego moda."""
    try:
        result = discover.fetch_catalog(query=name)
    except Exception as exc:  # noqa: BLE001 - sieć/parsowanie: brak sluga
        logger.warning("Slug lookup for %r failed: %s", name, exc)
        return None
    return match_items_slug(result.get("items", []), name)


def match_items_slug(items: list[dict], name: str) -> str | None:
    """Publiczna wersja dopasowania: dokładny tytuł → prefiks na granicy
    słowa (min. 5 znaków). Używane też przez miniatury ikon (etap 17)."""
    wanted = (name or "").strip().casefold()
    if not wanted:
        return None
    for item in items:   # 1. dokładne
        if str(item.get("title", "")).strip().casefold() == wanted:
            return item.get("slug") or None
    if len(wanted) < 5:
        # krótkie nazwy (techniczne mod_name typu "t3") - za dużo fałszywych
        # prefiksów w wyszukiwarce serwisu; zostaje tylko trafienie dokładne
        return None
    for item in items:   # 2. prefiks "The Winchester" ⊂ "The Winchester - V3.2 b9"
        title = str(item.get("title", "")).strip().casefold()
        if title.startswith(wanted) and \
                (len(title) == len(wanted) or not title[len(wanted)].isalnum()):
            return item.get("slug") or None
    return None


def _persist_web_slug(library_id: str, slug: str) -> None:
    from backend import library

    with library.LIBRARY_LOCK:
        entries = library.load_library_entries()
        for entry in entries:
            if entry.library_id == library_id and entry.web_slug != slug:
                entry.web_slug = slug
                library.save_library_entries(entries)
                return


def check_update(entry: LibraryModEntry, client: SevenDaysModsClient) -> UpdateInfo | None:
    """Porównuje wersję wpisu z wersją na stronie. None = nie umiemy
    ustalić (brak sluga / strona nie odpowiada / mod zniknął ze strony)."""
    slug = resolve_slug(entry, client)
    if not slug:
        return None

    now = time.monotonic()
    cached = _check_cache.get(slug)
    if cached and now - cached[0] < _CHECK_TTL_SECONDS:
        site_title, site_version = cached[1]
    else:
        try:
            mod = client.get_mod(slug)
        except Exception as exc:  # noqa: BLE001 - brak sieci/moda: brak decyzji
            logger.warning("Update check for %r failed: %s", slug, exc)
            return None
        main_file = next((f for f in mod.files if f.file_type == "main"), None) \
            or (mod.files[0] if mod.files else None)
        site_title = mod.title or slug
        site_version = (main_file.version if main_file else None) \
            or mod.current_version or ""
        _check_cache[slug] = (now, (site_title, site_version))

    local_version = entry.version or ""
    # zgłaszamy TYLKO numerycznie nowszą wersję - downgrade albo brak liczb
    # nie jest propozycją aktualizacji (decyzja użytkownika 27.09)
    has_update = is_newer(site_version, local_version)
    return UpdateInfo(entry.library_id, slug, site_title=site_title,
                      site_version=site_version, local_version=local_version,
                      has_update=has_update)


def reset_cache() -> None:
    """Wymusza świeże sprawdzenie (przycisk Odśwież w UI)."""
    _check_cache.clear()
