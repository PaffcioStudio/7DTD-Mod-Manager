"""App-level info + small desktop actions exposed to QML as ``App``."""

from __future__ import annotations

import platform
from urllib.parse import quote_plus

from PySide6.QtCore import Property, QObject, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from services import filesystem_service as fs

APP_NAME = "7 Days to Die - Menedżer modów"
APP_VERSION = "1.0.42"
ORG_NAME = "7dtd-modmanager"


class AppInfo(QObject):
    def __init__(self, bus, parent=None) -> None:
        super().__init__(parent)
        self._bus = bus

    @Property(str, constant=True)
    def name(self) -> str:
        return APP_NAME

    @Property(str, constant=True)
    def version(self) -> str:
        return APP_VERSION

    @Property(str, constant=True)
    def qtVersion(self) -> str:
        from PySide6.QtCore import qVersion
        return qVersion()

    @Property(str, constant=True)
    def pythonVersion(self) -> str:
        return platform.python_version()

    @Property(str, constant=True)
    def configDir(self) -> str:
        # single shared root since stage 1 of the migration - config and
        # data live together in ~/.7dtd_modmanager (app-owned files have plain names)
        return str(fs.data_dir())

    @Property(str, constant=True)
    def dataDir(self) -> str:
        return str(fs.data_dir())

    @Property(str, constant=True)
    def logsDir(self) -> str:
        return str(fs.logs_dir())

    # ------------------------------------------------------------------ #
    @Slot(str)
    def openPath(self, path: str) -> None:
        if not path:
            return
        target = path if path.startswith("/") else self._resolve_known(path)
        if not fs.path_exists(target):
            if target in (self.logsDir, self.configDir, self.dataDir):
                fs.ensure_dir(__import__("pathlib").Path(target))
            else:
                self._bus.toastKey("toast.app.pathNotFound", {"path": target}, "error")
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    @Slot(str)
    def openUrl(self, url: str) -> None:
        """Open a trusted external URL in the desktop browser."""
        url = (url or "").strip()
        if not url:
            return
        qurl = QUrl(url)
        if not qurl.isValid() or qurl.scheme() not in {"http", "https"}:
            self._bus.toastKey("toast.app.invalidUrl", {}, "error")
            return
        QDesktopServices.openUrl(qurl)

    @Slot(str)
    def searchModOnline(self, mod_name: str) -> None:
        """Open the 7daystodiemods.com search page for a mod name."""
        name = " ".join((mod_name or "").split()).strip()
        if not name:
            self._bus.toastKey("toast.app.modNameMissing", {}, "warning")
            return
        query = quote_plus(name.lower())
        self.openUrl(f"https://7daystodiemods.com/discover?q={query}")

    def _resolve_known(self, key: str) -> str:
        mapping = {
            "config": str(fs.data_dir()),
            "data": str(fs.data_dir()),
            "logs": str(fs.logs_dir()),
        }
        return mapping.get(key, key)

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self._bus.toastKey("toast.app.clipboardCopied", {}, "info")

    @Slot()
    def quit(self) -> None:
        QGuiApplication.quit()

    @Slot()
    def openLogsFolder(self) -> None:
        self.openPath(str(fs.ensure_dir(fs.logs_dir())))

    @Slot()
    def openConfigFolder(self) -> None:
        self.openPath(str(fs.ensure_dir(fs.data_dir())))
