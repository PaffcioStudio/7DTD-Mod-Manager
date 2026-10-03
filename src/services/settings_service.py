"""Application settings persisted to a JSON file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from services import filesystem_service as fs

DEFAULTS = {
    "language": "en",
    "startMinimized": False,
    "gameExecutable": "",
    "gameDirectory": "",
    "modsDirectory": "",
    "downloadDirectory": "",
    "maxConcurrentDownloads": 3,
    "autoCleanDownloads": "never",   # "never" | "24h" | "7d" (D9)
    "autoCheckUpdates": False,       # etap 11: sprawdzaj przy starcie (opt-in)
    "autoUpdateMods": False,         # etap 11: instaluj aktualizacje sam (opt-in)
    "windowWidth": 1400,             # etap 14: geometria okna (bez pozycji -
    "windowHeight": 880,             # przywracanie X/Y potrafi trafić poza ekran)
    "windowMaximized": False,
    "discoverDefaultCategory": "",   # domyślne filtry Odkrywaj
    "discoverDefaultVersion": "",
    "discoverDefaultProvider": "web",
    "discoverDefaultCreatedAfter": "",
    "discoverDefaultIncludeAdult": False,
    "accentColor": "#FF7A38",
    "themeMode": "dark",             # "dark" | "light" | "stalker" | "stalker-light"
    "uiScale": 1.0,
    "animationsEnabled": True,
    "heroRotationEnabled": True,  # okresowe losowanie tła Pulpitu
    "customWindowFrame": True,
    "browserShowHidden": False,      # przeglądarka folderów: pokazuj ukryte
    "loggingEnabled": False,
    "debugMode": False,
}


class SettingsService(QObject):
    """QObject exposed to QML as ``Settings``.

    Every setting is a Qt property so the QML side can bind (and write)
    directly.  Writes are persisted (debounced) to config/settings.json.
    """

    _generic_change = Signal()

    # forward declarations of per-property signals
    languageChanged = Signal()
    startMinimizedChanged = Signal()
    gameExecutableChanged = Signal()
    gameDirectoryChanged = Signal()
    modsDirectoryChanged = Signal()
    downloadDirectoryChanged = Signal()
    maxConcurrentDownloadsChanged = Signal()
    autoCleanDownloadsChanged = Signal()
    autoCheckUpdatesChanged = Signal()
    autoUpdateModsChanged = Signal()
    windowGeometryChanged = Signal()
    discoverDefaultsChanged = Signal()
    accentColorChanged = Signal()
    themeModeChanged = Signal()
    uiScaleChanged = Signal()
    animationsEnabledChanged = Signal()
    heroRotationEnabledChanged = Signal()
    customWindowFrameChanged = Signal()
    browserShowHiddenChanged = Signal()
    loggingEnabledChanged = Signal()
    debugModeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file: Path = fs.settings_path()
        self._values: dict = dict(DEFAULTS)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save)
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        stored = fs.read_json(self._file, None)
        if stored is None:
            # first run after the location change - pick up settings written
            # by earlier builds (XDG dir) and persist them at the new path
            stored = fs.read_json(fs.legacy_settings_path(), None)
            if stored is not None:
                self._save_timer.start()
        if not isinstance(stored, dict):
            stored = {}
        for key, value in stored.items():
            if key in DEFAULTS:
                self._values[key] = value
        # UI translations currently support English and Polish.
        # New installations start in English; an explicitly saved language is preserved.
        if self._values.get("language") not in ("pl", "en"):
            self._values["language"] = "en"
            self._save_timer.start()          # persist the fix right away
        # sane defaults for derived paths
        if self._values.get("autoCleanDownloads") not in ("never", "24h", "7d"):
            self._values["autoCleanDownloads"] = "never"
        # motyw: tylko znane wartości
        if self._values.get("themeMode") not in ("dark", "light", "stalker", "stalker-light"):
            self._values["themeMode"] = "dark"
        legacy_downloads = str(fs.home_dir() / ".local" / "share" / fs.LEGACY_UI_DIR_NAME / "downloads")
        # też stara ścieżka sprzed zmiany nazwy katalogu (D9)
        legacy_downloads_local = str(fs.data_dir() / "downloads")
        if not self._values.get("downloadDirectory") or \
                self._values["downloadDirectory"] in (legacy_downloads, legacy_downloads_local):
            self._values["downloadDirectory"] = str(fs.downloads_dir())
            self._save_timer.start()          # utrwal korektę od razu

        # moduł 10: leniwy import wartości ze STAREGO menedżera
        # (~/.7dtd_modmanager/settings.json, pola snake_case). Tylko pola
        # puste w nowym UI - nigdy nie nadpisujemy konfiguracji użytkownika.
        old = fs.read_json(fs.old_manager_settings_path(), None)
        if isinstance(old, dict):
            if not self._values.get("gameDirectory"):
                value = old.get("game_install_dir") or old.get("game_path") or ""
                if isinstance(value, str) and value.strip():
                    self._values["gameDirectory"] = str(
                        Path(value.strip()).expanduser().resolve(strict=False))
                    self._save_timer.start()
            if not self._values.get("modsDirectory"):
                game_data = old.get("game_data_dir") or ""
                if isinstance(game_data, str) and game_data.strip():
                    mods = Path(game_data.strip()).expanduser() / "Mods"
                    if mods.is_dir():   # tylko realnie istniejący folder Mods
                        self._values["modsDirectory"] = str(mods.resolve(strict=False))
                        self._save_timer.start()

    def _save(self) -> None:
        fs.write_json(self._file, self._values)

    def _get(self, key: str):
        return self._values.get(key, DEFAULTS.get(key))

    def _set(self, key: str, value, signal: Signal) -> None:
        if self._values.get(key) == value:
            return
        self._values[key] = value
        signal.emit()
        self._generic_change.emit()
        self._save_timer.start()

    # ------------------------------------------------------------------ #
    # properties
    # ------------------------------------------------------------------ #
    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._get("language")

    @language.setter
    def language(self, value: str) -> None:
        value = "en" if str(value) == "en" else "pl"
        self._set("language", value, self.languageChanged)

    @Property(bool, notify=startMinimizedChanged)
    def startMinimized(self) -> bool:
        return bool(self._get("startMinimized"))

    @startMinimized.setter
    def startMinimized(self, value: bool) -> None:
        self._set("startMinimized", value, self.startMinimizedChanged)

    @Property(str, notify=gameExecutableChanged)
    def gameExecutable(self) -> str:
        return self._get("gameExecutable")

    @gameExecutable.setter
    def gameExecutable(self, value: str) -> None:
        self._set("gameExecutable", value, self.gameExecutableChanged)

    @Property(str, notify=gameDirectoryChanged)
    def gameDirectory(self) -> str:
        return self._get("gameDirectory")

    @gameDirectory.setter
    def gameDirectory(self, value: str) -> None:
        self._set("gameDirectory", value, self.gameDirectoryChanged)

    @Property(str, notify=modsDirectoryChanged)
    def modsDirectory(self) -> str:
        return self._get("modsDirectory")

    @modsDirectory.setter
    def modsDirectory(self, value: str) -> None:
        self._set("modsDirectory", value, self.modsDirectoryChanged)

    @Property(str, notify=downloadDirectoryChanged)
    def downloadDirectory(self) -> str:
        return self._get("downloadDirectory")

    @downloadDirectory.setter
    def downloadDirectory(self, value: str) -> None:
        self._set("downloadDirectory", value, self.downloadDirectoryChanged)

    @Property(int, notify=maxConcurrentDownloadsChanged)
    def maxConcurrentDownloads(self) -> int:
        return int(self._get("maxConcurrentDownloads"))

    @maxConcurrentDownloads.setter
    def maxConcurrentDownloads(self, value: int) -> None:
        clamped = max(1, min(5, int(value)))
        self._set("maxConcurrentDownloads", clamped, self.maxConcurrentDownloadsChanged)

    @Property(bool, notify=autoCheckUpdatesChanged)
    def autoCheckUpdates(self) -> bool:
        return bool(self._get("autoCheckUpdates"))

    @autoCheckUpdates.setter
    def autoCheckUpdates(self, value: bool) -> None:
        self._set("autoCheckUpdates", bool(value), self.autoCheckUpdatesChanged)

    @Property(bool, notify=autoUpdateModsChanged)
    def autoUpdateMods(self) -> bool:
        return bool(self._get("autoUpdateMods"))

    @autoUpdateMods.setter
    def autoUpdateMods(self, value: bool) -> None:
        self._set("autoUpdateMods", bool(value), self.autoUpdateModsChanged)

    @Property(int, notify=windowGeometryChanged)
    def windowWidth(self) -> int:
        return int(self._get("windowWidth"))

    @windowWidth.setter
    def windowWidth(self, value: int) -> None:
        clamped = max(900, min(6000, int(value)))
        self._set("windowWidth", clamped, self.windowGeometryChanged)

    @Property(int, notify=windowGeometryChanged)
    def windowHeight(self) -> int:
        return int(self._get("windowHeight"))

    @windowHeight.setter
    def windowHeight(self, value: int) -> None:
        clamped = max(600, min(4000, int(value)))
        self._set("windowHeight", clamped, self.windowGeometryChanged)

    @Property(bool, notify=windowGeometryChanged)
    def windowMaximized(self) -> bool:
        return bool(self._get("windowMaximized"))

    @windowMaximized.setter
    def windowMaximized(self, value: bool) -> None:
        self._set("windowMaximized", bool(value), self.windowGeometryChanged)

    @Property(bool, notify=browserShowHiddenChanged)
    def browserShowHidden(self) -> bool:
        return bool(self._get("browserShowHidden"))

    @browserShowHidden.setter
    def browserShowHidden(self, value: bool) -> None:
        self._set("browserShowHidden", bool(value), self.browserShowHiddenChanged)

    @Property(str, notify=discoverDefaultsChanged)
    def discoverDefaultCategory(self) -> str:
        return str(self._get("discoverDefaultCategory"))

    @discoverDefaultCategory.setter
    def discoverDefaultCategory(self, value: str) -> None:
        self._set("discoverDefaultCategory", str(value or ""),
                  self.discoverDefaultsChanged)

    @Property(str, notify=discoverDefaultsChanged)
    def discoverDefaultVersion(self) -> str:
        return str(self._get("discoverDefaultVersion"))

    @discoverDefaultVersion.setter
    def discoverDefaultVersion(self, value: str) -> None:
        self._set("discoverDefaultVersion", str(value or ""),
                  self.discoverDefaultsChanged)

    @Property(str, notify=discoverDefaultsChanged)
    def discoverDefaultProvider(self) -> str:
        value = str(self._get("discoverDefaultProvider") or "web")
        return value if value in ("web", "local") else "web"

    @discoverDefaultProvider.setter
    def discoverDefaultProvider(self, value: str) -> None:
        value = "local" if value == "local" else "web"
        self._set("discoverDefaultProvider", value, self.discoverDefaultsChanged)

    @Property(str, notify=discoverDefaultsChanged)
    def discoverDefaultCreatedAfter(self) -> str:
        value = str(self._get("discoverDefaultCreatedAfter") or "")
        return value if value in ("", "7d", "30d", "365d") else ""

    @discoverDefaultCreatedAfter.setter
    def discoverDefaultCreatedAfter(self, value: str) -> None:
        value = str(value or "")
        if value not in ("", "7d", "30d", "365d"):
            value = ""
        self._set("discoverDefaultCreatedAfter", value, self.discoverDefaultsChanged)

    @Property(bool, notify=discoverDefaultsChanged)
    def discoverDefaultIncludeAdult(self) -> bool:
        return bool(self._get("discoverDefaultIncludeAdult"))

    @discoverDefaultIncludeAdult.setter
    def discoverDefaultIncludeAdult(self, value: bool) -> None:
        self._set("discoverDefaultIncludeAdult", bool(value), self.discoverDefaultsChanged)

    @Property(str, notify=autoCleanDownloadsChanged)
    def autoCleanDownloads(self) -> str:
        return self._get("autoCleanDownloads")

    @autoCleanDownloads.setter
    def autoCleanDownloads(self, value: str) -> None:
        if value in ("never", "24h", "7d"):
            self._set("autoCleanDownloads", value, self.autoCleanDownloadsChanged)

    @Property(str, notify=themeModeChanged)
    def themeMode(self) -> str:
        return str(self._get("themeMode"))

    @themeMode.setter
    def themeMode(self, value: str) -> None:
        if value not in ("dark", "light", "stalker", "stalker-light"):
            value = "dark"
        self._set("themeMode", value, self.themeModeChanged)

    @Property(str, notify=accentColorChanged)
    def accentColor(self) -> str:
        return self._get("accentColor")

    @accentColor.setter
    def accentColor(self, value: str) -> None:
        self._set("accentColor", value, self.accentColorChanged)

    @Property(float, notify=uiScaleChanged)
    def uiScale(self) -> float:
        return float(self._get("uiScale"))

    @uiScale.setter
    def uiScale(self, value: float) -> None:
        clamped = max(0.85, min(1.25, round(float(value), 2)))
        self._set("uiScale", clamped, self.uiScaleChanged)

    @Property(bool, notify=animationsEnabledChanged)
    def animationsEnabled(self) -> bool:
        return bool(self._get("animationsEnabled"))

    @animationsEnabled.setter
    def animationsEnabled(self, value: bool) -> None:
        self._set("animationsEnabled", value, self.animationsEnabledChanged)

    @Property(bool, notify=heroRotationEnabledChanged)
    def heroRotationEnabled(self) -> bool:
        return bool(self._get("heroRotationEnabled"))

    @heroRotationEnabled.setter
    def heroRotationEnabled(self, value: bool) -> None:
        self._set("heroRotationEnabled", bool(value), self.heroRotationEnabledChanged)

    @Property(bool, notify=customWindowFrameChanged)
    def customWindowFrame(self) -> bool:
        return bool(self._get("customWindowFrame"))

    @customWindowFrame.setter
    def customWindowFrame(self, value: bool) -> None:
        self._set("customWindowFrame", value, self.customWindowFrameChanged)

    @Property(bool, notify=loggingEnabledChanged)
    def loggingEnabled(self) -> bool:
        return bool(self._get("loggingEnabled"))

    @loggingEnabled.setter
    def loggingEnabled(self, value: bool) -> None:
        self._set("loggingEnabled", value, self.loggingEnabledChanged)

    @Property(bool, notify=debugModeChanged)
    def debugMode(self) -> bool:
        return bool(self._get("debugMode"))

    @debugMode.setter
    def debugMode(self, value: bool) -> None:
        self._set("debugMode", value, self.debugModeChanged)

    # ------------------------------------------------------------------ #
    @Property(str, constant=True)
    def configPath(self) -> str:
        return str(self._file)

    def raw_values(self) -> dict:
        return dict(self._values)

    def reset_to_defaults(self) -> None:
        self._values = dict(DEFAULTS)
        self._values["downloadDirectory"] = str(fs.downloads_dir())
        for signal in (self.languageChanged, self.startMinimizedChanged,
                       self.gameExecutableChanged, self.gameDirectoryChanged,
                       self.modsDirectoryChanged, self.downloadDirectoryChanged,
                       self.maxConcurrentDownloadsChanged, self.autoCleanDownloadsChanged,
                       self.autoCheckUpdatesChanged, self.autoUpdateModsChanged,
                       self.windowGeometryChanged,
                       self.discoverDefaultsChanged,
                       self.accentColorChanged, self.themeModeChanged,
                       self.uiScaleChanged, self.animationsEnabledChanged,
                       self.heroRotationEnabledChanged, self.customWindowFrameChanged,
                       self.loggingEnabledChanged,
                       self.debugModeChanged):
            signal.emit()
        self._save_timer.start()

    @Slot()
    def resetToDefaults(self) -> None:
        """camelCase alias for QML callers."""
        self.reset_to_defaults()
