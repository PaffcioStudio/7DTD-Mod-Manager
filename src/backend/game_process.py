"""Detection of the running 7 Days to Die game process (Linux).

Ported from the legacy PyQt6 manager's game_process.py (migration stage 2)
with ONE deliberate change: the unified scan reads /proc directly instead
of using psutil - this project deliberately has no dependency beyond
PySide6, and everything psutil provided here (name, exe, cmdline,
create_time, cpu, rss) is available from /proc. Matching criteria are
ported 1:1 from the legacy module (originally from Proton Manager).

Two ways the game can run:

1. Native Linux client - /proc/<pid>/comm is the game binary name.
2. Wine/Proton - comm is "wine"/"wine64"/"wineserver" instead, so matching
   by comm never fires; instead we match the game's install dir as a FULL
   path segment of the executable (or of any cmdline argument), or an
   argument whose basename is exactly the game executable name. Full
   segment/basename matching, never substring-of-cmdline: a substring match
   would produce false "game is running" hits (e.g. an editor opened from
   the game folder).

From every matched process we also extract the ``-UserDataFolder=`` launch
flag value - stage 6 (instances) uses it to tell WHICH instance is running.
The raw value stays in Wine convention (``Z:`` prefix); unix<->wine path
conversion belongs to the instances layer, not here.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend import bepinex_loader
from backend.wine_paths import to_wine_path

logger = logging.getLogger(__name__)

# 7DaysToDie.x86_64 is the native client; the .exe variants appear under
# Wine/Proton (and EAC's launcher when AntiCheat is active).
GAME_PROCESS_NAMES = ("7DaysToDie.x86_64", "7DaysToDie.x86", "7DaysToDie_EAC.exe", "7DaysToDie.exe")
# Natywne pliki wykonywalne Linuksa: /proc/PID/comm jest ucinane do 15 znaków
# ("7DaysToDie.x86_64" -> "7DaysToDie.x86_"), więc natywny klient rozpoznajemy
# dodatkowo po basename symlinku /proc/PID/exe (bez ucinania). Wine/Proton
# ma w exe "wine64-preloader", więc .exe celowo tu NIE należy.
NATIVE_EXE_NAMES = ("7DaysToDie.x86_64", "7DaysToDie.x86")

STEAM_APP_ID = "251570"  # 7 Days to Die - SteamDB/sklep Steam

# Install folder name under Wine/Proton - matches install.dir from
# appmanifest_251570.acf. Used only for the full-segment match below.
WINE_INSTALL_DIR_NAME = "7 Days To Die"

# Launch flag redirecting the whole user data dir (Saves/Mods/EOS cache) -
# the base mechanism for per-instance data isolation (see stage 6).
USER_DATA_FOLDER_FLAG = "-UserDataFolder"

_PROC = Path("/proc")
_OWN_PID = os.getpid()
_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096

# previous (wall_time, cpu_ticks) per pid, for psutil-style cpu_percent
_PREV_CPU: dict[int, tuple[float, float]] = {}


@dataclass
class GameProcessInfo:
    """Snapshot of ONE detected game process (native or Wine/Proton).

    user_data_folder is the raw flag value (outer quotes stripped, but no
    case/separator normalization - the instances layer owns both path
    conventions). None = the process has no such flag, i.e. the game uses
    the default data location (the "default instance").
    """

    pid: int
    cpu_percent: float
    ram_mb: float
    running_since: float  # epoch seconds
    matched_by: str = "wine"  # "native" (comm = game binary name) | "wine"
    user_data_folder: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.time() - self.running_since)

    @property
    def elapsed_str(self) -> str:
        total = int(self.elapsed_seconds)
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _read_proc_comm(pid: str) -> str:
    try:
        return (_PROC / pid / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def _read_proc_cmdline_parts(pid: str) -> list[str]:
    """cmdline as a list of arguments (NUL-separated in /proc)."""
    try:
        raw = (_PROC / pid / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="ignore") for part in raw.split(b"\0") if part]


def _read_proc_exe(pid: str) -> str:
    try:
        target = os.readlink(_PROC / pid / "exe")
    except OSError:
        return ""
    return target.removesuffix(" (deleted)")


def _boot_time() -> float:
    """System boot time (epoch seconds) from /proc/stat - cached."""
    global _BOOT_TIME
    if _BOOT_TIME is None:
        try:
            for line in (_PROC / "stat").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("btime "):
                    _BOOT_TIME = float(line.split()[1])
                    break
        except OSError:
            pass
        if _BOOT_TIME is None:
            _BOOT_TIME = 0.0
    return _BOOT_TIME


_BOOT_TIME: float | None = None


def _proc_stat_fields(pid: str) -> list[str] | None:
    """Numeric fields of /proc/<pid>/stat AFTER 'pid (comm)'.

    Splitting at the LAST ')' is required - comm can contain spaces and
    parentheses. Field layout after that split (0-based):
    0 state, 11 utime, 12 stime, 19 starttime (clock ticks).
    """
    try:
        text = (_PROC / pid / "stat").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if ")" not in text:
        return None
    return text.rsplit(")", 1)[1].split()


def _read_proc_rss_mb(pid: str) -> float:
    try:
        fields = (_PROC / pid / "statm").read_text(encoding="utf-8", errors="ignore").split()
        return (int(fields[1]) * _PAGE_SIZE) / (1024 * 1024)
    except (OSError, IndexError, ValueError):
        return 0.0


def _create_time(fields: list[str]) -> float:
    """Process start as epoch seconds (boot time + starttime/HZ)."""
    try:
        return _boot_time() + int(fields[19]) / _CLK_TCK
    except (IndexError, ValueError):
        return time.time()


def _cpu_percent(pid: int, fields: list[str], now: float) -> float:
    """CPU % since the previous scan (psutil Process.cpu_percent semantics:
    first sighting reports 0.0, later the delta against the previous call;
    can exceed 100 on many cores)."""
    try:
        total = (int(fields[11]) + int(fields[12])) / _CLK_TCK
    except (IndexError, ValueError):
        return 0.0
    prev = _PREV_CPU.get(pid)
    _PREV_CPU[pid] = (now, total)
    if prev is None:
        return 0.0
    prev_time, prev_ticks = prev
    dt = now - prev_time
    if dt <= 0:
        return 0.0
    return max(0.0, 100.0 * (total - prev_ticks) / dt)


def _prune_cpu_cache(live_pids: set[int]) -> None:
    for stale in [pid for pid in _PREV_CPU if pid not in live_pids]:
        _PREV_CPU.pop(stale, None)


def _exe_matches_install_dir(exe_path: str, install_dir_name: str) -> bool:
    """True when install_dir_name appears as a FULL path segment of the
    executable path (e.g. .../steamapps/common/<install_dir>/7DaysToDie.exe),
    never as an arbitrary substring. Case-insensitive, matching the
    case-insensitive Windows filesystems inside Wine/Proton prefixes;
    both / and \\ separators are accepted."""
    if not exe_path or not install_dir_name:
        return False
    needle = install_dir_name.lower()
    normalized = exe_path.replace("\\", "/").lower()
    return needle in PurePosixPath(normalized).parts


def _strip_outer_quotes(value: str) -> str:
    """Strip outer double quotes (Steam -> Proton -> wine may or may not
    have parsed them away, so both variants must be handled)."""
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _extract_user_data_folder(cmdline_parts: list[str] | tuple[str, ...] | None) -> str | None:
    """Extract the -UserDataFolder=<path> value from process arguments.

    Flag name matched case-insensitively (Unity accepts variants and the
    Steam->Proton chain does not guarantee preserved casing). Only the
    single-argument form ("-UserDataFolder=Z:/x") is recognized - that is
    the only form the launcher ever builds.
    """
    if not cmdline_parts:
        return None
    prefix = USER_DATA_FOLDER_FLAG.lower() + "="
    for part in cmdline_parts:
        if not isinstance(part, str):
            continue
        if part.lower().startswith(prefix):
            return _strip_outer_quotes(part[len(prefix):])
        # variant where the quotes wrapped the WHOLE argument (flag included)
        unquoted = _strip_outer_quotes(part)
        if unquoted is not part and unquoted.lower().startswith(prefix):
            return _strip_outer_quotes(unquoted[len(prefix):])
    return None


def _cmdline_part_matches_game_name(part: str) -> bool:
    """True when the argument's basename (after \\ -> /) is EXACTLY the
    game executable name. Basename matching is precise: it won't fire for
    an editor holding "notes_7DaysToDie.exe.txt" (different basename),
    and it also covers non-standard install locations the install-dir
    segment match can't see."""
    if not part:
        return False
    basename = part.replace("\\", "/").rsplit("/", 1)[-1]
    return basename in GAME_PROCESS_NAMES


def find_game_processes(
    install_dir_name: str = WINE_INSTALL_DIR_NAME,
) -> list[GameProcessInfo]:
    """Scan running processes and return ALL that look like 7 Days to Die
    (native client and Wine/Proton), each with its -UserDataFolder= value.

    Match criteria (deliberately precise - full segment/basename, never an
    arbitrary substring of the whole cmdline):

    1. matched_by="native" - comm is exactly one of GAME_PROCESS_NAMES, OR
       the basename of /proc/PID/exe is one of NATIVE_EXE_NAMES.
       NOTE: /proc/PID/comm is capped at 15 chars, so "7DaysToDie.x86_64"
       (17 chars) shows up as "7DaysToDie.x86_" and does NOT match via
       comm - the exe basename check catches that case.
    2. matched_by="wine" - install_dir_name appears as a full path segment
       of the executable or of any cmdline argument, AND some cmdline
       argument has a basename equal to the game executable name (both
       together - the segment alone matched user scripts living in the
       game's directory tree, false positive 26.09).
    3. matched_by="wine" - some cmdline argument has a basename equal to
       the game executable name.

    May return more than one process (EAC launcher + the game, or two
    instances launched manually). Sorted by pid ascending.
    """
    if not _PROC.is_dir():
        return []
    if not install_dir_name:
        # criterion 2 needs a non-empty install dir name; 1 and 3 don't
        install_dir_name = ""

    now = time.monotonic()
    results: list[GameProcessInfo] = []
    try:
        entries = os.listdir(_PROC)
    except OSError:
        return []

    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == _OWN_PID:
            continue
        try:
            name = _read_proc_comm(entry)
            exe = _read_proc_exe(entry)
            cmdline_parts = _read_proc_cmdline_parts(entry)

            matched_by = ""
            has_game_exe_arg = any(
                _cmdline_part_matches_game_name(part) for part in cmdline_parts)
            exe_basename = exe.rsplit("/", 1)[-1] if exe else ""
            if name in GAME_PROCESS_NAMES or exe_basename in NATIVE_EXE_NAMES:
                matched_by = "native"
            elif has_game_exe_arg and install_dir_name and (
                _exe_matches_install_dir(exe, install_dir_name)
                or any(_exe_matches_install_dir(part, install_dir_name) for part in cmdline_parts)
            ):
                # Wine/Proton: segment katalogu instalacji ORAZ exe gry
                # w argumentach RAZEM - sam segment łapał fałszywie skrypty
                # użytkownika ze ścieżką "7 Days To Die" (zgłoszenie 26.09)
                matched_by = "wine"

            if not matched_by:
                continue

            fields = _proc_stat_fields(entry)
            results.append(
                GameProcessInfo(
                    pid=pid,
                    cpu_percent=_cpu_percent(pid, fields, now) if fields else 0.0,
                    ram_mb=_read_proc_rss_mb(entry),
                    running_since=_create_time(fields) if fields else time.time(),
                    matched_by=matched_by,
                    user_data_folder=_extract_user_data_folder(cmdline_parts),
                )
            )
        except (OSError, ValueError):
            # process vanished or is unreadable between listdir and reads
            continue

    results.sort(key=lambda info: info.pid)
    _prune_cpu_cache({info.pid for info in results})
    return results


def kill_game_processes(
    install_dir_name: str = WINE_INSTALL_DIR_NAME,
    *,
    timeout: float = 3.0,
) -> int:
    """Zatrzymuje wykryte procesy gry: najpierw SIGTERM (łagodnie), po
    `timeout` s SIGKILL dla ocalałych. Zwraca liczbę procesów, które
    udało się zakończyć. 0 = nie znaleziono działającej gry."""
    procs = find_game_processes(install_dir_name)
    if not procs:
        return 0
    for info in procs:
        try:
            os.kill(info.pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not find_game_processes(install_dir_name):
            return len(procs)
        time.sleep(0.2)
    survivors = 0
    for info in procs:
        try:
            os.kill(info.pid, signal.SIGKILL)
        except OSError:
            continue
        survivors += 1
    time.sleep(0.3)
    still = {p.pid for p in find_game_processes(install_dir_name)}
    return len([p for p in procs if p.pid not in still])


def find_game_pids() -> list[int]:
    """PIDs of all detected game processes ([] when /proc is unavailable).

    Unlike the legacy helper, this uses the STRICT unified criteria from
    find_game_processes() - the legacy loose cmdline substring pre-check
    was a documented false-positive source and is not ported."""
    return [info.pid for info in find_game_processes()]


def is_game_running() -> bool:
    return len(find_game_pids()) > 0


# --- Uruchamianie (port z game_process.py starego projektu, etap 6) -------


def build_launch_args(
    user_data_folder: str | Path | None = None,
    *,
    noeos: bool = False,
    noeac: bool = False,
    skip_news_screen: bool = False,
    skip_intro: bool = False,
) -> list[str]:
    """Buduje listę argumentów startowych gry. user_data_folder (jeśli
    podany) MUSI być bezwzględną ścieżką unixową - zostaje skonwertowany
    przez to_wine_path() (prefiks Z:); nie ma opcji przekazania
    już-skonwertowanej ścieżki wine, bo pominięcie konwersji = gra z danymi
    w złym miejscu bez żadnego komunikatu.

    noeac: znana flaga startowa gry wyłączająca EasyAntiCheat - EAC i tak
    koliduje z modowaniem (skanuje pliki gry), a pod Proton ma znany bug
    fałszywego "naruszenia integralności" własnego pliku ntdll.dll."""
    args: list[str] = []

    if user_data_folder is not None:
        wine_path = to_wine_path(user_data_folder)
        args.append(f"-UserDataFolder={wine_path}")

    if noeos:
        args.append("-noeos")
    if noeac:
        args.append("-noeac")
    if skip_news_screen:
        args.append("-skipnewsscreen=true")
    if skip_intro:
        args.append("-skipintro")

    return args


def format_launch_args_for_steam(args: list[str]) -> str:
    """Skleja argumenty do formy Steam Launch Options, cytując podwójnym
    cudzysłowem każdy argument z białym znakiem (cudzysłów, nie apostrof -
    windowsowy runtime C / Unity rozpoznaje wyłącznie podwójne)."""
    formatted: list[str] = []
    for arg in args:
        if any(ch.isspace() for ch in arg):
            formatted.append(f'"{arg}"')
        else:
            formatted.append(arg)
    return " ".join(formatted)


def _manager_data_root() -> Path:
    """Główny katalog danych launchera."""
    return Path.home() / ".7dtd_modmanager"


def _prepare_instance_user_data_compat(
    user_data_folder: str | Path | None,
    compat_root: Path,
) -> None:
    """Redirect old Windows 7DTD user-data locations into one instance dir.

    ``-UserDataFolder`` is supported by modern 7DTD, but very old builds used
    hard-coded defaults. The Alpha 12 release notes document a change from
    ``%USERPROFILE%\\Documents\\7 Days To Die`` to
    ``%APPDATA%\\7DaysToDie``; Alpha 8.x belongs to the older layout.
    Because a copied historical build may ignore ``-UserDataFolder``, create
    symlinks for BOTH historical locations inside this branch's Proton prefix.
    This keeps Saves/GeneratedWorlds/logs/etc. in the launcher instance folder
    without touching the user's normal/native 7DTD data.

    Existing data under the old location is moved into the instance folder when
    possible. If a name collision prevents a safe merge, the old directory is
    renamed to a timestamped ``.modmanager-backup-*`` sibling before the link is
    created, so nothing is silently overwritten.
    """
    if user_data_folder is None:
        return

    target = Path(user_data_folder).expanduser().resolve(strict=False)
    target.mkdir(parents=True, exist_ok=True)

    prefix_users = compat_root / "pfx" / "drive_c" / "users"
    user_home = prefix_users / "steamuser"

    # Historical 7DTD Windows locations covered here:
    #   old: %USERPROFILE%/Documents/7 Days To Die
    #   old variants sometimes surfaced as "My Documents"
    #   newer: %APPDATA%/7DaysToDie
    legacy_dirs = [
        user_home / "Documents" / "7 Days To Die",
        user_home / "My Documents" / "7 Days To Die",
        user_home / "AppData" / "Roaming" / "7DaysToDie",
    ]

    def _unique_backup(path: Path) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = path.with_name(path.name + f".modmanager-backup-{stamp}")
        candidate = base
        index = 1
        while candidate.exists() or candidate.is_symlink():
            candidate = path.with_name(
                path.name + f".modmanager-backup-{stamp}-{index}"
            )
            index += 1
        return candidate

    for legacy in legacy_dirs:
        legacy.parent.mkdir(parents=True, exist_ok=True)
        try:
            if legacy.is_symlink():
                try:
                    if legacy.resolve(strict=False) == target:
                        logger.debug("User-data link already points to instance: %s", legacy)
                        continue
                except OSError:
                    pass
                # A foreign symlink should never be silently repointed.
                backup = _unique_backup(legacy)
                legacy.rename(backup)
                logger.warning("Moved foreign user-data symlink %s -> %s", legacy, backup)
            elif legacy.exists():
                if legacy.is_dir():
                    # Merge old branch data into the instance folder. Do not
                    # overwrite existing launcher-managed files.
                    for child in list(legacy.iterdir()):
                        dest = target / child.name
                        if not dest.exists() and not dest.is_symlink():
                            shutil.move(str(child), str(dest))
                        else:
                            backup = _unique_backup(dest)
                            shutil.move(str(child), str(backup))
                            logger.warning(
                                "User-data name collision: moved %s -> %s",
                                child, backup)
                    try:
                        legacy.rmdir()
                    except OSError:
                        backup = _unique_backup(legacy)
                        legacy.rename(backup)
                        logger.warning(
                            "Could not empty legacy user-data directory %s; backed it up as %s",
                            legacy, backup)
                else:
                    backup = _unique_backup(legacy)
                    legacy.rename(backup)
                    logger.warning("Moved unexpected user-data path %s -> %s", legacy, backup)

            if not legacy.exists() and not legacy.is_symlink():
                legacy.symlink_to(target, target_is_directory=True)
                logger.info("Mapped legacy 7DTD user-data location %s -> %s", legacy, target)
        except OSError:
            logger.exception("Could not prepare legacy 7DTD user-data path %s", legacy)


def _steam_library_roots() -> list[Path]:
    """Zwraca katalogi bibliotek Steam, w tym biblioteki na innych dyskach.

    UWAGA: to NIE są ścieżki odpowiednie dla
    STEAM_COMPAT_CLIENT_INSTALL_PATH. To ścieżki bibliotek zawierające
    `steamapps`; właściwy katalog klienta ustalamy osobno w
    `_find_steam_client_root()`.
    """
    roots: list[Path] = []
    home = Path.home()
    roots.extend([
        home / ".steam" / "root",
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
        home / ".steam" / "debian-installation",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
    ])

    # Dołącz biblioteki z libraryfolders.vdf, ponieważ Proton/GE-Proton może
    # być zainstalowany poza główną biblioteką Steam.
    for base in list(roots):
        vdf = base / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text, re.IGNORECASE):
            raw = match.group(1).replace("\\\\", "\\")
            roots.append(Path(raw).expanduser())

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _looks_like_steam_client_root(path: Path) -> bool:
    """Czy `path` wygląda na faktyczną instalację klienta Steam?

    Biblioteka na dodatkowym dysku może zawierać `steamapps/common`, ale nie
    jest katalogiem klienta Steam. `STEAM_COMPAT_CLIENT_INSTALL_PATH` musi
    wskazywać właśnie klienta, zgodnie z interfejsem Steam compatibility tool.
    """
    try:
        path = path.expanduser().resolve(strict=False)
    except OSError:
        path = path.expanduser()
    markers = (
        path / "steam.sh",
        path / "steam",
        path / "steamclient.so",
        path / "ubuntu12_32" / "steam",
        path / "ubuntu12_32" / "steamclient.so",
        path / "ubuntu12_64" / "steam",
        path / "ubuntu12_64" / "steamclient.so",
    )
    return any(marker.is_file() for marker in markers)


def _find_steam_client_root() -> Path | None:
    """Znajduje rzeczywisty katalog instalacji klienta Steam.

    To rozróżnienie jest krytyczne dla bibliotek na osobnych dyskach:
    `/media/.../SteamLibrary` jest biblioteką gry, a nie `Steam client
    install path`. Najpierw preferujemy `~/.steam/root`, które Steam i
    dokumentacja compatibility-tools traktują jako kanoniczne wskazanie
    instalacji klienta.
    """
    candidates: list[Path] = []
    env_root = os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH", "").strip()
    if env_root:
        candidates.append(Path(env_root).expanduser())

    home = Path.home()
    candidates.extend([
        home / ".steam" / "root",
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
        home / ".steam" / "debian-installation",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
    ])

    # Najpierw sprawdź kandydatów wynikających z bieżącego HOME/środowiska.
    # Jest to też deterministyczne w testach, gdzie Path.home() jest izolowane.
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve(strict=False))
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_steam_client_root(candidate):
            return candidate.expanduser().resolve(strict=False)

    # Dopiero gdy standardowe ścieżki nie zadziałały, użyj działającego Steam
    # jako dodatkowej wskazówki.
    for proc in Path("/proc").iterdir() if Path("/proc").is_dir() else []:
        if not proc.name.isdigit():
            continue
        try:
            comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip().casefold()
            if comm != "steam":
                continue
            exe = (proc / "exe").resolve(strict=False)
        except OSError:
            continue
        for parent in (exe.parent, exe.parent.parent, exe.parent.parent.parent):
            if _looks_like_steam_client_root(parent):
                return parent.expanduser().resolve(strict=False)
    return None


def find_proton() -> tuple[Path | None, Path | None]:
    """Znajduje Proton oraz odpowiadający mu root klienta Steam.

    Szukamy Protonów w głównych bibliotekach Steam i w katalogu
    compatibilitytools.d. Zwracamy (ścieżka do `proton`, steam_root).
    """
    candidates: list[tuple[Path, Path]] = []
    roots = _steam_library_roots()

    for root in roots:
        common = root / "steamapps" / "common"
        if common.is_dir():
            for child in sorted(common.iterdir(), key=lambda p: p.name.casefold()):
                if child.is_dir() and child.name.casefold().startswith("proton"):
                    proton = child / "proton"
                    if proton.is_file() and os.access(proton, os.X_OK):
                        candidates.append((proton, root))
        compat_dir = root / "compatibilitytools.d"
        if compat_dir.is_dir():
            for child in sorted(compat_dir.iterdir(), key=lambda p: p.name.casefold()):
                proton = child / "proton"
                if proton.is_file() and os.access(proton, os.X_OK):
                    candidates.append((proton, root))

    # Najpierw preferujemy Experimental, następnie Hotfix, potem wersje
    # numerowane. Nazwa katalogu zainstalowanego Protona jest stabilniejsza
    # niż kolejność modyfikacji plików.
    def rank(item: tuple[Path, Path]) -> tuple[int, int, str]:
        name = item[0].parent.name.casefold()
        if "experimental" in name:
            family = 0
        elif "hotfix" in name:
            family = 1
        elif "proton" in name:
            family = 2
        else:
            family = 3
        version_num = 0
        nums = re.findall(r"\d+", name)
        if nums:
            version_num = int(nums[-1])
        return (family, -version_num, name)

    if not candidates:
        return None, None
    candidates.sort(key=rank)
    return candidates[0]


def _find_steam_binary() -> str | None:
    """Znajduje polecenie klienta Steam dostępne dla bieżącego użytkownika."""
    for candidate in ("steam", "/usr/bin/steam", "/usr/games/steam", "/usr/bin/steam-runtime"):
        try:
            result = subprocess.run(
                ["which", candidate], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return candidate
        except Exception:
            continue
    return None


def _ensure_steam_client_running(steam_bin: str) -> None:
    """Próbuje uruchomić klienta Steam, jeśli nie ma procesu `steam`.

    Steamworks wymaga aktywnego klienta Steam przy bezpośrednim starcie
    executable; gdy Steam już działa, niczego nie uruchamiamy ponownie.
    """
    try:
        check = subprocess.run(
            ["pgrep", "-x", "steam"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if check.returncode == 0:
            return
    except Exception:
        # Brak pgrep albo niestandardowa nazwa procesu - bezpieczniej spróbować
        # uruchomić Steam z -silent; klient sam przekieruje się do istniejącej
        # instancji, jeżeli już działa.
        pass

    try:
        subprocess.Popen(
            [steam_bin, "-silent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Dajemy klientowi chwilę na utworzenie IPC/SteamPipe przed SteamAPI_Init.
        time.sleep(2.0)
    except Exception:
        logger.exception("Failed to start the Steam client")


def _launch_downloaded_windows_version(
    game_branch: str,
    user_data_folder: str | Path | None = None,
    *,
    noeos: bool = False,
    noeac: bool = False,
    skip_news_screen: bool = False,
    skip_intro: bool = False,
) -> bool:
    """Uruchamia pobraną przez DepotDownloader wersję Windows przez Proton.

    To omija `steam -applaunch`, które zawsze wskazuje na wersję zainstalowaną
    w bibliotece Steam. Gra nadal ma dostęp do Steamworks, ponieważ klient
    Steam pozostaje uruchomiony, a katalog gry zawiera `steam_appid.txt`.
    Proton dostaje osobny prefix dla każdej wersji, aby stare buildy nie
    dzieliły stanu Wine z innymi wersjami.
    """
    if not game_branch:
        return False

    data_root = _manager_data_root()
    game_dir = data_root / "game-versions" / game_branch
    # Flaga -noeac wybiera zwykły klient. Gdy EAC ma być włączony,
    # korzystamy z launchera EAC, ale tylko wtedy, gdy plik faktycznie istnieje.
    if not noeac and (game_dir / "7DaysToDie_EAC.exe").is_file():
        exe = game_dir / "7DaysToDie_EAC.exe"
    else:
        exe = game_dir / "7DaysToDie.exe"
    if not exe.is_file():
        logger.error("Missing executable of downloaded version %s: %s", game_branch, exe)
        return False

    proton, steam_library_root = find_proton()
    if proton is None or steam_library_root is None:
        logger.error("No installed Proton found for downloaded version %s", game_branch)
        return False

    steam_client_root = _find_steam_client_root()
    if steam_client_root is None:
        logger.error(
            "Could not find a real Steam client directory for downloaded version %s; "
            "the game library cannot be used as STEAM_COMPAT_CLIENT_INSTALL_PATH",
            game_branch,
        )
        return False

    steam_bin = _find_steam_binary()
    if steam_bin is None:
        logger.error("Steam client not found - downloaded version %s cannot initialize Steamworks", game_branch)
        return False
    _ensure_steam_client_running(steam_bin)

    # Osobny prefix na branch: np. ~/.7dtd_modmanager/compatdata/alpha12.5.
    # Proton potrzebuje wyłącznie ścieżki katalogu, resztę tworzy samo.
    compat_root = data_root / "compatdata" / game_branch
    compat_root.mkdir(parents=True, exist_ok=True)
    _prepare_instance_user_data_compat(user_data_folder, compat_root)

    env = os.environ.copy()
    env.update({
        # To MUSI być instalacja klienta Steam, nie biblioteka na dodatkowym
        # dysku. Biblioteka jest przekazywana osobno przez STEAM_COMPAT_LIBRARY_PATHS.
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_client_root),
        "STEAM_COMPAT_DATA_PATH": str(compat_root),
        "STEAM_COMPAT_INSTALL_PATH": str(game_dir),
        "STEAM_COMPAT_LIBRARY_PATHS": str(steam_library_root),
        "STEAM_COMPAT_TOOL_PATHS": str(proton.parent),
        "STEAM_COMPAT_APP_ID": STEAM_APP_ID,
        "WINEPREFIX": str(compat_root / "pfx"),
        "SteamAppId": STEAM_APP_ID,
        "SteamGameId": STEAM_APP_ID,
        "SteamOverlayGameId": STEAM_APP_ID,
        # Pomaga Protonowi znaleźć wybrane narzędzie również wtedy, gdy
        # pochodzi z compatibilitytools.d zamiast steamapps/common.
        "STEAM_EXTRA_COMPAT_TOOLS_PATHS": str(proton.parent),
    })

    # Katalog gry jest wspólny dla instancji tej wersji, a loader BepInEx
    # (winhttp.dll + Doorstop, np. Undead Legacy) ma działać tylko w instancji,
    # która go ma - wdrażamy go (albo sprzątamy) przy każdym starcie.
    loader_active = False
    try:
        loader_active = bepinex_loader.sync_game_dir(game_dir, user_data_folder)
    except Exception:
        logger.exception("Could not prepare the BepInEx loader in %s", game_dir)
    if loader_active:
        # Wine musi wczytać natywny winhttp.dll (Doorstop) z katalogu gry
        bepinex_loader.apply_dll_override(env)

    launch_args = build_launch_args(
        user_data_folder,
        noeos=noeos,
        noeac=noeac,
        skip_news_screen=skip_news_screen,
        skip_intro=skip_intro,
    )
    command = [str(proton), "run", str(exe), *launch_args]

    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "game-launch.log"

    try:
        log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
        try:
            log_fh.write(
                f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"launch {game_branch} via {proton} ===\n"
            )
            log_fh.write(f"cwd: {game_dir}\n")
            log_fh.write(f"compatdata: {compat_root}\n")
            log_fh.write(f"steam_client_root: {steam_client_root}\n")
            log_fh.write(f"steam_library_root: {steam_library_root}\n")
            log_fh.write(f"instance_user_data_folder: {user_data_folder}\n")
            log_fh.write(
                "compat_user_data_links: "
                + "; ".join([
                    str(compat_root / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "7 Days To Die"),
                    str(compat_root / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "7 Days To Die"),
                    str(compat_root / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "7DaysToDie"),
                ])
                + "\n"
            )
            log_fh.write(
                f"bepinex_loader: {'active (WINEDLLOVERRIDES=' + env.get('WINEDLLOVERRIDES', '') + ')' if loader_active else 'not used'}\n"
            )
            log_fh.write(f"command: {shlex.join(command)}\n")
            subprocess.Popen(
                command,
                cwd=str(game_dir),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_fh.close()
        logger.info("Launched downloaded version %s via Proton: %s", game_branch, exe)
        return True
    except Exception:
        logger.exception("Failed to launch downloaded version %s", game_branch)
        return False


def launch_game_via_steam(
    user_data_folder: str | Path | None = None,
    *,
    noeos: bool = False,
    noeac: bool = False,
    skip_news_screen: bool = False,
    skip_intro: bool = False,
    game_branch: str = "",
) -> bool:
    """Uruchamia instancję gry.

    Gdy instancja ma `game_branch`, startujemy konkretną kopię pobraną przez
    DepotDownloader przez Proton. Bez `game_branch` zachowanie pozostaje
    dotychczasowe: `steam -applaunch 251570 ...` uruchamia instalację Steama.
    """
    branch = (game_branch or "").strip()
    if branch:
        return _launch_downloaded_windows_version(
            branch,
            user_data_folder,
            noeos=noeos,
            noeac=noeac,
            skip_news_screen=skip_news_screen,
            skip_intro=skip_intro,
        )

    steam_bin = _find_steam_binary()
    if steam_bin is None:
        return False

    launch_args = build_launch_args(
        user_data_folder,
        noeos=noeos,
        noeac=noeac,
        skip_news_screen=skip_news_screen,
        skip_intro=skip_intro,
    )
    command = [steam_bin, "-applaunch", STEAM_APP_ID, *launch_args]
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False
