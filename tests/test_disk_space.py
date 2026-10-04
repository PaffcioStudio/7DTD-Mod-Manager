"""Regresja: pobranie overhaula (Undead Legacy ~7,5 GB) kończyło się
``[Errno 28] No space left on device`` w połowie wypakowywania, bez
ostrzeżenia i z ponownym pobieraniem całości przy "Ponów"."""
import errno
import io
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend import fileops
from backend import modpack_downloader as downloader
from backend.fileops import InsufficientDiskSpace
from backend.undead_legacy import MIRROR_URL

ROOT = Path(__file__).resolve().parents[1]
GB = 1024 ** 3


def _fake_usage(free):
    return patch.object(fileops.shutil, "disk_usage",
                        return_value=SimpleNamespace(total=100 * GB, used=0, free=free))


def test_ensure_free_space_raises_localizable_error():
    with tempfile.TemporaryDirectory() as d, _fake_usage(2 * GB):
        with pytest.raises(InsufficientDiskSpace) as info:
            fileops.ensure_free_space(Path(d), 8 * GB)
    text = str(info.value)
    assert text.startswith("__I18N__:download.error.noSpace|")
    assert "8.2 GB" in text and "2.0 GB" in text  # potrzeba (8 GB + zapas) / wolne


def test_ensure_free_space_passes_when_enough_or_size_unknown():
    with tempfile.TemporaryDirectory() as d, _fake_usage(50 * GB):
        fileops.ensure_free_space(Path(d), 8 * GB)
        fileops.ensure_free_space(Path(d), 0)


def test_extract_zip_checks_uncompressed_size_before_writing_anything():
    with tempfile.TemporaryDirectory() as d:
        archive = Path(d) / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Mods/X/ModInfo.xml", "<xml/>" * 1000)
        dest = Path(d) / "extracted"
        with _fake_usage(1024):  # mniej niż sam zapas
            with pytest.raises(InsufficientDiskSpace):
                downloader._extract_zip(archive, dest)
        assert not any(dest.rglob("*.xml")), "nic nie powinno zostać zapisane"


def test_extract_zip_maps_enospc_during_write_to_friendly_error():
    with tempfile.TemporaryDirectory() as d:
        archive = Path(d) / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Mods/X/ModInfo.xml", "<xml/>")
        real_open = Path.open

        def failing_open(self, mode="r", *a, **kw):
            if "w" in mode and self.name == "ModInfo.xml":
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_open(self, mode, *a, **kw)

        with patch.object(Path, "open", failing_open):
            with pytest.raises(InsufficientDiskSpace) as info:
                downloader._extract_zip(archive, Path(d) / "out")
        assert "noSpaceDuringWrite" in str(info.value)


class _FakeResponse(io.BytesIO):
    def __init__(self, payload=b"", content_length=None, code=200):
        super().__init__(payload)
        self.headers = {"Content-Length": str(content_length if content_length is not None else len(payload))}
        self._code = code

    def getcode(self):
        return self._code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_download_refuses_before_transfer_when_disk_too_small():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "download.zip"
        resp = _FakeResponse(b"x", content_length=7_481_211_002)
        with patch.object(downloader.urllib.request, "urlopen", return_value=resp), \
             _fake_usage(3 * GB):
            with pytest.raises(InsufficientDiskSpace):
                downloader._http_download_file("https://example.test/a.zip", dest)
        assert not dest.exists()
        assert not dest.with_suffix(".zip.part").exists() or dest.with_suffix(".zip.part").stat().st_size == 0


def test_http_download_resume_only_counts_missing_bytes():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "download.zip"
        part = dest.with_suffix(".zip.part")
        part.write_bytes(b"a" * 10)
        # serwer zwraca 206 i 5 brakujących bajtów (Content-Length = reszta)
        resp = _FakeResponse(b"b" * 5, content_length=5, code=206)
        with patch.object(downloader.urllib.request, "urlopen", return_value=resp), \
             _fake_usage(1):  # 1 B wolnego, ale i tak sprawdzamy TYLKO 5 B + zapas
            with pytest.raises(InsufficientDiskSpace):
                downloader._http_download_file("https://example.test/a.zip", dest)
        with patch.object(downloader.urllib.request, "urlopen",
                          return_value=_FakeResponse(b"b" * 5, content_length=5, code=206)), \
             _fake_usage(10 * GB):
            downloader._http_download_file("https://example.test/a.zip", dest)
        assert dest.read_bytes() == b"a" * 10 + b"b" * 5


def test_complete_zip_from_previous_attempt_is_reused_not_redownloaded():
    with tempfile.TemporaryDirectory() as d:
        temp_dir = Path(d)
        with zipfile.ZipFile(temp_dir / "download.zip", "w") as zf:
            zf.writestr("Mods/UndeadLegacy/ModInfo.xml", "<xml />")
        with patch.object(downloader, "_http_download_file") as download:
            extracted = downloader.download_and_extract(MIRROR_URL, temp_dir)
        download.assert_not_called()
        assert (extracted / "Mods/UndeadLegacy/ModInfo.xml").is_file()
        assert (temp_dir / "download.zip").is_file()


def test_truncated_zip_is_not_reused():
    with tempfile.TemporaryDirectory() as d:
        temp_dir = Path(d)
        (temp_dir / "download.zip").write_bytes(b"PK\x03\x04 truncated")
        with patch.object(downloader, "_http_download_file") as download, \
             patch.object(downloader, "_extract_zip"):
            downloader.download_and_extract(MIRROR_URL, temp_dir)
        download.assert_called_once()


def test_no_space_during_extraction_cleans_partial_tree_but_keeps_zip():
    with tempfile.TemporaryDirectory() as d:
        temp_dir = Path(d)
        with zipfile.ZipFile(temp_dir / "download.zip", "w") as zf:
            zf.writestr("Mods/UndeadLegacy/ModInfo.xml", "<xml />")
        with _fake_usage(1024), pytest.raises(InsufficientDiskSpace):
            downloader.download_and_extract(MIRROR_URL, temp_dir)
        assert not (temp_dir / "extracted").exists()
        assert (temp_dir / "download.zip").is_file(), "ponowienie nie może ściągać od zera"


def test_staging_dir_lives_under_app_data_not_system_tmp(tmp_path, monkeypatch):
    from services import filesystem_service as fs
    monkeypatch.setattr(fs.Path, "home", classmethod(lambda cls: tmp_path))
    staging = fs.staging_dir()
    assert staging == tmp_path / ".7dtd_modmanager" / "tmp"
    assert fileops.same_device(staging, fs.downloads_dir())


def test_download_workers_use_staging_dir_and_move_instead_of_copy():
    source = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert 'mkdtemp(prefix="mm-dl-")' not in source
    assert 'mkdtemp(prefix="mm-mod-")' not in source
    assert source.count("dir=fs.staging_dir()") == 3
    assert "shutil.copytree(source, target, symlinks=True)" not in source
    assert "shutil.move(str(source), str(target))" in source
    # instalacja PRZED przeniesieniem archiwum (porażka instalacji nie gubi ZIP-a)
    assert source.index("entry_count = self._install_overhaul_as_instance(\n                        item.title, item.title") \
        < source.index("preserved_archive = self._preserve_undead_legacy_archive(temp_dir)")


def test_no_space_messages_exist_in_both_languages():
    catalog = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
    for key in ("download.error.noSpace", "download.error.noSpaceDuringWrite"):
        assert catalog.count(f'"{key}"') == 2, key
