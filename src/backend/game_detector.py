"""Detect the installed 7 Days to Die game (Steam on Linux), watch whether
it is RUNNING right now (native client or Wine/Proton), and launch it."""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from backend import game_process
from backend.events import EventBus
from services import filesystem_service as fs
from services.settings_service import SettingsService
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)

GAME_FOLDER = "7 Days To Die"
CANDIDATE_EXECUTABLES = (
    "7DaysToDie.x86_64",
    "7DaysToDie",
    "7DaysToDie.exe",
    "7dLauncher.exe",
)

# how often the running-game scan refreshes (mirrors the legacy manager's
# auto-refresh default of 3000 ms; the /proc scan is cheap)
RUNNING_POLL_MS = 3000

STEAM_ROOTS = [
    Path.home() / ".steam" / "steam",
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "debian-installation",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" /
    "data" / "Steam",                                   # flatpak
]


def _parse_library_folders(vdf_path: Path) -> list[Path]:
    """Extract library paths from Steam's libraryfolders.vdf."""
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    roots = []
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        path = match.group(1).replace("\\\\", "/")
        if path:
            roots.append(Path(path))
    return roots


def _safe_child_dirs(path: Path) -> list[Path]:
    try:
        return [child for child in path.iterdir() if child.is_dir()]
    except OSError:
        return []


def _media_steam_libraries() -> list[Path]:
    """Steam libraries commonly created on extra mounted drives."""
    username = os.environ.get("USER") or Path.home().name
    media_root = Path("/media") / username
    libraries: list[Path] = []
    for mount in _safe_child_dirs(media_root):
        libraries.append(mount / "SteamLibrary")
    return libraries


def _steam_libraries() -> list[Path]:
    libraries: list[Path] = []
    for steam_root in STEAM_ROOTS:
        if not steam_root.is_dir():
            continue
        libraries.append(steam_root)
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            libraries.extend(_parse_library_folders(vdf))
    libraries.extend(_media_steam_libraries())

    unique: list[Path] = []
    seen: set[str] = set()
    for library in libraries:
        key = str(library.expanduser())
        if key not in seen:
            seen.add(key)
            unique.append(library)
    return unique


def _game_dirs_in_common(common_dir: Path) -> list[Path]:
    exact = common_dir / GAME_FOLDER
    if exact.is_dir():
        return [exact]

    game_key = GAME_FOLDER.casefold()
    return [
        child for child in _safe_child_dirs(common_dir)
        if child.name.casefold() == game_key
    ]


def _game_info(game_dir: Path, source: str) -> dict | None:
    for exe_name in CANDIDATE_EXECUTABLES:
        exe = game_dir / exe_name
        if exe.is_file():
            return {
                "executable": str(exe),
                "gameDir": str(game_dir),
                "modsDir": str(game_dir / "Mods"),
                "source": source,
                "label": f"{source} - {fs.display_path(str(game_dir))}",
            }
    return None


def find_games() -> list[dict]:
    """Search common Steam locations for every matching game executable."""
    libraries: list[Path] = []
    libraries.extend(_steam_libraries())

    seen: set[str] = set()
    games: list[dict] = []
    for library in libraries:
        common_dir = library / "steamapps" / "common"
        if not common_dir.is_dir():
            continue
        source = "Steam"
        if str(library).startswith(f"/media/{os.environ.get('USER') or Path.home().name}/"):
            source = "SteamLibrary"
        for game_dir in _game_dirs_in_common(common_dir):
            info = _game_info(game_dir, source)
            if not info:
                continue
            key = info["gameDir"]
            if key in seen:
                continue
            seen.add(key)
            games.append(info)
    return games


def find_game() -> dict | None:
    """Search common Steam locations for the first game executable."""
    games = find_games()
    return games[0] if games else None


class GameDetector(QObject):
    """Exposed to QML as ``Game``.

    Two layers:

    1. Installed-game detection (Steam library scan + manual paths in
       Settings) - ``detect``/``isDetected``/``statusText``.
    2. Running-game watch (migration stage 2): a /proc scan every
       RUNNING_POLL_MS, matching the native client AND Wine/Proton
       processes (see backend/game_process.py). Exposes ``isRunning`` and
       details of the primary (lowest-pid) process, including the raw
       ``-UserDataFolder=`` value - stage 6 (instances) will map it to the
       instance registry; until then ``runningUsesDefaultData`` says
       whether the game runs on the default data location.
    """

    statusChanged = Signal()
    runningChanged = Signal()
    detectionCandidatesChanged = Signal()
    versionGroupChanged = Signal()

    def __init__(self, settings: SettingsService, bus: EventBus,
                 parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._bus = bus
        self._detection: dict | None = None
        self._detection_candidates: list[dict] = []
        self._running: list[game_process.GameProcessInfo] = []
        self._build_id = ""
        self._version_group = ""
        settings.gameExecutableChanged.connect(self.statusChanged)
        settings.gameExecutableChanged.connect(self._schedule_version_refresh)
        # Initial filesystem/network refresh runs after the event loop starts
        # so backend construction can never block the first window.
        QTimer.singleShot(0, self._schedule_version_refresh)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(RUNNING_POLL_MS)
        self._poll_timer.timeout.connect(self.refreshRunning)
        self._poll_timer.start()
        QTimer.singleShot(0, self.refreshRunning)

    # ------------------------------------------------------------------ #
    # wersja gry: buildid z appmanifest_251570.acf -> branch (steamcmd API,
    # plikowy cache 24 h) -> grupa "v1"/"v2"/"v3"/"alpha"
    # ------------------------------------------------------------------ #
    def _schedule_version_refresh(self) -> None:
        threading.Thread(target=self._refresh_version_worker,
                         daemon=True).start()

    def _refresh_version_worker(self) -> None:
        from backend import game_versions
        exe = self._settings.gameExecutable or ""
        build_id = ""
        if exe:
            try:
                # .../steamapps/common/<dir>/7DaysToDie.exe -> steamapps/
                appmanifest = Path(exe).parents[2] / "appmanifest_251570.acf"
                text = appmanifest.read_text(encoding="utf-8",
                                             errors="replace")
                match = re.search(r'"buildid"\s+"(\d+)"', text)
                if match:
                    build_id = match.group(1)
            except OSError:
                pass
        group = ""
        if build_id:
            try:
                branch = game_versions.branches_cached().get(build_id, "")
                group = game_versions.version_group(branch)
            except Exception as exc:  # noqa: BLE001 - brak sieci = bez grupy
                logger.info("Version group lookup skipped: %s", exc)
        if build_id != self._build_id or group != self._version_group:
            self._build_id = build_id
            self._version_group = group
            self.versionGroupChanged.emit()

    @Property(str, notify=versionGroupChanged)
    def buildId(self) -> str:
        return self._build_id

    @Property(str, notify=versionGroupChanged)
    def versionGroup(self) -> str:
        return self._version_group

    # ------------------------------------------------------------------ #
    def _exe_valid(self) -> bool:
        return fs.path_exists(self._settings.gameExecutable)

    @Property(bool, notify=statusChanged)
    def isDetected(self) -> bool:
        return self._exe_valid()

    @Property(str, notify=statusChanged)
    def statusKey(self) -> str:
        if self._exe_valid():
            return "settings.game.status.detected"
        if self._detection_candidates:
            return "settings.game.status.multiple"
        if self._detection:
            return "settings.game.status.foundNotApplied"
        return "settings.game.status.notDetected"

    @Property("QVariantMap", notify=statusChanged)
    def statusValues(self) -> dict:
        return {}

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        if self._exe_valid():
            return i18n_message("settings.game.status.detected")
        if self._detection_candidates:
            return i18n_message("settings.game.status.multiple")
        if self._detection:
            return i18n_message("settings.game.status.foundNotApplied")
        return i18n_message("settings.game.status.notDetected")

    @Property(str, notify=statusChanged)
    def executablePath(self) -> str:
        return self._settings.gameExecutable

    @Property(str, notify=statusChanged)
    def gameDir(self) -> str:
        return self._settings.gameDirectory

    @Property(str, notify=statusChanged)
    def modsDir(self) -> str:
        return self._settings.modsDirectory

    @Property("QVariantList", notify=detectionCandidatesChanged)
    def detectionCandidates(self) -> list:
        return list(self._detection_candidates)

    # ------------------------------------------------------------------ #
    # running-game watch (stage 2) - refreshed by an internal timer       #
    # ------------------------------------------------------------------ #
    def _primary_running(self) -> game_process.GameProcessInfo | None:
        return self._running[0] if self._running else None

    @Property(bool, notify=runningChanged)
    def isRunning(self) -> bool:
        return bool(self._running)

    @Property(int, notify=runningChanged)
    def runningProcessCount(self) -> int:
        return len(self._running)

    @Property(int, notify=runningChanged)
    def runningPid(self) -> int:
        primary = self._primary_running()
        return primary.pid if primary else 0

    @Property(str, notify=runningChanged)
    def runningMatchedBy(self) -> str:
        primary = self._primary_running()
        return primary.matched_by if primary else ""

    @Property(float, notify=runningChanged)
    def runningCpuPercent(self) -> float:
        primary = self._primary_running()
        return round(primary.cpu_percent, 1) if primary else 0.0

    @Property(float, notify=runningChanged)
    def runningRamMb(self) -> float:
        primary = self._primary_running()
        return round(primary.ram_mb, 1) if primary else 0.0

    @Property(str, notify=runningChanged)
    def runningElapsed(self) -> str:
        primary = self._primary_running()
        return primary.elapsed_str if primary else ""

    @Property(str, notify=runningChanged)
    def runningUserDataFolder(self) -> str:
        """RAW -UserDataFolder= value (Wine convention) of the primary
        process, or "" when the game uses the default data location."""
        primary = self._primary_running()
        return primary.user_data_folder or "" if primary else ""

    @Property("QVariantList", notify=runningChanged)
    def runningUserDataList(self) -> list:
        """Raw -UserDataFolder= values of ALL matched processes ("" for
        processes without the flag) - consumed by the instances layer
        (stage 6) to tell WHICH instance is running."""
        return [p.user_data_folder or "" for p in self._running]

    @Property(bool, notify=runningChanged)
    def runningUsesDefaultData(self) -> bool:
        """True when the game is running WITHOUT -UserDataFolder=, i.e. on
        the default data location (the "default instance")."""
        primary = self._primary_running()
        return primary is not None and not primary.user_data_folder

    @Slot()
    def stopRunningGame(self) -> None:
        """Zatrzymuje (ubija) wykryte procesy gry - na życzenie użytkownika
        po potwierdzeniu w UI."""
        killed = game_process.kill_game_processes()
        self.refreshRunning()
        if killed:
            self._bus.toastKey("toast.game.processesStopped", {"count": killed}, "success")
        else:
            self._bus.toastKey("toast.game.noProcesses", {}, "info")

    def refreshRunning(self) -> None:
        """Re-scan /proc for the game and re-emit runningChanged.

        Emitted on EVERY tick (not only on state flips): cpu/elapsed are
        live dashboard metrics and re-reading a handful of properties
        every 3 s is cheap."""
        try:
            self._running = game_process.find_game_processes()
        except Exception:  # never let a /proc hiccup kill the timer
            logger.exception("Running-game scan failed")
            self._running = []
        self.runningChanged.emit()

    @Slot(result="QVariantMap")
    def runningInfo(self) -> dict:
        """Full snapshot of the primary running process (QML convenience)."""
        primary = self._primary_running()
        if primary is None:
            return {}
        return {
            "pid": primary.pid,
            "matchedBy": primary.matched_by,
            "cpuPercent": round(primary.cpu_percent, 1),
            "ramMb": round(primary.ram_mb, 1),
            "elapsed": primary.elapsed_str,
            "userDataFolder": primary.user_data_folder or "",
            "usesDefaultData": primary.user_data_folder is None,
            "processCount": len(self._running),
        }

    # ------------------------------------------------------------------ #
    def _set_detection_candidates(self, candidates: list[dict]) -> None:
        self._detection_candidates = list(candidates)
        self.detectionCandidatesChanged.emit()

    def _apply_detection(self, info: dict) -> None:
        self._detection = info
        self._settings.gameExecutable = info["executable"]
        self._settings.gameDirectory = info["gameDir"]
        self._settings.modsDirectory = info["modsDir"]
        self.statusChanged.emit()

    @Slot(result="QVariantMap")
    def detect(self):
        """Detect the game; apply paths into settings when found."""
        candidates = find_games()
        self._set_detection_candidates(candidates)
        if len(candidates) == 1:
            info = candidates[0]
            self._apply_detection(info)
            self._bus.toastKey("toast.game.detected", {"source": info["source"], "path": fs.display_path(info["gameDir"])}, "success")
            result = dict(info)
            result["candidateCount"] = 1
            return result
        if len(candidates) > 1:
            self._detection = None
            self.statusChanged.emit()
            self._bus.toastKey("toast.game.multiple", {"count": len(candidates)}, "info")
            return {
                "candidateCount": len(candidates),
                "multiple": True,
            }
        self._detection = None
        self.statusChanged.emit()
        self._bus.toastKey("toast.game.notFound", {}, "warning")
        return {"candidateCount": 0}

    @Slot(str, result=bool)
    def applyDetectedGame(self, game_dir: str) -> bool:
        for info in self._detection_candidates:
            if info.get("gameDir") != game_dir:
                continue
            self._apply_detection(info)
            self._bus.toastKey("toast.game.applied", {"path": fs.display_path(info["gameDir"])}, "success")
            return True
        self._bus.toastKey("toast.game.applyFailed", {}, "error")
        return False

    @Slot(result=bool)
    def launch(self) -> bool:
        exe = self._settings.gameExecutable
        if not fs.path_exists(exe):
            self._bus.toastKey("toast.game.exeMissing", {}, "error")
            return False
        work_dir = self._settings.gameDirectory or str(Path(exe).parent)
        started = QProcess.startDetached(exe, [], work_dir)
        if started:
            self._bus.toastKey("toast.game.launching", {}, "info")
        else:
            self._bus.toastKey("toast.game.launchFailed", {}, "error")
        return started

    @Slot(str, result=bool)
    def validateExecutable(self, path: str) -> bool:
        return fs.path_exists(path)
