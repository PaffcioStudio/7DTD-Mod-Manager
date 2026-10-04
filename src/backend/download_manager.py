"""Download queue: REAL downloads (modpacks from Git/GitHub-ZIP URLs,
migration stage 5) + the demo simulator (restoreDemo) behind one model.

Real items ("url" kind) run in worker threads via
backend/modpack_downloader.py and install into the LIBRARY
(library_ops.install_modpack_to_library - additive, content-deduped).
Pause/resume: HTTP downloads (ZIP / GitHub release) support true pause -
the stream is closed and resumed with HTTP Range from the kept .part
file; git clone supports only cancel/retry (a clone cannot be suspended).
Demo items (update/catalog kinds, seeded only by restoreDemo) are driven
by the tick() timer exactly as before.
"""

from __future__ import annotations

import json
import logging
import random
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    QObject,
    Qt,
    Signal,
    Slot,
    QTimer,
)

from backend import library
from backend import library_ops
from backend import instances as inst_mod
from backend import downloads_cleanup
from backend import mock_data
from backend import modpack_downloader
from backend import undead_legacy
from backend.modinfo import find_modinfo
from backend.scraper_client import (
    SevenDaysModsClient,
    parse_mod_url,
    detect_file_game_versions,
    detect_artifact_game_versions,
    game_version_matches,
    select_concrete_game_version,
)
from backend.game_versions import (
    required_game_branch, resolve_downloaded_branch, version_requirement_text,
    versions_root, APP_ID)
from backend.events import EventBus
from backend.fileops import OperationCancelled
from backend.mod_manager import ModManager
from services import install_log
from services.i18n_message import message as i18n_message
from models.mod import human_size
from services import filesystem_service as fs
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

TICK_MS = 120


class DownloadItem:
    def __init__(self, kind: str, ref_id: str, title: str, subtitle: str,
                 total_bytes: int, progress: float = 0.0,
                 status: str = "queued", fail_at: float | None = None,
                 real: bool = False, pausable: bool = True,
                 url: str = "", flavor: str = "",
                 update_for: str | None = None,
                 chosen_file_ref: str = "",
                 game_version: str = "") -> None:
        self.id: str = uuid.uuid4().hex[:10]
        self.kind = kind                    # "update" | "catalog" | "url" | "mod"
        self.ref_id = ref_id
        self.title = title
        self.subtitle = subtitle
        self.total_bytes = max(0, int(total_bytes))   # 0 = rozmiar nieznany
        self.downloaded = int(progress * self.total_bytes)
        self.status = status                # queued/downloading/paused/failed/completed
        self.speed = 0.0                    # bytes / s
        self.base_speed = random.uniform(7_000_000, 26_000_000)
        self.fail_at = fail_at              # fraction where a scripted failure happens
        self.finished_at: float | None = None
        # real (worker-backed) items - migration stage 5
        self.real = real
        self.pausable = pausable            # HTTP: yes; git clone: no
        self.url = url
        self.flavor = flavor                # "git" | "github" | "zip" | "mod"
        self.update_for = update_for        # library_id aktualizowanego wpisu (kind="update")
        self.chosen_file_ref = chosen_file_ref  # "hosted:<id>" / "external:<url>" (etap 13)
        self.game_version = game_version    # wersja gry modu wg katalogu (slug, "" = nieznana)
        self.temp_dir: Path | None = None
        self.restored_paused = False        # odtworzone z downloads.json jako pauza (brak żywego workera)
        self.restored_from_queue = False   # pozycja odtworzona z poprzedniej sesji
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self._last_sample: tuple[float, int] | None = None  # (monotonic, bytes)
        # DepotDownloader reports progress as a percentage with decimal
        # precision. Keep that value separately so the UI can render e.g.
        # 12.50% exactly even when total_bytes is small in unit tests or when
        # converting the percentage back to an integer byte count would round
        # it to 12%. ``downloaded`` remains an integer byte estimate for
        # speed/size/ETA calculations.
        self._progress_override: float | None = None

    # ------------------------------------------------------------------ #
    @property
    def progress(self) -> float:
        if self._progress_override is not None:
            return max(0.0, min(1.0, float(self._progress_override)))
        if self.total_bytes <= 0:
            return 0.0  # rozmiar nieznany - pasek pokazuje tryb nieokreślony
        downloaded = max(0, int(self.downloaded or 0))
        total = max(1, int(self.total_bytes or 0))
        return max(0.0, min(1.0, downloaded / total))

    @property
    def status_text(self) -> str:
        return i18n_message(f"download.status.{self.status}") if self.status in {
            "queued", "downloading", "paused", "failed", "completed"
        } else self.status

    @property
    def speed_text(self) -> str:
        if self.status != "downloading" or self.speed <= 0:
            return "-"
        return f"{human_size(self.speed)}/s"

    @property
    def eta_seconds(self) -> int:
        if self.status != "downloading" or self.speed <= 0 or self.total_bytes <= 0:
            return 0
        remaining_bytes = max(0, self.total_bytes - max(0, self.downloaded))
        return max(0, int(remaining_bytes / self.speed))

    @property
    def eta_text(self) -> str:
        seconds = self.eta_seconds
        if seconds <= 0:
            return ""
        if seconds < 60:
            return i18n_message("download.eta.seconds", {"seconds": max(1, seconds)})
        return i18n_message("download.eta.minutes", {
            "minutes": seconds // 60, "seconds": seconds % 60
        })


class DownloadListModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = IdRole + 1
    SubtitleRole = IdRole + 2
    ProgressRole = IdRole + 3
    ProgressTextRole = IdRole + 4
    TotalTextRole = IdRole + 5
    DownloadedTextRole = IdRole + 6
    SpeedTextRole = IdRole + 7
    EtaTextRole = IdRole + 8
    EtaSecondsRole = IdRole + 9
    StatusKeyRole = IdRole + 10
    StatusTextRole = IdRole + 11
    KindRole = IdRole + 12
    PausableRole = IdRole + 13

    ROLES = {
        IdRole: b"downloadId",
        TitleRole: b"title",
        SubtitleRole: b"subtitle",
        ProgressRole: b"progress",
        ProgressTextRole: b"progressText",
        TotalTextRole: b"totalText",
        DownloadedTextRole: b"downloadedText",
        SpeedTextRole: b"speedText",
        EtaTextRole: b"etaText",
        EtaSecondsRole: b"etaSeconds",
        StatusKeyRole: b"statusKey",
        StatusTextRole: b"statusText",
        KindRole: b"kind",
        PausableRole: b"pausable",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[DownloadItem] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        total = max(0, int(item.total_bytes or 0))
        downloaded = max(0, int(item.downloaded or 0))
        # Nigdy nie pokazujemy wartości ujemnych ani stanu > 100%.  Błędny
        # callback/progress z zewnętrznego workera nie może przeciec do UI.
        if total > 0:
            downloaded = min(downloaded, total)
        known = total > 0
        attr = {
            self.IdRole: item.id,
            self.TitleRole: item.title,
            self.SubtitleRole: item.subtitle,
            self.ProgressRole: item.progress if known else 0.0,
            self.ProgressTextRole:
                f"{item.progress * 100:.2f}".rstrip("0").rstrip(".") + "%"
                if known else "",
            self.TotalTextRole: human_size(total) if known else "",
            self.DownloadedTextRole: (
                f"{human_size(downloaded)} / {human_size(total)}"
                if known else human_size(downloaded)),
            self.SpeedTextRole: item.speed_text,
            self.EtaTextRole: item.eta_text,
            self.EtaSecondsRole: item.eta_seconds,
            self.StatusKeyRole: item.status,
            self.StatusTextRole: item.status_text,
            self.KindRole: item.kind,
            self.PausableRole: item.pausable,
        }
        return attr.get(role)

    # ------------------------------------------------------------------ #
    @property
    def items(self) -> list[DownloadItem]:
        return self._items

    def append(self, item: DownloadItem) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def remove(self, download_id: str) -> None:
        for row, item in enumerate(self._items):
            if item.id == download_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                return

    def row_of(self, download_id: str) -> int:
        for row, item in enumerate(self._items):
            if item.id == download_id:
                return row
        return -1

    def touch(self, row: int) -> None:
        if 0 <= row < len(self._items):
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)

    def touch_all(self) -> None:
        if self._items:
            top = self.index(0, 0)
            bottom = self.index(len(self._items) - 1, 0)
            self.dataChanged.emit(top, bottom)

    def clear(self) -> None:
        self.beginResetModel()
        self._items = []
        self.endResetModel()


class DownloadManager(QObject):
    """Exposed to QML as ``Downloads``."""

    updateFinished = Signal(str)        # mod id
    activeCountChanged = Signal()
    completedCountChanged = Signal()
    activeMapChanged = Signal()
    # real URL downloads (stage 5); emitted from worker threads
    urlProgress = Signal(str, object, object, str)   # id, done, total, label; object keeps 64-bit+ byte counts safe
    urlState = Signal(str, str)                # id, "downloading"/"paused"/"completed[:info]"/"failed:msg"/"cancelled"
    modpackInstalled = Signal(str)             # summary - ModManager reloads the library
    # zestaw modów (overhaul ze strony) - pytanie: osobna instancja czy mody
    multiModFound = Signal(str, str, int)      # item_id, tytuł, liczba modów
    instancesRefreshNeeded = Signal()          # przeładuj rejestr instancji w UI
    # scraper mods (stage 9): id, title, subtitle, total_bytes (0 = no change)
    modMeta = Signal(str, str, str, object)     # total bytes; object avoids Qt signed-int overflow
    archiveBusyChanged = Signal()
    archivePreviewReady = Signal(str, int)
    archiveJobFinished = Signal(str, object, str)

    def __init__(self, mods: ModManager, bus: EventBus,
                 settings: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self._mods = mods
        self._bus = bus
        self._settings = settings
        # GameVersionsManager owns the real DepotDownloader process.  The
        # common queue only mirrors its state, so game pause/resume/cancel
        # actions must be forwarded to that owner.
        self._game_versions = None
        self._model = DownloadListModel(self)
        self._last_tick = time.monotonic()
        self._last_queue_json = ""
        self._multi_decisions: dict[str, dict] = {}   # item_id -> {event, choice}
        self._archive_busy = False
        self._archive_thread = None
        self.archiveJobFinished.connect(self._on_archive_job_finished)
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(60 * 60 * 1000)
        self._cleanup_timer.timeout.connect(self._auto_clean_archives)
        self._cleanup_timer.start()
        settings.autoCleanDownloadsChanged.connect(self._auto_clean_archives)
        QTimer.singleShot(5000, self._auto_clean_archives)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # real download flow (stage 5); demo seeds only via restoreDemo
        self.urlProgress.connect(self._on_url_progress)
        self.urlState.connect(self._on_url_state)
        self.modMeta.connect(self._on_mod_meta)

        # trwałość kolejki (etap 12): niezakończone pozycje z poprzedniej
        # sesji wracają - aktywne kontynuują z .part, pauzy czekają na Wznów
        self._restore_queue()

        mods.demoReset.connect(self.reset_demo)

    @Property(bool, notify=archiveBusyChanged)
    def archiveBusy(self) -> bool:
        return self._archive_busy

    @Property(str, constant=True)
    def archiveDirectory(self) -> str:
        return str(fs.downloads_dir())

    @Slot()
    def previewArchives(self) -> None:
        self._archive_job("preview")

    @Slot()
    def cleanArchives(self) -> None:
        self._archive_job("manual")

    def _auto_clean_archives(self) -> None:
        if self._settings.autoCleanDownloads != "never":
            self._archive_job("auto")

    def _archive_job(self, mode: str) -> None:
        if self._archive_busy:
            return
        days = {"24h": 1, "7d": 7}.get(self._settings.autoCleanDownloads)
        if mode == "auto" and days is None:
            return
        self._archive_busy = True
        self.archiveBusyChanged.emit()

        def worker():
            try:
                if mode == "preview":
                    result = downloads_cleanup.stats()
                elif mode == "manual":
                    result = downloads_cleanup.clean_all()
                else:
                    result = downloads_cleanup.auto_clean(days)
                self.archiveJobFinished.emit(mode, result, "")
            except Exception as exc:
                self.archiveJobFinished.emit(mode, None, str(exc))

        self._archive_thread = threading.Thread(target=worker, daemon=True)
        self._archive_thread.start()

    @Slot(str, object, str)
    def _on_archive_job_finished(self, mode, result, error):
        self._archive_busy = False
        self.archiveBusyChanged.emit()
        if error:
            if mode != "auto":
                self._bus.toastKey("common.operationFailed", {"error": error}, "warning")
            return
        if mode == "preview":
            self.archivePreviewReady.emit(human_size(result["size"]), result["count"])
        elif mode == "manual" or result[1]:
            self._bus.toastKey("toast.downloads.archiveCleanup", {"count": result[1], "size": human_size(result[0])}, "success")

    # ------------------------------------------------------------------ #
    # seeding
    # ------------------------------------------------------------------ #
    def _seed_initial(self) -> None:
        active = mock_data.INITIAL_ACTIVE_DOWNLOAD
        item = DownloadItem(
            kind=active["kind"],
            ref_id=active["ref_id"],
            title=active["title"],
            subtitle=active["subtitle"],
            total_bytes=active["total_bytes"],
            progress=active["progress"],
            status="downloading",
        )
        self._model.append(item)

        done = mock_data.INITIAL_COMPLETED_DOWNLOAD
        completed = DownloadItem(
            kind=done["kind"],
            ref_id=done["ref_id"],
            title=done["title"],
            subtitle=done["subtitle"],
            total_bytes=done["total_bytes"],
            progress=1.0,
            status="completed",
        )
        completed.finished_at = time.monotonic()
        self._model.append(completed)

    # ------------------------------------------------------------------ #
    def shutdown(self) -> None:
        """Stop the simulation timer (used on app teardown)."""
        self._persist_queue()   # pobierania w locie wrócą po restarcie
        self._timer.stop()
        self._cleanup_timer.stop()
        if self._archive_thread is not None:
            self._archive_thread.join()

    @Slot(object)
    def setGameVersionsManager(self, manager) -> None:
        """Podepnij właściciela procesów DepotDownloadera.

        DownloadManager nie uruchamia ani nie zatrzymuje DepotDownloadera
        bezpośrednio; dzięki temu wspólna kolejka pozostaje warstwą UI/stanu.
        """
        self._game_versions = manager

    @Slot()
    def resumeRestoredGameDownloads(self) -> None:
        """Automatycznie wznow wyłącznie gry odtworzone z poprzedniej sesji.

        Aktywne pobranie zapisujemy jako ``queued`` przy ponownym starcie,
        a ręcznie zapauzowane pozostaje ``paused``. DepotDownloader sam
        wykorzystuje istniejące pliki stagingu w game-versions/<branch>.
        """
        if self._game_versions is None:
            return
        item = next((i for i in self._model.items
                     if i.kind == "game" and i.status == "queued"
                     and i.restored_from_queue), None)
        if item is None:
            return
        item.restored_from_queue = False
        self._model.touch(self._model.row_of(item.id))
        self._emit_counts()
        self._game_versions.resume(item.ref_id)

    # ------------------------------------------------------------------ #
    # trwałość kolejki (etap 12) - wzorowane na starym mod_downloads.py:
    # niezakończone pozycje (queued/downloading/paused) zapisywane przy
    # KAŻDEJ zmianie stanu do downloads.json i odtwarzane na starcie;
    # DONE/FAILED/CANCELLED nie są zapisywane - zamknięcie appki zapomina
    # tylko to, co się zakończyło
    # ------------------------------------------------------------------ #
    def _persist_queue(self) -> None:
        records = []
        for item in self._model.items:
            if not item.real or item.status in ("failed", "cancelled"):
                continue
            # Zakończone pobrania typu "mod" pozostają w kolejce jako
            # historia, ale ich stan "Pobrano" nie może być traktowany jako
            # dowód, że zawartość nadal istnieje. Instancję Overhaul można
            # przecież usunąć z zakładki Instancje, pozostawiając wpis kolejki.
            if item.status == "completed" and item.kind != "mod":
                continue
            records.append({
                "kind": item.kind,
                "ref_id": item.ref_id,
                "chosen_file_ref": item.chosen_file_ref,
                "title": item.title,
                "subtitle": item.subtitle,
                "url": item.url,
                "flavor": item.flavor,
                "update_for": item.update_for,
                "pausable": item.pausable,
                "game_version": item.game_version,
                "status": item.status,
                "total_bytes": int(item.total_bytes or 0),
                "downloaded": int(item.downloaded or 0),
                "progress": float(item.progress),
                "temp_dir": str(item.temp_dir) if item.temp_dir else "",
            })
        payload = json.dumps({"items": records}, ensure_ascii=False)
        if payload == self._last_queue_json:
            return   # nic się nie zmieniło (np. tik symulatora demo) - bez zapisu
        try:
            fs.write_json(fs.downloads_queue_path(), {"items": records})
            self._last_queue_json = payload
        except OSError as exc:
            logger.warning("Failed to save the download queue: %s", exc)

    def _restore_queue(self) -> None:
        data = fs.read_json(fs.downloads_queue_path(), None)
        items = data.get("items", []) if isinstance(data, dict) else []
        for rec in items:
            if not isinstance(rec, dict):
                continue
            kind = str(rec.get("kind", "url"))
            # Game-version downloads have no HTTP URL; their source of truth
            # is the DepotDownloader staging directory under game-versions/.
            if kind != "game" and not rec.get("url"):
                continue
            saved_status = str(rec.get("status", "queued"))
            if kind == "mod" and saved_status == "completed":
                status = "completed"
            else:
                status = "paused" if saved_status == "paused" else "queued"
            try:
                total_bytes = max(0, int(rec.get("total_bytes", 0) or 0))
            except (TypeError, ValueError):
                total_bytes = 0
            try:
                saved_progress = max(0.0, min(1.0, float(rec.get("progress", 0.0) or 0.0)))
            except (TypeError, ValueError):
                saved_progress = 0.0
            item = DownloadItem(
                kind=kind,
                ref_id=str(rec.get("ref_id", "")),
                title=str(rec.get("title", "")),
                subtitle=str(rec.get("subtitle", "")),
                total_bytes=total_bytes,
                progress=saved_progress,
                status=status,
                real=True,
                pausable=bool(rec.get("pausable", True)),
                url=str(rec.get("url", "")),
                flavor=str(rec.get("flavor", "")),
                update_for=rec.get("update_for"),
                chosen_file_ref=str(rec.get("chosen_file_ref") or ""),
                game_version=required_game_branch(str(rec.get("game_version") or "")),
            )
            item.restored_from_queue = True
            if status == "paused":
                item.restored_paused = True
            if kind == "game":
                # The actual DepotDownloader worker is owned by
                # GameVersionsManager. Do not create an HTTP worker for it.
                item.flavor = "game"
                item.real = True
                item.pausable = True
                item.downloaded = max(0, int(rec.get("downloaded", item.downloaded) or 0))
                item._progress_override = saved_progress
            temp_dir = str(rec.get("temp_dir") or "")
            if item.flavor != "git" and temp_dir and Path(temp_dir).is_dir():
                item.temp_dir = Path(temp_dir)
                # wstępny postęp z istniejącego .part (UI), dokładny offset
                # i tak wylicza _http_download_file przy wznowieniu Range
                for zip_name in ("download.zip", "release.zip"):
                    part = item.temp_dir / f"{zip_name}.part"
                    if part.exists():
                        item.downloaded = part.stat().st_size
                        break
            elif item.kind == "url":
                item.temp_dir = Path(tempfile.mkdtemp(prefix="mm-dl-"))
            self._model.append(item)
            logger.info("Restored download queue item: %s (%s)", item.title, status)
        if any(i.status == "queued" for i in self._model.items):
            self._promote_queued()
            self._emit_counts()

    def reset_demo(self) -> None:
        self._model.clear()
        self._seed_initial()
        self._emit_counts()

    # ------------------------------------------------------------------ #
    # properties
    # ------------------------------------------------------------------ #
    @Property("QVariant", constant=True)
    def model(self) -> QAbstractListModel:
        return self._model

    @Property(int, notify=activeCountChanged)
    def activeCount(self) -> int:
        return sum(1 for i in self._model.items
                   if i.status in ("downloading", "paused", "queued"))

    @Property(int, notify=completedCountChanged)
    def completedCount(self) -> int:
        return sum(1 for i in self._model.items if i.status == "completed")

    @Property(bool, notify=activeCountChanged)
    def hasActive(self) -> bool:
        return self.activeCount > 0

    @staticmethod
    def _completed_mod_is_still_installed(item: DownloadItem) -> bool:
        """Sprawdza fizyczny stan zakończonego pobrania moda.

        Historia kolejki nie jest źródłem prawdy o tym, czy zawartość nadal
        istnieje. Dla Overhauli szukamy dedykowanej instancji utworzonej z
        opisem ``Overhaul <slug> ...`` i istniejącym Mods/. Dla zwykłych
        modów sprawdzamy wpis Biblioteki po ``web_slug`` lub ``source`` oraz
        fizyczny katalog moda.
        """
        slug = str(item.ref_id or "").strip().casefold()
        if not slug:
            return False

        try:
            # Overhaul ze strony 7daystodiemods.com jest przechowywany
            # wyłącznie w dedykowanej instancji.
            prefix = f"overhaul {slug}"
            for instance in inst_mod.load_instances():
                description = str(instance.description or "").strip().casefold()
                if not (description == prefix or description.startswith(prefix + " ")):
                    continue
                data_dir = instance.mods_dir
                if data_dir is None or not data_dir.is_dir():
                    continue
                for child in data_dir.iterdir():
                    if child.is_dir() and find_modinfo(child) is not None:
                        return True

            # Zwykły mod / zestaw modów trafia do Biblioteki. Sama obecność
            # metadanych nie wystarcza: folder musi nadal istnieć fizycznie.
            for entry in library.load_library_entries():
                source_slug = ""
                source = str(entry.source or "")
                if source.startswith("web:"):
                    source_slug = source[4:].strip().casefold()
                web_slug = str(entry.web_slug or "").strip().casefold()
                if source_slug != slug and web_slug != slug:
                    continue
                if entry.path.is_dir() and find_modinfo(entry.path) is not None:
                    return True
        except (OSError, ValueError, TypeError):
            logger.debug("Failed to verify installation of mod %s", slug, exc_info=True)
        return False

    @Property("QVariantMap", notify=activeMapChanged)
    def modDownloads(self) -> dict:
        """Stan pobrań widoczny dla Discover i drawerów.

        Aktywne pobrania są publikowane zawsze. Zakończone pobranie moda
        pokazujemy jako "Pobrano" tylko wtedy, gdy zawartość nadal istnieje
        w Bibliotece lub odpowiadającej jej dedykowanej instancji Overhaul.
        Dzięki temu usunięcie instancji natychmiast odblokowuje ponowne
        pobranie, mimo zachowanego wpisu historii w downloads.json.
        """
        out = {}
        for item in self._model.items:
            if item.kind == "mod":
                if item.status == "completed" and not self._completed_mod_is_still_installed(item):
                    continue
                status = item.status
                if item.chosen_file_ref:
                    out[item.chosen_file_ref] = status
                if item.ref_id:
                    out[item.ref_id] = status
            elif item.kind == "url":
                if item.status in ("queued", "downloading", "paused"):
                    out[item.url] = item.status
                    if item.ref_id and item.ref_id != item.url:
                        out[item.ref_id] = item.status
        return out

    @Slot()
    def refreshModDownloadStates(self) -> None:
        """Powiadom QML, że fizyczny stan instalacji modów mógł się zmienić."""
        self.activeMapChanged.emit()

    @Property("QVariantMap", notify=activeMapChanged)
    def activeMap(self) -> dict:
        """modId -> {progress, statusKey} for the Updates page (klucz:
        update_for = library_id; dla starych atrap bez update_for - ref_id)."""
        result = {}
        for item in self._model.items:
            if item.kind != "update":
                continue
            key = item.update_for or item.ref_id
            if item.status not in ("completed", "failed"):
                result[key] = {
                    "progress": round(item.progress * 100, 1),
                    "statusKey": item.status,
                }
            elif item.status == "completed":
                result[key] = {
                    "progress": 100.0,
                    "statusKey": "completed",
                }
        return result

    # ------------------------------------------------------------------ #
    # engine
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(1.0, now - self._last_tick)
        self._last_tick = now
        changed = False
        completed: list[DownloadItem] = []

        for item in self._model.items:
            if item.status != "downloading":
                continue
            if item.real:
                continue  # real downloads progress in their own worker threads
            item.speed = item.base_speed * random.uniform(0.72, 1.28)
            item.downloaded = min(item.total_bytes,
                                  int(item.downloaded + item.speed * dt))
            changed = True
            if item.fail_at is not None and item.progress >= item.fail_at:
                item.status = "failed"
                item.speed = 0.0
                item.fail_at = None
                self._bus.toastKey("toast.downloads.failed", {"title": item.title}, "error")
            elif item.downloaded >= item.total_bytes:
                item.status = "completed"
                item.speed = 0.0
                item.finished_at = now
                completed.append(item)

        self._promote_queued()
        if changed or completed:
            self._model.touch_all()
        for item in completed:
            self._on_completed(item)
        if completed or changed:
            self._emit_counts()

    def _promote_queued(self) -> None:
        active = sum(1 for i in self._model.items if i.status == "downloading")
        for item in self._model.items:
            if active >= self._settings.maxConcurrentDownloads:
                break
            if item.status == "queued":
                # Game-version downloads are owned by GameVersionsManager,
                # not by this HTTP/modpack worker pool. They are resumed
                # explicitly after signal wiring during application startup.
                if item.kind == "game":
                    continue
                item.status = "downloading"
                active += 1
                if item.real:
                    if item.flavor == "mod":
                        self._start_mod_worker(item)
                    else:
                        self._start_url_worker(item)

    def _on_completed(self, item: DownloadItem) -> None:
        if item.kind == "update":
            self._bus.toastKey("toast.downloads.updateDownloaded", {"title": item.title}, "success")
            self.updateFinished.emit(item.ref_id)
        else:
            self._bus.toastKey("toast.downloads.completed", {"title": item.title}, "success")

    def _emit_counts(self) -> None:
        self.activeCountChanged.emit()
        self.completedCountChanged.emit()
        self.activeMapChanged.emit()
        # hook trwałości kolejki: każda zmiana stanu pozycji przechodzi
        # przez _emit_counts; zapis pomija niezmieniony payload
        self._persist_queue()

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #
    @Slot(str)
    def startModUpdate(self, mod_id: str) -> None:
        """Prawdziwa aktualizacja (etap 11): pobiera nową wersję moda
        z 7daystodiemods.com i podmienia zawartość wpisu Biblioteki
        W MIEJSCU (library_id i stan aktywacji nietknięte)."""
        entry = self._mods.library_entry(mod_id)
        if entry is None:
            self._bus.toastKey("toast.downloads.notLibraryMod", {}, "error")
            return
        from backend import mod_updates
        slug = mod_updates.slug_from_source(entry.source) or (entry.web_slug or None)
        if not slug:
            self._bus.toastKey("toast.downloads.unlinked", {"title": entry.title}, "error")
            return
        for item in self._model.items:
            if item.kind in ("mod", "update") and item.ref_id == slug \
                    and item.status in ("queued", "downloading", "paused"):
                self._bus.toastKey("toast.downloads.alreadyQueuedMod", {}, "info")
                return
        item = DownloadItem(
            kind="update",
            ref_id=slug,
            title=entry.title,
            subtitle="Aktualizacja · 7daystodiemods.com",
            total_bytes=0,   # znane po pobraniu strony moda
            status="queued",
            real=True,
            pausable=True,
            url=slug,
            flavor="mod",
            update_for=mod_id,
        )
        self._model.append(item)
        self._persist_queue()
        self._promote_queued()
        self._emit_counts()
        self._bus.toastKey("toast.downloads.startedUpdate", {"title": entry.title}, "info")

    @Slot()
    def enqueueAvailableUpdates(self) -> None:
        """Auto-tryb (opt-in, Settings.autoUpdateMods): kolejkuj pobieranie
        wszystkich wykrytych aktualizacji. Bez włączonej opcji = no-op."""
        if not getattr(self._settings, "autoUpdateMods", False):
            return
        for entry in self._mods.updatesList:
            self.startModUpdate(str(entry.get("id", "")))

    def _find(self, download_id: str) -> DownloadItem | None:
        row = self._model.row_of(download_id)
        return self._model.items[row] if row >= 0 else None

    @Slot(str)
    def pauseAt(self, download_id: str) -> None:
        item = self._find(download_id)
        if item and item.status == "downloading":
            if item.kind == "game":
                if item.pausable and self._game_versions is not None:
                    # DepotDownloader nie ma własnego trybu pause.
                    # Zatrzymujemy proces i zostawiamy staging na dysku;
                    # Resume uruchomi ten sam branch ponownie i downloader
                    # dokończy istniejące dane.
                    self._game_versions.pause()
                else:
                    self._bus.toastKey("toast.downloads.pauseUnavailable", {}, "info")
                return
            if item.real:
                # prawdziwa pauza HTTP: strumień zamykany, .part zostaje,
                # wznowienie przez HTTP Range (tylko flavor != "git")
                if item.pausable:
                    item.pause_event.set()
                else:
                    self._bus.toastKey("toast.downloads.pauseUnavailable", {}, "info")
                return
            item.status = "paused"
            item.speed = 0.0
            self._model.touch_all()
            self._emit_counts()

    @Slot(str)
    def resumeAt(self, download_id: str) -> None:
        item = self._find(download_id)
        if item and item.status == "paused":
            if item.kind == "game":
                if self._game_versions is None:
                    return
                item.restored_paused = False
                item.status = "queued"
                item.speed = 0.0
                item._last_sample = None
                self._model.touch_all()
                self._emit_counts()
                self._game_versions.resume(item.ref_id)
                return
            if item.real:
                item.pause_event.clear()
                if item.restored_paused:
                    # pozycja odtworzona z poprzedniej sesji: nie ma żywego
                    # workera - startujemy go teraz (wznowi z .part)
                    item.restored_paused = False
                    item.status = "queued"
                    self._promote_queued()
                    self._model.touch_all()
                    self._emit_counts()
                return
            item.status = "queued"
            self._promote_queued()
            self._model.touch_all()
            self._emit_counts()

    @Slot(str)
    def cancelAt(self, download_id: str) -> None:
        item = self._find(download_id)
        if item and item.status in ("downloading", "paused", "queued"):
            if item.kind == "game":
                if self._game_versions is not None:
                    self._game_versions.cancel()
                # Po pauzie DepotDownloader już nie ma żywego workera, więc
                # nie nadejdzie później sygnał "cancelled". W takim przypadku
                # usuń kartę od razu; rozpoczęte dane na dysku pozostają jako
                # staging i mogą zostać wykorzystane przy kolejnym pobraniu.
                if item.status == "paused":
                    self._model.remove(item.id)
                    self._emit_counts()
                return
            if item.real:
                # worker (jeśli już biegnie) sam zgłosi "cancelled" i posprząta
                item.cancel_event.set()
                item.pause_event.clear()
                if item.status == "queued" or item.restored_paused:
                    # wątek jeszcze nie wystartował (albo pozycja odtworzona
                    # z poprzedniej sesji jako pauza - nie ma żywego workera,
                    # który zgłosiłby "cancelled") - usuwamy od razu
                    self._model.remove(download_id)
                    modpack_downloader.cleanup_temp_dir(item.temp_dir)
                    self._bus.toastKey("toast.downloads.cancelled", {"title": item.title}, "info")
                    self._emit_counts()
                return
            self._model.remove(download_id)
            self._bus.toastKey("toast.downloads.cancelled", {"title": item.title}, "info")
            self._emit_counts()

    @Slot(str)
    def retryAt(self, download_id: str) -> None:
        item = self._find(download_id)
        if item and item.status == "failed":
            item.downloaded = 0
            item._progress_override = 0.0
            item.status = "queued"
            if item.real:
                # .part zostaje - HTTP dociągnie resztę przez Range;
                # nieudany git clone zacznie się od świeżego klonu
                # (download_and_extract czyści extract/ przed klonem)
                self._promote_queued()
                self._model.touch_all()
                self._emit_counts()
                self._bus.toastKey("toast.downloads.retrying", {"title": item.title}, "info")
                return
            self._promote_queued()
            self._model.touch_all()
            self._emit_counts()
            self._bus.toastKey("toast.downloads.retrying", {"title": item.title}, "info")

    @Slot()
    def clearCompleted(self) -> None:
        for item in list(self._model.items):
            if item.status == "completed":
                self._model.remove(item.id)
        self._emit_counts()

    @Slot(str)
    def removeCompletedAt(self, download_id: str) -> None:
        """Usuń pojedynczy wpis z historii zakończonych pobrań."""
        item = self._find(download_id)
        if item is None or item.status != "completed":
            return
        self._model.remove(download_id)
        self._emit_counts()

    # ------------------------------------------------------------------ #
    # Steam game-version downloads (owned by GameVersionsManager)
    # ------------------------------------------------------------------ #
    @Slot(str, object)
    def startGameVersionDownload(self, branch: str, total_bytes: int = 0) -> None:
        # Depot size is a Python integer and may exceed 2 GiB; do not
        # let Qt coerce it to a 32-bit C++ int at the signal boundary.
        branch = (branch or "").strip()
        if not branch:
            return
        existing = [i for i in self._model.items
                    if i.kind == "game" and i.ref_id == branch]
        # Nie twórz drugiej karty po ponownym kliknięciu po nieudanej próbie.
        # Sygnały kolejnej próby muszą trafić do tej samej pozycji; w
        # przeciwnym razie updateGameVersionDownload() może aktualizować
        # pierwszą kartę, a druga zostanie na 0%.
        if existing:
            item = existing[-1]
            if item.status in ("queued", "downloading"):
                return
            if item.status == "paused":
                item.status = "downloading"
            else:
                item.status = "downloading"
                item.downloaded = 0
                item._progress_override = 0.0
            item.total_bytes = max(0, int(total_bytes or item.total_bytes or 0))
            item.speed = 0.0
            item._last_sample = None
            item.subtitle = f"Steam · branch {branch} · Depot 251576"
            item.pausable = True
            item.real = True
            item.flavor = "game"
        else:
            item = DownloadItem(
                kind="game",
                ref_id=branch,
                title=f"7 Days to Die - {branch}",
                subtitle=f"Steam · branch {branch} · Depot 251576",
                total_bytes=max(0, int(total_bytes or 0)),
                status="downloading",
                real=True,
                # Steam pause = terminate current DepotDownloader and resume
                # from its on-disk staging on the next run.
                pausable=True,
                flavor="game",
            )
            self._model.append(item)
        self._model.touch_all()
        self._emit_counts()

    @Slot(str, float, str)
    def updateGameVersionDownload(self, branch: str, percent: float, status: str) -> None:
        branch = (branch or "").strip()
        item = next((i for i in reversed(self._model.items)
                     if i.kind == "game" and i.ref_id == branch
                     and i.status in ("downloading", "queued", "paused")), None)
        if item is None:
            # Compatibility with an old queue entry left in failed state.
            item = next((i for i in reversed(self._model.items)
                         if i.kind == "game" and i.ref_id == branch), None)
        if item is None:
            return
        now = time.monotonic()
        pct = max(0.0, min(100.0, float(percent)))
        item._progress_override = pct / 100.0
        if item.total_bytes > 0:
            item.downloaded = int(round(item.total_bytes * pct / 100.0))
        if item._last_sample is not None:
            old_t, old_b = item._last_sample
            dt = now - old_t
            delta = item.downloaded - old_b
            # Status updates (np. zmiana aktualnego pliku) mogą nadejść bez
            # żadnego przyrostu bajtów. Nie zeruj wtedy prędkości - właśnie
            # to powodowało migotanie wartości/samej obecności speed + ETA.
            if delta > 0 and dt >= 0.15:
                instant = delta / dt
                item.speed = instant if item.speed <= 0 else (item.speed * 0.75 + instant * 0.25)
                item._last_sample = (now, item.downloaded)
            elif now - old_t > 12.0:
                # Nie zeruj prędkości po kilku sekundach bez nowych bajtów.
                # DepotDownloader długo potrafi przetwarzać plik / weryfikować
                # zawartość; zerowanie powodowało migotanie speed/ETA w QML.
                # Po 12 s zostawiamy ostatnią próbkę do czasu kolejnego przyrostu.
                pass
        else:
            item._last_sample = (now, item.downloaded)
        item.status = "downloading"
        if status and status != item.subtitle:
            # Pokazujemy aktualnie obrabiany plik pod paskiem zamiast
            # zostawiać użytkownika z surowym stdout DepotDownloadera.
            item.subtitle = status
        self._model.touch(self._model.row_of(item.id))
        self._emit_counts()

    @Slot(str, str, str)
    def finishGameVersionDownload(self, branch: str, state: str, message: str) -> None:
        branch = (branch or "").strip()
        item = next((i for i in reversed(self._model.items)
                     if i.kind == "game" and i.ref_id == branch
                     and i.status in ("downloading", "queued", "paused")), None)
        if item is None:
            item = next((i for i in reversed(self._model.items)
                         if i.kind == "game" and i.ref_id == branch), None)
        if item is None:
            return
        if state == "completed":
            if item.total_bytes > 0:
                item.downloaded = item.total_bytes
            item._progress_override = 1.0
            item.status = "completed"
            item.speed = 0.0
            item._last_sample = None
            item.subtitle = i18n_message("download.gameVersion.ready")
            self._model.touch(self._model.row_of(item.id))
            self._emit_counts()
            self._bus.toastKey("toast.downloads.gameVersionDownloaded", {"branch": branch}, "success")
            return
        if state == "paused":
            item.status = "paused"
            item.speed = 0.0
            item._last_sample = None
            item.subtitle = i18n_message("download.status.paused")
            self._model.touch(self._model.row_of(item.id))
            self._emit_counts()
            return
        if state == "cancelled":
            self._model.remove(item.id)
            self._emit_counts()
            self._bus.toastKey("toast.downloads.gameVersionCancelled", {"branch": branch}, "info")
            return
        item.status = "failed"
        item._progress_override = item.progress
        item.speed = 0.0
        if message:
            item.subtitle = message
        self._model.touch(self._model.row_of(item.id))
        self._emit_counts()
        self._bus.toastKey("toast.downloads.gameVersionFailed", {"branch": branch}, "error")

    @staticmethod
    def _is_downloaded_game_version(branch: str) -> bool:
        return bool(resolve_downloaded_branch(branch))

    def _check_required_game_version(self, game_version: str, subject: str) -> str:
        """Return the concrete branch or raise before a mod/modpack download.

        A selected catalog version is a hard compatibility requirement. The
        launcher therefore refuses to start the network job until the matching
        Windows game copy exists physically in game-versions/<branch>. An empty
        version means the source did not provide a reliable requirement and is
        intentionally allowed.
        """
        required_branch = required_game_branch((game_version or "").strip())
        if not required_branch:
            return ""
        resolved = resolve_downloaded_branch(required_branch)
        if not resolved:
            raise modpack_downloader.DownloadError(
                i18n_message("download.gameVersion.missing", {
                    "branch": required_branch
                })
            )
        return resolved

    # ------------------------------------------------------------------ #
    # real URL downloads (migration stage 5)
    # ------------------------------------------------------------------ #
    @Slot(str)
    def startUrlDownload(self, url: str) -> None:
        self.startUrlDownloadNamed(url, "")

    @Slot(str, str)
    @Slot(str, str, str)
    def startUrlDownloadNamed(self, url: str, title: str, game_version: str = "") -> None:
        """Pobiera modpack z URL (repo Git / GitHub releases / .zip).

        Pobrana zawartość to OVERHAUL (katalog GitHub w Odkrywaj albo
        ręcznie wklejony URL) - ląduje w DEDYKOWANEJ INSTANCJI, nigdy
        w globalnej Bibliotece: mody trafiają fizycznie do Mods/ instancji,
        więc usunięcie instancji usuwa cały pakiet. Link do moda z
        7daystodiemods.com (albo sam slug) kieruje na scraper -
        startModDownload (etap 9)."""
        url = (url or "").strip()
        if not url:
            return
        if "7daystodiemods.com" in url:
            self.startModDownloadWithVersion(url, game_version)
            return
        kind = modpack_downloader.detect_source_kind(url)
        if kind == modpack_downloader.DownloadSourceKind.UNSUPPORTED \
                and re.fullmatch(r"[a-z0-9-]+", url, re.I):
            # sam slug bez hosta - jedyna sensowna interpretacja to strona moda
            self.startModDownload(url)
            return
        if kind == modpack_downloader.DownloadSourceKind.UNSUPPORTED:
            self._bus.toastKey("toast.downloads.unsupportedSource", {}, "error")
            return
        game_version = (game_version or "").strip()
        try:
            required_branch = self._check_required_game_version(game_version, "Overhaul")
        except modpack_downloader.DownloadError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "warning")
            return
        for item in self._model.items:
            if item.real and item.url == url \
                    and item.status in ("queued", "downloading", "paused"):
                self._bus.toastKey("toast.downloads.alreadyQueuedUrl", {}, "info")
                return

        flavor = {
            modpack_downloader.DownloadSourceKind.GIT_REPO: "git",
            modpack_downloader.DownloadSourceKind.GITHUB_RELEASES: "github",
            modpack_downloader.DownloadSourceKind.DIRECT_ZIP: "zip",
            # Undead Legacy uses a stable redirect which resolves to the
            # current ZIP archive at download time. It still behaves like a
            # normal resumable ZIP download once queued.
            modpack_downloader.DownloadSourceKind.UNDEAD_LEGACY_MIRROR: "zip",
        }[kind]
        title = (title or "").strip() or url.rstrip("/").rsplit("/", 1)[-1] or url
        item = DownloadItem(
            kind="url",
            ref_id=url,
            title=title,
            subtitle=i18n_message("download.overhaul.source", {
                "source": modpack_downloader.source_kind_label(kind),
            }),
            total_bytes=0,   # nieznany do pierwszego nagłówka HTTP
            status="queued",
            real=True,
            pausable=(flavor != "git"),
            url=url,
            flavor=flavor,
            game_version=game_version,
        )
        item.temp_dir = Path(tempfile.mkdtemp(prefix="mm-dl-"))
        self._model.append(item)
        self._promote_queued()
        self._emit_counts()
        install_log.info("URL download queued: title=%r url=%s flavor=%s",
                         title, url, flavor)
        self._bus.toastKey("toast.downloads.started", {"title": title}, "info")

    # ------------------------------------------------------------------ #
    # scraper mods - 7daystodiemods.com (migration stage 9)
    # ------------------------------------------------------------------ #
    @Slot(str)
    def startModDownload(self, url_or_slug: str) -> None:
        self.startModDownloadWithVersion(url_or_slug, "")

    @Slot(str, str)
    def startModDownloadWithVersion(self, url_or_slug: str, game_version: str) -> None:
        """Pobiera pojedynczy mod ze strony 7daystodiemods.com (etap 9).

        Przyjmuje pełny URL strony moda albo sam slug. game_version: slug
        wersji gry wybrany filtrem w Odkrywaj (np. "v3") - zapisywany w
        Bibliotece i używany do blokady niezgodnych aktywacji.
        Archiwum ląduje w downloads/ jako <slug>-<wersja>.zip (D9: nic nie
        kasujemy automatycznie, istniejące archiwum = pomijamy pobieranie),
        a jego zawartość instalowana jest do Biblioteki jak z modpacka.
        """
        raw = (url_or_slug or "").strip()
        if not raw:
            return
        game_version = (game_version or "").strip()
        try:
            required_branch = self._check_required_game_version(game_version, "Mod")
        except modpack_downloader.DownloadError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "warning")
            return
        try:
            slug = parse_mod_url(raw)
        except ValueError:
            self._bus.toastKey("toast.downloads.modUrlInvalid", {}, "error")
            return
        for item in list(self._model.items):
            if item.kind != "mod":
                continue
            item_slug = item.ref_id
            if item.chosen_file_ref:
                # Wpisy utworzone przez nowszą wersję mają slug w ref_id.
                item_slug = item.ref_id
            if item_slug.casefold() != slug.casefold():
                continue
            if item.status in ("queued", "downloading", "paused"):
                self._bus.toastKey("toast.downloads.alreadyQueuedMod", {}, "info")
                return
            if item.status == "completed":
                if self._completed_mod_is_still_installed(item):
                    self._bus.toastKey("toast.downloads.alreadyDownloaded", {}, "info")
                    return
                # Historia jest nieaktualna (np. użytkownik usunął instancję
                # Overhaul). Usuwamy ją z modelu przed utworzeniem nowego
                # zadania, aby nie blokowała ponownego pobrania.
                self._model.remove(item.id)
        item = DownloadItem(
            kind="mod",
            ref_id=slug,
            title=slug,
            subtitle="Mod · 7daystodiemods.com",
            total_bytes=0,   # znane dopiero po pobraniu strony moda
            status="queued",
            real=True,
            pausable=True,   # pauza: DownloadPaused z callbacka postępu
            url=raw,
            flavor="mod",
            game_version=required_branch or game_version,
        )
        self._model.append(item)
        self._persist_queue()
        self._promote_queued()
        self._emit_counts()
        self._bus.toastKey("toast.downloads.started", {"title": slug}, "info")

    @Slot(str, str)
    @Slot(str, str, str)
    def startModDownloadWithFileVersion(self, slug: str, file_ref: str,
                                        game_version: str) -> None:
        self._startModDownloadWithFile(slug, file_ref, game_version)

    @Slot(str, str)
    def startModDownloadWithFile(self, slug: str, file_ref: str) -> None:
        self._startModDownloadWithFile(slug, file_ref, "")

    def _startModDownloadWithFile(self, slug: str, file_ref: str,
                                  game_version: str = "") -> None:
        """Pobiera mod z WYBRANYM plikiem z karty szczegółów (etap 13).
        file_ref: "hosted:<id>" (plik serwisu) albo "external:<url>"
        (link zewnętrzny GitHub/GitLab/CurseForge/direct)."""
        raw = (slug or "").strip()
        file_ref = (file_ref or "").strip()
        if not raw or not file_ref:
            return
        game_version = (game_version or "").strip()
        try:
            required_branch = self._check_required_game_version(game_version, "Mod")
        except modpack_downloader.DownloadError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "warning")
            return
        try:
            slug_norm = parse_mod_url(raw)
        except ValueError:
            self._bus.toastKey("toast.downloads.invalidModId", {}, "error")
            return
        for item in self._model.items:
            if item.kind not in ("mod", "update"):
                continue
            same_file = (item.chosen_file_ref or item.ref_id) == file_ref
            same_mod = item.kind == "mod" and item.ref_id.casefold() == slug_norm.casefold()
            if (same_file or same_mod) and item.status in ("queued", "downloading", "paused", "completed"):
                self._bus.toastKey("toast.downloads.alreadyDownloadedOrQueued", {}, "info")
                return
        item = DownloadItem(
            kind="mod",
            ref_id=slug_norm,
            title=slug_norm,
            subtitle="Mod · 7daystodiemods.com",
            total_bytes=0,
            status="queued",
            real=True,
            pausable=True,
            url=raw,
            flavor="mod",
            chosen_file_ref=file_ref,
            game_version=required_branch or game_version,
        )
        self._model.append(item)
        self._persist_queue()
        self._promote_queued()
        self._emit_counts()
        self._bus.toastKey("toast.downloads.started", {"title": slug_norm}, "info")

    @staticmethod
    def _file_matches_selected_game_version(file, game_version: str, mod_info) -> bool:
        """Return whether a scraper file is safe for the selected game version."""
        selected = (game_version or "").strip()
        if not selected:
            return True
        detected = detect_file_game_versions(
            label=file.label,
            filename=file.filename,
            mod_version=file.version,
        )
        if detected:
            return game_version_matches(selected, detected)

        # Jeżeli nazwa pliku nic nie mówi, wolno użyć go tylko wtedy, gdy sam
        # mod deklaruje jedną, jednoznaczną wersję gry zgodną z wyborem.
        declared = [
            str(value).strip()
            for value in (mod_info.game_versions or [])
            if str(value).strip()
        ]
        return len(declared) == 1 and game_version_matches(selected, declared)

    @staticmethod
    def _external_matches_selected_game_version(link, game_version: str, mod_info) -> bool:
        selected = (game_version or "").strip()
        if not selected:
            return True
        detected = detect_artifact_game_versions(
            label=link.label,
            # Dla stron hostujących używamy nazwę rzeczywistego artefaktu,
            # gdy parser potrafi ją bezpiecznie wydobyć z URL-a. Dla MediaFire
            # jest to segment przed ``/file``; nie jest to tymczasowy CDN URL.
            filename=link.filename,
            declared_versions=mod_info.game_versions,
            mod_version=link.version,
        )
        if detected:
            return game_version_matches(selected, detected)
        declared = [
            str(value).strip()
            for value in (mod_info.game_versions or [])
            if str(value).strip()
        ]
        return len(declared) == 1 and game_version_matches(selected, declared)

    @staticmethod
    def _select_external_for_download(links, selected_game_version: str, mod_info):
        """Wybiera zewnętrzny artefakt, także gdy filtr wersji jest pusty.

        Gdy 7daystodiemods.com zwraca wyłącznie link zewnętrzny (np.
        MediaFire), wcześniejsza ścieżka ``<main>`` pobierała właściwy ZIP,
        ale nie przypisywała jego wykrytej wersji do automatycznie tworzonej
        instancji. ``chosen_ext`` pozostawało puste, więc ``game_branch``
        kończył jako ``""`` = Steam.

        Przy wybranym filtrze wymagamy jednoznacznego dopasowania. Bez filtra
        akceptujemy jeden i tylko jeden zewnętrzny artefakt; jego etykieta
        może dostarczyć konkretnej wersji, np. ``V2.6``. Przy wielu linkach
        nie zgadujemy, żeby nie zainstalować złego wydania.
        """
        candidates = list(links or [])
        if not candidates:
            return None

        selected = (selected_game_version or "").strip()
        if selected:
            matching = [
                link for link in candidates
                if DownloadManager._external_matches_selected_game_version(
                    link, selected, mod_info)
            ]
            return matching[0] if len(matching) == 1 else None

        if len(candidates) != 1:
            return None

        # Bez filtra jeden link jest bezpieczny tylko wtedy, gdy sam link
        # albo deklaracja moda daje jednoznaczną informację o wersji gry.
        link = candidates[0]
        detected = detect_artifact_game_versions(
            label=link.label,
            filename=link.filename,
            declared_versions=mod_info.game_versions,
            mod_version=link.version,
        )
        if len(detected) == 1:
            return link

        declared = [
            str(value).strip()
            for value in (mod_info.game_versions or [])
            if str(value).strip()
        ]
        return link if len(declared) == 1 else None

    def _start_mod_worker(self, item: DownloadItem) -> None:
        cancel = item.cancel_event
        pause = item.pause_event
        client = SevenDaysModsClient()

        def check_cancel() -> None:
            if cancel.is_set():
                raise OperationCancelled(i18n_message("common.operationCancelled"))

        def progress(done: int, total: int) -> None:
            check_cancel()
            if pause.is_set():
                # wypływa z download_to (nie łapie własnych wyjątków requests),
                # a istniejący .part pozwala wznowić przez HTTP Range
                raise modpack_downloader.DownloadPaused("Pauza")
            self.urlProgress.emit(item.id, done, total, "")

        def worker() -> None:
            temp_dir: Path | None = None
            # ``item.game_version`` jest później zamieniane na konkretny
            # pobrany branch (np. alpha21.2). Do dopasowania pliku potrzebujemy
            # jednak wersji wybranej przez użytkownika (np. alpha21).
            selected_game_version = (item.game_version or "").strip()
            try:
                item.game_version = required_game_branch(item.game_version)
                if item.game_version:
                    item.game_version = resolve_downloaded_branch(item.game_version) or item.game_version
                if item.game_version and not self._is_downloaded_game_version(item.game_version):
                    raise modpack_downloader.DownloadError(
                        i18n_message("download.gameVersion.missing", {
                            "branch": item.game_version
                        })
                    )
                info = client.get_mod(item.url)
                install_log.info(
                    "MOD download start: slug=%s title=%r file_ref=%s update_for=%s",
                    info.slug, info.title or "", item.chosen_file_ref or "<main>",
                    item.update_for or "-")
                check_cancel()
                subtitle = (i18n_message("download.mod.subtitleUpdate", {
                    "author": info.author or i18n_message("common.unknown")
                }) if item.kind == "update" else i18n_message("download.mod.subtitleMod", {
                    "author": info.author or i18n_message("common.unknown")
                }))
                self.modMeta.emit(item.id, info.title, subtitle, 0)

                # wybór pliku: domyślnie main, ewentualnie plik/link wybrany
                # na karcie szczegółów moda (etap 13)
                main_file = None
                chosen_ext = None
                if item.chosen_file_ref.startswith("hosted:"):
                    ref_id = item.chosen_file_ref[len("hosted:"):]
                    main_file = next((f for f in info.files if f.id == ref_id), None)
                    if main_file is None:
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.mod.fileMissing"))
                    if not self._file_matches_selected_game_version(
                            main_file, selected_game_version, info):
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.mod.incompatibleFile", {
                                "version": selected_game_version
                            }))
                elif item.chosen_file_ref.startswith("external:"):
                    ext_url = item.chosen_file_ref[len("external:"):]
                    chosen_ext = next(
                        (l for l in info.external_links if l.url == ext_url), None)
                    if chosen_ext is None:
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.mod.externalMissing"))
                    if not self._external_matches_selected_game_version(
                            chosen_ext, selected_game_version, info):
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.mod.incompatibleFile", {
                                "version": selected_game_version
                            }))
                else:
                    # Przy aktywnym filtrze wersji nie wolno brać "pierwszego"
                    # pliku. Wybieramy wyłącznie plik rozpoznany jako zgodny.
                    if selected_game_version:
                        compatible_files = [
                            f for f in info.files
                            if self._file_matches_selected_game_version(
                                f, selected_game_version, info)
                        ]
                        if compatible_files:
                            main_file = next(
                                (f for f in compatible_files if f.file_type == "main"),
                                compatible_files[0],
                            )
                        else:
                            compatible_external = [
                                link for link in info.external_links
                                if self._external_matches_selected_game_version(
                                    link, selected_game_version, info)
                            ]
                            if not compatible_external:
                                raise modpack_downloader.DownloadError(
                                    i18n_message("download.mod.noCompatibleFile", {
                                        "version": selected_game_version
                                    }))
                            chosen_ext = compatible_external[0]
                    else:
                        # Bez filtra zachowujemy dotychczasowy priorytet dla
                        # plików hostowanych. Dopiero gdy katalog nie ma
                        # żadnego ``mod_file``, a posiada dokładnie jeden link
                        # zewnętrzny (np. MediaFire), wybieramy go jawnie.
                        # Dzięki temu nie tracimy wersji artefaktu przy tworzeniu
                        # Overhaulu i jednocześnie nie zmieniamy zachowania modów,
                        # które mają natywny plik 7daystodiemods.com.
                        if info.files:
                            detected = {
                                version
                                for file in info.files
                                for version in detect_file_game_versions(
                                    label=file.label,
                                    filename=file.filename,
                                    mod_version=file.version,
                                )
                            }
                            if len(detected) > 1:
                                raise modpack_downloader.DownloadError(
                                    i18n_message("download.mod.selectGameVersion")
                                )
                            main_file = next(
                                (f for f in info.files if f.file_type == "main"), None) \
                                or info.files[0]
                        else:
                            chosen_ext = self._select_external_for_download(
                                info.external_links, selected_game_version, info)
                            if chosen_ext is None:
                                detected = {
                                    version
                                    for link in info.external_links
                                    for version in detect_artifact_game_versions(
                                        label=link.label,
                                        filename=link.filename,
                                        declared_versions=info.game_versions,
                                        mod_version=link.version,
                                    )
                                }
                                if len(detected) > 1:
                                    raise modpack_downloader.DownloadError(
                                        i18n_message("download.mod.selectGameVersion")
                                    )

                # Zachowujemy konkretną wersję gry dla automatycznie tworzonej
                # instancji. Katalog może deklarować szeroką rodzinę (np.
                # ``V2 Mods``), a nazwa konkretnego pliku/linku wskazywać np.
                # ``V2.6``. W takim przypadku instancja ma dostać ``v2.6``,
                # a nie pustą wartość oznaczającą Steam.
                artifact_versions: list[str] = []
                if main_file is not None:
                    artifact_versions = detect_artifact_game_versions(
                        label=main_file.label,
                        filename=main_file.filename,
                        declared_versions=info.game_versions,
                        mod_version=main_file.version,
                    )
                elif chosen_ext is not None:
                    artifact_versions = detect_artifact_game_versions(
                        label=chosen_ext.label,
                        filename=chosen_ext.filename,
                        declared_versions=info.game_versions,
                        mod_version=chosen_ext.version,
                    )

                inferred_branch = select_concrete_game_version(
                    selected_game_version, artifact_versions)
                if not inferred_branch:
                    # Gdy nazwa pliku nic nie mówi, wykorzystujemy deklarację
                    # moda (np. ``V2 Mods``) i rozwiązujemy ją do konkretnego
                    # zainstalowanego brancha, np. ``v2`` -> ``v2.6``.
                    inferred_branch = select_concrete_game_version(
                        selected_game_version, list(info.game_versions or []))

                install_branch = inferred_branch or item.game_version
                if install_branch:
                    install_branch = required_game_branch(install_branch)
                    install_branch = resolve_downloaded_branch(install_branch) or install_branch
                    if not self._is_downloaded_game_version(install_branch):
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.gameVersion.missing", {
                                "branch": install_branch
                            })
                        )
                    item.game_version = install_branch
                install_log.info(
                    "MOD game branch: selected=%r detected=%s -> install=%r",
                    selected_game_version, artifact_versions, item.game_version or "Steam")

                version = re.sub(r"[^\w.-]+", "_",
                                 (main_file.version if main_file else None)
                                 or info.current_version or "latest")
                suffix = (Path(main_file.filename).suffix
                          if main_file and main_file.filename else "") or ".zip"
                dest = fs.downloads_dir() / f"{info.slug}-{version}{suffix}"

                download_url: str | None = None
                if chosen_ext is not None:
                    if chosen_ext.is_direct_file:
                        download_url = chosen_ext.url
                        ext_name = chosen_ext.filename
                    else:
                        resolved = client.resolve_external_url(chosen_ext)
                        if resolved is None:
                            raise modpack_downloader.DownloadError(
                                i18n_message("download.mod.unsupportedLink"))
                        download_url, _sz, ext_name = resolved
                    dest = fs.downloads_dir() / f"{info.slug}-{version}-{ext_name}"
                elif main_file is not None:
                    self.modMeta.emit(item.id, info.title, subtitle,
                                      main_file.size)
                else:
                    # brak plików hostowanych - linki zewnętrzne (GitHub/CurseForge)
                    resolved = None
                    for link in info.external_links:
                        if link.is_direct_file:
                            resolved = (link.url, 0, link.filename)
                            break
                        resolved = client.resolve_external_url(link)
                        if resolved:
                            break
                    if resolved is None:
                        raise modpack_downloader.DownloadError(
                            i18n_message("download.mod.noFiles"))
                    download_url, ext_size, filename = resolved
                    if ext_size > 0:
                        self.modMeta.emit(item.id, "", "", ext_size)
                    dest = fs.downloads_dir() / f"{info.slug}-{version}-{filename}"

                if dest.exists():
                    # D9: transfer jest limitowany - archiwum już na dysku,
                    # więc pobierania nie powtarzamy
                    progress(dest.stat().st_size, max(1, dest.stat().st_size))
                else:
                    if download_url is None:
                        download_url = client.resolve_download_url(
                            info.id, main_file.id)
                    while True:
                        try:
                            client.download_to(download_url, dest, progress=progress)
                            break
                        except modpack_downloader.DownloadPaused:
                            self.urlState.emit(item.id, "paused")
                            while pause.is_set() and not cancel.is_set():
                                time.sleep(0.1)
                            if cancel.is_set():
                                raise OperationCancelled(i18n_message("common.operationCancelled"))
                            self.urlState.emit(item.id, "downloading")
                            continue   # download_to wznowi z .part (Range)

                if dest.suffix.lower() != ".zip":
                    raise modpack_downloader.DownloadError(
                        i18n_message("download.mod.notZip", {
                            "extension": dest.suffix or "(bez rozszerzenia)"
                        }))

                temp_dir = Path(tempfile.mkdtemp(prefix="mm-mod-"))
                item.temp_dir = temp_dir

                def extract_progress(done: int, total: int, label: str) -> None:
                    # Wypakowywanie raportuje LICZBĘ PLIKÓW, nie bajty. Nie
                    # przepuszczamy tego licznika jako postępu transferu.
                    self.urlProgress.emit(
                        item.id,
                        item.downloaded,
                        item.total_bytes,
                        label or i18n_message("download.mod.extracting", {"name": ""}),
                    )

                modpack_downloader._extract_zip(
                    dest, temp_dir,
                    progress_cb=extract_progress,
                    cancel_event=cancel,
                )
                mods_root = modpack_downloader.find_mods_root_in_extracted(temp_dir)
                if mods_root is None or not modpack_downloader.mods_root_has_valid_mods(mods_root):
                    raise modpack_downloader.DownloadError(
                        i18n_message("download.mod.invalidArchive"))

                # foldery modów w archiwum (potrzebne dla obu ścieżek)
                mod_folders = [
                    child for child in sorted(mods_root.iterdir(), key=lambda p: p.name.lower())
                    if child.is_dir() and find_modinfo(child) is not None]
                install_log.info("MOD extracted: mods_root=%s, %d mod folders: %s",
                                 mods_root, len(mod_folders),
                                 [p.name for p in mod_folders])

                # aktualizacja (etap 11): pojedynczy mod w archiwum = podmiana
                # zawartości wpisu W MIEJSCU (library_id i aktywacja nietknięte)
                if item.update_for is not None:
                    if len(mod_folders) == 1:
                        updated_entry, changed = library_ops.update_entry_content(
                            item.update_for, mod_folders[0], cancel_event=cancel)
                        parts = [i18n_message("download.mod.updated", {
                            "version": updated_entry.version or "z archiwum"
                        })] if changed else [i18n_message("download.mod.unchanged")]
                        modpack_downloader.cleanup_temp_dir(temp_dir)
                        temp_dir = None
                        item.temp_dir = None
                        self.urlState.emit(item.id, "completed:" + "; ".join(parts))
                        return

                # Overhaul ma własną semantykę: jego Mods/ pozostaje wyłącznie
                # w dedykowanej instancji i nigdy nie trafia do globalnej
                # Biblioteki. Kategorie są pobierane ze strony moda.
                categories = {c.casefold() for c in getattr(info, "categories", [])}
                is_overhaul = any("overhaul" in category for category in categories)
                if item.update_for is None and is_overhaul:
                    install_log.info(
                        "MOD is an OVERHAUL (categories=%s) - dedicated instance path",
                        sorted(categories))
                    entry_count = self._install_overhaul_as_instance(
                        info.slug, info.title or info.slug, mod_folders, cancel,
                        game_version=item.game_version)
                    self.instancesRefreshNeeded.emit()
                    modpack_downloader.cleanup_temp_dir(temp_dir)
                    temp_dir = None
                    item.temp_dir = None
                    self.urlState.emit(
                        item.id,
                        "completed:" + i18n_message("download.mod.createdOverhaul", {
                            "count": entry_count
                        }))
                    return

                # zestaw modów (kilka modów bez kategorii Overhaul): pytamy
                # użytkownika czy ma powstać osobna instancja.
                if item.update_for is None and len(mod_folders) > 1:
                    install_log.info(
                        "MOD multi-set (%d mods) - asking user for decision",
                        len(mod_folders))
                    decision = self._multi_decisions.setdefault(
                        item.id, {"event": threading.Event(), "choice": ""})
                    decision["event"].clear()
                    item.subtitle = i18n_message("download.mod.foundMods", {
                        "count": len(mod_folders)
                    })
                    self._model.touch(self._model.row_of(item.id))
                    self.multiModFound.emit(item.id, info.title or info.slug,
                                            len(mod_folders))
                    decision["event"].wait()
                    check_cancel()
                    install_log.info("MOD multi-set decision: %r",
                                     decision["choice"])
                    if decision["choice"] == "instance":
                        entry_count = self._install_multi_as_instance(
                            info.slug, info.title or info.slug,
                            mod_folders, cancel,
                            game_version=item.game_version)
                        self.instancesRefreshNeeded.emit()
                        modpack_downloader.cleanup_temp_dir(temp_dir)
                        temp_dir = None
                        item.temp_dir = None
                        self.urlState.emit(
                            item.id,
                            "completed:" + i18n_message("download.mod.createdInstance", {
                                "count": entry_count
                            }))
                        return

                report = library_ops.install_modpack_to_library(
                    mods_root, source=f"web:{info.slug}", enable=False,
                    cancel_event=cancel, game_version=item.game_version)
                if not report.errors and (report.imported or report.already_present):
                    downloads_cleanup.register_installed(
                        dest.name, dest.stat().st_size, source=f"web:{info.slug}")
                parts = [i18n_message("download.mod.installedCount", {
                    "count": len(report.imported)
                })]
                if report.already_present:
                    parts.append(i18n_message("download.mod.alreadyCount", {
                        "count": len(report.already_present)
                    }))
                if report.errors:
                    parts.append(i18n_message("download.mod.errorCount", {
                        "count": len(report.errors)
                    }))
                modpack_downloader.cleanup_temp_dir(temp_dir)
                temp_dir = None
                item.temp_dir = None
                self.urlState.emit(item.id, "completed:" + "; ".join(parts))
            except OperationCancelled:
                install_log.info("MOD download cancelled: %s", item.url)
                self.urlState.emit(item.id, "cancelled")
            except Exception as exc:  # noqa: BLE001 - błąd trafia na kartę + toast
                install_log.exception("MOD download FAILED: %s (%s)", item.url, exc)
                logger.exception("Mod download from 7daystodiemods.com failed")
                self.urlState.emit(item.id, f"failed:{exc}")
            finally:
                if temp_dir is not None:
                    modpack_downloader.cleanup_temp_dir(temp_dir)

        def protected_worker():
            with downloads_cleanup.archive_use():
                worker()

        threading.Thread(target=protected_worker, daemon=True).start()

    def _on_mod_meta(self, item_id: str, title: str, subtitle: str,
                     total: int) -> None:
        item = self._find(item_id)
        if item is None:
            return
        if title:
            item.title = title
        if subtitle:
            item.subtitle = subtitle
        if total > 0:
            item.total_bytes = max(1, total)
        self._model.touch(self._model.row_of(item_id))

    @Slot(str, str)
    def resolveMulti(self, item_id: str, choice: str) -> None:
        """Decyzja UI dla zestawu modów (overhaul): "instance" albo "mods".
        Zwalnia worker, który czekał na Event."""
        info = self._multi_decisions.get(item_id)
        if info is None or info["event"].is_set():
            return
        info["choice"] = choice
        info["event"].set()

    def _install_overhaul_as_instance(self, slug: str, title: str,
                                      mod_folders: list, cancel,
                                      source_note: str = "z 7daystodiemods.com",
                                      game_version: str = "") -> int:
        """Instaluje Overhaul bezpośrednio do świeżej instancji.

        Nie tworzymy wpisów w Bibliotece ani stanu globalnej aktywacji. Cały
        pakiet jest fizycznie przechowywany w katalogu Mods instancji, więc
        usunięcie instancji z opcją kasowania danych usuwa również Overhaul.
        """
        registry = inst_mod.load_instances()
        base_name = (title or slug).strip()[:60] or slug
        instance_name = base_name
        counter = 2
        while inst_mod.validate_instance_name(instance_name, registry):
            instance_name = f"{base_name} ({counter})"[:60]
            counter += 1
        required_branch = required_game_branch(game_version)
        if required_branch:
            required_branch = resolve_downloaded_branch(required_branch) or required_branch
        instance = inst_mod.create_instance(
            instance_name,
            str(inst_mod.suggest_data_dir_for_name(instance_name)),
            noeos=True, noeac=True,
            description=f"Overhaul {slug} {source_note}",
            game_branch=required_branch,
            instances=registry,
        )
        install_log.info(
            "INSTANCE create: name=%r -> %s (game_branch=%r, description=%r)",
            instance.name, instance.data_dir, instance.game_branch, instance.description)
        fs.ensure_dir(instance.mods_dir)
        for folder in mod_folders:
            if cancel.is_set():
                raise OperationCancelled(i18n_message("common.operationCancelled"))
            source = Path(folder)
            target = instance.mods_dir / source.name
            if target.exists() or target.is_symlink():
                shutil.rmtree(target) if target.is_dir() and not target.is_symlink() else target.unlink()
            shutil.copytree(source, target, symlinks=True)
        inst_mod.save_instances(registry + [instance])
        install_log.info("INSTANCE ready: %r -> %s (%d mods copied)",
                         instance.name, instance.data_dir, len(mod_folders))
        return len(mod_folders)

    def _install_multi_as_instance(self, slug: str, title: str,
                                   mod_folders: list, cancel,
                                   game_version: str = "") -> int:
        """Ścieżka "utwórz instancję" (etap 18, wątek roboczy): mody z
        archiwum trafiają do Biblioteki (bez globalnego włączania), powstaje
        OSOBNA INSTANCJA o nazwie zestawu, mody są w niej punktowo włączone
        i folder Mods instancji jest budowany. Zwraca liczbę modów
        włączonych w instancji (nowo zaimportowane + te, które już były
        w Bibliotece)."""
        report = library_ops.import_mods_to_library(
            mod_folders, enable=False, source=f"web:{slug}", cancel_event=cancel,
            game_version=game_version)

        instance_name = (title or slug)[:60]
        registry = inst_mod.load_instances()
        required_branch = required_game_branch(game_version)
        if required_branch:
            required_branch = resolve_downloaded_branch(required_branch) or required_branch
        inst_obj = inst_mod.create_instance(
            instance_name,
            str(inst_mod.suggest_data_dir_for_name(instance_name)),
            noeos=True, noeac=True,
            description=f"Zestaw {slug} z 7daystodiemods.com",
            game_branch=required_branch,
            instances=registry)
        inst_mod.save_instances(registry + [inst_obj])

        # mody, które były już w Bibliotece, trafiły do report.already_present
        # jako NAZWY folderów źródłowych - odnajdujemy ich wpisy po content
        # hashu (tym samym kluczu, po którym import wykrył duplikat)
        library_ids = [entry.library_id for entry in report.imported]
        if report.already_present:
            present = set(report.already_present)
            entries = library.load_library_entries()
            for folder in mod_folders:
                folder_path = Path(folder)
                if folder_path.name not in present:
                    continue
                try:
                    existing = library.find_by_content_hash(
                        entries, library.compute_content_hash(folder_path))
                except OSError:
                    continue
                if existing is not None and existing.library_id not in library_ids:
                    library_ids.append(existing.library_id)

        state = library.load_activation_state()
        for library_id in library_ids:
            state.set_instance_inclusion(library_id, inst_obj.instance_id, True)
        library.save_activation_state(state)
        inst_mod.build_mods_for_instance(
            inst_obj, library.load_library_entries(),
            library.load_activation_state(), cancel_event=cancel)
        return len(library_ids)

    def _preserve_undead_legacy_archive(self, temp_dir: Path) -> Path | None:
        """Przenieś pobrane archiwum Undead Legacy do downloads/.

        Archiwum jest celowo zachowywane po udanej instalacji. Zarządzanie
        jego cyklem życia należy do istniejącego mechanizmu czyszczenia
        pobranych archiwów w launcherze, a nie do workera modpacka.
        """
        archive = Path(temp_dir) / "download.zip"
        if not archive.is_file():
            install_log.warning(
                "Undead Legacy archive was not found after extraction: %s",
                archive,
            )
            return None

        try:
            metadata = undead_legacy.fetch_latest_release(refresh=False)
            version = str(metadata.get("version") or undead_legacy.DEFAULT_VERSION).strip()
        except Exception:
            version = undead_legacy.DEFAULT_VERSION
            install_log.warning(
                "Could not refresh Undead Legacy archive version for filename; "
                "using fallback %s", version, exc_info=True,
            )

        safe_version = re.sub(r"[^0-9A-Za-z._-]+", "_", version).strip("._-")
        filename = f"UndeadLegacy_{safe_version}.zip" if safe_version else "UndeadLegacy.zip"
        destination = fs.downloads_dir() / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive.replace(destination)
        install_log.info("Undead Legacy archive preserved: %s", destination)
        return destination

    def _start_url_worker(self, item: DownloadItem) -> None:
        """Odpala wątek roboczy dla pozycji URL (promowanej z kolejki)."""
        cancel, pause = item.cancel_event, item.pause_event
        temp_dir = item.temp_dir

        def progress(done: int, total: int, label: str) -> None:
            self.urlProgress.emit(item.id, done, total, label)

        def worker() -> None:
            try:
                item.game_version = required_game_branch(item.game_version)
                if item.game_version:
                    item.game_version = resolve_downloaded_branch(item.game_version) or item.game_version
                if item.game_version and not self._is_downloaded_game_version(item.game_version):
                    raise modpack_downloader.DownloadError(
                        i18n_message("download.gameVersion.missing", {
                            "branch": item.game_version
                        })
                    )
                while True:
                    try:
                        install_log.info("URL download start: %s (%s)",
                                         item.url, item.flavor)
                        extracted = modpack_downloader.download_and_extract(
                            item.url, item.temp_dir,
                            progress_cb=progress,
                            cancel_event=cancel,
                            pause_event=pause,
                        )
                        install_log.info("URL download + extract done: %s",
                                         extracted)
                        break
                    except modpack_downloader.DownloadPaused:
                        install_log.info("URL download paused: %s", item.url)
                        self.urlState.emit(item.id, "paused")
                        while pause.is_set() and not cancel.is_set():
                            time.sleep(0.1)
                        if cancel.is_set():
                            raise OperationCancelled(i18n_message("common.operationCancelled"))
                        self.urlState.emit(item.id, "downloading")
                        continue

                mods_root = modpack_downloader.find_mods_root_in_extracted(extracted)
                if mods_root is None or not modpack_downloader.mods_root_has_valid_mods(mods_root):
                    raise modpack_downloader.DownloadError(
                        i18n_message("download.mod.modpackInvalid"))

                # Overhaul (katalog GitHub / wklejony URL): dedykowana
                # INSTANCJA zamiast globalnej Biblioteki - mody fizycznie
                # w Mods/ instancji (usunięcie instancji usuwa cały pakiet)
                mod_folders = [
                    child for child in sorted(mods_root.iterdir(), key=lambda p: p.name.lower())
                    if child.is_dir() and find_modinfo(child) is not None]
                install_log.info("URL mod folders (%d): %s",
                                 len(mod_folders), [p.name for p in mod_folders])
                if mod_folders:
                    host = re.match(r"https?://([^/]+)/", item.url or "")
                    source_note = f"z {host.group(1)}" if host else "pobrany z sieci"
                    install_log.info(
                        "URL is an OVERHAUL - dedicated instance path: title=%r",
                        item.title)
                    preserved_archive = None
                    if modpack_downloader.detect_source_kind(item.url) == modpack_downloader.DownloadSourceKind.UNDEAD_LEGACY_MIRROR:
                        preserved_archive = self._preserve_undead_legacy_archive(temp_dir)
                    entry_count = self._install_overhaul_as_instance(
                        item.title, item.title, mod_folders, cancel,
                        source_note=source_note, game_version=item.game_version)
                    self.instancesRefreshNeeded.emit()
                    if preserved_archive is not None:
                        try:
                            downloads_cleanup.register_installed(
                                preserved_archive.name,
                                preserved_archive.stat().st_size,
                                source="undead-legacy",
                            )
                        except Exception:
                            # Rejestr ma wpływ tylko na przyszłe auto-czyszczenie.
                            # Nie może oznaczać udanej instalacji jako błędnej.
                            install_log.warning(
                                "Could not register preserved Undead Legacy archive: %s",
                                preserved_archive,
                                exc_info=True,
                            )
                    # Archiwum zostało wcześniej przeniesione poza temp_dir,
                    # więc usuwamy wyłącznie wypakowaną zawartość roboczą.
                    modpack_downloader.cleanup_temp_dir(temp_dir)
                    temp_dir = None
                    item.temp_dir = None
                    self.urlState.emit(
                        item.id,
                        "completed:" + i18n_message("download.mod.createdOverhaul", {
                            "count": entry_count
                        }))
                    return

                # fallback: zawartość bez modów (teoretycznie niemożliwe -
                # mods_root_has_valid_mods już to sprawdza)
                report = library_ops.install_modpack_to_library(
                    mods_root, source="modpack", enable=False, cancel_event=cancel)
                parts = [i18n_message("download.mod.installedCount", {
                    "count": len(report.imported)
                })]
                if report.already_present:
                    parts.append(i18n_message("download.mod.alreadyCount", {
                        "count": len(report.already_present)
                    }))
                if report.errors:
                    parts.append(i18n_message("download.mod.errorCount", {
                        "count": len(report.errors)
                    }))
                self.urlState.emit(item.id, "completed:" + "; ".join(parts))
            except OperationCancelled:
                install_log.info("URL download cancelled: %s", item.url)
                self.urlState.emit(item.id, "cancelled")
            except Exception as exc:  # noqa: BLE001 - błąd trafia na kartę + toast
                install_log.exception("URL download FAILED: %s (%s)", item.url, exc)
                logger.exception("URL download failed")
                self.urlState.emit(item.id, f"failed:{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_url_progress(self, item_id: str, done: int, total: int, label: str) -> None:
        item = self._find(item_id)
        if item is None:
            return

        # Progress callback jest używany zarówno do transferu bajtów, jak i
        # do etapów post-processingu (np. wypakowywania ZIP-a, gdzie done/total
        # oznacza liczbę plików). Nie wolno mieszać tych jednostek, bo po cache
        # dostawalibyśmy np. 2 GB -> 1/31 i błędne/ujemne wartości w UI.
        phase = str(label or "")
        if phase.startswith(("__I18N__:download.mod.extracting|", "__I18N__:download.mod.cloning|")):
            item.speed = 0.0
            item._last_sample = None
            if phase:
                item.subtitle = phase[:180]
            # Transfer pliku został już zakończony; pozostawiamy ostatni sensowny
            # stan bajtowy zamiast podstawiać licznik plików jako bajty.
            self._model.touch(self._model.row_of(item_id))
            return

        try:
            done_i = max(0, int(done or 0))
            total_i = max(0, int(total or 0))
        except (TypeError, ValueError):
            done_i, total_i = 0, 0

        # Absolutna osłona przed ujemnym postępem i przekroczeniem totalu.
        effective_total = total_i if total_i > 0 else max(0, int(item.total_bytes or 0))
        if effective_total > 0:
            item.total_bytes = effective_total
            done_i = min(done_i, effective_total)

        now = time.monotonic()
        if item._last_sample is not None:
            dt = now - item._last_sample[0]
            if dt > 0:
                item.speed = max(0.0, (done_i - item._last_sample[1]) / dt)
        item._last_sample = (now, done_i)
        item.downloaded = done_i
        self._model.touch(self._model.row_of(item_id))

    def _on_url_state(self, item_id: str, state: str) -> None:
        item = self._find(item_id)
        if item is None:
            return
        if state == "paused":
            item.status = "paused"
            item.speed = 0.0
            self._model.touch_all()
            self._emit_counts()
            return
        if state == "downloading":
            item.status = "downloading"
            self._model.touch_all()
            self._emit_counts()
            return
        if state.startswith("completed"):
            info = state.split(":", 1)[1] if ":" in state else ""
            item.status = "completed"
            if item.total_bytes <= 0:
                # rozmiar nieznany (np. zipball GitHub bez Content-Length) -
                # po ukończeniu znamy go z liczby pobranych bajtów
                item.total_bytes = max(1, item.downloaded)
            item.downloaded = item.total_bytes
            item.finished_at = time.monotonic()
            self._model.touch_all()
            self._emit_counts()
            self._bus.toastKey("toast.downloads.installedToLibrary", {"info": info}, "success")
            self.modpackInstalled.emit(info)
            if item.kind == "update" and item.update_for:
                self.updateFinished.emit(item.update_for)
            return
        if state == "cancelled":
            self._model.remove(item_id)
            modpack_downloader.cleanup_temp_dir(item.temp_dir)
            self._bus.toastKey("toast.downloads.cancelled", {"title": item.title}, "info")
            self._emit_counts()
            return
        if state.startswith("failed:"):
            item.status = "failed"
            item.speed = 0.0
            item.subtitle = state.split(":", 1)[1]
            self._model.touch_all()
            self._emit_counts()
            self._bus.toastKey("toast.downloads.failed", {"title": item.title or item.subtitle}, "error")
