"""Pobieranie modpacków z sieci - port rdzenia starego projektu
(7dtd-mod-manager/downloads.py, etap 5 migracji) z dwiema świadomymi
zmianami:

1. PAUZA/WZNOWIENIE: pobrania HTTP (bezpośredni ZIP i assety release'ów
   GitHub) wspierają pauzę - strumień jest zamykany, plik *.part zostaje
   w katalogu tymczasowym, a po wznowieniu żądanie idzie z nagłówkiem
   HTTP Range (serwer bez wsparcia Range odpowie 200 = start od zera).
   git clone NIE wspiera pauzy (tylko anuluj/ponów - klon zawsze od
   zera); pauza sygnalizowana jest wyjątkiem DownloadPaused.
2. BEZ INSTALACJI DO GRY: stary install_modpack_to_game (destrukcyjny
   replace/merge katalogu Mods gry) NIE jest portowany - w Modelu A
   pobrany modpack trafia do Biblioteki przez
   library_ops.install_modpack_to_library() (addytywnie, z dedupem),
   a co jest aktywne w grze decyduje wyłącznie aktywacja.

Obsługiwane źródła (detect_source_kind, kryteria 1:1 ze starym projektem):
- repozytorium Git (GitHub, Azure DevOps, GitLab, Codeberg, ...) -> git clone
- strona GitHub /releases -> najnowszy release przez GitHub API (asset .zip
  albo zipball)
- bezpośredni link do pliku .zip (w tym publiczny eksport ZIP z Azure DevOps Git Items API)
NexusMods i strony-listingi (7daystodiemods.com) są świadomie
NIEOBSŁUGIWANE tu - 7daystodiemods.com dojdzie w module 9 (modscraper).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import http.cookiejar
import urllib.error
import urllib.request
from services.i18n_message import message as i18n_message
from backend.undead_legacy import MIRROR_URL
import zipfile
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from backend.fileops import (
    InsufficientDiskSpace,
    OperationCancelled,
    ProgressCallback,
    check_cancel,
    ensure_free_space,
    raise_if_no_space,
)
from backend.modinfo import find_modinfo

USER_AGENT = "mod-manager/1.0 (+7 Days to Die mod manager)"
REQUEST_TIMEOUT = 20
_CHUNK_SIZE = 262144  # 256 KB


class DownloadError(Exception):
    """Błąd pobierania lub przygotowania modpacka do instalacji."""


class DownloadPaused(Exception):
    """Sygnał kontrolny: pobieranie HTTP wstrzymane na żądanie (pauza).
    Plik *.part pozostaje na dysku - wznowienie korzysta z HTTP Range."""


# --- Rozpoznawanie typu źródła i walidacja URL (1:1 ze starym projektem) ---

class DownloadSourceKind(Enum):
    GIT_REPO = "git_repo"                # klonowalne repo (GitHub/Azure DevOps/GitLab/...)
    GITHUB_RELEASES = "github_releases"  # .../releases (bez konkretnego tagu) -> GitHub API
    DIRECT_ZIP = "direct_zip"            # bezpośredni link do pliku .zip
    UNDEAD_LEGACY_MIRROR = "undead_legacy_mirror"  # stable redirect -> current ZIP
    UNSUPPORTED = "unsupported"          # np. NexusMods albo strona-witryna - nieobsługiwane


_GITHUB_RELEASES_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/releases/?($|/tag/)")
_GITHUB_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(\.git)?/?$")
_AZURE_REPO_RE = re.compile(r"^https?://dev\.azure\.com/[^/]+/(?:[^/]+/)?_git/[^/]+/?$")
_NEXUSMODS_RE = re.compile(r"^https?://(www\.)?nexusmods\.com/", re.IGNORECASE)


def _is_azure_items_zip_url(url: str) -> bool:
    """Return True for the Azure DevOps Git Items API ZIP export.

    Azure exposes repository snapshots as URLs such as::

        https://dev.azure.com/org/project/_apis/git/repositories/<repo>/items
            ?path=/&...&%24format=zip&download=true

    These links do not end in ``.zip`` because ``zip`` is selected by the
    ``$format=zip`` query parameter, so suffix-only URL detection misses them.
    Public repository exports can be downloaded with the regular HTTP ZIP
    downloader; private repositories still require credentials that the
    manager does not currently provide.
    """
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"}:
            return False
        if parts.netloc.lower() != "dev.azure.com":
            return False
        path = parts.path.rstrip("/")
        if "/_apis/git/repositories/" not in path:
            return False
        if not path.endswith("/items"):
            return False
        query = parse_qs(parts.query, keep_blank_values=True)
        formats = [str(v).strip().lower() for v in query.get("$format", [])]
        if not formats:
            formats = [str(v).strip().lower() for v in query.get("%24format", [])]
        return "zip" in formats
    except ValueError:
        return False

# Znane hosty repozytoriów Git spoza GitHub/Azure DevOps. Dopasowanie wymaga
# /owner/repo z co najmniej dwoma segmentami ścieżki - samo trafienie w
# domenę to za mało, żeby odróżnić realne repo od strony głównej/profilu.
_KNOWN_GIT_HOST_RE = re.compile(
    r"^https?://(www\.)?(gitlab\.com|bitbucket\.org|codeberg\.org|git\.sr\.ht|gitea\.com)"
    r"/[^/]+/[^/]+/?$",
    re.IGNORECASE,
)
_GENERIC_DOTGIT_RE = re.compile(r"^https?://.+\.git/?$", re.IGNORECASE)

# Strony-listingi modów NIE są bezpośrednimi linkami do plików/repo -
# traktujemy je jako nieobsługiwane, zamiast próbować "na wyczucie".
_KNOWN_MOD_LISTING_SITE_RE = re.compile(
    r"^https?://(www\.)?(7daystodiemods\.com|nexusmods\.com)/",
    re.IGNORECASE,
)


def detect_source_kind(url: str) -> DownloadSourceKind:
    url = (url or "").strip()
    if not url:
        return DownloadSourceKind.UNSUPPORTED
    if url.rstrip("/") == MIRROR_URL:
        return DownloadSourceKind.UNDEAD_LEGACY_MIRROR
    if _NEXUSMODS_RE.match(url) or _KNOWN_MOD_LISTING_SITE_RE.match(url):
        return DownloadSourceKind.UNSUPPORTED
    # query/fragment nie zmieniają typu źródła - GitLab archive i inne
    # serwisy dokładają parametry do bezpośrednich linków .zip. Azure DevOps
    # ma dodatkowo eksport ZIP z Git Items API, gdzie format ZIP jest
    # określony parametrem $format=zip, a ścieżka nie kończy się na .zip.
    bare = re.split(r"[?#]", url, maxsplit=1)[0]
    if bare.lower().endswith(".zip") or _is_azure_items_zip_url(url):
        return DownloadSourceKind.DIRECT_ZIP
    if _GITHUB_RELEASES_RE.match(url):
        return DownloadSourceKind.GITHUB_RELEASES
    if _GITHUB_REPO_RE.match(url) or _AZURE_REPO_RE.match(url):
        return DownloadSourceKind.GIT_REPO
    if _KNOWN_GIT_HOST_RE.match(url) or _GENERIC_DOTGIT_RE.match(url):
        return DownloadSourceKind.GIT_REPO
    return DownloadSourceKind.UNSUPPORTED


def is_supported_url(url: str) -> bool:
    return detect_source_kind(url) != DownloadSourceKind.UNSUPPORTED


def source_kind_label(kind: DownloadSourceKind) -> str:
    return {
        DownloadSourceKind.GIT_REPO: i18n_message("download.source.git"),
        DownloadSourceKind.GITHUB_RELEASES: i18n_message("download.source.github"),
        DownloadSourceKind.DIRECT_ZIP: i18n_message("download.source.zip"),
        DownloadSourceKind.UNDEAD_LEGACY_MIRROR: i18n_message("download.source.zip"),
    }.get(kind, i18n_message("download.source.unknown"))


# --- Pobieranie -------------------------------------------------------------


def _http_get_json(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise DownloadError(i18n_message("download.error.connect", {"url": url, "error": str(exc)})) from exc


def _http_download_file(
    url: str,
    dest: Path,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event=None,
    pause_event=None,
    label: str = "",
    request_headers: Optional[dict[str, str]] = None,
    use_cookies: bool = False,
) -> None:
    """Pobiera plik HTTP do dest, z PAUZĄ (DownloadPaused, .part zostaje)
    i WZNOWIENIEM przez HTTP Range. Serwer ignorujący Range odpowie 200
    zamiast 206 - wtedy startujemy od zera (rozpoznawane po kodzie).
    Anulowanie rzuca OperationCancelled; błędy sieciowe DownloadError.

    use_cookies=True: cały łańcuch przekierowań (np. ul.subquake.com ->
    dropbox.com -> dropboxusercontent.com) idzie jedną sesją z cookie jar.
    Podpisany link dropboxusercontent jest związany z sesją i działa raz,
    więc nie wolno go „rozwiązać” osobnym requestem i dopiero potem pobrać."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    downloaded = part.stat().st_size if part.exists() else 0

    while True:
        check_cancel(cancel_event)
        if pause_event is not None and pause_event.is_set():
            raise DownloadPaused(label)

        headers = {"User-Agent": USER_AGENT}
        if request_headers:
            headers.update({str(k): str(v) for k, v in request_headers.items()})
        if downloaded:
            headers["Range"] = f"bytes={downloaded}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            if use_cookies:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                resp = opener.open(request, timeout=REQUEST_TIMEOUT)
            else:
                resp = urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT)
        except urllib.error.URLError as exc:
            raise DownloadError(i18n_message("download.error.fetch", {"url": url, "error": str(exc)})) from exc

        with resp:
            code = resp.getcode()
            resumed = code == 206 and downloaded > 0
            if not resumed:
                downloaded = 0
            total_size = int(resp.headers.get("Content-Length", 0) or 0)
            if resumed:
                total_size += downloaded

            # Zanim ruszy transfer wielu GB: sprawdź, czy dysk w ogóle
            # pomieści resztę pliku (przy wznowieniu liczymy tylko brakujące
            # bajty). Rozmiar nieznany (brak Content-Length) = brak kontroli.
            if total_size:
                ensure_free_space(part.parent, total_size - (downloaded if resumed else 0))

            mode = "ab" if resumed else "wb"
            with open(part, mode) as f:
                while True:
                    check_cancel(cancel_event)
                    if pause_event is not None and pause_event.is_set():
                        raise DownloadPaused(label)
                    chunk = resp.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    try:
                        f.write(chunk)
                    except OSError as exc:
                        # .part zostaje - po zwolnieniu miejsca "Ponów"
                        # dociągnie resztę przez Range
                        raise_if_no_space(exc, part.parent)
                        raise
                    downloaded += len(chunk)
                    if progress_cb:
                        mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024) if total_size else 0
                        text = f"{label}: {mb:.1f} MB" + (f" / {total_mb:.1f} MB" if total_mb else "")
                        if total_size:
                            progress_cb(min(downloaded, total_size), total_size, text)
                        else:
                            progress_cb(downloaded, downloaded + _CHUNK_SIZE, text)

        # wyszliśmy z bloku resp bez pauzy/anulowania -> plik kompletny
        part.replace(dest)
        return


def _zip_already_complete(zip_path: Path) -> bool:
    """Czy pod zip_path leży kompletne archiwum z poprzedniej próby.

    ``download.zip`` powstaje wyłącznie przez ``part.replace(dest)`` po
    zakończonym transferze, więc jeśli jest poprawnym ZIP-em (is_zipfile czyta
    końcowy katalog centralny, obcięty plik nie przejdzie), nie ma po co
    ściągać go drugi raz - to ratuje ponowne pobieranie 7,5 GB po błędzie
    wypakowywania (np. braku miejsca)."""
    try:
        return zip_path.is_file() and zipfile.is_zipfile(zip_path)
    except OSError:
        return False


def _git_clone(
    url: str,
    dest: Path,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event=None,
) -> None:
    """git clone --depth 1. NIE wspiera pauzy (klonowania nie da się
    wstrzymać w połowie) - wspiera tylko anulowanie (terminate/kill)."""
    if shutil.which("git") is None:
        raise DownloadError(i18n_message("download.error.gitMissing"))

    if progress_cb:
        progress_cb(0, 1, i18n_message("download.mod.cloning", {"name": url}))

    process = subprocess.Popen(
        ["git", "clone", "--depth", "1", "--progress", url, str(dest)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise OperationCancelled(i18n_message("common.operationCancelled"))
            line = process.stdout.readline() if process.stdout else ""
            if not line:
                if process.poll() is not None:
                    break
                continue
            if progress_cb:
                progress_cb(0, 1, line.strip()[:120])
    finally:
        if process.stdout:
            process.stdout.close()

    return_code = process.wait()
    if return_code != 0:
        raise DownloadError(i18n_message("download.error.gitClone", {"code": return_code, "url": url}))


def _extract_zip(
    zip_path: Path,
    dest: Path,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event=None,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.infolist()
            targets = []
            # Some Windows packers store backslashes instead of ZIP's '/'.
            # Validate the normalized paths before writing any archive data.
            for member in members:
                name = member.filename.replace("\\", "/")
                parts = name.split("/")
                if name.startswith("/") or ".." in parts or any(":" in p for p in parts):
                    raise DownloadError(i18n_message("download.error.unsafePath", {"path": member.filename}))
                target = root.joinpath(*parts).resolve()
                if not target.is_relative_to(root):
                    raise DownloadError(i18n_message("download.error.outsidePath", {"path": member.filename}))
                targets.append((target, name.endswith("/")))
            # Rozmiar PO rozpakowaniu znamy z nagłówków ZIP - sprawdzamy go
            # zanim zapiszemy pierwszy bajt, zamiast paść po kilku minutach
            # na Errno 28 z połową drzewa na dysku.
            ensure_free_space(dest, sum(m.file_size for m in members))
            total = len(members) or 1
            for i, (member, (target, is_dir)) in enumerate(zip(members, targets)):
                check_cancel(cancel_event)
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with zf.open(member) as source, target.open("wb") as output:
                            while chunk := source.read(_CHUNK_SIZE):
                                check_cancel(cancel_event)
                                output.write(chunk)
                    except OSError as exc:
                        raise_if_no_space(exc, dest)
                        raise
                if progress_cb:
                    progress_cb(i + 1, total, i18n_message("download.mod.extracting", {"name": member.filename}))
    except zipfile.BadZipFile as exc:
        raise DownloadError(i18n_message("download.error.badZip", {"error": str(exc)})) from exc


def _github_latest_release_asset_url(owner: str, repo: str) -> tuple[str, str]:
    """Zwraca (url_do_pobrania, nazwa_release) dla najnowszego release'a
    GitHub. Preferuje pierwszy załączony plik .zip; bez assetów używa
    zipball (source code) z tagu release'a."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    data = _http_get_json(api_url)
    tag_name = str(data.get("tag_name") or data.get("name") or "latest")

    for asset in data.get("assets", []) or []:
        name = str(asset.get("name", ""))
        if name.lower().endswith(".zip"):
            url = asset.get("browser_download_url")
            if url:
                return url, tag_name

    zipball = data.get("zipball_url")
    if zipball:
        return zipball, tag_name

    raise DownloadError(i18n_message("download.error.releaseZip", {"tag": tag_name, "repo": f"{owner}/{repo}"}))


def _parse_github_releases_url(url: str) -> tuple[str, str]:
    match = _GITHUB_RELEASES_RE.match(url) or re.match(r"^https?://github\.com/([^/]+)/([^/]+)", url)
    if not match:
        raise DownloadError(i18n_message("download.error.githubUrl", {"url": url}))
    return match.group(1), match.group(2)


def download_and_extract(
    url: str,
    temp_dir: Path,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event=None,
    pause_event=None,
) -> Path:
    """Pobiera modpack spod danego URL (git repo / GitHub releases / ZIP)
    do KATALOGU TYMCZASOWEGO podanego przez wołającego i zwraca ścieżkę
    wypakowanej zawartości.

    temp_dir jest własnością wołającego i musi przetrwać pauzę oraz
    ponowienie (plik *.part jest w nim wznawiany przez HTTP Range); na
    pauzę rzuca DownloadPaused BEZ sprzątania (.part zostaje), przy
    błędzie/anulowaniu sprząta wypakowaną zawartość. Wyjątki propagowane
    jako DownloadError/OperationCancelled."""
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    kind = detect_source_kind(url)
    if kind == DownloadSourceKind.UNSUPPORTED:
        raise DownloadError(i18n_message("download.error.unsupportedSource"))

    extract_dir = temp_dir / "extracted"

    try:
        if kind == DownloadSourceKind.GIT_REPO:
            # klon zawsze od zera - resztki po nieudanym klonowaniu usuwamy
            shutil.rmtree(extract_dir, ignore_errors=True)
            _git_clone(url, extract_dir, progress_cb=progress_cb, cancel_event=cancel_event)
        elif kind == DownloadSourceKind.GITHUB_RELEASES:
            owner, repo = _parse_github_releases_url(url)
            asset_url, release_name = _github_latest_release_asset_url(owner, repo)
            zip_path = temp_dir / "release.zip"
            if not _zip_already_complete(zip_path):
                _http_download_file(
                    asset_url, zip_path, progress_cb=progress_cb,
                    cancel_event=cancel_event, pause_event=pause_event,
                    label=i18n_message("download.mod.release", {"release": release_name}),
                )
            _extract_zip(zip_path, extract_dir, progress_cb=progress_cb, cancel_event=cancel_event)
            zip_path.unlink(missing_ok=True)
        elif kind in (DownloadSourceKind.DIRECT_ZIP, DownloadSourceKind.UNDEAD_LEGACY_MIRROR):
            zip_path = temp_dir / "download.zip"
            resolved_url = url
            request_headers = None
            reuse_zip = _zip_already_complete(zip_path)
            if reuse_zip:
                if progress_cb:
                    progress_cb(1, 1, i18n_message("download.mod.extracting", {"name": zip_path.name}))
            elif kind == DownloadSourceKind.UNDEAD_LEGACY_MIRROR:
                # Dropbox (oficjalny mechanizm: link udostepniony z dl=1)
                # odpowiada przekierowaniem na jednorazowy, podpisany link
                # dropboxusercontent zwiazany z sesja (cookies). Dlatego NIE
                # rozwiazujemy go osobnym requestem - stabilny URL mirrora
                # idzie prosto do downloadera, ktory prowadzi caly lancuch
                # przekierowan jedna sesja z cookie jar (Range przy wznowieniu
                # jest przenoszony przez przekierowania). Swiezy link przy
                # kazdej probie = wznowienie po restarcie aplikacji dziala.
                request_headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) "
                        "Gecko/20100101 Firefox/156.0"
                    ),
                    "Referer": "https://ul.subquake.com/",
                    "Accept": "*/*",
                }
            if not reuse_zip:
                _http_download_file(
                    resolved_url, zip_path, progress_cb=progress_cb,
                    cancel_event=cancel_event, pause_event=pause_event,
                    request_headers=request_headers,
                    use_cookies=kind == DownloadSourceKind.UNDEAD_LEGACY_MIRROR,
                )
            _extract_zip(zip_path, extract_dir, progress_cb=progress_cb, cancel_event=cancel_event)
            # Undead Legacy keeps the original archive. The download manager
            # moves it to downloads/ after a successful installation so the
            # launcher's existing archive-cleanup setting remains authoritative.
            if kind != DownloadSourceKind.UNDEAD_LEGACY_MIRROR:
                zip_path.unlink(missing_ok=True)
        else:
            raise DownloadError(i18n_message("download.error.unknownSource"))
    except OperationCancelled:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    except DownloadPaused:
        # celowe: .part zostaje, niczego nie sprzątamy - wznowienie
        # kontynuuje z pobranymi bajtami
        raise
    except (DownloadError, InsufficientDiskSpace):
        # brak miejsca: sprzątamy częściowo wypakowane drzewo (zwalnia dysk),
        # a kompletny download.zip/.part zostaje - "Ponów" nie ściąga od zera
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise DownloadError(i18n_message("download.error.unexpected", {"error": str(exc)})) from exc

    return extract_dir


def cleanup_temp_dir(temp_dir: Path | None) -> None:
    """Usuwa katalog tymczasowy pobierania (po sukcesie albo anulowaniu)."""
    if temp_dir is None:
        return
    shutil.rmtree(temp_dir, ignore_errors=True)


# --- Weryfikacja struktury ---------------------------------------------------


def find_mods_root_in_extracted(extracted_dir: Path) -> Optional[Path]:
    """Szuka folderu 'Mods' w wypakowanej/sklonowanej zawartości. Repo
    modpacków 7DTD zwykle mają <repo>/Mods/<ModName>/ModInfo.xml, czasem
    zagnieżdżone (zipball GitHub dodaje folder z hashem commita)."""
    if not extracted_dir.exists():
        return None

    direct = extracted_dir / "Mods"
    if direct.is_dir():
        return direct

    # jeden poziom w głąb (typowe dla zipball GitHub: repo-<hash>/Mods)
    try:
        for child in extracted_dir.iterdir():
            if child.is_dir():
                candidate = child / "Mods"
                if candidate.is_dir():
                    return candidate
    except OSError:
        pass

    # ostateczność: całe drzewo
    for path in extracted_dir.rglob("Mods"):
        if path.is_dir():
            return path

    # archiwa pojedynczych modów z 7daystodiemods.com często trzymają
    # foldery modów BEZPOŚREDNIO w korzeniu (bez opakowującego Mods/) -
    # wtedy sam korzeń jest sztucznym Mods-rootem (etap 9)
    try:
        for child in extracted_dir.iterdir():
            if child.is_dir() and find_modinfo(child) is not None:
                return extracted_dir
    except OSError:
        pass

    return None


def mods_root_has_valid_mods(mods_root: Path) -> bool:
    """Czy w folderze Mods jest przynajmniej jeden podfolder z
    ModInfo.xml - podstawowa weryfikacja, że to modpack, a nie przypadkowy
    folder o tej samej nazwie."""
    if not mods_root.is_dir():
        return False
    try:
        for child in mods_root.iterdir():
            if child.is_dir() and find_modinfo(child) is not None:
                return True
    except OSError:
        return False
    return False
