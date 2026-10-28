"""Pobieranie konkretnych wersji 7 Days to Die prosto ze Steam przez
DepotDownloader (SteamRE) - z autoryzacją Steam Guard przez kod QR.

Mechanika (zweryfikowana mini-projektem /home/paffcio/Pobrane/test/):
    DepotDownloader -app 251570 -depot 251576 -branch <branch>
        -os windows -osarch 64 -dir <cel> -remember-password [-qr]

- pierwsza autoryzacja: -qr -> kod QR w stdout (ASCII bloki) skanowany
  aplikacją mobilną Steam; sesja zapisywana w ~/.local/share/DepotDownloader
- kolejne pobrania korzystają z sesji (bez QR)
- branch = wersja gry (lista z publicznego API steamcmd: alpha8.8 ... v3.1.0)

Pobrane wersje trafiają do ~/.7dtd_modmanager/game-versions/<branch>/,
rejestr trzyma game-versions.json. Przypisanie wersji do instancji to
osobna funkcja (Instance.game_branch, profile_manager).

URUCHAMIANIE: pobrana wersja jest pełną kopią Windows z `steam_appid.txt`.
Instancja z przypisanym game_branch uruchamia tę kopię przez Proton z
osobnym prefixem Wine i aktywnym klientem Steam; -applaunch jest używane
tylko dla instancji bez przypisanej kopii.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import secrets
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path

import requests
from PySide6.QtCore import Property, QObject, QThread, QTimer, Qt, Signal, Slot

from services import filesystem_service as fs
from services.i18n_message import message as i18n_message
from services import install_log
from backend.legacy_game_catalog import RELEASE_BY_BRANCH, release_options

logger = logging.getLogger(__name__)

APP_ID = "251570"
DEPOT_ID = "251576"
STEAMCMD_API = "https://api.steamcmd.net/v1/info/251570"
DEPOTDOWNLOADER_RELEASES = (
    "https://api.github.com/repos/SteamRE/DepotDownloader/releases/latest")
DEPOTDOWNLOADER_FALLBACK_VERSIONS = ("3.3.0", "3.2.0", "3.1.0")

BRANCH_CACHE_TTL = 1800
BRANCHES_FILE_CACHE_TTL = 86400
DOWNLOAD_MAX_RETRIES = 6
DOWNLOAD_RETRY_DELAY = 4.0
DOWNLOAD_RETRY_MAX_DELAY = 20.0
DOWNLOAD_MAX_DOWNLOADS = 4
FILE_LOCK_RETRIES = 3
FILE_LOCK_RETRY_DELAY = 2.0
GAME_PROGRESS_LOG_STEP = 5.0

# Steam can rate-limit repeated login handshakes. DepotDownloader itself may
# keep retrying internally, so the manager must stop the child process as soon
# as the rate-limit is visible and block immediate re-launches.
STEAM_RATE_LIMIT_COOLDOWN = 120.0

# DepotDownloader retries manifest failures internally until it gets a
# manifest. Protect the GUI process from an endless retry loop when a
# SteamKit/CDN request keeps returning a manifest error.
MANIFEST_ERROR_REPEAT_LIMIT = 3

PROGRESS_RE = re.compile(r"(\d{1,3}\.\d{2})%")
QR_CHARS = set("█▀▄▌▐░▒▓")
AUTH_SUCCESS_RE = re.compile(
    r"Next time you can login with\s+-username\s+([^\s]+)\s+-remember-password",
    re.IGNORECASE,
)
AUTH_LOGIN_RE = re.compile(
    r"Logging ['\"]?([^'\"]+)['\"]? into Steam3",
    re.IGNORECASE,
)
STEAM_ACCOUNT_FILE = "steam-account.json"

# Modpacki/strony często oznaczają stare wydania tylko numerem głównym
# (np. "Alpha 20"), podczas gdy Steam udostępnia je jako konkretny stable
# branch. Dla znanych legacy alpha wybieramy właściwy stable branch zamiast
# uruchamiać aktualne Steam/public.
LEGACY_ALPHA_STABLE_BRANCHES = {
    "alpha5": "alpha5.0-fix2",
    "alpha6": "alpha6.4",
    "alpha7": "alpha7.11",
    "alpha8": "alpha8.8",
    "alpha9": "alpha9.3",
    "alpha10": "alpha10.4",
    "alpha11": "alpha11.6",
    "alpha12": "alpha12.5",
    "alpha13": "alpha13.8",
    "alpha14": "alpha14.7",
    "alpha15": "alpha15.2",
    "alpha16": "alpha16.4",
    "alpha17": "alpha17.4",
    "alpha18": "alpha18.4",
    "alpha19": "alpha19.6",
    "alpha20": "alpha20.7",
}  # alpha21+ rozwiązuje resolve_downloaded_branch (alpha21 -> alpha21.x)


def _normalize_game_version_label(value: str) -> str:
    text = re.sub(r"[^a-z0-9.]+", "", (value or "").strip().lower())
    return text


def required_game_branch(value: str) -> str:
    """Zamienia oznaczenie wersji moda/modpacka na konkretny branch Steam.

    Strony używają zarówno slugów (``alpha20``/``v3``), jak i etykiet
    prezentowanych użytkownikowi (``Alpha 20``, ``V3 Mods``). Stare wersje
    Alpha bez patcha są wiązane z ich konkretnym stable branchem Steam.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.lower() in RELEASE_BY_BRANCH:
        return raw.lower()
    compact = _normalize_game_version_label(raw)

    alpha = re.match(r"^alpha(\d+)((?:\.\d+)*)", compact)
    if alpha:
        major = alpha.group(1)
        rest = alpha.group(2)
        if rest:
            return f"alpha{major}{rest}"
        return LEGACY_ALPHA_STABLE_BRANCHES.get(f"alpha{major}", f"alpha{major}")

    # Pełny numer zostaje (v3.2.0, v3.0.1) - Steam ma takie nazwy branchy.
    modern = re.match(r"^v(\d+)((?:\.\d+)*)", compact)
    if modern:
        return f"v{modern.group(1)}{modern.group(2)}"

    lowered = raw.casefold()
    if lowered in {"public", "latest", "latest_experimental", "latest_experimental_fallback"}:
        return raw
    return raw


def version_requirement_text(value: str) -> str:
    branch = required_game_branch(value)
    if not branch:
        return ""
    if _normalize_game_version_label(value) != _normalize_game_version_label(branch):
        return f"{value.strip()} → {branch}"
    return branch


def version_group(name: str) -> str:
    """Grupa wersji gry z brancha/slugu: "v2.6" -> "v2", "public" -> "v3",
    "alpha19.6" -> "alpha". Slugi katalogu 7daystodiemods.com ("v1"/"v2"/"v3")
    porównywalne z grupami branchy Steam."""
    n = (name or "").strip().lower()
    if n.startswith("v1"):
        return "v1"
    if n.startswith("v2"):
        return "v2"
    if n.startswith("v3") or n in ("public", "latest_experimental", "latest"):
        return "v3"
    if n.startswith("alpha"):
        return "alpha"
    return n


def _game_files_look_complete(target: Path) -> bool:
    """Minimalny zestaw plików gry, a nie tylko EXE pobrany na początku."""
    if not target.is_dir() or not (target / "7DaysToDie.exe").is_file():
        return False
    appid = target / "steam_appid.txt"
    if not appid.is_file():
        return False
    try:
        if appid.read_text(encoding="utf-8", errors="replace").strip() != APP_ID:
            return False
    except OSError:
        return False
    data = target / "7DaysToDie_Data"
    if not data.is_dir():
        return False
    # Starsze wersje używają Mono, a nowsze mogą korzystać z IL2CPP.
    return (data / "Managed" / "Assembly-CSharp.dll").is_file() or (target / "GameAssembly.dll").is_file()


def _branch_dir_is_complete(target: Path) -> bool:
    """Uznaj wersję za zainstalowaną tylko po zapisanym sukcesie pobierania.

    Samo EXE i steam_appid.txt nie świadczą o kompletnym transferze.
    Rejestr jest zapisywany dopiero po powodzeniu DepotDownloadera.
    """
    branch = target.name
    record = next((v for v in load_versions() if v.get("branch") == branch), None)
    if record is None or Path(str(record.get("dir", ""))) != target:
        return False
    release = RELEASE_BY_BRANCH.get(branch)
    if release and not release.steam_branch and record.get("origin") != "imported":
        if str(record.get("depot", "")) != release.depot or str(record.get("manifest", "")) != release.manifest:
            return False
    return _game_files_look_complete(target)


def branch_sort_key(name: str) -> tuple:
    """Modern numbered releases follow alpha releases; preserve named branches."""
    low = name.casefold()
    if low in {"latest_experimental", "public"}:
        return (3, (1 if low == "latest_experimental" else 0,), low)
    match = re.match(r"(alpha|v)(\d+(?:\.\d+)*)", low)
    if match:
        return (2 if match[1] == "v" else 1,
                tuple(int(n) for n in match[2].split(".")), low)
    return (0, (), low)


def _branch_sort_key(name: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", name))


def resolve_downloaded_branch(value: str) -> str:
    """Zwraca KONKRETNY pobrany branch spełniający wymaganie, albo "".

    Katalog modów podaje wymaganą wersję tylko jako grupę (``v2``,
    ``alpha21``), a na dysku leży konkretny branch (``v2.6``,
    ``alpha21.2``). Dokładne trafienie ma pierwszeństwo. Dla samej grupy:
    - ``v1``/``v2``: najnowszy pobrany ``v<N>.x``,
    - ``v3``: ``public``, potem ``v3.x`` (malejąco), na końcu
      ``latest_experimental``/``latest``,
    - ``alpha<N>``: najnowszy pobrany ``alpha<N>.x``.
    """
    branch = required_game_branch(value)
    if not branch:
        return ""
    root = versions_root()
    if _branch_dir_is_complete(root / branch):
        return branch
    if branch in RELEASE_BY_BRANCH:
        return ""  # Nie zastępuj historycznej wersji sąsiednim wydaniem.

    if re.fullmatch(r"alpha\d+", branch):
        matches = lambda n: re.fullmatch(re.escape(branch) + r"\.\d+", n) is not None
    elif re.fullmatch(r"v\d+", branch):
        group = version_group(branch)
        matches = lambda n: n != branch and version_group(n) == group
    elif re.fullmatch(r"(v|alpha)\d+(\.\d+)+", branch):
        # niepełny numer (v3.1) -> v3.1.x
        matches = lambda n: n.startswith(branch + ".")
    else:
        return ""

    try:
        entries = list(root.iterdir())
    except OSError:
        return ""
    candidates = [e.name for e in entries
                  if matches(e.name) and _branch_dir_is_complete(e)]
    if not candidates:
        return ""

    def rank(name: str) -> tuple:
        low = name.lower()
        if low == "public":
            return (3, ())
        if re.match(r"(v|alpha)\d", low):
            return (2, _branch_sort_key(low))
        return (1, ())  # latest_experimental / latest
    candidates.sort(key=rank, reverse=True)
    return candidates[0]


def branches_cached() -> dict[str, str]:
    """Mapa buildid -> branch (api.steamcmd, plikowy cache 24 h) - używana
    do tłumaczenia buildid z appmanifest_251570.acf na wersję gry."""
    cache = fs.cache_dir() / "steam-branches.json"
    data = fs.read_json(cache, None)
    if isinstance(data, dict) \
            and time.time() - data.get("time", 0) < BRANCHES_FILE_CACHE_TTL \
            and isinstance(data.get("map"), dict):
        return {str(k): str(v) for k, v in data["map"].items()}
    resp = requests.get(STEAMCMD_API, timeout=(10, 30))
    resp.raise_for_status()
    depots = resp.json().get("data", {}).get(APP_ID, {}).get("depots", {})
    branches = depots.get("branches", {})
    mapping = {
        str(info.get("buildid", "")): str(name)
        for name, info in branches.items()
        if isinstance(info, dict) and info.get("buildid")
    }
    fs.write_json(cache, {"time": time.time(), "map": mapping})
    return mapping


class GameVersionsError(Exception):
    pass


def tools_dir() -> Path:
    return fs.ensure_dir(fs.data_dir() / "tools")


def tool_path() -> Path:
    return tools_dir() / "DepotDownloader"


def parse_depot_code(code: str) -> dict[str, str]:
    """Kod jest zestawem liczb, nigdy poleceniem do wykonania w shellu."""
    match = re.fullmatch(
        r"\s*(?:download_depot\s+)?([0-9]{1,10})\s+([0-9]{1,10})\s+([0-9]{1,20})\s*",
        code or "", re.IGNORECASE,
    )
    if not match:
        raise GameVersionsError(i18n_message("steamReleases.code.invalid"))
    numbers = tuple(int(part) for part in match.groups())
    if any(number <= 0 or number >= 2 ** bits
           for number, bits in zip(numbers, (32, 32, 64))):
        raise GameVersionsError(i18n_message("steamReleases.code.invalid"))
    app_id, depot, manifest = map(str, numbers)
    if app_id != APP_ID:
        raise GameVersionsError(i18n_message("steamReleases.code.wrongApp", {"app": app_id}))
    return {"app_id": app_id, "depot": depot, "manifest": manifest,
            "osarch": "32" if depot in {"251571", "251574"} else "64"}


def manifest_source(branch: str) -> dict[str, str] | None:
    match = re.fullmatch(r"manifest-([0-9]{1,10})-([0-9]{1,20})", branch)
    if not match:
        return None
    source = parse_depot_code(APP_ID + " " + " ".join(match.groups()))
    if branch != "manifest-" + "-".join(source[key] for key in ("depot", "manifest")):
        raise GameVersionsError(i18n_message("steamReleases.code.invalid"))
    return source


def branch_for_depot_code(code: str) -> str:
    source = parse_depot_code(code)
    for release in RELEASE_BY_BRANCH.values():
        if (release.depot, release.manifest) == (source["depot"], source["manifest"]):
            return release.branch
    # Depot i manifest w identyfikatorze pozwalają wznowić kolejkę bez
    # tworzenia fikcyjnej instalacji w game-versions.json przed sukcesem.
    return "manifest-" + "-".join(source[key] for key in ("depot", "manifest"))


def build_download_command(binary: Path, branch: str, target: Path,
                           username: str, use_qr: bool) -> list[str]:
    """Zbuduj polecenie pobierania bez mieszania historycznych depotów z public."""
    legacy = RELEASE_BY_BRANCH.get(branch)
    source = manifest_source(branch)
    if source:
        depot_args = ["-depot", source["depot"], "-manifest", source["manifest"]]
        os_arch = source["osarch"]
    elif legacy and not legacy.steam_branch:
        depot_args = ["-depot", legacy.depot, "-manifest", legacy.manifest]
        os_arch = legacy.osarch
    else:
        depot_args = ["-depot", DEPOT_ID, "-branch", branch]
        os_arch = "64"
    cmd = [
        str(binary), "-app", APP_ID, *depot_args,
        "-os", "windows", "-osarch", os_arch,
        "-dir", str(target), "-remember-password",
        "-loginid", str(new_login_id()),
        "-max-downloads", str(DOWNLOAD_MAX_DOWNLOADS),
    ]
    if use_qr:
        cmd.append("-qr")
    else:
        cmd.extend(["-username", username])
    return cmd


def new_login_id() -> int:
    """Generuje unikalny LoginID dla sesji DepotDownloadera.

    Steam może rozłączyć dwa klienty korzystające z tego samego LoginID.
    Menedżer uruchamia DepotDownloader obok pełnego klienta Steam, dlatego
    każda sesja dostaje własną dodatnią wartość 31-bitową.
    """
    return secrets.randbelow(2**31 - 1) + 1


def versions_root() -> Path:
    return fs.ensure_dir(fs.data_dir() / "game-versions")


def registry_path() -> Path:
    return fs.data_dir() / "game-versions.json"


def _download_depot_tool(release_url: str, binary_path: Path) -> Path:
    """Pobierz konkretną wersję DepotDownloadera do wskazanego pliku."""
    tools_dir().mkdir(parents=True, exist_ok=True)
    logger.info("Downloading DepotDownloader (%s)...", release_url.rsplit("/", 1)[-1])
    resp = requests.get(release_url, timeout=(10, 30))
    resp.raise_for_status()
    assets = resp.json().get("assets", [])
    url = next((a["browser_download_url"] for a in assets
                if "linux-x64.zip" in a.get("name", "")), None)
    if not url:
        raise GameVersionsError(i18n_message("gameVersions.status.toolArchiveMissing"))
    zip_path = tools_dir() / f"{binary_path.name}.download.zip"
    try:
        with requests.get(url, stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
        tmp_binary = binary_path.with_suffix(binary_path.suffix + ".part")
        tmp_binary.unlink(missing_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open("DepotDownloader", "r") as source, open(tmp_binary, "wb") as target:
                shutil.copyfileobj(source, target)
        tmp_binary.chmod(tmp_binary.stat().st_mode | 0o111)
        tmp_binary.replace(binary_path)
    finally:
        zip_path.unlink(missing_ok=True)
        binary_path.with_suffix(binary_path.suffix + ".part").unlink(missing_ok=True)
    return binary_path


def ensure_tool() -> Path:
    """Pobiera aktualny DepotDownloader (Linux x64) przy pierwszym użyciu."""
    binary = tool_path()
    if binary.is_file():
        return binary
    return _download_depot_tool(DEPOTDOWNLOADER_RELEASES, binary)


def ensure_fallback_tool(version: str) -> Path:
    """Pobierz wskazaną starszą wersję DepotDownloadera jako fallback."""
    if version not in DEPOTDOWNLOADER_FALLBACK_VERSIONS:
        raise GameVersionsError(i18n_message("gameVersions.status.fallbackUnsupported", {"version": version}))
    release_url = (
        "https://api.github.com/repos/SteamRE/DepotDownloader/releases/tags/"
        f"DepotDownloader_{version}"
    )
    binary = tools_dir() / f"DepotDownloader-{version}"
    if binary.is_file():
        return binary
    return _download_depot_tool(release_url, binary)


def steam_account_path() -> Path:
    return fs.data_dir() / STEAM_ACCOUNT_FILE


def load_steam_username() -> str:
    """Login Steam zapamiętany przez ten launcher (bez tokenów/hasła)."""
    data = fs.read_json(steam_account_path(), {})
    if not isinstance(data, dict):
        return ""
    value = data.get("username", "")
    return str(value).strip() if value is not None else ""


def save_steam_username(username: str) -> bool:
    username = (username or "").strip()
    if not username:
        return False
    return fs.write_json(steam_account_path(), {"username": username})


def clear_steam_username() -> None:
    try:
        steam_account_path().unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to remove the locally stored Steam account name")


def has_saved_session(username: str | None = None) -> bool:
    """Czy launcher ma zapamiętane konto Steam.

    DepotDownloader nie trzyma account.config jako zwykłego pliku w
    ``~/.local/share/DepotDownloader``: korzysta z .NET IsolatedStorage.
    Dlatego obecność katalogu na dysku nie jest wiarygodnym wykrywaczem
    aktywnej sesji. Źródłem stanu UI jest zapisany login; przy użyciu tokenu
    DepotDownloader sam zweryfikuje sesję, a po odrzuceniu tokenu stan jest
    czyszczony.
    """
    username = (username or load_steam_username()).strip()
    return bool(username)


def load_versions() -> list[dict]:
    data = fs.read_json(registry_path(), {"versions": []})
    versions = data.get("versions", []) if isinstance(data, dict) else []
    return [v for v in versions if isinstance(v, dict)]


def save_versions(versions: list[dict]) -> None:
    if not fs.write_json(registry_path(), {"versions": versions}):
        raise OSError("Nie udało się zapisać rejestru wersji gry.")


def reinstall_stage(branch: str) -> Path:
    """Osobny staging, aby działająca gra pozostała nietknięta."""
    return versions_root() / f".{branch}.reinstall"


def _replace_version_after_download(branch: str, staging: Path, target: Path) -> None:
    """Podmień katalog dopiero po sukcesie, z cofnięciem przy błędzie."""
    if target.is_symlink():
        raise GameVersionsError("Nie można nadpisać importu zewnętrznego. Usuń wpis importu i pobierz własną kopię.")
    backup = versions_root() / f".{branch}.before-reinstall"
    if backup.exists() or backup.is_symlink():
        raise GameVersionsError(f"Pozostała kopia zabezpieczająca: {backup}. Sprawdź ją przed ponowną próbą.")
    moved_original = False
    try:
        if target.exists():
            target.rename(backup)
            moved_original = True
        staging.rename(target)
    except Exception:
        if moved_original and not target.exists() and backup.exists():
            backup.rename(target)
        raise
    if moved_original:
        try:
            shutil.rmtree(backup)
        except OSError as exc:
            logger.warning("Could not remove the previous version backup %s: %s", backup, exc)


def game_fingerprint(folder: Path) -> str:
    """Szybki odcisk zawartości, bez czytania gigabajtów zasobów Unity."""
    base = Path(folder)
    files = (
        "7DaysToDie.exe",
        "7DaysToDie_Data/Managed/Assembly-CSharp.dll",
        "7DaysToDie_Data/mainData",
        "Data/Config/recipes.xml",
    )
    digest = hashlib.sha256()
    found = 0
    for relative in files:
        path = base / relative
        if not path.is_file():
            continue
        found += 1
        size = path.stat().st_size
        digest.update(relative.encode("utf-8"))
        digest.update(str(size).encode("ascii"))
        with path.open("rb") as stream:
            digest.update(stream.read(256 * 1024))
            if size > 256 * 1024:
                stream.seek(max(0, size - 256 * 1024))
                digest.update(stream.read(256 * 1024))
    return digest.hexdigest() if found else ""


def import_game_version(folder: str, branch: str, custom_name: str = "") -> dict:
    """Rejestruje instalację bez kopiowania lub modyfikacji plików źródłowych."""
    source = Path(folder).expanduser().resolve(strict=True)
    if not source.is_dir() or not (source / "7DaysToDie.exe").is_file():
        raise GameVersionsError(i18n_message("steamReleases.legacy.error.invalidFolder"))
    if not (source / "7DaysToDie_Data").is_dir():
        raise GameVersionsError(i18n_message("steamReleases.legacy.error.incompleteFolder"))
    # Gra Unity wymaga własnej biblioteki kodu gry. Sam EXE i folder o
    # odpowiedniej nazwie to za mało, żeby uznać obcy katalog za 7DTD.
    if not (source / "7DaysToDie_Data" / "Managed" / "Assembly-CSharp.dll").is_file():
        raise GameVersionsError(i18n_message("steamReleases.legacy.error.invalidGameFiles"))

    raw_name = (custom_name or "").strip()
    if raw_name:
        name = re.sub(r"[^a-z0-9._-]+", "-", raw_name.casefold()).strip(".-_")
        if len(name) < 2 or len(name) > 65:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.invalidName"))
        name = "custom-" + name
    else:
        name = (branch or "").strip().lower()
        if name not in RELEASE_BY_BRANCH:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.chooseRelease"))

    root = versions_root()
    dest = root / name
    if dest.exists() or dest.is_symlink():
        raise GameVersionsError(i18n_message("steamReleases.legacy.error.duplicateRelease", {"name": name}))
    if source == root or root in source.parents:
        raise GameVersionsError(i18n_message("steamReleases.legacy.error.alreadyManaged"))

    fingerprint = game_fingerprint(source)
    for record in load_versions():
        old_path = Path(str(record.get("dir", ""))).expanduser()
        if old_path.exists() and old_path.resolve() == source:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.duplicateLocation", {"branch": record.get("branch", "")}))
        if fingerprint and old_path.is_dir() and game_fingerprint(old_path) == fingerprint:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.duplicateContent", {"branch": record.get("branch", "")}))

    # Zewnętrzna kopia musi mieć prawidłowe AppID dla Steamworks/Protona.
    # To jedyny plik, jaki import może dodać do istniejącego katalogu.
    appid_file = source / "steam_appid.txt"
    created_appid = not appid_file.exists()
    if not created_appid:
        if appid_file.read_text(encoding="utf-8").strip() != APP_ID:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.wrongAppId"))
    else:
        try:
            appid_file.write_text(APP_ID + "\n", encoding="utf-8")
        except OSError as exc:
            raise GameVersionsError(i18n_message("steamReleases.legacy.error.writeAppId", {"error": str(exc)})) from exc
    try:
        dest.symlink_to(source, target_is_directory=True)
    except OSError:
        if created_appid:
            appid_file.unlink(missing_ok=True)
        raise
    entry = RELEASE_BY_BRANCH.get(name)
    record = {
        "branch": name,
        "dir": str(dest),
        "source_dir": str(source),
        "size_bytes": dir_size(source),
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "origin": "imported",
        "fingerprint": fingerprint,
        "depot": entry.depot if entry else "",
        "manifest": entry.manifest if entry else "",
    }
    try:
        versions = load_versions()
        versions.append(record)
        save_versions(versions)
    except Exception:
        dest.unlink(missing_ok=True)
        if created_appid:
            appid_file.unlink(missing_ok=True)
        raise
    return record


def dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


# Co ile ms wątek GUI odświeża postęp/status pobierania. DepotDownloader
# potrafi wypisać tysiące linii na sekundę - UI dostaje jedną paczkę zmian.
UI_FLUSH_INTERVAL_MS = 100


class GameVersionsManager(QObject):
    """Pobieranie listy branchy Steam + pobieranie wybranych wersji gry."""

    changed = Signal()
    busyChanged = Signal()
    progressChanged = Signal()
    statusChanged = Signal()
    qrChanged = Signal()
    finished = Signal(str, str)          # branch, error ("" = ok/cancel)
    accountConnected = Signal(str)       # username po udanym QR
    # total_bytes can exceed a signed 32-bit integer (the 7DTD depot is
    # multiple GiB), so pass it as a Python object through Qt signals.
    # Using Signal(str, int) lets PySide6 coerce the byte count to a
    # C++ int and can raise OverflowError before the receiving slot runs.
    gameDownloadStarted = Signal(str, object)  # branch, total bytes
    gameDownloadProgress = Signal(str, float, str)  # branch, percent, status
    gameDownloadFinished = Signal(str, str, str)   # branch, state, message
    # Wewnętrzny most wątek roboczy -> wątek GUI (patrz _emit).
    _uiCall = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._versions = load_versions()
        self._available: list[dict] = []
        self._available_time = 0.0
        self._busy = False
        self._progress = 0.0
        self._status = ""
        self._qr_text = ""
        self._needs_qr = False
        self._qr_lines: list[str] = []
        self._steam_username = load_steam_username()
        self._pending_username = ""
        self._auth_succeeded = False
        self._session_invalid = False
        self._steam_rate_limited = False
        self._steam_rate_limit_until = 0.0
        self._manifest_error_count = 0
        self._manifest_failure_storm = False
        self._download_retryable_error = False
        self._last_download_chunk_error = ""
        self._previous_chunk_error = ""
        self._download_staging_reset_done = False
        self._chunk_fallback_index = 0
        self._primary_depot_binary = ""
        self._download_file_lock_error = False
        self._download_file_lock_path = ""
        self._download_branch = ""
        self._reinstall_branch = ""
        self._last_game_progress = -1.0
        self._last_logged_game_progress = -1.0
        self._process: subprocess.Popen | None = None
        self._worker_thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._pause_requested = threading.Event()
        self._lock = threading.Lock()
        # Wątek roboczy (DepotDownloader) NIE może emitować sygnałów wprost:
        # bindingi QML podpięte do notify liczą się w wątku emitującym, co
        # zawiesza UI. Wszystko przechodzi przez kolejkowane _uiCall.
        self._flush_lock = threading.Lock()
        self._flush_pending = False
        self._progress_dirty = False
        self._status_dirty = False
        self._uiCall.connect(self._run_ui_call, Qt.ConnectionType.QueuedConnection)
        # Do not scan /proc while constructing the backend during application
        # startup. Stale DepotDownloader processes are cleaned immediately
        # before an actual download starts and again during shutdown.

    # ---------------- properties ---------------- #
    @Property("QVariantList", notify=changed)
    def versions(self):
        # Pokaż również uszkodzone wpisy, ale nie opisuj ich jako pobranych.
        entries = []
        for item in self._versions:
            entry = dict(item)
            entry["installed"] = self.is_installed(str(item.get("branch", "")))
            entries.append(entry)
        return sorted(entries, key=lambda v: branch_sort_key(v["branch"]), reverse=True)

    @Property("QVariantList", notify=changed)
    def branchChoices(self):
        choices = {v["branch"]: v for v in self._available + self._versions if v.get("branch")}
        return sorted(choices.values(), key=lambda v: branch_sort_key(v["branch"]), reverse=True)

    @Property("QVariantList", notify=changed)
    def available(self):
        return self._available

    @Property("QVariantList", constant=True)
    def historicalReleases(self):
        return release_options()

    @Property(bool, notify=changed)
    def hasSavedSession(self):
        return has_saved_session(self._steam_username)

    @Property(str, notify=changed)
    def steamUsername(self):
        return self._steam_username

    @Property(str, notify=changed)
    def downloadingBranch(self):
        return self._download_branch

    @Property(str, notify=changed)
    def reinstallingBranch(self):
        return self._reinstall_branch

    @Slot(str, result=bool)
    def isInstalled(self, branch: str) -> bool:
        return self.is_installed(branch)

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(float, notify=progressChanged)
    def progress(self):
        return self._progress

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=qrChanged)
    def qrText(self):
        return self._qr_text

    @Property(str, notify=qrChanged)
    def qrDataUrl(self) -> str:
        """Kod QR jako PNG (data URL) - renderowany z ASCII bloków
        DepotDownloadera ('█' pełny moduł, '▀' górny, '▄' dolny)."""
        lines = [l for l in self._qr_lines if l.strip()
                 and any(ch in QR_CHARS for ch in l)]
        if not lines:
            return ""
        try:
            from PySide6.QtCore import QBuffer
            from PySide6.QtGui import QColor, QImage, QPainter
            cols = max(len(l) for l in lines)
            rows = len(lines) * 2
            scale = 8
            margin = 3
            img = QImage((cols + 2 * margin) * scale,
                         (rows + 2 * margin) * scale,
                         QImage.Format.Format_RGB32)
            img.fill(QColor("#ffffff"))
            painter = QPainter(img)
            painter.setPen(QColor("#111111"))
            for row, line in enumerate(lines):
                for col, ch in enumerate(line):
                    if ch in ("█", "▀"):
                        painter.fillRect((col + margin) * scale,
                                         (2 * row + margin) * scale,
                                         scale, scale, QColor("#111111"))
                    if ch in ("█", "▄"):
                        painter.fillRect((col + margin) * scale,
                                         (2 * row + 1 + margin) * scale,
                                         scale, scale, QColor("#111111"))
            painter.end()
            buf = QBuffer()
            buf.open(QBuffer.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            import base64
            b64 = base64.b64encode(bytes(buf.data())).decode("ascii")
            return "data:image/png;base64," + b64
        except Exception:  # noqa: BLE001
            logger.exception("QR image render failed")
            return ""

    @Slot(str)
    def fakeQrSet(self, text: str) -> None:
        """Wyłącznie do testów wizualnych QML (harness)."""
        self._qr_lines = text.split("\n")
        self._set_qr(text, True)

    @Property(bool, notify=qrChanged)
    def needsQr(self):
        return self._needs_qr

    # ---------------- helpers ---------------- #
    @Slot(object)
    def _run_ui_call(self, fn) -> None:
        """Wykonuje callable w wątku GUI (cel kolejkowanego _uiCall)."""
        try:
            fn()
        except Exception:  # noqa: BLE001 - UI nie może paść przez callback
            logger.exception("Queued UI callback failed")

    def _on_gui(self, fn) -> None:
        """Wykonuje fn w wątku GUI: od razu, gdy już w nim jesteśmy, w
        przeciwnym razie przez kolejkowany _uiCall."""
        if QThread.currentThread() is self.thread():
            fn()
        else:
            self._uiCall.emit(fn)

    def _emit(self, signal, *args) -> None:
        """Bezpieczna emisja sygnału z dowolnego wątku.

        W wątku GUI emitujemy od razu; z wątku roboczego emisja jest
        kolejkowana do wątku GUI, więc bindingi QML nigdy nie wykonują się
        w wątku DepotDownloadera."""
        self._on_gui(lambda: signal.emit(*args))

    def _request_flush(self) -> None:
        """Planuje jedno zbiorcze odświeżenie postępu/statusu (throttling)."""
        with self._flush_lock:
            if self._flush_pending:
                return
            self._flush_pending = True
        self._on_gui(self._arm_flush)

    def _arm_flush(self) -> None:
        QTimer.singleShot(UI_FLUSH_INTERVAL_MS, self._flush_ui)

    def _flush_ui(self) -> None:
        """Wątek GUI: wysyła do UI najświeższy postęp i status."""
        with self._flush_lock:
            self._flush_pending = False
            progress_dirty = self._progress_dirty
            status_dirty = self._status_dirty
            self._progress_dirty = False
            self._status_dirty = False
        if progress_dirty:
            self.progressChanged.emit()
        if status_dirty:
            self.statusChanged.emit()
        if (progress_dirty or status_dirty) and self._download_branch:
            self._last_game_progress = self._progress
            self.gameDownloadProgress.emit(
                self._download_branch, self._progress, self._status)

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        self._emit(self.busyChanged)

    def _set_progress(self, value: float) -> None:
        self._progress = value
        if self._download_branch:
            if (value >= 100.0
                    or self._last_logged_game_progress < 0
                    or value - self._last_logged_game_progress >= GAME_PROGRESS_LOG_STEP):
                self._last_logged_game_progress = value
                install_log.info(
                    "DEPOT: %s progress %.1f%%", self._download_branch, value)
        with self._flush_lock:
            self._progress_dirty = True
        self._request_flush()

    @staticmethod
    def _i18n_status(key: str, values: dict | None = None) -> str:
        return i18n_message(key, values)

    def _set_status(self, value: str) -> None:
        self._status = value
        with self._flush_lock:
            self._status_dirty = True
        self._request_flush()

    def _set_qr(self, text: str, needs: bool) -> None:
        self._qr_text = text
        self._needs_qr = needs
        self._emit(self.qrChanged)

    def _rate_limit_remaining(self) -> int:
        return max(0, int(self._steam_rate_limit_until - time.monotonic() + 0.999))

    def _rate_limit_status(self) -> str:
        remaining = self._rate_limit_remaining()
        if remaining > 0:
            return self._i18n_status("gameVersions.status.rateLimit", {"seconds": remaining})
        return self._i18n_status("gameVersions.status.rateLimitSoon")

    def _read_proc_cmdline(self, pid: int) -> list[str]:
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except (OSError, ValueError):
            return []
        return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]

    def _managed_depot_processes(self, target: Path | None = None) -> list[tuple[int, list[str]]]:
        """Znajdź osierocone procesy DepotDownloader uruchomione przez managera.

        Nie korzystamy z `pgrep`/`subprocess.run`, ponieważ diagnostyka ma być
        bezpieczna nawet wtedy, gdy sam downloader właśnie się kończy. Proces
        uznajemy za nasz, jeśli jego executable/argv wskazuje na binarkę w
        `~/.7dtd_modmanager/tools` i ma `-dir` w katalogu managera. Gdy `target`
        jest podany, dopasowujemy dokładnie ten katalog pobierania.
        """
        proc_root = Path("/proc")
        if not proc_root.is_dir():
            return []
        tools_root = tools_dir().resolve(strict=False)
        wanted = target.resolve(strict=False) if target is not None else None
        result: list[tuple[int, list[str]]] = []
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            argv = self._read_proc_cmdline(pid)
            if not argv:
                continue
            argv0 = Path(argv[0]).expanduser().resolve(strict=False)
            if argv0.name.casefold() != "dep otdownloader".replace(" ", ""):
                continue
            # /proc/<pid>/exe może wskazywać na hosta .NET (np. /usr/bin/dotnet),
            # więc decydujący jest argv[0], który u nas zawiera właściwą ścieżkę
            # do ~/.7dtd_modmanager/tools/DepotDownloader.
            if tools_root not in argv0.parents:
                continue
            try:
                di = argv.index("-dir")
                raw_target = argv[di + 1]
            except (ValueError, IndexError):
                continue
            try:
                proc_target = Path(raw_target).expanduser().resolve(strict=False)
            except OSError:
                proc_target = Path(raw_target).expanduser()
            manager_root = fs.data_dir().resolve(strict=False)
            if manager_root not in proc_target.parents:
                continue
            if wanted is not None and proc_target != wanted:
                continue
            result.append((pid, argv))
        return result

    def _file_lock_holders(self, path: str) -> str:
        """Zwróć krótki opis procesów trzymających otwarty dany plik.

        Na Linuksie używamy ``fuser`` jako głównego źródła diagnostyki, bo
        potrafi wskazać dowolny proces, nie tylko DepotDownloader uruchomiony
        przez managera. Jeśli ``fuser`` nie jest dostępny, wracamy do /proc.
        Ta funkcja jest wywoływana po zatrzymaniu bieżącego downloadera, więc
        nie powinna raportować go jako blokującego plik.
        """
        if not path:
            return ""
        target = Path(path).expanduser()

        try:
            result = subprocess.run(
                ["fuser", "-v", "--", str(target)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
                check=False,
            )
            raw = (
                (getattr(result, "stdout", "") or "")
                + "\n"
                + (getattr(result, "stderr", "") or "")
            ).strip()
            if raw:
                # Fuser's verbose output is already useful in a log/toast.
                # Collapse whitespace so one bad path cannot create a huge row.
                compact = " ".join(raw.split())
                if compact:
                    return compact[:500]
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            pass

        lines: list[str] = []
        for pid, argv in self._managed_depot_processes(None):
            try:
                di = argv.index("-dir")
                proc_target = Path(argv[di + 1]).expanduser().resolve(strict=False)
                locked_path = target.resolve(strict=False)
            except (ValueError, IndexError, OSError):
                continue
            if proc_target != locked_path and proc_target not in locked_path.parents:
                continue
            lines.append(f"PID {pid}: {' '.join(argv)[:260]}")
        return " | ".join(lines)[:500]

    def _terminate_os_pid(self, pid: int, description: str = "DepotDownloader") -> bool:
        """Zatrzymaj konkretny PID: TERM, a po krótkim czasie KILL."""
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
        except PermissionError:
            logger.warning("No permission to terminate %s PID %s", description, pid)
            return False
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                break
            time.sleep(0.05)
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return True
        return True

    def _cleanup_stale_depot_processes(self, target: Path | None = None) -> int:
        """Usuń stare procesy managera blokujące pobieranie.

        Ta funkcja celowo nie zabija wszystkich DepotDownloaderów w systemie:
        tylko te uruchomione z naszego katalogu tools i wskazujące na katalog
        pobierania należący do managera.
        """
        killed = 0
        for pid, argv in self._managed_depot_processes(target):
            install_log.warning(
                "DEPOT: found stale DepotDownloader PID %s for target %s; terminating before download",
                pid, target or "manager data",
            )
            if self._terminate_os_pid(pid):
                killed += 1
        if killed:
            install_log.info("DEPOT: cleaned %d stale DepotDownloader process(es)", killed)
        return killed

    def _stop_subprocess(self, process) -> None:
        """Zatrzymaj bieżący downloader i jego dzieci bez zawieszania workera."""
        if process is None:
            return
        try:
            poll = getattr(process, "poll", None)
            if poll is not None and poll() is not None:
                return
        except (OSError, AttributeError):
            return

        pid = getattr(process, "pid", None)
        terminated_by_group = False
        if pid:
            try:
                # Popen(..., start_new_session=True) daje downloaderowi własną
                # grupę procesów. Zabijamy całą grupę, żeby np. procesy .NET
                # trzymające stdout/stderr nie pozostawiały workera wiszącego.
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                terminated_by_group = True
            except (OSError, ProcessLookupError):
                pass

        if not terminated_by_group:
            try:
                process.terminate()
            except (OSError, ProcessLookupError, AttributeError):
                return

        try:
            process.wait(timeout=1.5)
            return
        except TypeError:
            # Minimal test doubles may expose wait() without timeout.
            try:
                process.wait()
            except Exception:
                pass
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            if pid:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
            else:
                kill = getattr(process, "kill", None)
                if kill is not None:
                    kill()
        except (OSError, ProcessLookupError, AttributeError):
            pass

        try:
            process.wait(timeout=1.0)
        except TypeError:
            try:
                process.wait()
            except Exception:
                pass
        except subprocess.TimeoutExpired:
            pass

    def _terminate_process(self) -> None:
        """Przerwij bieżący DepotDownloader, a jeśli trzeba wymuś KILL."""
        with self._lock:
            process = self._process
        self._stop_subprocess(process)

    def _reset_download_staging(self, target: Path | None) -> bool:
        """Wyczyść tylko staging nieukończonych plików DepotDownloadera."""
        if target is None or self._download_staging_reset_done:
            return False
        staging = target / ".DepotDownloader" / "staging"
        if not staging.exists():
            self._download_staging_reset_done = True
            return False
        try:
            shutil.rmtree(staging)
            staging.mkdir(parents=True, exist_ok=True)
            self._download_staging_reset_done = True
            install_log.warning("DEPOT: cleaned staging of incomplete files: %s", staging)
            return True
        except OSError as exc:
            install_log.warning("DEPOT: failed to clean staging %s: %s", staging, exc)
            return False

    def _consume_line(self, raw: str) -> None:
        """Parsuje stdout DepotDownloadera.

        Aktualny DepotDownloader wypisuje osobny komunikat
        ``The QR code has changed:`` przed każdym odświeżeniem challenge URL,
        a następnie ponownie ``Use the Steam Mobile App...`` i cały nowy
        obraz ASCII. Czyścimy więc poprzednią ramkę na oba sygnały.
        """
        # Surowy stdout DepotDownloadera potrafi zawierać tysiące linii
        # walidacji/progresu. Nie zapisujemy go na poziomie INFO do stałego
        # installs.log - szczegóły trafiają do zwykłego debugowania procesu.
        install_log.debug("DEPOT: %s", raw[:400])
        lower = raw.lower()

        # Po udanym QR DepotDownloader sam wypisuje nazwę konta. To jest
        # właśnie login potrzebny przy kolejnych uruchomieniach z pamiętaną
        # sesją (-username ... -remember-password). Nie przechowujemy hasła
        # ani tokenu w danych aplikacji.
        success = AUTH_SUCCESS_RE.search(raw)
        if success:
            username = success.group(1).strip().strip('"\'')
            if username:
                # Sam komunikat "Success!" nie wystarcza: DepotDownloader może
                # chwilę później zakończyć InitializeSteam błędem. Zapisujemy
                # login i emitujemy accountConnected dopiero po exit code == 0.
                self._pending_username = username
                self._set_status(
                    self._i18n_status("gameVersions.status.loginConfirmed", {"username": username})
                )
            return

        # Nie zapisujemy loginu z samego komunikatu "Logging ... into Steam3".
        # Ten komunikat może wystąpić przed faktycznym zalogowaniem; zapisujemy
        # go tylko jako kandydata i zatwierdzimy dopiero po udanym zakończeniu
        # procesu. Dzięki temu anulowanie QR nie tworzy pozornego połączenia.
        login = AUTH_LOGIN_RE.search(raw)
        if login:
            username = login.group(1).strip()
            if username:
                self._pending_username = username
            if self._auth_succeeded:
                self._set_status(self._i18n_status("gameVersions.status.loginSuccess", {"username": username}))
            return

        # Steam odświeża challenge URL w tle. Ten komunikat pojawia się PRZED
        # nowym kodem QR i jest pewniejszym miejscem do wyczyszczenia starego.
        if "the qr code has changed" in lower:
            self._qr_lines = []
            self._set_qr("", True)
            install_log.info("AUTH: DepotDownloader refreshed the QR code")
            self._set_status(self._i18n_status("gameVersions.status.qrRefresh"))
            return

        if "use the steam mobile app to sign in with this qr code" in lower:
            self._qr_lines = []
            self._set_qr("", True)
            install_log.info("AUTH: received Steam QR code")
            self._set_status(self._i18n_status("gameVersions.status.qrScan"))
            return

        if "access token was rejected" in lower:
            # DepotDownloader sam usuwa odrzucony token. Lokalnie kasujemy
            # tylko zapamiętany login, żeby aplikacja nie udawała połączenia.
            clear_steam_username()
            self._steam_username = ""
            self._session_invalid = True
            self._emit(self.changed)
            self._set_status(self._i18n_status("gameVersions.status.sessionExpired"))
            return

        if "ratelimitexceeded" in lower:
            self._steam_rate_limited = True
            self._steam_rate_limit_until = max(
                self._steam_rate_limit_until,
                time.monotonic() + STEAM_RATE_LIMIT_COOLDOWN,
            )
            install_log.warning(
                "AUTH: Steam returned RateLimitExceeded; stopping DepotDownloader"
            )
            self._set_status(self._rate_limit_status())
            self._terminate_process()
            return

        # Zerowanie licznika po otrzymaniu poprawnego manifestu sprawia, że
        # pojedynczy timeout nie przesądza o porażce, ale trzy kolejne błędy
        # manifestu kończą wewnętrzną pętlę DepotDownloadera.
        if re.search(r"\bmanifest \d+ \(", lower):
            self._manifest_error_count = 0
            if self._download_branch:
                install_log.info("DEPOT: %s manifest received", self._download_branch)

        manifest_error = (
            "encountered error downloading manifest for depot" in lower
            or "connection timeout downloading depot manifest" in lower
        )
        if manifest_error:
            self._manifest_error_count += 1
            install_log.warning(
                "DEPOT: manifest download error %d/%d: %s",
                self._manifest_error_count,
                MANIFEST_ERROR_REPEAT_LIMIT,
                raw[:240],
            )

            if self._manifest_error_count >= MANIFEST_ERROR_REPEAT_LIMIT:
                self._manifest_failure_storm = True
                self._set_status(self._i18n_status("gameVersions.status.manifestStorm"))
                self._terminate_process()
            return

        match = PROGRESS_RE.search(raw)
        if match:
            self._set_progress(min(100.0, float(match.group(1))))
            tail = raw[match.end():].strip(" ->")
            self._set_status(self._i18n_status("gameVersions.status.downloadingFile", {"file": Path(tail).name})
                             if tail else raw.strip()[:120])
            return

        if "pre-allocating" in lower:
            tail = raw.split("Pre-allocating", 1)[-1].strip()
            self._set_status(self._i18n_status("gameVersions.status.preparing", {"file": Path(tail).name or "files"}))
            return

        if any(ch in QR_CHARS for ch in raw):
            self._qr_lines.append(raw)
            self._set_qr("\n".join(self._qr_lines), True)
            return

        # DepotDownloader 3.x can abort a download because a single content
        # chunk fails with a transient HTTP/stream error. Mark these exact
        # download errors as retryable so _run_depot can rerun the same
        # destination and continue the incomplete download.
        file_lock_error = (
            "being used by another process" in lower
            or "cannot access the file" in lower
            or "sharing violation" in lower
        )
        if file_lock_error and self._download_branch:
            self._download_file_lock_error = True
            path_match = re.search(
                r"file ['\"]([^'\"]+)['\"] because it is being used",
                raw, re.IGNORECASE)
            if path_match:
                self._download_file_lock_path = path_match.group(1)
            self._set_status(self._i18n_status("gameVersions.status.fileLocked"))
            # Najpierw ubij bieżącego DepotDownloadera. Dopiero potem diagnozuj
            # fuserem, kto nadal trzyma plik, żeby nie wskazać przypadkiem
            # właśnie kończącego się procesu jako winowajcy.
            self._terminate_process()
            holder = self._file_lock_holders(self._download_file_lock_path)
            install_log.warning(
                "DEPOT: %s file is locked by another process: %s%s",
                self._download_branch,
                self._download_file_lock_path or raw[:240],
                f"; holder={holder}" if holder else "",
            )
            return

        retryable_markers = (
            "error while copying content to a stream",
            "unexpected error downloading chunk",
            "error downloading chunk",
            "connection timeout downloading chunk",
            "serviceunavailable",
            "internalservererror",
            "temporarily unavailable",
        )
        if self._download_branch and any(marker in lower for marker in retryable_markers):
            self._download_retryable_error = True
            self._last_download_chunk_error = raw.strip()[:1000]
            self._set_status(self._i18n_status("gameVersions.status.transientRetry"))
            install_log.warning(
                "DEPOT: %s transient chunk error; stopping the process before automatic retry: %s",
                self._download_branch, raw[:240],
            )
            self._terminate_process()
            return

        # Słowa kluczowe tylko jako całe słowa i nigdy w liniach "Validating
        # <plik>" - inaczej "terrOreCoal.png" ("terrore...") łapie "error".
        if not lower.lstrip().startswith("validating ") \
                and re.search(r"\b(error|failed)\b", lower):
            message = raw.strip()[:1000]
            install_log.error("DEPOT: %s: %s", self._download_branch or "auth", message)
            self._set_status(message[:200])

    def _run_depot(self, cmd: list[str], branch: str,
                   finish_status: str) -> str:
        """Wspólny przebieg DepotDownloadera (download / auth).

        Dla pobierania gry ponawiamy automatycznie przejściowe błędy
        pojedynczych chunków. DepotDownloader zapisuje już pobrane dane w
        katalogu docelowym, więc kolejne uruchomienie tej samej komendy może
        dokończyć przerwany download; retry nie wykonuje kosztownej pełnej
        walidacji katalogu. Przy błędzie streamu downloader jest przełączany na
        starszą wersję, zamiast czekać na jego wewnętrzne retry. Autoryzacja QR nie jest automatycznie
        ponawiana.

        Zwraca pusty string dla poprawnego zakończenia lub anulowania oraz
        komunikat błędu dla faktycznej porażki. Kod 143 po naszym terminate()
        nie jest błędem użytkownika.
        """
        error = ""
        self._qr_lines = []
        self._session_invalid = False
        self._steam_rate_limited = False
        self._manifest_error_count = 0
        self._manifest_failure_storm = False
        self._download_retryable_error = False
        self._last_download_chunk_error = ""
        self._previous_chunk_error = ""
        self._download_staging_reset_done = False
        self._chunk_fallback_index = 0
        self._primary_depot_binary = str(cmd[0]) if cmd else ""
        self._download_file_lock_error = False
        self._download_file_lock_path = ""
        if branch == "auth":
            self._pending_username = ""
            self._auth_succeeded = False

        attempt = 0
        file_lock_attempts = 0
        failure_detail = ""
        try:
            if branch != "auth":
                install_log.info(
                    "DEPOT: start branch=%s target=%s",
                    branch, cmd[cmd.index("-dir") + 1] if "-dir" in cmd else "?",
                )
            while True:
                self._download_retryable_error = False
                failure_detail = ""
                self._download_file_lock_error = False
                self._download_file_lock_path = ""
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    start_new_session=True)
                with self._lock:
                    self._process = process
                for line in process.stdout:
                    if self._cancel.is_set():
                        try:
                            process.terminate()
                        except OSError:
                            pass
                        break
                    raw = line.rstrip("\r\n")
                    if raw.strip():
                        # Wersje Alpha 6 mogą być blokowane przez Steam.
                        # Zachowaj ostatnią konkretną diagnozę z narzędzia,
                        # zamiast pokazywać tylko mało przydatny kod 1.
                        lowered = raw.casefold()
                        if any(mark in lowered for mark in (
                            "error", "failed", "access denied", "accessdenied",
                            "unauthorized", "not authorized", "not subscribed",
                            "no manifest", "no depot key", "forbidden",
                            "not available from this account", "no license", "401", "403",
                        )) and not lowered.startswith("validating "):
                            failure_detail = raw.strip()[:300]
                        self._consume_line(raw)
                process.wait()

                if self._cancel.is_set():
                    self._set_status(self._i18n_status("gameVersions.status.authCancelled" if branch == "auth" else "gameVersions.status.downloadCancelled"))
                    break

                if self._steam_rate_limited:
                    raise GameVersionsError(self._rate_limit_status())

                if self._manifest_failure_storm:
                    install_log.error(
                        "DEPOT: %s manifest retry storm stopped after %d errors",
                        branch, self._manifest_error_count,
                    )
                    raise GameVersionsError(
                        self._i18n_status("gameVersions.status.manifestFailed")
                    )

                if branch != "auth" and self._download_file_lock_error:
                    if file_lock_attempts < FILE_LOCK_RETRIES:
                        file_lock_attempts += 1
                        delay = FILE_LOCK_RETRY_DELAY * file_lock_attempts
                        self._set_status(
                            self._i18n_status("gameVersions.status.fileLockedRetry", {
                                "attempt": file_lock_attempts,
                                "max": FILE_LOCK_RETRIES,
                                "seconds": f"{delay:.0f}",
                            })
                        )
                        install_log.warning(
                            "DEPOT: %s file-lock retry %d/%d after %.1fs; path=%s",
                            branch, file_lock_attempts, FILE_LOCK_RETRIES, delay,
                            self._download_file_lock_path or "unknown",
                        )
                        # Nie uruchamiaj pełnej walidacji katalogu przy blokadzie pliku.
                        # Blokada jest problemem procesu, a nie sum kontrolnych; retry
                        # ma być szybki po zwolnieniu uchwytu.
                        if "-max-downloads" in cmd:
                            idx = cmd.index("-max-downloads")
                            if idx + 1 < len(cmd):
                                cmd[idx + 1] = "1"
                        if self._cancel.wait(delay):
                            self._set_status(self._i18n_status("gameVersions.status.downloadCancelled"))
                            break
                        target_raw = cmd[cmd.index("-dir") + 1] if "-dir" in cmd else ""
                        target_path = Path(target_raw).expanduser() if target_raw else None
                        cleaned = self._cleanup_stale_depot_processes(target_path)
                        holder = self._file_lock_holders(self._download_file_lock_path)
                        if holder:
                            install_log.warning(
                                "DEPOT: %s lock holder still present before retry: %s",
                                branch, holder,
                            )
                        elif cleaned:
                            self._set_status(self._i18n_status("gameVersions.status.staleSessionRetry"))
                        continue
                    locked = self._download_file_lock_path or "unknown file"
                    holder = self._file_lock_holders(locked)
                    install_log.error(
                        "DEPOT: %s file remains locked after %d retries: %s%s",
                        branch, FILE_LOCK_RETRIES, locked,
                        f"; holder={holder}" if holder else "",
                    )
                    holder_hint = holder if holder else ""
                    raise GameVersionsError(self._i18n_status("gameVersions.status.lockedFinal", {
                        "path": locked,
                        "holder": holder_hint.strip(),
                    }))

                if process.returncode != 0 and self._session_invalid:
                    raise GameVersionsError(self._i18n_status("gameVersions.status.sessionExpired"))

                # Auth is valid only after DepotDownloader itself exits with
                # status 0. The success message is only a pending candidate.
                if branch == "auth" and process.returncode == 0:
                    if not self._pending_username:
                        raise GameVersionsError(self._i18n_status("gameVersions.status.authNoUsername"))
                    username = self._pending_username
                    if not save_steam_username(username):
                        raise GameVersionsError(self._i18n_status("gameVersions.status.saveUsernameFailed"))
                    self._steam_username = username
                    self._auth_succeeded = True
                    self._emit(self.changed)
                    self._emit(self.accountConnected, username)
                    self._set_status(finish_status)
                    break

                # A transient chunk/stream error is retryable even if a future
                # DepotDownloader build happens to return exit code 0 after logging it.
                if branch != "auth" and self._download_retryable_error:
                    if attempt < DOWNLOAD_MAX_RETRIES:
                        attempt += 1
                        delay = min(DOWNLOAD_RETRY_DELAY * (2 ** (attempt - 1)),
                                    DOWNLOAD_RETRY_MAX_DELAY)
                        target_raw = cmd[cmd.index("-dir") + 1] if "-dir" in cmd else ""
                        target_path = Path(target_raw).expanduser() if target_raw else None

                        # Nie włączaj kosztownego -validate na każdym retry.
                        # Przy starej wersji ~7 GB potrafi to oznaczać długą pełną
                        # walidację po każdym błędzie, mimo że brakuje tylko jednego
                        # chunka. Pierwszy retry zachowuje normalną równoległość,
                        # a następne schodzą do jednego pobieranego chunka.
                        # Po pierwszym błędzie chunku od razu schodzimy do jednego
                        # równoległego pobierania. To ogranicza liczbę jednoczesnych
                        # połączeń podczas ponownego pobierania dokładnie tego
                        # brakującego fragmentu i jest też deterministyczne dla retry.
                        if "-max-downloads" in cmd:
                            idx = cmd.index("-max-downloads")
                            if idx + 1 < len(cmd):
                                cmd[idx + 1] = "1"
                        else:
                            cmd.extend(["-max-downloads", "1"])

                        repeated_chunk = (
                            bool(self._last_download_chunk_error)
                            and self._last_download_chunk_error == self._previous_chunk_error
                        )
                        staging_reset = False
                        fallback_switched = False

                        # 3.4.0 ma otwarty upstreamowy problem dotyczący dokładnie
                        # "Error while copying content to a stream". Nie czekamy na
                        # drugi minutowy cykl tego samego chunka: pierwszy błąd streamu
                        # przełącza nas od razu na starszy downloader. Kolejne identyczne
                        # błędy przechodzą po następnych wersjach fallbacku.
                        fallback_version = None
                        should_fallback = bool(self._last_download_chunk_error) and bool(self._primary_depot_binary)
                        if should_fallback and self._chunk_fallback_index < len(DEPOTDOWNLOADER_FALLBACK_VERSIONS):
                            fallback_version = DEPOTDOWNLOADER_FALLBACK_VERSIONS[self._chunk_fallback_index]
                            self._chunk_fallback_index += 1
                        if fallback_version:
                            try:
                                fallback = ensure_fallback_tool(fallback_version)
                                cmd[0] = str(fallback)
                                fallback_switched = True
                                # Fallback po błędzie streamu ma nadal działać z jednym
                                # równoległym pobieraniem. Nie wracamy tu do 4, bo właśnie
                                # zmniejszenie współbieżności jest jednym z mechanizmów
                                # diagnostycznych tego retry.
                                if "-max-downloads" in cmd:
                                    idx = cmd.index("-max-downloads")
                                    if idx + 1 < len(cmd):
                                        cmd[idx + 1] = "1"
                                else:
                                    cmd.extend(["-max-downloads", "1"])
                                # Przejście na inną wersję downloadera ma sens bez
                                # pełnej walidacji całego katalogu.
                                cmd = [x for x in cmd if x != "-validate"]
                                install_log.warning(
                                    "DEPOT: %s repeated chunk failure; switching to DepotDownloader %s",
                                    branch, fallback_version,
                                )
                            except Exception as exc:  # noqa: BLE001
                                install_log.warning(
                                    "DEPOT: %s fallback DepotDownloader %s unavailable: %s",
                                    branch, fallback_version, exc,
                                )

                        # Jeśli starszy fallback też zwróci identyczny błąd,
                        # wyczyść jego staging i wróć do aktualnego narzędzia
                        # na ostatnie próby.
                        if (repeated_chunk and not fallback_switched
                                and self._chunk_fallback_index >= len(DEPOTDOWNLOADER_FALLBACK_VERSIONS)):
                            staging_reset = self._reset_download_staging(target_path)
                            if self._download_staging_reset_done and not staging_reset:
                                raise GameVersionsError(self._i18n_status("gameVersions.status.lastChunkRetry"))

                        self._previous_chunk_error = self._last_download_chunk_error

                        if fallback_switched:
                            key = "gameVersions.status.retryingFallback"
                        elif staging_reset:
                            key = "gameVersions.status.refreshingStaging"
                        elif attempt == 1:
                            key = "gameVersions.status.retryingLimited"
                        else:
                            key = "gameVersions.status.retrying"
                        self._set_status(self._i18n_status(key, {
                            "attempt": attempt, "max": DOWNLOAD_MAX_RETRIES, "seconds": f"{delay:.0f}"
                        }))
                        install_log.warning(
                            "DepotDownloader transient chunk error for %s; retry %d/%d after %.1fs "
                            "(tool=%s, max-downloads=%s, validate=%s, staging-reset=%s, exit=%s)",
                            branch, attempt, DOWNLOAD_MAX_RETRIES, delay,
                            Path(cmd[0]).name if cmd else "?",
                            (cmd[cmd.index("-max-downloads") + 1]
                             if "-max-downloads" in cmd and cmd.index("-max-downloads") + 1 < len(cmd)
                             else "?"),
                            "-validate" in cmd, staging_reset, process.returncode)
                        if self._cancel.wait(delay):
                            self._set_status(self._i18n_status("gameVersions.status.downloadCancelled"))
                            break
                        continue
                    raise GameVersionsError(self._i18n_status("gameVersions.status.chunkFinal", {
                        "retries": DOWNLOAD_MAX_RETRIES,
                        "detail": self._last_download_chunk_error or "",
                    }))

                if process.returncode != 0:
                    install_log.error(
                        "DEPOT: %s exited with code %s; detail=%s",
                        branch, process.returncode, failure_detail or "none")
                    key = ("gameVersions.status.depotExitDetail" if failure_detail
                           else "gameVersions.status.depotExit")
                    details = {"code": process.returncode, "detail": failure_detail}
                    self._set_status(self._i18n_status(key, details))
                    raise GameVersionsError(self._i18n_status(key, details))

                install_log.info("DEPOT: %s completed successfully", branch)
                self._set_status(finish_status)
                break
        except GameVersionsError as exc:
            error = str(exc)
            self._set_status(error)
        except Exception as exc:  # noqa: BLE001
            logger.exception("DepotDownloader run failed")
            error = str(exc)
            self._set_status(self._i18n_status("gameVersions.status.genericError", {"error": str(exc)}))
        finally:
            with self._lock:
                self._process = None
            self._set_busy(False)
            self._set_qr("", False)
            self._emit(self.changed)
            self._emit(self.finished, branch, error)
        return error

    @Slot(str, result=str)
    def downloadSource(self, branch: str) -> str:
        source = manifest_source(branch)
        if source:
            return f"Steam · Depot {source['depot']} · manifest {source['manifest']}"
        entry = RELEASE_BY_BRANCH.get(branch)
        if entry and not entry.steam_branch:
            return f"Steam · Depot {entry.depot} · manifest {entry.manifest}"
        return f"Steam · branch {branch} · Depot {DEPOT_ID}"

    def is_installed(self, branch: str) -> bool:
        """Czy kompletna kopia brancha (lub jego grupy, np. v2 -> v2.6)
        naprawdę istnieje na dysku.

        Rejestr JSON jest tylko cache'em metadanych. Launcher nie może uznać
        wersji za zainstalowaną, jeśli użytkownik usunął katalog ręcznie albo
        pobieranie zakończyło się częściowym stanem.
        """
        return bool(resolve_downloaded_branch(branch))

    def installed_path(self, branch: str) -> Path | None:
        resolved = resolve_downloaded_branch(branch)
        return versions_root() / resolved if resolved else None

    # ---------------- slots ---------------- #
    @Slot(str, result=bool)
    def downloadCode(self, code: str) -> bool:
        try:
            branch = branch_for_depot_code(code)
        except (GameVersionsError, ValueError) as exc:
            self._set_status(str(exc))
            return False
        return self.download(branch)

    @Slot()
    def refreshAvailable(self) -> None:
        """Lista branchy (wersji gry) z publicznego API steamcmd."""
        if time.time() - self._available_time < BRANCH_CACHE_TTL \
                and self._available:
            return
        def worker():
            try:
                resp = requests.get(STEAMCMD_API, timeout=(10, 30))
                resp.raise_for_status()
                data = resp.json().get("data", {})
                branches = data.get(APP_ID, {}).get("depots", {}) \
                    .get("branches", {})
                manifests = data.get(APP_ID, {}).get("depots", {}) \
                    .get(DEPOT_ID, {}).get("manifests", {})
                items = []
                for name, info in branches.items():
                    if not isinstance(info, dict):
                        continue
                    manifest = manifests.get(name, {}) or {}
                    items.append({
                        "branch": name,
                        "buildid": str(info.get("buildid", "")),
                        "size_bytes": int(manifest.get("size", 0) or 0),
                    })
                # Release families and numeric versions, newest first.
                items.sort(key=lambda i: branch_sort_key(i["branch"]), reverse=True)
                self._available = items
                self._available_time = time.time()
                self._emit(self.changed)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Branch list fetch failed: %s", exc)
                self._set_status(self._i18n_status("gameVersions.status.listFailed", {"error": str(exc)}))
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, result=bool)
    def download(self, branch: str) -> bool:
        """Pobierz lub wznów brakującą wersję gry."""
        return self._start_download(branch, reinstall=False)

    @Slot(str, result=bool)
    def reinstall(self, branch: str) -> bool:
        """Pobierz świeżą kopię bez zmieniania obecnej aż do sukcesu."""
        return self._start_download(branch, reinstall=True)

    def _start_download(self, branch: str, reinstall: bool = False) -> bool:
        branch = required_game_branch((branch or "").strip())
        if not branch or self._busy:
            return False
        try:
            source = manifest_source(branch)
        except (GameVersionsError, ValueError) as exc:
            self._set_status(str(exc))
            return False
        if source and source["depot"] == "251574":
            self._set_status(self._i18n_status("steamReleases.legacy.downloadUnavailable", {
                "branch": branch, "depot": source["depot"],
            }))
            return False
        release = RELEASE_BY_BRANCH.get(branch)
        if release and not release.download_available:
            self._set_status(self._i18n_status("steamReleases.legacy.downloadUnavailable", {
                "branch": branch, "depot": release.depot,
            }))
            return False
        installed = self.is_installed(branch)
        if installed and not reinstall:
            self._set_status(self._i18n_status("gameVersions.status.alreadyDownloaded", {"branch": branch}))
            return False
        record = next((v for v in load_versions() if v.get("branch") == branch), None)
        if reinstall and (not installed or record is None):
            self._set_status(self._i18n_status("steamReleases.reinstallUnavailable"))
            return False
        if record and record.get("origin") == "imported" and reinstall:
            self._set_status(self._i18n_status("steamReleases.reinstallImported"))
            return False
        if self._rate_limit_remaining() > 0:
            self._set_status(self._rate_limit_status())
            return False
        try:
            binary = ensure_tool()
        except Exception as exc:  # noqa: BLE001
            self._set_status(self._i18n_status("gameVersions.status.toolFailed", {"error": str(exc)}))
            return False

        installed_target = versions_root() / branch
        target = reinstall_stage(branch) if reinstall else installed_target
        if target.is_symlink() or installed_target.is_symlink() and not reinstall:
            self._set_status(self._i18n_status("steamReleases.reinstallImported"))
            return False
        # Po awaryjnym zamknięciu aplikacji DepotDownloader może przeżyć jako
        # sierota i dalej trzymać pliki. Przed nowym pobraniem nie zostawiamy
        # żadnego starego procesu należącego do tego managera.
        self._cleanup_stale_depot_processes()
        fs.ensure_dir(target)
        username = self._steam_username.strip()
        use_qr = not has_saved_session(username)
        legacy = RELEASE_BY_BRANCH.get(branch)
        cmd = build_download_command(binary, branch, target, username, use_qr)

        total_bytes = 0
        for item in self._available:
            if str(item.get("branch", "")) == branch:
                try:
                    total_bytes = max(0, int(item.get("size_bytes", 0) or 0))
                except (TypeError, ValueError):
                    total_bytes = 0
                break

        self._download_branch = branch
        self._reinstall_branch = branch if reinstall else ""
        self._last_game_progress = -1.0
        self._last_logged_game_progress = -1.0
        self._set_busy(True)
        self._set_progress(0.0)
        self._set_qr("", use_qr)
        self._set_status(self._i18n_status("gameVersions.status.downloadingQr" if use_qr else "gameVersions.status.downloading", {"branch": branch}))
        self._cancel.clear()
        self._pause_requested.clear()
        self._emit(self.changed)
        self._emit(self.gameDownloadStarted, branch, total_bytes)

        def worker():
            try:
                error = self._run_depot(cmd, branch, self._i18n_status("gameVersions.status.downloadFinished", {"branch": branch}))
                paused = self._pause_requested.is_set()
                cancelled = self._cancel.is_set() and not paused
                if paused:
                    self._emit(self.gameDownloadFinished, branch, "paused", "")
                    return False
                if cancelled:
                    self._emit(self.gameDownloadFinished, branch, "cancelled", "")
                    return False
                if error:
                    self._emit(self.gameDownloadFinished, branch, "failed", error)
                    return False
                # AppID musi być widoczny dla uruchamiania kopii przez Proton.
                appid_file = target / "steam_appid.txt"
                if not appid_file.exists():
                    appid_file.write_text(APP_ID + "\n", encoding="utf-8")
                if not _game_files_look_complete(target):
                    raise GameVersionsError(self._i18n_status("steamReleases.incompleteDownload"))
                if reinstall:
                    _replace_version_after_download(branch, target, installed_target)
                versions = [v for v in load_versions() if v.get("branch") != branch]
                versions.append({
                    "branch": branch,
                    "dir": str(installed_target),
                    "size_bytes": dir_size(installed_target),
                    "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "origin": "steam_manifest" if source or legacy and not legacy.steam_branch else "steam_branch",
                    "app_id": APP_ID,
                    "depot": source["depot"] if source else legacy.depot if legacy and not legacy.steam_branch else DEPOT_ID,
                    "manifest": source["manifest"] if source else legacy.manifest if legacy and not legacy.steam_branch else "",
                })
                save_versions(versions)
                self._versions = versions
                self._emit(self.changed)
                self._emit(self.gameDownloadFinished, 
                    branch, "completed", self._i18n_status("gameVersions.status.downloadFinished", {"branch": branch}))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Game version download bookkeeping failed")
                self._emit(self.gameDownloadFinished, branch, "failed", str(exc))
            finally:
                self._download_branch = ""
                self._reinstall_branch = ""
                self._last_game_progress = -1.0
                self._last_logged_game_progress = -1.0
                with self._lock:
                    if self._worker_thread is threading.current_thread():
                        self._worker_thread = None
                self._emit(self.changed)

        self._worker_thread = threading.Thread(target=worker, daemon=True, name=f"DepotDownload-{branch}")
        self._worker_thread.start()
        return True

    @Slot()
    def startAuth(self) -> None:
        """Uruchamia autoryzację Steam Guard QR, gdy nie ma zapamiętanego konta."""
        self._start_auth(False)

    @Slot()
    def reauthorize(self) -> None:
        """Wymusza nowe logowanie QR (np. przełączenie konta)."""
        self._start_auth(True)

    def _start_auth(self, force: bool) -> None:
        if self._busy:
            return
        if self._rate_limit_remaining() > 0:
            self._set_status(self._rate_limit_status())
            return
        if not force and has_saved_session(self._steam_username):
            self._set_status(self._i18n_status("gameVersions.status.connected", {"username": self._steam_username}))
            return
        try:
            binary = ensure_tool()
        except Exception as exc:  # noqa: BLE001
            self._set_status(self._i18n_status("gameVersions.status.toolFailed", {"error": str(exc)}))
            return

        self._cleanup_stale_depot_processes()
        auth_dir = fs.ensure_dir(tools_dir() / "auth")
        cmd = [
            str(binary),
            "-app", APP_ID,
            "-depot", DEPOT_ID,
            "-branch", "public",
            "-os", "windows",
            "-osarch", "64",
            "-dir", str(auth_dir),
            "-manifest-only",
            "-remember-password",
            "-loginid", str(new_login_id()),
            "-qr",
        ]
        self._set_busy(True)
        self._set_progress(0.0)
        self._set_qr("", True)
        self._set_status(self._i18n_status("gameVersions.status.qrScan"))
        self._cancel.clear()

        def worker():
            try:
                self._run_depot(cmd, "auth", self._i18n_status("gameVersions.status.authFinished"))
                # Liczymy wyłącznie faktycznie potwierdzone QR. Sam zapisany
                # steam-account.json nie może oznaczać sukcesu anulowanej próby.
                if self._auth_succeeded and has_saved_session(self._steam_username):
                    self._set_status(
                        self._i18n_status("gameVersions.status.connectedSaved", {"username": self._steam_username})
                    )
                    install_log.info(
                        "AUTH: Steam session saved for %s", self._steam_username
                    )
                    self._emit(self.changed)
                elif not self._cancel.is_set():
                    install_log.info(
                        "AUTH: authorization was not confirmed"
                    )
            finally:
                shutil.rmtree(auth_dir, ignore_errors=True)
                with self._lock:
                    if self._worker_thread is threading.current_thread():
                        self._worker_thread = None
                self._emit(self.changed)

        self._worker_thread = threading.Thread(target=worker, daemon=True, name="DepotAuth")
        self._worker_thread.start()

    @Slot()
    def logout(self) -> None:
        """Wyloguj konto zapamiętane przez launcher.

        Launcher przechowuje osobno wyłącznie nazwę użytkownika, która steruje
        stanem UI. Właściwe dane sesji DepotDownloadera pozostają poza
        profilem aplikacji i nie są kasowane w ciemno z nieznanej lokalizacji.
        Po wylogowaniu następne użycie pobierania uruchomi ponownie logowanie
        Steam Guard przez QR.
        """
        clear_steam_username()
        self._steam_username = ""
        self._pending_username = ""
        self._session_invalid = False
        self._set_status(self._i18n_status("gameVersions.status.loggedOut"))
        self._emit(self.changed)

    @Slot(str)
    def setSteamUsername(self, username: str) -> None:
        """Zapisuje login Steam dla istniejącej sesji DepotDownloadera.

        Przydaje się przy imporcie sesji utworzonej wcześniej przez zewnętrzny
        skrypt. Token pozostaje wyłącznie w magazynie DepotDownloadera.
        """
        username = (username or "").strip()
        if not username:
            return
        if username == self._steam_username:
            self._emit(self.changed)
            return
        if save_steam_username(username):
            self._steam_username = username
            self._set_status(self._i18n_status("gameVersions.status.loginSaved", {"username": username}))
            self._emit(self.changed)

    @Slot()
    def pause(self) -> None:
        """Wstrzymaj pobieranie gry, zachowując dane DepotDownloadera."""
        if not self._busy or not self._download_branch:
            return
        self._pause_requested.set()
        self._cancel.set()
        threading.Thread(
            target=self._terminate_process,
            daemon=True,
            name="DepotPause",
        ).start()

    @Slot(str, result=bool)
    def resume(self, branch: str) -> bool:
        """Wznów pobieranie brancha z istniejącego stagingu na dysku."""
        branch = required_game_branch((branch or "").strip())
        if not branch or self._busy:
            return False
        return self.download(branch)

    @Slot()
    def cancel(self) -> None:
        """Przerwij bieżące pobieranie/autoryzację bez blokowania GUI."""
        self._pause_requested.clear()
        self._cancel.set()
        # Nie czekamy na wait() w wątku GUI. Sam worker zobaczy _cancel, a
        # osobny krótki worker sprzątnie grupę procesów DepotDownloadera.
        threading.Thread(
            target=self._terminate_process,
            daemon=True,
            name="DepotCancel",
        ).start()

    def shutdown(self) -> None:
        """Bezpiecznie zakończ worker i nie zostawiaj DepotDownloadera po app.quit()."""
        self._cancel.set()
        self._terminate_process()
        with self._lock:
            worker = self._worker_thread
            branch = self._download_branch
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=4.0)
        # Jeśli worker nie zdążył zejść z powodu zewnętrznego downloadera,
        # ponowny cleanup po jego zakończeniu chroni nas przed sierotą.
        target = versions_root() / branch if branch else None
        self._cleanup_stale_depot_processes(target)

    @Slot(str, str, str, result=str)
    def importVersion(self, folder: str, branch: str, custom_name: str) -> str:
        if self._busy:
            return self._i18n_status("steamReleases.legacy.error.busy")
        try:
            record = import_game_version(folder, branch, custom_name)
        except (OSError, ValueError, GameVersionsError) as exc:
            message = self._i18n_status("steamReleases.legacy.error.importFailed", {"error": str(exc)})
            self._set_status(message)
            return message
        self._versions = load_versions()
        self._set_status(self._i18n_status("steamReleases.legacy.importSuccess", {"branch": record["branch"]}))
        self._emit(self.changed)
        return ""

    @Slot(str)
    def deleteVersion(self, branch: str) -> None:
        """Usuwa wpis i własny katalog, nigdy zewnętrzne pliki importu."""
        branch = (branch or "").strip()
        record = next((v for v in self._versions if v.get("branch") == branch), None)
        if record is None or self._busy:
            return
        root = versions_root()
        target = root / branch
        # Nie pozwalaj metadanym JSON zmienić celu usuwania.
        if branch in ("", ".", "..") or "/" in branch or "\\" in branch:
            return
        recorded = Path(str(record.get("dir", "")))
        if recorded != target:
            logger.warning("Refusing unsafe game version deletion: %s", recorded)
            return
        if target.is_symlink():
            target.unlink()
        elif record.get("origin") == "imported":
            # Uszkodzony wpis importu nie powinien nigdy kasować danych.
            logger.warning("Imported version is no longer a link: %s", target)
            return
        elif target.is_dir():
            shutil.rmtree(target)
        self._versions = [v for v in self._versions if v.get("branch") != branch]
        save_versions(self._versions)
        self._emit(self.changed)
