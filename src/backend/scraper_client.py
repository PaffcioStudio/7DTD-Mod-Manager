"""Klient strony i API 7daystodiemods.com."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

import requests

from backend.nuxtdata import build_all, extract_payload
from services.i18n_message import message as i18n_message

BASE_URL = "https://7daystodiemods.com"
API_BASE_URL = "https://api.7daystodiemods.com"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

ProgressCallback = Callable[[int, int], None]  # (pobrane_bajty, calkowite_bajty)


@dataclass
class ModFile:
    """Jeden plik do pobrania w zakładce Download moda."""

    id: str
    media_id: str
    filename: str
    size: int  # bajty
    label: str
    file_type: str  # "main" / "optional" / "old" ...
    version: str | None
    scan_status: str | None  # "clean" = "Verified safe"
    description: str | None = None
    sort_order: int = 0

    @property
    def is_verified(self) -> bool:
        return self.scan_status == "clean"


_DIRECT_FILE_SUFFIXES = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".exe", ".dll", ".pak", ".bnk",
}


def _is_azure_items_zip_url(url: str) -> bool:
    """Czy URL jest publicznym eksportem ZIP z Azure DevOps Git Items API.

    Azure nie umieszcza ``.zip`` w ścieżce URL. Format archiwum jest
    wybierany przez parametr ``$format=zip`` (często zapisany jako ``%24format``),
    np. ``/_apis/git/repositories/<id>/items?...&$format=zip&download=true``.
    """
    try:
        parts = urlsplit((url or "").strip())
        if parts.scheme.lower() not in {"http", "https"}:
            return False
        if parts.netloc.lower() != "dev.azure.com":
            return False
        path = parts.path.rstrip("/")
        if "/_apis/git/repositories/" not in path or not path.endswith("/items"):
            return False
        query = parse_qs(parts.query, keep_blank_values=True)
        formats = [str(v).strip().lower() for v in query.get("$format", [])]
        return "zip" in formats
    except ValueError:
        return False


# https://www.curseforge.com/<game>/mods/<slug>/download/<file_id>
CURSEFORGE_FILE_RE = re.compile(
    r"curseforge\.com/[a-z0-9_-]+/mods/[a-z0-9_-]+/download/(?:file/)?(\d+)", re.I
)

# https://github.com/<owner>/<repo> - dokładnie strona repo (bez podstron)
GITHUB_REPO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?",
    re.I,
)

# https://gitlab.com/<owner>/<repo> - strona repo (zob. resolve_external_url)
GITLAB_REPO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?gitlab\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$",
    re.I,
)

# https://mediafilez.forgecdn.net/files/<file_id // 1000>/<file_id % 1000>/<nazwa>
FORGECDN_URL = "https://mediafilez.forgecdn.net/files/{major}/{minor}/{name}"


def _filename_with_direct_suffix(text: str | None) -> str | None:
    """Nazwa pliku z tekstu, o ile kończy się rozszerzeniem pliku bezpośredniego."""
    if not text:
        return None
    suffix = os.path.splitext(text.strip())[1].lower()
    return text.strip() if suffix in _DIRECT_FILE_SUFFIXES else None


@dataclass
class ExternalLink:
    """Plik moda udostępniony jako link zewnętrzny (np. GitHub, Drive, CurseForge)."""

    id: str
    url: str
    label: str
    file_type: str = "main"
    version: str | None = None
    description: str | None = None
    sort_order: int = 0

    @property
    def is_direct_file(self) -> bool:
        """True, gdy URL wskazuje na plik (a nie np. stronę repo na GitHubie)."""
        from urllib.parse import urlparse

        suffix = os.path.splitext(urlparse(self.url).path)[1].lower()
        return suffix in _DIRECT_FILE_SUFFIXES or _is_azure_items_zip_url(self.url)

    @property
    def filename(self) -> str:
        from urllib.parse import urlparse, unquote

        # autorzy wpisują w label realną nazwę pliku nawet, gdy URL prowadzi
        # do strony (np. CurseForge) - wtedy to lepsze źródło niż ścieżka URL
        name = _filename_with_direct_suffix(self.label)
        if name:
            return name
        if _is_azure_items_zip_url(self.url):
            return "azure-repository.zip"
        name = unquote(os.path.basename(urlparse(self.url).path))
        return name or re.sub(r"[^\w.-]+", "_", self.label or "download")


@dataclass
class ModInfo:
    """Dane moda sparsowane ze strony."""

    id: str
    slug: str
    title: str
    url: str
    author: str | None = None
    summary: str | None = None
    current_version: str | None = None
    download_count: int = 0
    categories: list[str] = field(default_factory=list)
    game_versions: list[str] = field(default_factory=list)
    files: list[ModFile] = field(default_factory=list)
    external_links: list[ExternalLink] = field(default_factory=list)
    download_instructions: str | None = None

    def files_by_type(self) -> dict[str, list[ModFile]]:
        grouped: dict[str, list[ModFile]] = {}
        for f in self.files:
            grouped.setdefault(f.file_type, []).append(f)
        return grouped


class DownloadNotReadyError(RuntimeError):
    """API nie zwróciło jeszcze URL-a po upływie cooldownu."""


class ModNotFoundError(LookupError):
    pass


def parse_mod_url(url_or_slug: str) -> str:
    """Przyjmuje pełny URL (https://7daystodiemods.com/mods/<slug>) albo sam slug."""
    text = url_or_slug.strip().rstrip("/")
    match = re.search(r"/mods/([a-z0-9-]+)$", text, re.I)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-z0-9-]+", text, re.I):
        return text.lower()
    raise ValueError(i18n_message("discover.error.slug", {"url": url_or_slug}))


def human_size(num_bytes: float) -> str:
    try:
        value = max(0.0, float(num_bytes or 0))
    except (TypeError, ValueError):
        value = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


class SevenDaysModsClient:
    def __init__(self, session: requests.Session | None = None, timeout: float = 30.0):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout

    # ------------------------------------------------------------- strona

    def _fetch_mod(self, url_or_slug: str) -> tuple[dict, str]:
        """Pobiera stronę moda i zwraca (obiekt moda z payloadu, url strony)."""
        slug = parse_mod_url(url_or_slug)
        page_url = f"{BASE_URL}/mods/{slug}"
        resp = self.session.get(page_url, timeout=self.timeout)
        if resp.status_code == 404:
            raise ModNotFoundError(i18n_message("discover.error.modNotFound", {"url": page_url}))
        resp.raise_for_status()
        return self._find_main_mod(extract_payload(resp.text)), page_url

    def get_mod(self, url_or_slug: str) -> ModInfo:
        """Pobiera stronę moda i parsuje dane z payloadu __NUXT_DATA__."""
        mod, url = self._fetch_mod(url_or_slug)
        return self._map_mod(mod, url)

    @staticmethod
    def _map_changelog(mod: dict) -> list[dict]:
        """Historia wersji w kolejności jak na stronie (najnowsza pierwsza).

        Payload zawiera PEŁNĄ historię - UI pokazuje 5 i przycisk
        "Show older versions", my zwracamy wszystko.
        """
        entries = []
        for raw in mod.get("version_history") or []:
            if not isinstance(raw, dict) or raw.get("version") is None:
                continue
            entries.append({
                "version": str(raw.get("version")),
                "date": raw.get("created_at"),
                "changelog": raw.get("changelog") or "",
            })
        return entries

    def get_changelog(self, url_or_slug: str) -> list[dict]:
        """Zwraca changelogi moda jako listę {version, date, changelog}."""
        mod, _ = self._fetch_mod(url_or_slug)
        return self._map_changelog(mod)

    @staticmethod
    def _find_main_mod(payload: list) -> dict:
        """Główny mod strony ma pełny obiekt z kluczem 'mod_files' (karty
        powiązanych modów go nie mają)."""
        for value in build_all(payload):
            if isinstance(value, dict) and "mod_files" in value and value.get("id"):
                files = value["mod_files"]
                if isinstance(files, list):
                    return value
        raise ModNotFoundError(i18n_message("discover.error.modObjectMissing"))

    @staticmethod
    def _map_mod(mod: dict, url: str) -> ModInfo:
        author = mod.get("author")
        if isinstance(author, dict):
            author = (
                author.get("display_name")
                or author.get("username")
                or author.get("name")
            )

        files = []
        for raw in mod.get("mod_files") or []:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            files.append(
                ModFile(
                    id=raw["id"],
                    media_id=raw.get("media_id") or "",
                    filename=raw.get("filename") or "",
                    size=int(raw.get("size") or 0),
                    label=raw.get("label") or raw.get("filename") or i18n_message("common.unnamed"),
                    file_type=raw.get("file_type") or "main",
                    version=raw.get("mod_version"),
                    scan_status=raw.get("scan_status"),
                    description=raw.get("description"),
                    sort_order=int(raw.get("sort_order") or 0),
                )
            )
        files.sort(key=lambda f: (f.file_type != "main", f.sort_order, f.label.lower()))

        categories = []
        for category in mod.get("categories") or mod.get("mod_categories") or []:
            if isinstance(category, str):
                value = category.strip()
            elif isinstance(category, dict):
                value = str(category.get("name") or category.get("title") or category.get("slug") or "").strip()
            else:
                value = ""
            if value:
                categories.append(value)

        game_versions = []
        for gv in mod.get("game_versions") or []:
            if isinstance(gv, str):
                game_versions.append(gv)
            elif isinstance(gv, dict):
                game_versions.append(str(gv.get("name") or gv.get("version") or gv.get("slug") or ""))

        current_version = mod.get("current_version")
        if isinstance(current_version, dict):
            current_version = current_version.get("version")

        external_links = []
        for raw in mod.get("external_links") or []:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("url"):
                continue
            external_links.append(
                ExternalLink(
                    id=raw["id"],
                    url=raw["url"],
                    label=raw.get("label") or raw["url"],
                    file_type=raw.get("file_type") or "external",
                    version=raw.get("mod_version"),
                    description=raw.get("description"),
                    sort_order=int(raw.get("sort_order") or 0),
                )
            )
        external_links.sort(key=lambda l: (l.sort_order, l.label.lower()))

        return ModInfo(
            id=mod["id"],
            slug=mod.get("slug") or url.rsplit("/", 1)[-1],
            title=mod.get("title") or mod.get("slug") or "(bez tytułu)",
            url=url,
            author=author,
            summary=mod.get("summary"),
            current_version=current_version,
            download_count=int(mod.get("download_count") or 0),
            categories=categories,
            game_versions=game_versions,
            files=files,
            external_links=external_links,
            download_instructions=mod.get("download_instructions"),
        )

    # ------------------------------------------------------------- metadane

    def get_metadata(self, url_or_slug: str, resolve: bool = False) -> dict:
        """Zwraca metadane moda jako słownik gotowy do JSON-a.

        Zawiera: tytuł, autora, opis (markdown z zakładki Overview), daty
        publikacji/aktualizacji, wersję gry, kategorie, galerię zdjęć oraz
        listę plików do pobrania oraz pełną historię wersji (changelogi).
        Bez credits. Z flagą ``resolve`` dla plików hostowanych dociąga
        podpisane URL-e (każdy kosztuje cooldown ~5 s); linki zewnętrzne
        mają URL zawsze.
        """
        slug = parse_mod_url(url_or_slug)
        mod, page_url = self._fetch_mod(url_or_slug)

        author = mod.get("author")
        if isinstance(author, dict):
            author = author.get("display_name") or author.get("username") or author.get("name")

        current_version = mod.get("current_version")
        if isinstance(current_version, dict):
            current_version = current_version.get("version")

        def _names(key: str) -> list[str]:
            out = []
            for item in mod.get(key) or []:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    out.append(str(item.get("name") or item.get("version") or item.get("slug") or ""))
            return [n for n in out if n]

        files = []
        for raw in mod.get("mod_files") or []:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            files.append({
                "kind": "hosted",
                "id": raw["id"],
                "filename": raw.get("filename") or "",
                "label": raw.get("label") or raw.get("filename"),
                "file_type": raw.get("file_type") or "main",
                "version": raw.get("mod_version"),
                "size_bytes": int(raw.get("size") or 0),
                "verified": raw.get("scan_status") == "clean",
                "download_url": None,  # podpisany URL dopiero z flagą --resolve
            })

        external = []
        for raw in mod.get("external_links") or []:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("url"):
                continue
            external.append({
                "kind": "external",
                "id": raw["id"],
                "label": raw.get("label") or raw["url"],
                "url": raw["url"],
                "file_type": raw.get("file_type") or "external",
                "version": raw.get("mod_version"),
            })

        gallery = [
            img.get("url")
            for img in (mod.get("gallery_images") or [])
            if isinstance(img, dict) and img.get("url")
        ]
        thumbnail = mod.get("thumbnail")
        if isinstance(thumbnail, dict):
            thumbnail = thumbnail.get("url")

        # opis to markdown z wplecionym HTML (np. <span style=...>); wyciągamy
        # z niego URL-e obrazków - markdown ![alt](url) i ewentualne <img src="...">
        description = mod.get("description") or ""
        found_images = re.findall(r"!\[[^\]]*\]\(([^)\s]+)", description)
        found_images += re.findall(r'<img[^>]+src="([^"]+)"', description)
        seen_urls: set[str] = set()
        description_images = [u for u in found_images if not (u in seen_urls or seen_urls.add(u))]

        meta = {
            "id": mod["id"],
            "slug": mod.get("slug") or slug,
            "title": mod.get("title"),
            "url": page_url,
            "author": author,
            "description": mod.get("description"),
            "description_images": description_images,
            "published_at": mod.get("published_at"),
            "updated_at": mod.get("updated_at"),
            "current_version": current_version,
            "game_versions": _names("game_versions"),
            "categories": _names("categories"),
            "download_count": int(mod.get("download_count") or 0),
            "view_count": int(mod.get("view_count") or 0),
            "thumbnail": thumbnail,
            "gallery": gallery,
            "files": files,
            "external_links": external,
            "changelog": self._map_changelog(mod),
        }

        if resolve:
            for entry in meta["files"]:
                entry["download_url"] = self.resolve_download_url(meta["id"], entry["id"])
        return meta

    # ---------------------------------------------------------------- API

    def _api_post(self, path: str, **kwargs) -> requests.Response:
        headers = {
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "Accept": "application/json",
        }
        return self.session.post(
            f"{API_BASE_URL}{path}", headers=headers, timeout=self.timeout, **kwargs
        )

    def _api_get(self, path: str) -> requests.Response:
        headers = {
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "Accept": "application/json",
        }
        return self.session.get(
            f"{API_BASE_URL}{path}", headers=headers, timeout=self.timeout
        )

    def request_download(self, mod_id: str, file_id: str) -> tuple[str, float]:
        """Otwiera "zamówienie" pobierania. Zwraca (token, wait_seconds)."""
        resp = self._api_post(f"/v1/mods/{mod_id}/files/{file_id}/download", json={})
        if resp.status_code == 404:
            raise ModNotFoundError(i18n_message("discover.error.fileNotFound", {"mod": mod_id, "file": file_id}))
        resp.raise_for_status()
        data = resp.json()
        return data["token"], (data.get("wait_ms") or 0) / 1000.0

    def claim_download(self, token: str) -> str:
        """Wymienia token na podpisany URL pliku. Rzuca DownloadNotReadyError,
        jeśli cooldown jeszcze nie minął."""
        resp = self._api_get(f"/v1/mods/downloads/{token}")
        if resp.status_code == 404:
            raise ModNotFoundError(i18n_message("discover.error.downloadToken", {"token": token}))
        if resp.status_code in (425, 409, 403):  # jeszcze za wcześnie
            raise DownloadNotReadyError(i18n_message("discover.error.cooldown", {"code": resp.status_code}))
        resp.raise_for_status()
        url = resp.json().get("url")
        if not url:
            raise DownloadNotReadyError(i18n_message("discover.error.downloadUrl", {"error": resp.text[:200]}))
        return url

    def resolve_download_url(
        self, mod_id: str, file_id: str, on_wait: Callable[[float], None] | None = None
    ) -> str:
        """Pełny flow z przeglądarki: zamów pobranie, odczekaj cooldown,
        wymień token na podpisany URL (ważny zwykle 24 h)."""
        token, wait_s = self.request_download(mod_id, file_id)
        if on_wait:
            on_wait(wait_s)
        if wait_s > 0:
            time.sleep(wait_s + 0.25)

        last_error: Exception | None = None
        for _ in range(6):  # doliczamy zapas, gdyby serwer był bardziej wyczulony
            try:
                return self.claim_download(token)
            except DownloadNotReadyError as exc:
                last_error = exc
                time.sleep(1.0)
        raise last_error  # type: ignore[misc]

    # ----------------------------------------------------------- pobieranie

    def resolve_external_url(self, link: ExternalLink) -> tuple[str, int, str] | None:
        """Dla linka zewnętrznego, który nie prowadzi wprost do pliku, próbuje
        znaleźć URL bezpośredniego pliku. Zwraca (url, size_bajtów, nazwa_pliku)
        albo None, gdy się nie da.

        Obsługiwane:
        - CurseForge ``/download/<file_id>`` - strona samego curseforge.com
          jest za Cloudflare (challenge dla zwykłych requestów), ale pliki
          leżą jawnie na mediafilez.forgecdn.net pod adresem wyliczanym z
          file_id i nazwy pliku (label na 7daystodiemods.com to dokładna
          nazwa pliku),
        - strona repo na GitHubie (``github.com/<owner>/<repo>``) - całe
          repo pobierane jako ZIP przez ``api.github.com/.../zipball``,
          który przekierowuje na codeload z domyślnym branchem (nie trzeba
          znać gałęzi; nazwa ZIP-a z nagłówka Content-Disposition),
        - strona repo na GitLabie (``gitlab.com/<owner>/<repo>``) - całe
          repo jako ZIP przez ``/-/archive/<default_branch>/...`` (domyślna
          gałąź z API v4; archiwa GitLab są generowane na locie, więc bez
          z góry znanej długości)."""
        gh = GITHUB_REPO_RE.fullmatch(link.url.strip().rstrip("/"))
        if gh:
            owner, repo = gh.group(1), gh.group(2)
            if repo.lower().endswith(".git"):
                repo = repo[:-4]
            zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
            try:
                resp = self.session.head(zip_url, timeout=self.timeout, allow_redirects=True)
            except requests.RequestException:
                return None
            if resp.status_code != 200:
                return None
            name = None
            disp = resp.headers.get("Content-Disposition") or ""
            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disp, re.I)
            if m:
                name = m.group(1).strip()
            if not name or not name.lower().endswith(".zip"):
                name = f"{owner}-{repo}.zip"
            return zip_url, int(resp.headers.get("Content-Length") or 0), name

        if _is_azure_items_zip_url(link.url):
            # Azure DevOps Git Items API generuje archiwum ZIP z repozytorium
            # i zwraca je bez ``.zip`` w ścieżce URL. Nie potrzeba HEAD ani
            # dodatkowego API: zwykły downloader HTTP poprawnie podąży za
            # redirectem i zapisze wynik jako archiwum ZIP.
            return link.url.strip(), 0, link.filename

        gl = GITLAB_REPO_RE.fullmatch(link.url.strip().rstrip("/"))
        if gl:
            # GitLab generuje archiwa na locie (chunked, bez Content-Length):
            # /-/archive/<branch>/<repo>-<branch>.zip; domyślna gałąź z API,
            # a przy niepowodzeniu zgadujemy "main"
            owner, repo = gl.group(1), gl.group(2)
            if repo.lower().endswith(".git"):
                repo = repo[:-4]
            branch = "main"
            try:
                api = f"https://gitlab.com/api/v4/projects/{owner}%2F{repo}"
                resp = self.session.get(api, timeout=self.timeout)
                if resp.status_code == 200:
                    branch = resp.json().get("default_branch") or branch
            except (requests.RequestException, ValueError):
                pass
            archive = f"https://gitlab.com/{owner}/{repo}/-/archive/{branch}/{repo}-{branch}.zip"
            return archive, 0, f"{repo}-{branch}.zip"

        match = CURSEFORGE_FILE_RE.search(link.url)
        if not match:
            return None
        file_id = int(match.group(1))
        name = _filename_with_direct_suffix(link.label) or _filename_with_direct_suffix(link.filename)
        if not name:
            return None
        cdn_url = FORGECDN_URL.format(
            major=file_id // 1000, minor=file_id % 1000, name=name
        )
        try:
            resp = self.session.head(cdn_url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException:
            return None
        if resp.status_code in (200, 206):
            return cdn_url, int(resp.headers.get("Content-Length") or 0), name
        return None

    def download_to(
        self,
        url: str,
        dest: Path | str,
        progress: ProgressCallback | None = None,
        chunk_size: int = 1024 * 1024,
        max_retries: int = 8,
        on_retry: Callable[[int, float, Exception], None] | None = None,
    ) -> Path:
        """Strumieniowo zapisuje plik z URL-a (np. podpisanego z R2).

        Wznawianie: zapis idzie do ``<nazwa>.part``; po zerwaniu połączenia
        (sieć, Ctrl-C i ponowne uruchomienie) pobieranie kontynuuje od rozmiaru
        istniejącego .part przez HTTP Range (serwer musi zwracać 206 - R2 tak
        robi). Gdy serwer zignoruje Range, zaczyna od nowa.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")

        attempt = 0
        while True:
            offset = tmp.stat().st_size if tmp.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset > 0 else {}
            try:
                with self.session.get(
                    url, stream=True, timeout=self.timeout, headers=headers
                ) as resp:
                    if resp.status_code == 416 and offset > 0:
                        # offset >= rozmiar pliku => .part był już kompletny
                        tmp.rename(dest)
                        return dest
                    resp.raise_for_status()
                    if resp.status_code == 206 and offset > 0:
                        total = offset + int(resp.headers.get("Content-Length") or 0)
                        mode = "ab"
                    else:
                        if offset > 0:  # serwer zignorował Range
                            offset = 0
                        total = int(resp.headers.get("Content-Length") or 0)
                        mode = "wb"

                    done = offset
                    with open(tmp, mode) as fh:
                        for chunk in resp.iter_content(chunk_size=chunk_size):
                            if not chunk:
                                continue
                            fh.write(chunk)
                            done += len(chunk)
                            if progress:
                                progress(done, total)
                tmp.rename(dest)
                return dest
            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.exceptions.ChunkedEncodingError,  # zerwane połączenie w trakcie
            ) as exc:
                attempt += 1
                if attempt > max_retries:
                    raise
                delay = min(2 ** (attempt - 1), 15)
                if on_retry:
                    on_retry(attempt, delay, exc)
                time.sleep(delay)

    def download_mod_file(
        self,
        mod: ModInfo,
        mod_file: ModFile,
        dest_dir: Path | str = ".",
        progress: ProgressCallback | None = None,
        filename: str | None = None,
        on_retry: Callable[[int, float, Exception], None] | None = None,
    ) -> Path:
        """Rozwiązuje URL dla wybranego pliku moda i zapisuje go w dest_dir."""
        signed_url = self.resolve_download_url(mod.id, mod_file.id)
        return self.download_to(
            signed_url,
            Path(dest_dir) / (filename or mod_file.filename),
            progress,
            on_retry=on_retry,
        )


def iter_with_progress(
    progress: ProgressCallback, interval: float = 0.2
) -> ProgressCallback:
    """Ogranicza liczbę wywołań callbacka postępu (do UI w terminalu)."""
    state = {"last": 0.0}

    def wrapped(done: int, total: int) -> None:
        now = time.monotonic()
        if now - state["last"] >= interval or done >= total > 0:
            state["last"] = now
            progress(done, total)

    return wrapped
