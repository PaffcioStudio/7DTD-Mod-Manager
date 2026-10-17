"""Sprawdzanie aktualizacji samego programu przez GitHub Releases.

Wydania są publikowane pod STAŁYM tagiem ``release`` (zob. git-release.sh),
a numer wersji jest w tytule wydania (``name``), np. "1.0.44". Dlatego
pytamy API o ten jeden tag i porównujemy tytuł z APP_VERSION.

Część czysta (parse_version / is_newer / notes_since) nie zależy od Qt.
QObject ``AppUpdates`` wystawiony do QML robi zapytanie w wątku i zgłasza
wynik sygnałami:

* ``updateAvailable(version, notes, url)`` - zawsze, gdy jest nowsza wersja,
* ``upToDate(version)`` / ``checkFailed(error)`` - tylko przy ręcznym
  sprawdzeniu (start aplikacji milczy, gdy nie ma nic do pokazania).
"""
from __future__ import annotations

import logging
import re
import threading

import requests
from PySide6.QtCore import Property, QObject, Signal, Slot

from services.app_info import APP_VERSION

logger = logging.getLogger(__name__)

REPO = "PaffcioStudio/7DTD-Mod-Manager"
API_URL = f"https://api.github.com/repos/{REPO}/releases/tags/release"
RELEASE_PAGE = f"https://github.com/{REPO}/releases/tag/release"
_MAX_NOTES = 6000

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")
_SECTION_RE = re.compile(r"^##\s+(?:\(\s*(?:latest|old)\s*\)\s+)?v?(\d+(?:\.\d+)*)\s*$", re.M | re.I)


def parse_version(text: str) -> tuple[int, ...] | None:
    """"1.0.44" / "v1.0.44" / "Release 1.0.44" -> (1, 0, 44); brak liczby -> None."""
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _padded(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)), b + (0,) * (size - len(b))


def is_newer(remote: str, local: str) -> bool:
    """True, gdy wersja ``remote`` jest ściśle nowsza niż ``local``."""
    r, l = parse_version(remote), parse_version(local)
    if r is None or l is None:
        return False
    r, l = _padded(r, l)
    return r > l


def notes_since(body: str, local_version: str) -> str:
    """Z całego RELEASE_NOTES.md zostawia tylko sekcje nowsze niż ``local_version``.

    Plik zawiera historię wszystkich wersji ("## 1.0.44", "## 1.0.43"...),
    a użytkownika interesuje wyłącznie to, co doszło po jego wersji. Bez
    rozpoznanych sekcji zwracamy treść w całości (przycięta).
    """
    body = (body or "").strip()
    matches = list(_SECTION_RE.finditer(body))
    if matches:
        parts: list[str] = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            if is_newer(m.group(1), local_version):
                parts.append(body[m.start():end].strip())
        if parts:
            body = "\n\n".join(parts)
        else:
            # nic nowszego w historii - pokaż samą najnowszą sekcję
            end = matches[1].start() if len(matches) > 1 else len(body)
            body = body[matches[0].start():end].strip()
    if len(body) > _MAX_NOTES:
        body = body[:_MAX_NOTES].rstrip() + "\n\n..."
    return body


def parse_release(payload: dict, local_version: str = APP_VERSION) -> dict | None:
    """Odpowiedź GitHub API -> {version, notes, url, newer} albo None, gdy
    tytuł wydania nie zawiera numeru wersji."""
    if not isinstance(payload, dict):
        return None
    title = str(payload.get("name") or "").strip()
    if parse_version(title) is None:
        return None
    version = ".".join(str(n) for n in parse_version(title))  # type: ignore[arg-type]
    url = str(payload.get("html_url") or RELEASE_PAGE)
    if not url.startswith("https://"):
        url = RELEASE_PAGE
    return {
        "version": version,
        "notes": notes_since(str(payload.get("body") or ""), local_version),
        "url": url,
        "newer": is_newer(version, local_version),
    }


def fetch_latest(timeout: tuple[int, int] = (10, 20)) -> dict | None:
    response = requests.get(
        API_URL,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": f"7dtd-mod-manager/{APP_VERSION}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_release(response.json())


class AppUpdates(QObject):
    """Wystawiony do QML jako ``AppUpdates``."""

    busyChanged = Signal()
    updateAvailable = Signal(str, str, str)   # wersja, notatki (markdown), url
    upToDate = Signal(str)                    # wersja (tylko ręczne sprawdzenie)
    checkFailed = Signal(str)                 # komunikat (tylko ręczne sprawdzenie)

    def __init__(self, settings=None, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._busy = False
        self._release_url = RELEASE_PAGE

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, constant=True)
    def releasePage(self) -> str:
        return RELEASE_PAGE

    @Slot()
    def checkOnStartup(self) -> None:
        """Start aplikacji: tylko gdy włączone w Ustawieniach, bez komunikatów."""
        if self._settings is not None and not getattr(self._settings, "autoCheckAppUpdates", True):
            logger.info("App update check on startup disabled in settings")
            return
        self._start(manual=False)

    @Slot()
    def checkNow(self) -> None:
        """Przycisk w Ustawieniach: zawsze odpowiada (jest nowa / aktualna / błąd)."""
        self._start(manual=True)

    # ------------------------------------------------------------------ #
    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    def _start(self, manual: bool) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker() -> None:
            try:
                info = fetch_latest()
            except Exception as exc:  # noqa: BLE001 - sieć/JSON: komunikat dla UI
                logger.warning("App update check failed: %s", exc)
                if manual:
                    self.checkFailed.emit(str(exc))
            else:
                if info is None:
                    logger.warning("App update check: release title has no version number")
                    if manual:
                        self.checkFailed.emit("no version in release title")
                elif info["newer"]:
                    logger.info("App update available: %s (current %s)", info["version"], APP_VERSION)
                    self.updateAvailable.emit(info["version"], info["notes"], info["url"])
                elif manual:
                    self.upToDate.emit(APP_VERSION)
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()
