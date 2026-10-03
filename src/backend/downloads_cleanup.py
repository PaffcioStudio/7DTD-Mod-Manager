"""Zarządzanie pobranymi archiwami w downloads/ (D9, etap 9 krok B).

Zasady z D9:
- DOMYŚLNIE nic nie jest kasowane automatycznie (transfer limitowany,
  dysk nie - priorytet: nie pobierać ponownie).
- Ręczne "Wyczyść pobrane pliki" kasuje WSZYSTKO z downloads/
  (użytkownik widzi podgląd zwolnionego miejsca przed potwierdzeniem).
- Auto-czyszczenie dotyczy WYŁĄCZNIE plików starszych niż próg ORAZ
  już zainstalowanych do Biblioteki - nigdy nie kasować archiwum
  nierozpakowanego/niezainstalowanego.

"Już zainstalowane" wiemy z rejestru installed-archives.json:
worker scrapera dopisuje archiwum po UDANEJ instalacji do Biblioteki.
Archiwa pobrane przed powstaniem rejestru nigdy nie podlegają
auto-czyszczeniu (konserwatywnie: traktowane jak niezainstalowane).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from services import filesystem_service as fs
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)

# jedno watko-bezpieczne zamkniecie na read-modify-write rejestru
# (rownolegle pobrania scrapera dopisuja wpisy z watkow roboczych)
_REGISTRY_LOCK = threading.RLock()
_ARCHIVE_LOCK = threading.RLock()
_active_users = 0


@contextmanager
def archive_use():
    """Prevent cleanup while a worker downloads or installs an archive."""
    global _active_users
    with _ARCHIVE_LOCK:
        _active_users += 1
    try:
        yield
    finally:
        with _ARCHIVE_LOCK:
            _active_users -= 1


def _exclusive_cleanup(operation):
    @wraps(operation)
    def guarded(*args, **kwargs):
        with _ARCHIVE_LOCK:
            if _active_users:
                raise RuntimeError(i18n_message("downloads.cleanup.busy"))
            return operation(*args, **kwargs)
    return guarded


def _registry_path() -> Path:
    return fs.installed_archives_path()


def _load_registry() -> dict:
    try:
        data = json.loads(_registry_path().read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("installed"), list):
            data["installed"] = [e for e in data["installed"] if isinstance(e, dict)]
            return data
    except (OSError, ValueError):
        pass
    return {"installed": []}


def _save_registry(data: dict) -> None:
    fs.write_json(_registry_path(), data)


def register_installed(filename: str, size: int, source: str = "") -> None:
    """Dopisuje archiwum jako zainstalowane do Biblioteki (po sukcesie)."""
    name = Path(filename).name
    stat = (fs.downloads_dir() / name).stat()
    with _REGISTRY_LOCK:
        data = _load_registry()
        entries = [e for e in data["installed"] if e.get("file") != name]
        entries.append({
            "file": name,
            "size": int(size),
            "mtime_ns": stat.st_mtime_ns,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": source,
        })
        data["installed"] = entries
        _save_registry(data)


def is_installed(filename: str) -> bool:
    name = Path(filename).name
    with _REGISTRY_LOCK:
        data = _load_registry()
    return any(e.get("file") == name for e in data["installed"])


def scan_downloads() -> list[dict]:
    """Lista plików w downloads/ ze statystykami (bez zagnieżdżeń)."""
    root = fs.downloads_dir()
    result = []
    with _REGISTRY_LOCK:
        installed = {e.get("file"): e for e in _load_registry()["installed"]}
    try:
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_symlink() or not entry.is_file():
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            result.append({
                "file": entry.name,
                "path": str(entry),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "installed": (entry.suffix != ".part"
                              and installed.get(entry.name, {}).get("size") == stat.st_size
                              and installed.get(entry.name, {}).get("mtime_ns") == stat.st_mtime_ns),
            })
    except OSError:
        pass
    return result


def stats() -> dict:
    """Podgląd do UI: liczba plików, łączny rozmiar, ile zainstalowanych."""
    files = scan_downloads()
    total = sum(f["size"] for f in files)
    installed = sum(1 for f in files if f["installed"])
    return {
        "count": len(files),
        "size": total,
        "installedCount": installed,
    }


@_exclusive_cleanup
def clean_all() -> tuple[int, int]:
    """Ręczne czyszczenie: kasuje WSZYSTKIE pliki z downloads/.
    Zwraca (zwolnione_bajty, liczba_plików). Rejestr zostaje - wpisy
    dla nieistniejących plików przycina _prune_registry."""
    freed = 0
    count = 0
    for info in scan_downloads():
        try:
            Path(info["path"]).unlink()
            freed += info["size"]
            count += 1
        except OSError as exc:
            logger.warning("Failed to remove %s: %s", info["path"], exc)
    _prune_registry()
    return freed, count


@_exclusive_cleanup
def auto_clean(max_age_days: float) -> tuple[int, int, list[str]]:
    """Auto-czyszczenie wg D9: WYŁĄCZNIE pliki starsze niż próg ORAZ
    zarejestrowane jako zainstalowane. Zwraca (zwolnione_bajty, liczba,
    nazwy_usuniętych)."""
    cutoff = time.time() - max(0.0, max_age_days) * 86_400
    freed = 0
    count = 0
    removed: list[str] = []
    for info in scan_downloads():
        if not info["installed"] or info["mtime"] > cutoff:
            continue
        try:
            Path(info["path"]).unlink()
            freed += info["size"]
            count += 1
            removed.append(info["file"])
        except OSError as exc:
            logger.warning("Auto-cleanup: did not remove %s: %s",
                           info["path"], exc)
    _prune_registry()
    return freed, count, removed


def _prune_registry() -> None:
    """Usuwa z rejestru wpisy o plikach, których już nie ma na dysku."""
    with _REGISTRY_LOCK:
        data = _load_registry()
        present = {info["file"] for info in scan_downloads()}
        kept = [e for e in data["installed"] if e.get("file") in present]
        if len(kept) != len(data["installed"]):
            data["installed"] = kept
            _save_registry(data)
