#!/usr/bin/env python3
"""7 Days to Die - Mod Manager (PySide6 + QML).

Entry point: wires the Python backend together, exposes it to the QML
frontend as context properties and loads the QML UI.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

# make `src/` importable when launched as `python src/main.py`
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

PROJECT_ROOT = SRC_DIR.parent

# Skompilowany cache QML bywa nieaktualny po nałożeniu nowszej paczki (Qt ładuje
# stare .qmlc zamiast źródeł).  Aplikacja jest mała - start bez cache kosztuje
# ułamek sekundy, a eliminuje całą klasę błędów "działa stary kod".
# Włączenie z powrotem: MM_QML_CACHE=1 ./run.sh
if os.environ.get("MM_QML_CACHE") != "1":
    os.environ["QML_DISABLE_DISK_CACHE"] = "1"


def _early_interrupt(signum, frame):
    """Ctrl+C podczas startu (zanim wystartuje pętla Qt i właściwy
    handler w main()): czyste wyjście bez tracebacku z głębi importów."""
    sys.exit(130)


signal.signal(signal.SIGINT, _early_interrupt)

from PySide6.QtCore import Property, QObject, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQml import QQmlNetworkAccessManagerFactory
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from backend.conflict_detector import ConflictDetector  # noqa: E402
from backend.discover import DiscoverManager
from backend.web_mod_details import WebModDetails
from backend.download_manager import DownloadManager  # noqa: E402
from backend.events import EventBus  # noqa: E402
from backend.game_detector import GameDetector  # noqa: E402
from backend.mod_manager import ModManager
from backend.file_browser import FileBrowser
from backend.game_versions import GameVersionsManager
from backend.global_search import GlobalSearchManager
from backend.modpack_manager import ModpackManager  # noqa: E402
from backend.profile_manager import ProfileManager  # noqa: E402
from backend.game_profiles import GameProfileManager  # noqa: E402
from services import filesystem_service as fs  # noqa: E402
from services.app_info import AppInfo, APP_NAME, APP_VERSION, ORG_NAME  # noqa: E402
from services.icon_service import IconService  # noqa: E402
from services.settings_service import SettingsService  # noqa: E402

logger = logging.getLogger("modmanager")


class CachedNetworkFactory(QQmlNetworkAccessManagerFactory):
    def create(self, parent):
        manager = QNetworkAccessManager(parent)
        cache = QNetworkDiskCache(manager)
        cache.setCacheDirectory(str(fs.cache_dir() / "images"))
        cache.setMaximumCacheSize(100 * 1024 * 1024)
        manager.setCache(cache)
        return manager


# --------------------------------------------------------------------------- #
# boot helper (also used for automated screenshot testing)
# --------------------------------------------------------------------------- #
class BootOptions(QObject):
    """Exposed to QML as ``Boot`` - initial state overrides."""

    def __init__(self, args, parent=None) -> None:
        super().__init__(parent)
        self._page = args.page or ""
        self._drawer_mod = args.open_drawer or ""
        self._discover_provider = args.discover_provider or ""
        self._wait_ms = int(args.wait)
        self._width = int(args.width)
        self._height = int(args.height)
        self._toast_demo = bool(args.toast_demo)

    @Property(str, constant=True)
    def page(self) -> str:
        return self._page

    @Property(str, constant=True)
    def drawerMod(self) -> str:
        return self._drawer_mod

    @Property(str, constant=True)
    def discoverProvider(self) -> str:
        return self._discover_provider

    @Property(int, constant=True)
    def waitMs(self) -> int:
        return self._wait_ms

    @Property(int, constant=True)
    def width(self) -> int:
        return self._width

    @Property(int, constant=True)
    def height(self) -> int:
        return self._height

    @Property(bool, constant=True)
    def toastDemo(self) -> bool:
        return self._toast_demo


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--page", default="",
                        help="initial page (dashboard/mods/profiles/…)")
    parser.add_argument("--open-drawer", default="",
                        help="open the details drawer for a mod id")
    parser.add_argument("--discover-provider", default="",
                        help="initial Discover provider (web/local) for tests")
    parser.add_argument("--toast-demo", action="store_true",
                        help="show a couple of demo toasts after launch")
    parser.add_argument("--wait", type=int, default=1400,
                        help="ms to wait before screenshot")
    parser.add_argument("--screenshot", default="",
                        help="capture the window to this PNG and exit")
    parser.add_argument("--width", type=int, default=0, help="window width")
    parser.add_argument("--height", type=int, default=0, help="window height")
    return parser.parse_args(argv)


def setup_logging(settings: SettingsService) -> None:
    level = logging.DEBUG if settings.debugMode else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.loggingEnabled:
        fs.ensure_dir(fs.logs_dir())
        handlers.append(logging.FileHandler(fs.logs_dir() / "app.log",
                                            encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    app = QGuiApplication(sys.argv[:1])
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(PROJECT_ROOT / "assets" / "icons" / "app-icon.svg")))

    # Ctrl+C w terminalu: zamiast lawiny KeyboardInterrupt z callbackow
    # timerow - pierwsze Ctrl+C zamyka applikacje porzadnie
    def _on_interrupt(signum, frame) -> None:
        app.exit(130)

    signal.signal(signal.SIGINT, _on_interrupt)
    sys.excepthook = lambda et, ev, tb: (
        app.quit() if et is KeyboardInterrupt
        else (logger.critical("Unhandled exception", exc_info=(et, ev, tb)),
              sys.__excepthook__(et, ev, tb)))

    settings = SettingsService()
    setup_logging(settings)
    try:
        from services import tree_check
        tree_check.purge_compiled_cache(PROJECT_ROOT, logger)
        tree_check.report(PROJECT_ROOT, logger)
    except Exception:
        logger.exception("Startup file check: import error")

    # consistent custom styling regardless of the desktop environment
    QQuickStyle.setStyle("Basic")

    # ------------------------------------------------------------------ #
    # backend
    # ------------------------------------------------------------------ #
    try:
        def boot_step(name, factory):
            logger.info("BOOT: %s", name)
            value = factory()
            logger.info("BOOT: %s OK", name)
            return value

        bus = boot_step("EventBus", EventBus)
        icons = boot_step("IconService", lambda: IconService(PROJECT_ROOT / "assets" / "icons"))
        game = boot_step("GameDetector", lambda: GameDetector(settings, bus))
        conflicts = boot_step("ConflictDetector", ConflictDetector)
        mods = boot_step("ModManager", lambda: ModManager(settings, bus, conflicts, game))
        profiles = boot_step("ProfileManager", lambda: ProfileManager(mods, bus, game))
        game_profiles = boot_step("GameProfileManager", GameProfileManager)
        modpacks = boot_step("ModpackManager", lambda: ModpackManager(profiles, bus))
        downloads = boot_step("DownloadManager", lambda: DownloadManager(mods, bus, settings))
        discover = boot_step("DiscoverManager", DiscoverManager)
        web_details = boot_step("WebModDetails", WebModDetails)
        app_info = boot_step("AppInfo", lambda: AppInfo(bus))
        file_browser = boot_step("FileBrowser", FileBrowser)
        game_versions = boot_step("GameVersionsManager", GameVersionsManager)
        global_search = boot_step("GlobalSearchManager", lambda: GlobalSearchManager(mods, profiles))
    except Exception:
        logger.exception("Failed to initialize the application backend")
        return 1

    # widoczność ukrytych plików w przeglądarce folderów jest ustawieniem
    # trwałym: start = wartość z Settings, zmiana w UI = zapis do Settings
    file_browser.showHidden = settings.browserShowHidden
    file_browser.showHiddenChanged.connect(
        lambda: setattr(settings, "browserShowHidden", file_browser.showHidden))

    # cross-manager wiring
    downloads.updateFinished.connect(mods.applyUpdate)
    # etap 11: po sprawdzeniu aktualizacji auto-pobranie NOWYCH wersji tylko
    # gdy użytkownik włączył opt-in w Ustawieniach (domyslnie WYŁĄCZONE)
    def _on_update_check_finished(found, failed, downloads=downloads):
        downloads.enqueueAvailableUpdates()
    mods.updateCheckFinished.connect(_on_update_check_finished)
    # etap 18: po decyzji "utwórz instancję" (zestaw modów) - odśwież listę
    def _on_instances_refresh_needed(downloads=downloads, profiles=profiles, game_profiles=game_profiles):
        profiles.refreshFromDisk()
        game_profiles.refresh()
    downloads.instancesRefreshNeeded.connect(_on_instances_refresh_needed)
    profiles.instancesChanged.connect(game_profiles.refresh)
    profiles.instancesChanged.connect(downloads.refreshModDownloadStates)
    profiles.instanceCreated.connect(lambda _id: game_profiles.refresh())
    profiles.instanceCreated.connect(lambda _id: downloads.refreshModDownloadStates())
    profiles.instanceRemoved.connect(lambda _id: game_profiles.refresh())
    profiles.instanceRemoved.connect(lambda _id: downloads.refreshModDownloadStates())
    game.runningChanged.connect(game_profiles.refresh)
    downloads.modpackInstalled.connect(mods.reload_library_from_disk)

    # DepotDownloader jest właścicielem procesu pobierania wersji gry, ale
    # jego stan jest pokazywany w jednej wspólnej kolejce "Pobieranie".
    game_versions.gameDownloadStarted.connect(downloads.startGameVersionDownload)
    game_versions.gameDownloadProgress.connect(downloads.updateGameVersionDownload)
    game_versions.gameDownloadFinished.connect(downloads.finishGameVersionDownload)

    # first run: try to detect the game quietly
    if not settings.gameExecutable:
        QTimer.singleShot(600, game.detect)

    # ------------------------------------------------------------------ #
    # QML
    # ------------------------------------------------------------------ #
    engine = QQmlApplicationEngine()
    network_factory = CachedNetworkFactory()
    engine.setNetworkAccessManagerFactory(network_factory)
    engine.warnings.connect(
        lambda warnings: [logger.warning("QML: %s", w.toString()) for w in warnings])

    def _qml_object_created(obj, url):
        if obj is None:
            logger.critical("QML: failed to create object from %s", url.toString())

    engine.objectCreated.connect(_qml_object_created)

    context = engine.rootContext()
    boot = BootOptions(args)
    context.setContextProperty("Boot", boot)
    context.setContextProperty("Settings", settings)
    context.setContextProperty("Bus", bus)
    context.setContextProperty("Icons", icons)
    context.setContextProperty("App", app_info)
    context.setContextProperty("Mods", mods)
    context.setContextProperty("Profiles", profiles)
    context.setContextProperty("GameProfiles", game_profiles)
    context.setContextProperty("Modpacks", modpacks)
    context.setContextProperty("Downloads", downloads)
    context.setContextProperty("Discover", discover)
    context.setContextProperty("WebDetails", web_details)
    context.setContextProperty("Conflicts", conflicts)
    context.setContextProperty("Game", game)
    context.setContextProperty("FileBrowser", file_browser)
    context.setContextProperty("GameVersions", game_versions)
    context.setContextProperty("GlobalSearch", global_search)

    qml_file = PROJECT_ROOT / "qml" / "Main.qml"
    logger.info("Loading QML interface: %s", qml_file)
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    logger.info("QML root objects after load: %d", len(engine.rootObjects()))

    if not engine.rootObjects():
        logger.critical("Failed to load QML entry point: %s", qml_file)
        return 1

    window = engine.rootObjects()[0]

    # ------------------------------------------------------------------ #
    # automated screenshot (dev/testing aid)
    # ------------------------------------------------------------------ #
    if args.screenshot:
        out_path = Path(args.screenshot).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def capture(downloads=downloads, game_versions=game_versions, window=window) -> None:
            game_versions.shutdown()
            downloads.shutdown()
            image = window.grabWindow()
            ok = image.save(str(out_path))
            logger.info("Screenshot %s -> %s", "saved" if ok else "FAILED", out_path)
            app.exit(0 if ok else 2)

        QTimer.singleShot(max(200, args.wait), capture)

    code = app.exec()
    # GameVersionsManager owns real DepotDownloader child processes and a worker
    # thread. It must be shut down explicitly, otherwise app.quit()/Ctrl+C can
    # leave DepotDownloader alive in the background and locking game files.
    game_versions.shutdown()
    global_search.shutdown()
    discover.shutdown()
    downloads.shutdown()

    # clean teardown: destroy the QML engine BEFORE the Python services so
    # bindings never evaluate against already-deleted context objects
    del window
    del engine
    del mods, profiles, game_profiles, modpacks, downloads, discover, web_details, conflicts, game, icons, app_info, file_browser, game_versions, global_search, bus
    del boot, settings
    return code


if __name__ == "__main__":
    def _excepthook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook
    sys.exit(main())
