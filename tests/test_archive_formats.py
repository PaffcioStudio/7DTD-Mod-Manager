"""Realny plik 7z i regresje obsługi wszystkich ścieżek instalatora."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from backend.archive_extractor import (
    ARCHIVE_SUFFIXES, ArchiveFormatError, archive_is_complete,
    extract_archive, _validated_target,
)
from backend import modpack_downloader

ROOT = Path(__file__).resolve().parents[1]
SEVENZ = ROOT / "tests/fixtures/InstantScrap.7z"


def test_real_sevenz_mod_is_extracted_and_recognized(tmp_path):
    root = tmp_path / "extracted"
    extract_archive(SEVENZ, root)
    assert (root / "InstantScrap/ModInfo.xml").is_file()
    assert (root / "InstantScrap/InstantScrap.dll").is_file()
    assert (root / "InstantScrap/Config/items.xml").is_file()
    mods_root = modpack_downloader.prepare_mods_root_in_extracted(root)
    assert modpack_downloader.mods_root_has_valid_mods(mods_root)
    mods = [d.name for d in mods_root.iterdir() if d.is_dir()]
    assert mods == ["InstantScrap"]


def test_archive_progress_reports_each_entry(tmp_path):
    callbacks = []
    extract_archive(SEVENZ, tmp_path / "out", progress_cb=lambda *args: callbacks.append(args))
    assert callbacks
    assert callbacks[-1][0] == callbacks[-1][1]


def test_archive_cancel_stops_safely(tmp_path):
    import threading
    from backend.fileops import OperationCancelled
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(OperationCancelled):
        extract_archive(SEVENZ, tmp_path / "out", cancel_event=cancel)


def test_rar_extension_is_supported_and_real_format_is_sniffed(tmp_path):
    # RAR-y mogą być rozpakowane przez tę samą bibliotekę libarchive.
    # Sufiks nie decyduje o dekoderze: sprawdzamy nagłówek archiwum.
    assert ".rar" in ARCHIVE_SUFFIXES
    renamed = tmp_path / "misnamed.rar"
    shutil.copy2(SEVENZ, renamed)
    assert archive_is_complete(renamed)
    extract_archive(renamed, tmp_path / "out")
    assert (tmp_path / "out/InstantScrap/ModInfo.xml").exists()


def test_archived_download_is_recognized_in_all_url_modes():
    kind = modpack_downloader.DownloadSourceKind.DIRECT_ZIP
    for ext in ("zip", "7z", "rar"):
        assert modpack_downloader.detect_source_kind(f"https://example.org/mod.{ext}?key=test") == kind
    assert modpack_downloader.detect_source_kind("https://example.org/website.html") == modpack_downloader.DownloadSourceKind.UNSUPPORTED


def test_modified_zip_uses_existing_extractor(tmp_path):
    zipped = tmp_path / "mod.zip"
    with zipfile.ZipFile(zipped, "w") as zf:
        zf.writestr("Mod/ModInfo.xml", '<xml><Name value="Mod"/></xml>')
    extract_archive(zipped, tmp_path / "out")
    assert (tmp_path / "out/Mod/ModInfo.xml").exists()


def test_7z_corruption_and_nonarchives_are_rejected(tmp_path):
    corrupt = tmp_path / "broken.7z"
    corrupt.write_bytes(SEVENZ.read_bytes()[:20])
    assert not archive_is_complete(corrupt)
    with pytest.raises(ArchiveFormatError):
        extract_archive(corrupt, tmp_path / "corrupt")


def test_paths_cannot_escape_or_create_devices(tmp_path):
    root = tmp_path.resolve()
    for malicious in ("../evil.txt", "a/../evil.txt", "/etc/passwd", "C:/Windows/system.ini", "../../outside"):
        with pytest.raises(ArchiveFormatError):
            _validated_target(root, malicious)
    assert _validated_target(root, "./safe/mod.xml") == root / "safe/mod.xml"


def test_installer_calls_common_extractor_and_reuses_complete_downloads():
    manager = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    downloader = (ROOT / "src/backend/modpack_downloader.py").read_text(encoding="utf-8")
    assert "if dest.suffix.lower() not in ARCHIVE_SUFFIXES:" in manager
    assert "extract_archive(\n                    dest, temp_dir," in manager
    assert "extract_archive(zip_path, extract_dir" in downloader
    assert "return archive_is_complete(zip_path)" in downloader


def test_7z_complete_archive_can_be_reused(tmp_path):
    archive = tmp_path / "download.7z"
    shutil.copy2(SEVENZ, archive)
    assert modpack_downloader._zip_already_complete(archive)
    archive.write_bytes(archive.read_bytes()[:20])
    assert not modpack_downloader._zip_already_complete(archive)


def test_mediafire_archive_filter_accepts_7z_and_rar():
    source = (ROOT / "src/backend/scraper_client.py").read_text(encoding="utf-8")
    assert 'if Path(name).suffix.lower() not in {".zip", ".7z", ".rar"}:' in source


def test_unverified_game_version_does_not_unlock_explicit_mismatch():
    source = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert "def _file_version_is_unknown" in source
    assert "not self._file_version_is_unknown(main_file, info)" in source
    assert "not self._external_version_is_unknown(chosen_ext, info)" in source
    assert "_file_matches_selected_game_version" in source


def test_direct_sevenz_url_download_extracts_real_archive(tmp_path, monkeypatch):
    def fake_download(_url, dest, **_kwargs):
        shutil.copy2(SEVENZ, dest)
    monkeypatch.setattr(modpack_downloader, "_http_download_file", fake_download)
    extracted = modpack_downloader.download_and_extract(
        "https://example.invalid/InstantScrap.7z", tmp_path / "work",
    )
    assert (extracted / "InstantScrap/ModInfo.xml").exists()
    assert not (tmp_path / "work/download.7z").exists()


def test_release_sevenz_asset_selects_archive_instead_of_zipball(tmp_path, monkeypatch):
    monkeypatch.setattr(modpack_downloader, "_http_get_json", lambda _: {
        "tag_name": "v2", "assets": [{
            "name": "InstantScrap.7z", "browser_download_url": "https://example.invalid/InstantScrap.7z",
        }], "zipball_url": "https://example.invalid/fallback.zip",
    })
    def fake_download(_url, dest, **_kwargs):
        shutil.copy2(SEVENZ, dest)
    monkeypatch.setattr(modpack_downloader, "_http_download_file", fake_download)
    extracted = modpack_downloader.download_and_extract(
        "https://github.com/example/mod/releases", tmp_path / "work",
    )
    assert (extracted / "InstantScrap/ModInfo.xml").exists()


def test_missing_and_malformed_nonzip_archive_reports_download_error(tmp_path, monkeypatch):
    def fake_download(_url, dest, **_kwargs):
        dest.write_bytes(b"Not an archive")
    monkeypatch.setattr(modpack_downloader, "_http_download_file", fake_download)
    with pytest.raises(modpack_downloader.DownloadError):
        modpack_downloader.download_and_extract("https://example.invalid/bad.rar", tmp_path / "work")


def test_mediafire_real_resolution_supports_7z_and_rar():
    from unittest.mock import Mock
    from backend.scraper_client import ExternalLink, SevenDaysModsClient

    client = SevenDaysModsClient()
    for suffix in ("7z", "rar"):
        direct = f"https://download123.mediafire.com/token/abcd/mod.{suffix}"
        client.session.get = Mock(return_value=Mock(
            status_code=200,
            text=f'<a href="{direct}">Download</a>',
        ))
        link = ExternalLink("mf", "https://www.mediafire.com/file/abcd/mod/file", "Mod")
        assert client.resolve_external_url(link) == (direct, 0, f"mod.{suffix}")
