"""Mod management: list model, filter/sort proxy and the manager facade.

Everything the QML layer needs is exposed through ``ModManager`` (context
property ``Mods``):

* ``listModel``  - QSortFilterProxyModel wrapping ModListModel (for ListView)
* counts / recent list / updates list - recomputed after every change
* slots - toggle, add, uninstall, update, profile apply, rescan, demo reset
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from backend import library as library_model
from backend import library_ops
from backend import mod_thumbs
from backend import mod_updates
from backend.game_process import is_game_running
from backend.conflict_detector import ConflictDetector
from backend.events import EventBus
from backend.library import LibraryModEntry, find_by_library_id
from backend.mod_loader import ModLoader
from backend.mod_scanner import ModScanner
from backend.modinfo import find_modinfo
from models.mod import Mod
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

GAME_VERSION = "V1.0 · B333 STABLE"


# =========================================================================== #
#  QAbstractListModel
# =========================================================================== #
class ModListModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = IdRole + 1
    VersionRole = IdRole + 2
    NewVersionRole = IdRole + 3
    AuthorRole = IdRole + 4
    DescriptionRole = IdRole + 5
    CategoryRole = IdRole + 6
    EnabledRole = IdRole + 7
    HasUpdateRole = IdRole + 8
    InConflictRole = IdRole + 9
    SizeTextRole = IdRole + 10
    SizeBytesRole = IdRole + 11
    InstalledTextRole = IdRole + 12
    InstalledStampRole = IdRole + 13
    UpdatedTextRole = IdRole + 14
    UpdatedStampRole = IdRole + 15
    UpdatedAgoRole = IdRole + 16
    DownloadsTextRole = IdRole + 17
    RatingRole = IdRole + 18
    TagsRole = IdRole + 19
    ThumbUrlRole = IdRole + 20
    GameVersionRole = IdRole + 21

    ROLES = {
        IdRole: b"modId",
        NameRole: b"name",
        VersionRole: b"version",
        NewVersionRole: b"newVersion",
        AuthorRole: b"author",
        DescriptionRole: b"description",
        CategoryRole: b"category",
        EnabledRole: b"modEnabled",
        HasUpdateRole: b"hasUpdate",
        InConflictRole: b"inConflict",
        SizeTextRole: b"sizeText",
        SizeBytesRole: b"sizeBytes",
        InstalledTextRole: b"installedText",
        InstalledStampRole: b"installedStamp",
        UpdatedTextRole: b"updatedText",
        UpdatedStampRole: b"updatedStamp",
        UpdatedAgoRole: b"updatedAgo",
        DownloadsTextRole: b"downloadsText",
        RatingRole: b"rating",
        TagsRole: b"tags",
        ThumbUrlRole: b"thumbUrl",
        GameVersionRole: b"gameVersion",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mods: list[Mod] = []
        self._conflict_ids: set[str] = set()
        self._thumbs: dict[str, str] = {}   # library_id -> file:// URL

    # -------------------------------------------------------------- #
    # Qt model API
    # -------------------------------------------------------------- #
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._mods)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._mods)):
            return None
        mod = self._mods[index.row()]
        attr = {
            self.IdRole: mod.id,
            self.NameRole: mod.name,
            self.VersionRole: mod.version,
            self.NewVersionRole: mod.new_version,
            self.AuthorRole: mod.author,
            self.DescriptionRole: mod.description,
            self.CategoryRole: mod.category,
            self.EnabledRole: mod.enabled,
            self.HasUpdateRole: mod.has_update,
            self.InConflictRole: mod.id in self._conflict_ids,
            self.SizeTextRole: mod.size_text,
            self.SizeBytesRole: mod.size_bytes,
            self.InstalledTextRole: mod.installed_text,
            self.InstalledStampRole: mod.installed_stamp,
            self.UpdatedTextRole: mod.updated_text,
            self.UpdatedStampRole: mod.updated_stamp,
            self.UpdatedAgoRole: mod.updated_ago,
            self.DownloadsTextRole: mod.downloads_text,
            self.RatingRole: mod.rating,
            self.TagsRole: mod.tags,
            self.ThumbUrlRole: self._thumbs.get(mod.id, ""),
            self.GameVersionRole: mod.game_version,
        }
        return attr.get(role)

    # -------------------------------------------------------------- #
    # list access
    # -------------------------------------------------------------- #
    @property
    def mods(self) -> list[Mod]:
        return self._mods

    def set_mods(self, mods: list[Mod]) -> None:
        self.beginResetModel()
        self._mods = list(mods)
        self.endResetModel()

    def row_of(self, mod_id: str) -> int:
        for row, mod in enumerate(self._mods):
            if mod.id == mod_id:
                return row
        return -1

    def mod_by_id(self, mod_id: str) -> Mod | None:
        row = self.row_of(mod_id)
        return self._mods[row] if row >= 0 else None

    def _row_changed(self, row: int) -> None:
        index = self.index(row, 0)
        self.dataChanged.emit(index, index)

    def touch(self, mod_id: str) -> None:
        row = self.row_of(mod_id)
        if row >= 0:
            self._row_changed(row)

    def set_thumb(self, mod_id: str, url: str) -> None:
        self._thumbs[mod_id] = url
        self.touch(mod_id)

    def set_thumbs(self, thumbs: dict[str, str]) -> None:
        self._thumbs.update(thumbs)

    def thumb_url(self, mod_id: str) -> str:
        return self._thumbs.get(mod_id, "")

    # -------------------------------------------------------------- #
    # mutations
    # -------------------------------------------------------------- #
    def set_enabled(self, mod_id: str, enabled: bool) -> bool:
        mod = self.mod_by_id(mod_id)
        if mod is None or mod.enabled == enabled:
            return False
        mod.enabled = enabled
        self.touch(mod_id)
        return True

    def toggle(self, mod_id: str) -> None:
        mod = self.mod_by_id(mod_id)
        if mod is not None:
            self.set_enabled(mod_id, not mod.enabled)

    def apply_update(self, mod_id: str) -> bool:
        mod = self.mod_by_id(mod_id)
        if mod is None or not mod.new_version:
            return False
        mod.version = mod.new_version
        mod.new_version = ""
        mod.updated_at = datetime.now()
        self.touch(mod_id)
        return True

    def insert_mod(self, mod: Mod, row: int = 0) -> None:
        row = max(0, min(row, len(self._mods)))
        self.beginInsertRows(QModelIndex(), row, row)
        self._mods.insert(row, mod)
        self.endInsertRows()

    def remove_mod(self, mod_id: str) -> Mod | None:
        row = self.row_of(mod_id)
        if row < 0:
            return None
        self.beginRemoveRows(QModelIndex(), row, row)
        mod = self._mods.pop(row)
        self.endRemoveRows()
        return mod

    def moveRows(self, sourceParent, sourceRow, count,
                 destinationParent, destinationRow) -> bool:
        if count != 1:
            return False
        n = len(self._mods)
        if not (0 <= sourceRow < n):
            return False
        if not (0 <= destinationRow <= n):
            return False
        if destinationRow in (sourceRow, sourceRow + 1):
            return False  # no-op

        self.beginMoveRows(sourceParent, sourceRow, sourceRow,
                           destinationParent, destinationRow)
        mod = self._mods.pop(sourceRow)
        insert_at = destinationRow if destinationRow < sourceRow else destinationRow - 1
        self._mods.insert(insert_at, mod)
        self.endMoveRows()
        return True

    def set_conflicts(self, ids: set[str]) -> None:
        changed = ids ^ self._conflict_ids
        if not changed:
            return
        self._conflict_ids = set(ids)
        for mod_id in changed:
            self.touch(mod_id)


# =========================================================================== #
#  Filter / sort / search proxy
# =========================================================================== #
class ModProxyModel(QSortFilterProxyModel):
    MODE_ALL = "all"
    MODE_ENABLED = "enabled"
    MODE_DISABLED = "disabled"
    MODE_UPDATES = "updates"
    MODE_CONFLICTS = "conflicts"

    searchTextChanged = Signal()
    filterModeChanged = Signal()
    sortModeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search = ""
        self._filter = self.MODE_ALL
        self._sort = "custom"
        self._sort_desc = False
        self.setDynamicSortFilter(False)

    # -- properties ------------------------------------------------- #
    @Property(str, notify=searchTextChanged)
    def searchText(self) -> str:
        return self._search

    @searchText.setter
    def searchText(self, value: str) -> None:
        value = value or ""
        if value == self._search:
            return
        self.beginFilterChange()
        self._search = value
        self.searchTextChanged.emit()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @Property(str, notify=filterModeChanged)
    def filterMode(self) -> str:
        return self._filter

    @filterMode.setter
    def filterMode(self, value: str) -> None:
        if value == self._filter:
            return
        self.beginFilterChange()
        self._filter = value or self.MODE_ALL
        self.filterModeChanged.emit()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @Property(str, notify=sortModeChanged)
    def sortMode(self) -> str:
        return self._sort

    @sortMode.setter
    def sortMode(self, value: str) -> None:
        if value == self._sort:
            return
        self._sort = value or "custom"
        # rozsądny domyślny kierunek dla kryterium (rozmiar/data: najwięsze
        # / najnowsze pierwsze); użytkownik może odwrócić przyciskiem w QML
        self._sort_desc = self._sort in ("size", "installed", "updated")
        self.sortModeChanged.emit()
        self._apply_sort()

    @Property(bool, notify=sortModeChanged)
    def sortDescending(self) -> bool:
        return self._sort_desc

    @sortDescending.setter
    def sortDescending(self, value: bool) -> None:
        value = bool(value)
        if value == self._sort_desc:
            return
        self._sort_desc = value
        self.sortModeChanged.emit()
        self._apply_sort()

    # -- sorting ------------------------------------------------------ #
    def _apply_sort(self) -> None:
        if self._sort == "custom":
            self.setDynamicSortFilter(False)
            self.sort(-1)  # restore source (load) order
        else:
            self.setDynamicSortFilter(True)
            order = (Qt.SortOrder.DescendingOrder if self._sort_desc
                     else Qt.SortOrder.AscendingOrder)
            self.sort(0, order)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if self._sort == "custom":
            return left.row() < right.row()
        roles = {
            "name": ModListModel.NameRole,
            "author": ModListModel.AuthorRole,
            "size": ModListModel.SizeBytesRole,
            "installed": ModListModel.InstalledStampRole,
            "updated": ModListModel.UpdatedStampRole,
        }
        role = roles.get(self._sort)
        if role is None:
            return left.row() < right.row()
        a, b = left.data(role), right.data(role)
        if isinstance(a, str) and isinstance(b, str):
            return a.casefold() < b.casefold()
        try:
            return a < b
        except TypeError:
            return False

    # -- filtering ---------------------------------------------------- #
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: ModListModel = self.sourceModel()  # type: ignore[assignment]
        index = model.index(source_row, 0)
        name = (index.data(ModListModel.NameRole) or "")
        author = (index.data(ModListModel.AuthorRole) or "")
        category = (index.data(ModListModel.CategoryRole) or "")
        description = (index.data(ModListModel.DescriptionRole) or "")
        tags = index.data(ModListModel.TagsRole) or []
        enabled = bool(index.data(ModListModel.EnabledRole))
        has_update = bool(index.data(ModListModel.HasUpdateRole))
        in_conflict = bool(index.data(ModListModel.InConflictRole))

        if self._search:
            needle = self._search.casefold()
            haystack = " ".join([name, author, category, description,
                                 " ".join(tags)]).casefold()
            if needle not in haystack:
                return False

        if self._filter == self.MODE_ENABLED:
            return enabled
        if self._filter == self.MODE_DISABLED:
            return not enabled
        if self._filter == self.MODE_UPDATES:
            return has_update
        if self._filter == self.MODE_CONFLICTS:
            return in_conflict
        return True

    # -- drag & drop --------------------------------------------------- #
    @Slot(int, int)
    def move(self, from_row: int, to_row: int) -> None:
        """Move an item (proxy rows) - called by the DnD delegates."""
        source: ModListModel = self.sourceModel()  # type: ignore[assignment]
        if source is None:
            return
        if not (0 <= from_row < self.rowCount()):
            return
        src = self.mapToSource(self.index(from_row, 0)).row()
        if to_row < 0 or to_row >= self.rowCount():
            return
        if to_row == from_row:
            return
        if from_row < to_row:
            # moving down: insert AFTER the destination row
            dst = self.mapToSource(self.index(to_row, 0)).row() + 1
        else:
            dst = self.mapToSource(self.index(to_row, 0)).row()
        source.moveRows(QModelIndex(), src, 1, QModelIndex(), dst)


# =========================================================================== #
#  Manager facade exposed to QML as "Mods"
# =========================================================================== #
class ModManager(QObject):
    countsChanged = Signal()
    searchTextChanged = Signal()
    filterModeChanged = Signal()
    sortModeChanged = Signal()
    modChanged = Signal(str)          # a single mod's data changed
    modAdded = Signal(str)
    modRemoved = Signal(str)
    demoReset = Signal()
    # library layer (migration stage 3); emitted from worker threads
    libraryRemoved = Signal(str, str)      # library_id, error ("" = ok)
    libraryImported = Signal(int, int, int)  # imported, already_present, errors
    libraryScanReady = Signal(dict, dict)  # id -> size_bytes, id -> [modified xml files]
    folderImportFinished = Signal(int, int, int, int)  # found, imported, already, errors
    # update checking (stage 11); worker -> GUI apply
    updateCheckReady = Signal(list, int)   # [(mod_id, UpdateInfo)], failed_count
    updateCheckFinished = Signal(int, int) # found, failed
    updateCheckBusyChanged = Signal()
    # miniatury ikon (etap 17); worker -> GUI
    thumbReady = Signal(str, str)          # library_id, file:// URL
    thumbStatusText = Signal(str)          # "12/36" - postęp dla strony Mody
    gameVersionChanged = Signal()          # wykryta wersja gry (z GameDetector)
    thumbStatusPropChanged = Signal()
    thumbScanFinished = Signal(int, int)   # added, failed

    def __init__(self, settings: SettingsService, bus: EventBus,
                 conflicts: ConflictDetector, game=None, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._bus = bus
        self._conflicts = conflicts
        self._game = game
        if game is not None:
            game.versionGroupChanged.connect(self.gameVersionChanged.emit)
        self._loader = ModLoader()
        self._scanner = ModScanner(self)
        self._scanner.scanFinished.connect(self._on_scan_finished)
        self._scanner.scanFailed.connect(lambda msg: bus.toastKey("common.operationFailed", {"error": msg}, "error"))

        self._model = ModListModel(self)
        self._proxy = ModProxyModel(self)
        self._proxy.setSourceModel(self._model)
        # Forward proxy state changes to the facade exposed to QML.
        # Filtering changes the model immediately, but without forwarding the
        # notify signal QML bindings such as FilterChip.active remain stale.
        self._proxy.filterModeChanged.connect(self.filterModeChanged.emit)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._persist)

        # migration stage 3: the Mods tab is fed by the REAL library
        # (library.json + activation.json), isolated from the legacy
        # manager. Demo seed data is kept as an internal/testing capability.
        self._library_entries: list[LibraryModEntry] = library_model.load_library_entries()
        self._activation = library_model.load_activation_state()
        self._modified_files: dict[str, list[str]] = {}
        self.libraryRemoved.connect(self._on_library_removed)
        self.libraryImported.connect(self._on_library_imported)
        self.folderImportFinished.connect(self._on_folder_import_finished)
        self.libraryScanReady.connect(self._on_library_scan_ready)

        if self._library_entries:
            self._model.set_mods(self._build_mods_from_library())
        else:
            self._model.set_mods([])
        self._refresh_conflicts(initial=True)
        if self._library_entries:
            self._scan_library_async()

        # etap 11: aktualizacje tylko na życzenie - automatyczne sprawdzanie
        # przy starcie wyłącznie jako opt-in w Ustawieniach (autoCheckUpdates)
        self._update_check_busy = False
        self.updateCheckReady.connect(self._on_update_check_ready)
        QTimer.singleShot(9000, self._auto_check_if_enabled)

        # etap 17: miniatury ikon modów - ściągane w tle przy starcie
        self._thumb_busy = False
        self._thumb_status = ""
        self._thumb_failed: set[str] = set()   # w tej sesji już nie ponawiamy
        self.thumbReady.connect(self._on_thumb_ready)
        self.thumbStatusText.connect(self._on_thumb_status_text)
        self.thumbScanFinished.connect(self._on_thumb_scan_finished)
        self._model.set_thumbs(mod_thumbs.preload_urls())
        QTimer.singleShot(12000, self._start_thumb_scan)

    # ------------------------------------------------------------------ #
    # update checking (stage 11) - NIGDY automatyczna instalacja z tego
    # miejsca; auto-pobranie po sprawdzeniu to osobna opt-in opcja
    # (Settings.autoUpdateMods) obsługiwana w main.py/DownloadManager
    # ------------------------------------------------------------------ #
    @Slot()
    def checkUpdates(self) -> None:
        """Sprawdza wszystkie mody Biblioteki względem 7daystodiemods.com
        (ręcznie z UI albo automatycznie, gdy autoCheckUpdates włączone)."""
        if self._update_check_busy:
            self._bus.toastKey("toast.mods.updateCheckBusy", {}, "info")
            return
        pairs = []
        for mod in self._model.mods:
            entry = self.library_entry(mod.id)
            if entry is not None:
                pairs.append((mod.id, entry))
        if not pairs:
            self._bus.toastKey("toast.mods.noModsToCheck", {}, "info")
            return
        self._update_check_busy = True
        self.updateCheckBusyChanged.emit()

        def worker() -> None:
            import time as _time
            client = mod_updates.SevenDaysModsClient()
            results = []
            failed = 0
            for index, (mod_id, entry) in enumerate(pairs):
                if index:
                    _time.sleep(0.8)   # grzecznościowa pauza dla serwisu
                try:
                    info = mod_updates.check_update(entry, client)
                except Exception as exc:  # noqa: BLE001 - per-mod błąd nie stopuje
                    logger.warning("Update check failed for %s: %s", mod_id, exc)
                    info = None
                if info is None:
                    failed += 1
                else:
                    results.append((mod_id, info))
            self.updateCheckReady.emit(results, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_ready(self, results: list, failed: int) -> None:
        self._update_check_busy = False
        self.updateCheckBusyChanged.emit()
        # odśwież wpisy - sprawdzanie mogło dopisać web_slug do rejestru
        self._library_entries = library_model.load_library_entries()
        found = 0
        for mod_id, info in results:
            mod = self._model.mod_by_id(mod_id)
            if mod is None:
                continue
            mod.new_version = info.site_version if info.has_update else ""
            self._model.touch(mod_id)
            if info.has_update:
                found += 1
        self.countsChanged.emit()
        if found or failed:
            key = "toast.mods.updateCheckSummary" if failed else "toast.mods.updateCheckSummaryFound"
            values = {"found": found, "failed": failed}
            self._bus.toastKey(key, values, "success" if found else "info")
        else:
            self._bus.toastKey("toast.mods.allUpToDate", {}, "success")
        self.updateCheckFinished.emit(found, failed)

    def _auto_check_if_enabled(self) -> None:
        if self._settings.autoCheckUpdates:
            self.checkUpdates()

    def library_entry(self, mod_id: str) -> LibraryModEntry | None:
        """Wpis Biblioteki dla id moda z modelu (id == library_id)."""
        return find_by_library_id(self._library_entries, mod_id)

    # ------------------------------------------------------------------ #
    # miniatury ikon (etap 17) - tło przy starcie; plik w cache/thumbs
    # jest źródłem prawdy (jest = nie pobieramy ponownie)
    # ------------------------------------------------------------------ #
    def _start_thumb_scan(self) -> None:
        if self._thumb_busy:
            return
        todo = []
        for mod in self._model.mods:
            entry = self.library_entry(mod.id)
            if entry is None or mod_thumbs.has_thumb(entry.library_id):
                continue
            todo.append((mod.id, entry))
        if not todo:
            return
        self._thumb_busy = True
        self.thumbStatusPropChanged.emit()
        self._bus.toastKey("toast.mods.thumbFetchStarted", {"count": len(todo)}, "info")

        def worker() -> None:
            import time as _time
            total = len(todo)
            added = failed = 0
            for index, (mod_id, entry) in enumerate(todo):
                # czekaj aż sprawdzanie aktualizacji skończy kolejkę żądań
                # (nie dubluj zapytań do serwisu)
                while self._update_check_busy:
                    _time.sleep(0.5)
                name = entry.display_name or entry.mod_name or ""
                # PRIORYTET 1: Banner/Icon z ModInfo.xml zainstalowanego moda
                # (zero sieci, natychmiast)
                local = None
                try:
                    local = mod_thumbs.local_banner(entry.path)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Local thumbnail %s: %s", name, exc)
                if local is not None:
                    cached = mod_thumbs.cache_banner(local, entry.library_id)
                    added += 1
                    self.thumbReady.emit(entry.library_id,
                                         "file://" + str(cached))
                    self.thumbStatusText.emit(f"{index + 1}/{total}")
                    continue

                # PRIORYTET 2: wyszukiwanie na stronie (czekaj na update-check)
                while self._update_check_busy:
                    _time.sleep(0.5)
                if index:
                    _time.sleep(0.9)
                try:
                    path = mod_thumbs.resolve_and_download(
                        name, entry.library_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Thumbnail %s: %s", name, exc)
                    path = None
                if path is None:
                    self._thumb_failed.add(entry.library_id)
                    failed += 1
                else:
                    added += 1
                    self.thumbReady.emit(
                        entry.library_id, "file://" + str(path))
                self.thumbStatusText.emit(f"{index + 1}/{total}")
            self.thumbScanFinished.emit(added, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_thumb_ready(self, library_id: str, url: str) -> None:
        self._model.set_thumb(library_id, url)

    def _on_thumb_status_text(self, text: str) -> None:
        self._thumb_status = text
        self.thumbStatusPropChanged.emit()

    def _on_thumb_scan_finished(self, added: int, failed: int) -> None:
        self._thumb_busy = False
        self._thumb_status = ""
        self.thumbStatusPropChanged.emit()
        if added:
            self._bus.toastKey("toast.mods.thumbsAdded", {"count": added}, "success")
        elif failed:
            self._bus.toastKey("toast.mods.thumbsFailed", {"count": failed}, "warning")

    # ------------------------------------------------------------------ #
    # models & properties
    # ------------------------------------------------------------------ #
    @Property("QVariant", constant=True)
    def listModel(self) -> QAbstractListModel:
        return self._proxy

    @Property(int, notify=countsChanged)
    def totalMods(self) -> int:
        return len(self._model.mods)

    @Property(int, notify=countsChanged)
    def enabledCount(self) -> int:
        return sum(1 for m in self._model.mods if m.enabled)

    @Property(int, notify=countsChanged)
    def updateCount(self) -> int:
        return sum(1 for m in self._model.mods if m.has_update)

    @Property(bool, notify=updateCheckBusyChanged)
    def updateCheckBusy(self) -> bool:
        return self._update_check_busy

    @Property(str, notify=thumbStatusPropChanged)
    def thumbStatus(self) -> str:
        return self._thumb_status

    @Property(int, notify=countsChanged)
    def conflictCount(self) -> int:
        return self._conflicts.count

    @Property(str, notify=gameVersionChanged)
    def gameVersion(self) -> str:
        """Wykryta wersja zainstalowanej gry (appmanifest -> branch -> grupa),
        np. "V3 · build 24994517"; "" = gra niewykryta/nieznana."""
        if self._game is None:
            return GAME_VERSION
        group = self._game.versionGroup
        if not group:
            return ""
        label = {"v1": "V1", "v2": "V2", "v3": "V3", "alpha": "Alpha"}.get(
            group, group.upper())
        build = self._game.buildId
        return f"{label} · build {build}" if build else label

    @Property("QVariantMap", notify=countsChanged)
    def filterCounts(self) -> dict:
        mods = self._model.mods
        return {
            "all": len(mods),
            "enabled": sum(1 for m in mods if m.enabled),
            "disabled": sum(1 for m in mods if not m.enabled),
            "updates": sum(1 for m in mods if m.has_update),
            "conflicts": len(self._conflicts.affected_ids),
        }

    @Property("QVariantList", notify=countsChanged)
    def recentUpdated(self) -> list:
        mods = sorted(self._model.mods, key=lambda m: m.updated_stamp, reverse=True)[:5]
        return [self._mini_mod(m) for m in mods]

    @Property("QVariantList", notify=countsChanged)
    def updatesList(self) -> list:
        return [self._full_mod(m) for m in self._model.mods if m.has_update]

    @Property(bool, notify=countsChanged)
    def hasMods(self) -> bool:
        return bool(self._model.mods)

    # -- search / filter / sort forwarding ---------------------------- #
    @Property(str, notify=searchTextChanged)
    def searchText(self) -> str:
        return self._proxy.searchText

    @searchText.setter
    def searchText(self, value: str) -> None:
        self._proxy.searchText = value

    @Property(str, notify=filterModeChanged)
    def filterMode(self) -> str:
        return self._proxy.filterMode

    @filterMode.setter
    def filterMode(self, value: str) -> None:
        self._proxy.filterMode = value

    @Property(str, notify=sortModeChanged)
    def sortMode(self) -> str:
        return self._proxy.sortMode

    @sortMode.setter
    def sortMode(self, value: str) -> None:
        self._proxy.sortMode = value
        self.sortModeChanged.emit()   # bez tego label dropdownu nie aktualizuje się

    @Property(bool, notify=sortModeChanged)
    def sortDescending(self) -> bool:
        return self._proxy.sortDescending

    @sortDescending.setter
    def sortDescending(self, value: bool) -> None:
        self._proxy.sortDescending = bool(value)
        self.sortModeChanged.emit()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _mini_mod(self, mod: Mod) -> dict:
        return {
            "id": mod.id,
            "name": mod.name,
            "version": mod.version,
            "newVersion": mod.new_version,
            "updatedAgo": mod.updated_ago,
            "category": mod.category,
            "author": mod.author,
        }

    def _full_mod(self, mod: Mod) -> dict:
        dep_names = []
        for dep_id in mod.dependencies:
            dep = self._model.mod_by_id(dep_id)
            dep_names.append(dep.name if dep else dep_id)
        conflict_names = self._conflicts.partners_of(mod.id)
        return {
            "id": mod.id,
            "name": mod.name,
            "version": mod.version,
            "newVersion": mod.new_version,
            "author": mod.author,
            "description": mod.description,
            "category": mod.category,
            "enabled": mod.enabled,
            "hasUpdate": mod.has_update,
            "inConflict": mod.id in self._conflicts.affected_ids,
            "sizeText": mod.size_text,
            "installedText": mod.installed_text,
            "updatedText": mod.updated_text,
            "updatedAgo": mod.updated_ago,
            "downloadsText": mod.downloads_text,
            "rating": mod.rating,
            "tags": list(mod.tags),
            "dependencies": dep_names,
            "conflictNames": conflict_names,
            "gameVersion": GAME_VERSION,
            "thumbUrl": self._model.thumb_url(mod.id),
        }

    def _notify_counts(self) -> None:
        self.countsChanged.emit()

    def _persist_later(self) -> None:
        self._save_timer.start()

    def _persist(self) -> None:
        self._loader.save_state(self._model.mods)

    def _refresh_conflicts(self, initial: bool = False) -> None:
        previous = set(self._conflicts.pair_keys())
        pairs = self._conflicts.recompute(self._model.mods)
        self._model.set_conflicts(self._conflicts.affected_ids)
        if not initial:
            for pair in pairs:
                key = (pair["modAId"], pair["modBId"])
                if key not in previous:
                    self._bus.toastKey("toast.mods.conflictDetected", {"a": pair["modAName"], "b": pair["modBName"]}, "warning")
        self._notify_counts()

    # ------------------------------------------------------------------ #
    # library integration (migration stage 3)
    # ------------------------------------------------------------------ #
    def _is_library_mod(self, mod_id: str) -> bool:
        return find_by_library_id(self._library_entries, mod_id) is not None

    def _library_entry(self, mod_id: str) -> LibraryModEntry | None:
        return find_by_library_id(self._library_entries, mod_id)

    def _reload_library(self) -> None:
        self._library_entries = library_model.load_library_entries()
        self._activation = library_model.load_activation_state()

    def _build_mods_from_library(self) -> list[Mod]:
        """Mapuje wpisy Biblioteki na model UI (role ModListModel niezmienne).
        Kolejność wczytywana ze stanu (state.json - drag&drop z trybu
        demo/sesji), wpisy nieznane w kolejności trafiają na koniec.
        Włączenie = ActivationState globalny (instancja "main" - wykluczenia
        per instancja dojdą z etapem 6)."""
        state = self._loader.load_state() or {}
        order = [str(x) for x in (state.get("order") or [])]
        position = {mod_id: i for i, mod_id in enumerate(order)}
        mods: list[Mod] = []
        for entry in self._library_entries:
            try:
                added = datetime.fromisoformat(entry.added_at)
            except ValueError:
                added = datetime.now()
            mods.append(
                Mod(
                    id=entry.library_id,
                    name=entry.title,
                    author=entry.author or i18n_message("common.unknown"),
                    category="Library",
                    version=entry.version or "?",
                    new_version="",
                    enabled=self._activation.is_enabled_for(entry.library_id),
                    description=entry.description,
                    size_bytes=0,  # liczone asynchronicznie (_scan_library_async)
                    downloads=0,
                    rating=0.0,
                    tags=[],
                    dependencies=[],
                    modified_files=self._modified_files.get(entry.library_id, []),
                    installed_at=added,
                    updated_at=added,
                    game_version=entry.game_version,
                )
            )
        mods.sort(key=lambda m: position.get(m.id, len(position)))
        return mods

    def _scan_library_async(self) -> None:
        """Rozmiary i modyfikowane pliki liczone w wątku tła (rglob po
        bibliotece potrafi potrwać) - wynik wraca sygnałem na GUI.

        Realny sygnał konfliktów (etap 4): pliki gry nadpisywane przez mod.
        Dla 7DTD to pliki XML (Config/*.xml i patche); zbieramy ścieżki
        WZGLĘDNE do korzenia moda (konwencja posix) - dwa włączone mody
        z tą samą względną ścieżką = detector oznaja konflikt."""
        entries = list(self._library_entries)

        def worker() -> None:
            sizes: dict[str, int] = {}
            modified: dict[str, list[str]] = {}
            for entry in entries:
                try:
                    files = [p for p in entry.path.rglob("*") if p.is_file()]
                    sizes[entry.library_id] = sum(f.stat().st_size for f in files)
                    # ModInfo.xml wykluczony: każdy mod ma WŁASNY w swoim
                    # folderze - nigdy się między modami nie nadpisuje, więc
                    # to nie jest konflikt (fałszywe alarmy, zgłoszenie 26.09)
                    relative_xml = []
                    for file_path in files:
                        if file_path.suffix.lower() != ".xml" or file_path.name.lower() == "modinfo.xml":
                            continue
                        try:
                            relative_xml.append(file_path.relative_to(entry.path).as_posix())
                        except ValueError:
                            # The library entry can disappear or be replaced while
                            # the background scan is running. Never let one stale
                            # path kill the worker thread and leave the scan model
                            # half-updated.
                            logger.debug(
                                "Skipping file outside library entry while scanning %s: %s",
                                entry.path,
                                file_path,
                            )
                    modified[entry.library_id] = sorted(relative_xml)
                except OSError:
                    sizes[entry.library_id] = 0
                    modified[entry.library_id] = []
            self.libraryScanReady.emit(sizes, modified)

        threading.Thread(target=worker, daemon=True).start()

    def _on_library_scan_ready(self, sizes: dict, modified: dict) -> None:
        self._modified_files = modified
        for mod in self._model.mods:
            changed = False
            if mod.id in sizes and mod.size_bytes != sizes[mod.id]:
                mod.size_bytes = sizes[mod.id]
                changed = True
            new_files = modified.get(mod.id, [])
            if mod.modified_files != new_files:
                mod.modified_files = new_files
                changed = True
            if changed:
                self._model.touch(mod.id)
        self._refresh_conflicts()

    def _on_library_removed(self, mod_id: str, error: str) -> None:
        self._reload_library()
        mod = self._model.remove_mod(mod_id)
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        self.modRemoved.emit(mod_id)
        name = mod.name if mod else mod_id
        if error:
            self._bus.toastKey("toast.mods.removeFailed", {"name": name, "error": error}, "error")
        else:
            self._bus.toastKey("toast.mods.removed", {"name": name}, "info")

    def _on_library_imported(self, imported: int, already: int, errors: int) -> None:
        self._reload_library()
        self._model.set_mods(self._build_mods_from_library())
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        self._scan_library_async()
        if imported:
            self._bus.toastKey("toast.mods.imported", {"count": imported}, "success")
        if already:
            self._bus.toastKey("toast.mods.alreadyInLibrary", {"count": already}, "info")
        if errors:
            self._bus.toastKey("toast.mods.importErrors", {"count": errors}, "error")

    @Slot()
    def reload_library_from_disk(self) -> None:
        """Publiczne przeładowanie Biblioteki z dysku (np. po instalacji
        modpacka z URL po stronie DownloadManagera) - bez toastów."""
        self._reload_library()
        self._model.set_mods(self._build_mods_from_library())
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        if self._library_entries:
            self._scan_library_async()

    # ------------------------------------------------------------------ #
    # slots (called from QML)
    # ------------------------------------------------------------------ #
    def _version_mismatch_details(self, mod_id: str) -> dict:
        entry = next((e for e in self._library_entries if e.library_id == mod_id), None)
        mod_version = (entry.game_version if entry else "").strip()
        if not mod_version or self._game is None:
            return {}
        game_group = self._game.versionGroup
        if not game_group:
            return {}
        from backend.game_versions import version_group
        return {"modVersion": mod_version, "gameGroup": game_group} if version_group(mod_version) != game_group else {}

    def _version_mismatch(self, mod_id: str) -> str:
        details = self._version_mismatch_details(mod_id)
        if not details:
            return ""
        return i18n_message("mods.versionMismatch", {"modVersion": details["modVersion"], "gameGroup": details["gameGroup"]})

    @Slot(str)
    def toggleMod(self, mod_id: str) -> None:
        mismatch = self._version_mismatch_details(mod_id)
        if mismatch:
            self._bus.toastKey("toast.mods.versionMismatch", mismatch, "warning")
            return
        if is_game_running():
            self._bus.toastKey("toast.mods.runningCannotToggle", {}, "warning")
            return
        mod = self._model.mod_by_id(mod_id)
        if mod is None:
            return
        mod.enabled = not mod.enabled
        if self._is_library_mod(mod_id):
            # prawdziwa aktywacja: globalny zestaw włączonych (instancja
            # "main"; wykluczenia per instancja dojdą z etapem 6).
            # świeży load-modify-save pod blokadą - równoległy pisarz
            # (np. kończący się import z URL z enable=True) nie zostanie
            # nadpisany naszą kopią w pamięci
            library_ops.set_global_enabled(mod_id, mod.enabled)
            self._activation = library_model.load_activation_state()
        self._model.touch(mod_id)
        self._refresh_conflicts()
        self._persist_later()
        self.modChanged.emit(mod_id)
        key = "toast.mods.enabled" if mod.enabled else "toast.mods.disabled"
        self._bus.toastKey(key, {"name": mod.name}, "success" if mod.enabled else "info")

    @Slot(str, bool)
    def setEnabled(self, mod_id: str, enabled: bool) -> None:
        if enabled:
            mismatch = self._version_mismatch_details(mod_id)
            if mismatch:
                self._bus.toastKey("toast.mods.versionMismatch", mismatch, "warning")
                return
        if is_game_running():
            self._bus.toastKey("toast.mods.runningCannotToggle", {}, "warning")
            return
        mod = self._model.mod_by_id(mod_id)
        if mod is None or mod.enabled == enabled:
            return
        mod.enabled = enabled
        if self._is_library_mod(mod_id):
            library_ops.set_global_enabled(mod_id, enabled)
            self._activation = library_model.load_activation_state()
        self._model.touch(mod_id)
        self._refresh_conflicts()
        self._persist_later()
        self.modChanged.emit(mod_id)
        self._bus.toastKey("toast.mods.enabled" if enabled else "toast.mods.disabled", {"name": mod.name}, "success" if enabled else "info")

    @Slot(str, result="QVariant")
    def modDetails(self, mod_id: str):
        mod = self._model.mod_by_id(mod_id)
        return self._full_mod(mod) if mod else {}

    @Slot(str)
    def uninstallMod(self, mod_id: str) -> None:
        if is_game_running():
            self._bus.toastKey("toast.mods.runningCannotUninstall", {}, "warning")
            return
        mod = self._model.mod_by_id(mod_id)
        if mod is None:
            return
        entry = self._library_entry(mod_id)
        if entry is not None:
            # twardy bezpiecznik jak w starym projekcie: zawartość Biblioteki
            # jest czytana przez grę (symlinki folderów Mods) - usuwanie
            # podczas gry jest blokowane, aktywacja/import dozwolone
            if library_ops.is_game_modifying_library_content():
                self._bus.toastKey("toast.mods.runningCannotRemove", {}, "warning")
                return
            self._bus.toastKey("toast.mods.removing", {"title": entry.title}, "info")

            def worker(entry=entry):
                try:
                    _removed, errors = library_ops.remove_mods_from_library([entry])
                    self.libraryRemoved.emit(mod_id, "; ".join(errors))
                except Exception as exc:  # noqa: BLE001 - sieci/IO: pokaż w UI
                    logger.exception("Library removal failed")
                    self.libraryRemoved.emit(mod_id, str(exc))

            threading.Thread(target=worker, daemon=True).start()
            return
        # tryb demo (mock entry) - zachowanie jak dotychczas
        self._model.remove_mod(mod_id)
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        self.modRemoved.emit(mod_id)
        self._bus.toastKey("toast.mods.uninstalled", {"name": mod.name}, "info")

    @Slot(str)
    def openFolder(self, mod_id: str) -> None:
        # mod z Biblioteki: otwieramy jego własny katalog
        entry = self._library_entry(mod_id) if mod_id else None
        if entry is not None and entry.path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(entry.path)))
            self._bus.toastKey("toast.mods.openFolder", {"title": entry.title}, "info")
            return
        mods_dir = self._settings.modsDirectory
        target = None
        if mods_dir and fs.path_exists(mods_dir):
            target = mods_dir
        else:
            target = str(fs.ensure_dir(fs.user_mods_dir()))
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))
        self._bus.toastKey("toast.mods.openModsFolder", {}, "info")

    @Slot(str)
    def applyUpdate(self, mod_id: str) -> None:
        mod = self._model.mod_by_id(mod_id)
        if mod is None:
            return
        if self._model.apply_update(mod_id):
            self._refresh_conflicts()
            self._persist_later()
            self._notify_counts()
            self.modChanged.emit(mod_id)
            self._bus.toastKey("toast.mods.updated", {"name": mod.name, "version": mod.version}, "success")

    @Slot("QVariantMap")
    def applyProfileStates(self, states) -> None:
        states = dict(states or {})
        for mod in self._model.mods:
            new_value = bool(states.get(mod.id, False))
            if mod.enabled != new_value:
                mod.enabled = new_value
                self._model.touch(mod.id)
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()

    @Slot(result="QVariantMap")
    def currentStates(self):
        return {m.id: m.enabled for m in self._model.mods}

    @Slot()
    def rescanGameMods(self) -> None:
        """Odświeża Bibliotekę z dysku: wciąga foldery dodane ręcznie
        (osierocone - bez wpisu w rejestrze), przeładowuje rejestr i stan
        aktywacji, odbudowuje listę modów."""
        orphans = library_ops.find_orphaned_library_folders()
        imported = 0
        if orphans:
            report = library_ops.register_orphaned_folders(orphans, source="orphan", enable=False)
            imported = len(report.imported)
        self._reload_library()
        self._model.set_mods(self._build_mods_from_library())
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        if self._library_entries:
            self._scan_library_async()
        if imported:
            self._bus.toastKey("toast.mods.libraryRefreshedWithImports", {"count": len(self._library_entries), "imported": imported}, "success")
        elif self._library_entries:
            self._bus.toastKey("toast.mods.libraryRefreshed", {"count": len(self._library_entries)}, "success")
        else:
            self._bus.toastKey("toast.mods.libraryEmpty", {}, "warning")

    def _expand_import_paths(self, paths) -> list[Path]:
        """Rozwija wskazane katalogi do konkretnych modów z ModInfo.xml."""
        expanded: list[Path] = []
        seen: set[Path] = set()
        for raw in paths:
            value = str(raw or "").strip()
            if not value:
                continue
            try:
                candidates = library_ops.discover_mod_folders(value)
            except Exception:
                candidates = []
            for candidate in candidates:
                resolved = candidate.resolve(strict=False)
                if resolved not in seen:
                    seen.add(resolved)
                    expanded.append(resolved)
        return expanded

    def _on_folder_import_finished(self, found: int, imported: int,
                                   already: int, errors: int) -> None:
        if found <= 0:
            self._bus.toastKey("toast.mods.noModsInFolder", {}, "warning")
            return

        # Ten sam refresh co dla pozostałych importów, ale z jednym,
        # konkretnym komunikatem podsumowującym skanowanie.
        self._reload_library()
        self._model.set_mods(self._build_mods_from_library())
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        self._scan_library_async()

        self._bus.toastKey("toast.mods.importSummary", {
            "found": found, "imported": imported, "already": already, "errors": errors
        }, "success" if not errors else "warning")

    @Slot(str)
    def importFolder(self, path: str) -> None:
        """Skanuje wskazany katalog, znajduje mody i importuje je wsadowo."""
        root = str(path or "").strip()
        if not root:
            return
        self._bus.toastKey("toast.mods.scanStarted", {}, "info")

        def worker() -> None:
            try:
                folders = library_ops.discover_mod_folders(root)
                if not folders:
                    self.folderImportFinished.emit(0, 0, 0, 0)
                    return
                report = library_ops.import_mods_to_library(
                    folders, source="import", enable=False)
                self.folderImportFinished.emit(
                    len(folders), len(report.imported),
                    len(report.already_present), len(report.errors))
            except Exception as exc:  # noqa: BLE001 - komunikat trafia do UI
                logger.exception("Folder import failed")
                self.folderImportFinished.emit(0, 0, 0, 1)
                self._bus.toastKey("toast.mods.importScanFailed", {"error": str(exc)}, "error")

        threading.Thread(target=worker, daemon=True).start()

    @Slot("QVariantList")
    def importFolders(self, paths) -> None:
        """Import folderów modów do Biblioteki (drag&drop / wybór folderu).
        Deduplikacja po zawartości po stronie library_ops (identyczna
        zawartość nie jest kopiowana drugi raz); jeden zły folder nie
        zatrzymuje paczki - błędy trafiają do toastów po zakończeniu."""
        raw_folders = [str(p) for p in (paths or []) if str(p).strip()]
        if not raw_folders:
            return
        folders = self._expand_import_paths(raw_folders)
        if not folders:
            self._bus.toastKey("toast.mods.noModInfoSelected", {}, "warning")
            return
        self._bus.toastKey("toast.mods.importing", {"count": len(folders)}, "info")

        def worker():
            report = library_ops.import_mods_to_library(folders, source="import", enable=False)
            self.libraryImported.emit(
                len(report.imported), len(report.already_present), len(report.errors))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_finished(self, mods: list) -> None:
        if not mods:
            self._bus.toastKey("toast.mods.noModsConfigured", {}, "warning")
            return
        self._model.set_mods(list(mods))
        self._refresh_conflicts()
        self._persist_later()
        self._notify_counts()
        self._bus.toastKey("toast.mods.found", {"count": len(mods)}, "success")

    @Slot()
    def restoreDemo(self) -> None:
        self._loader.reset_state()
        self._model.set_mods(self._loader.build_mods())
        self._refresh_conflicts(initial=True)
        self._persist_later()
        self._notify_counts()
        self.demoReset.emit()
        self._bus.toastKey("toast.mods.demoRestored", {}, "success")

    # ------------------------------------------------------------------ #
    # used by ProfileManager / DownloadManager
    # ------------------------------------------------------------------ #
    def all_mods(self) -> list[Mod]:
        return list(self._model.mods)

    def mod_name(self, mod_id: str) -> str:
        mod = self._model.mod_by_id(mod_id)
        return mod.name if mod else mod_id

    def has_mod(self, mod_id: str) -> bool:
        return self._model.mod_by_id(mod_id) is not None

    def mod_has_update(self, mod_id: str) -> bool:
        mod = self._model.mod_by_id(mod_id)
        return bool(mod and mod.new_version)

