"""A small native filesystem browser model used by the QML folder picker.

The system FolderDialog is intentionally avoided for importing mods: on some
Linux desktops its start location and sidebar do not expose all mounted
volumes consistently.  This browser gives the application its own predictable
view with mounted drives, hidden-file visibility, direct path entry and smooth
QML scrolling.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, Property, QObject, Qt, Signal, Slot, QCoreApplication, QTimer
from PySide6.QtCore import QStorageInfo

logger = logging.getLogger(__name__)


class FileEntryModel(QAbstractListModel):
    NameRole = Qt.ItemDataRole.UserRole + 1
    PathRole = NameRole + 1
    IsDirectoryRole = NameRole + 2
    IsHiddenRole = NameRole + 3
    SizeTextRole = NameRole + 4
    TypeLabelRole = NameRole + 5

    ROLES = {
        NameRole: b"entryName",
        PathRole: b"entryPath",
        IsDirectoryRole: b"isDirectory",
        IsHiddenRole: b"isHidden",
        SizeTextRole: b"sizeText",
        TypeLabelRole: b"typeLabel",
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        item = self._entries[index.row()]
        return {
            self.NameRole: item["name"],
            self.PathRole: item["path"],
            self.IsDirectoryRole: item["is_directory"],
            self.IsHiddenRole: item["hidden"],
            self.SizeTextRole: item["size_text"],
            self.TypeLabelRole: item["type_label"],
        }.get(role)

    def replace(self, entries: list[dict]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()



def _qt_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="ignore")
    try:
        return bytes(value).decode(errors="ignore")
    except Exception:
        return str(value)


def _i18n_message(key: str, values: dict | None = None) -> str:
    payload = json.dumps(values or {}, ensure_ascii=False, separators=(",", ":"))
    return f"__I18N__:{key}|{payload}"


def _human_size(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(max(0, value))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "0 B"


def _safe_name(path: Path) -> str:
    try:
        return path.name or str(path)
    except OSError:
        return str(path)


class FileBrowser(QObject):
    currentPathChanged = Signal()
    showHiddenChanged = Signal()
    errorChanged = Signal()
    drivesChanged = Signal()
    readyChanged = Signal()
    _scanReady = Signal(object, object, object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._home = Path.home().resolve(strict=False)
        self._current = self._home
        self._show_hidden = False
        self._error = ""
        self._ready = False
        self._initial_refresh_pending = False
        self._scan_in_progress = False
        self._scan_generation = 0
        self._scanReady.connect(self._apply_scan_result)
        self._entries_model = FileEntryModel(self)
        self._drives: list[dict] = []

        # FileBrowser is intentionally lazy. It must not touch mounted
        # volumes or enumerate the user's home directory during application
        # startup at all. A broken FUSE/network/USB mount can block Qt for an
        # unbounded amount of time. The folder picker calls ensureInitialized()
        # when it is actually opened, and that scan runs in a worker thread.

    @Property(str, constant=True)
    def homePath(self) -> str:
        return str(self._home)

    @Property(str, notify=currentPathChanged)
    def currentPath(self) -> str:
        return str(self._current)

    @Property(bool, notify=showHiddenChanged)
    def showHidden(self) -> bool:
        return self._show_hidden

    @Property(bool, notify=readyChanged)
    def ready(self) -> bool:
        return self._ready

    @showHidden.setter
    def showHidden(self, value: bool) -> None:
        value = bool(value)
        if value == self._show_hidden:
            return
        self._show_hidden = value
        if self._ready:
            self._refresh_entries()
        self.showHiddenChanged.emit()

    @Property(str, notify=errorChanged)
    def error(self) -> str:
        return self._error

    @Property(QObject, constant=True)
    def entriesModel(self) -> QObject:
        return self._entries_model

    @Property(list, notify=drivesChanged)
    def drives(self) -> list[dict]:
        return list(self._drives)

    @Property(bool, notify=currentPathChanged)
    def canGoUp(self) -> bool:
        return self._current.parent != self._current

    def _set_error(self, message: str) -> None:
        if message == self._error:
            return
        self._error = message
        self.errorChanged.emit()

    def _collect_drives(self) -> list[dict]:
        drives: list[dict] = []
        seen: set[str] = set()
        excluded_prefixes = ("/proc", "/sys", "/dev", "/run", "/snap")

        try:
            volumes = QStorageInfo.mountedVolumes()
        except Exception:
            volumes = []

        for volume in volumes:
            try:
                if not volume.isValid() or not volume.isReady():
                    continue
                root = Path(volume.rootPath()).resolve(strict=False)
                path = str(root)
                if path in seen:
                    continue
                if any(path == p or path.startswith(p + os.sep) for p in excluded_prefixes):
                    continue
                device = _qt_text(volume.device())
                if not device and path != "/":
                    continue
                seen.add(path)
                display = _qt_text(volume.displayName())
                label = display.strip() or (device.rsplit("/", 1)[-1] if device else "")
                total = int(volume.bytesTotal())
                free = int(volume.bytesAvailable())
                drives.append({
                    "name": label,
                    "name_key": "",
                    "path": path,
                    "device": device,
                    "total": _human_size(total),
                    "free": _human_size(free),
                    "readOnly": bool(volume.isReadOnly()),
                })
            except Exception:  # noqa: BLE001
                logger.debug("Failed to read mounted volume", exc_info=True)

        if "/" not in seen:
            drives.insert(0, {
                "name": "",
                "name_key": "folderPicker.root",
                "path": "/",
                "device": "",
                "total": "",
                "free": "",
                "readOnly": False,
            })
        else:
            drives.sort(key=lambda item: (item["path"] != "/", item["name"].lower()))
        return drives

    def _refresh_drives(self) -> None:
        self._drives = self._collect_drives()
        self.drivesChanged.emit()

    def _collect_entries(self, current: Path, show_hidden: bool) -> tuple[list[dict], str]:
        entries: list[dict] = []
        try:
            with os.scandir(current) as iterator:
                for raw in iterator:
                    try:
                        name = raw.name
                        hidden = name.startswith(".")
                        if hidden and not show_hidden:
                            continue
                        is_dir = raw.is_dir(follow_symlinks=True)
                        if is_dir:
                            type_label = "folder"
                            size_text = ""
                        else:
                            type_label = "file"
                            try:
                                size_text = _human_size(raw.stat(follow_symlinks=True).st_size)
                            except OSError:
                                size_text = ""
                        entries.append({
                            "name": name,
                            "path": raw.path,
                            "is_directory": is_dir,
                            "hidden": hidden,
                            "size_text": size_text,
                            "type_label": type_label,
                        })
                    except OSError:
                        continue
        except OSError as exc:
            return [], _i18n_message("folderPicker.error.read", {"error": str(exc)})

        entries.sort(key=lambda item: (not item["is_directory"], item["name"].lower()))
        return entries, ""

    @Slot()
    def ensureInitialized(self) -> None:
        """Start the first filesystem scan on demand, never during app boot."""
        self._initial_refresh()

    @Slot()
    def _initial_refresh(self) -> None:
        if self._scan_in_progress or self._ready:
            return
        self._initial_refresh_pending = False
        self._scan_in_progress = True
        self._scan_generation += 1
        generation = self._scan_generation
        current = self._current
        show_hidden = self._show_hidden
        logger.info("FileBrowser: filesystem scan started in background")

        def worker() -> None:
            try:
                drives = self._collect_drives()
                entries, error = self._collect_entries(current, show_hidden)
                self._scanReady.emit(generation, drives, entries, error)
            except Exception as exc:  # noqa: BLE001
                logger.exception("FileBrowser background scan failed")
                self._scanReady.emit(generation, [], [], _i18n_message("folderPicker.error.scan", {"error": str(exc)}))

        threading.Thread(target=worker, daemon=True, name="FileBrowserScan").start()

    @Slot(object, object, object, str)
    def _apply_scan_result(self, generation, drives, entries, error: str) -> None:
        if generation != self._scan_generation:
            return
        self._scan_in_progress = False
        was_ready = self._ready
        self._ready = True
        self._drives = list(drives or [])
        self.drivesChanged.emit()
        if not was_ready:
            self.readyChanged.emit()
        self._entries_model.replace(list(entries or []))
        self._set_error(error or "")
        logger.info("FileBrowser: initial filesystem scan complete")

    def _refresh_entries(self) -> None:
        entries, error = self._collect_entries(self._current, self._show_hidden)
        self._entries_model.replace(entries)
        self._set_error(error)

    @Slot(str, result=bool)
    def navigate(self, path: str) -> bool:
        raw = str(path or "").strip()
        if not raw:
            return False
        try:
            candidate = Path(os.path.expanduser(raw)).resolve(strict=False)
        except OSError:
            self._set_error(_i18n_message("folderPicker.error.invalidPath"))
            return False
        if not candidate.is_dir():
            self._set_error(_i18n_message("folderPicker.error.notDirectory", {"path": str(candidate)}))
            return False
        if candidate == self._current:
            if not self._ready:
                self._initial_refresh()
            else:
                self._refresh_entries()
            return True
        self._current = candidate
        self.currentPathChanged.emit()
        if not self._ready:
            self._initial_refresh()
        else:
            self._refresh_entries()
        return True

    @Slot(result=bool)
    def goUp(self) -> bool:
        parent = self._current.parent
        if parent == self._current:
            return False
        return self.navigate(str(parent))

    @Slot(result=bool)
    def refresh(self) -> bool:
        if not self._ready:
            self._initial_refresh()
            return True
        self._refresh_drives()
        self._refresh_entries()
        return True
