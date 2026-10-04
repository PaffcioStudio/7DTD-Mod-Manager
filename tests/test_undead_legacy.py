import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from backend import modpack_downloader as downloader
from backend.undead_legacy import MIRROR_URL


def test_undead_legacy_mirror_is_downloaded_in_one_cookie_session_without_pre_resolve():
    with tempfile.TemporaryDirectory() as directory:
        temp_dir = Path(directory)
        with patch.object(downloader, "_http_download_file") as download, \
             patch.object(downloader, "_extract_zip") as extract:
            result = downloader.download_and_extract(MIRROR_URL, temp_dir)
        assert result == temp_dir / "extracted"
        assert download.call_args.args[0] == MIRROR_URL
        assert download.call_args.kwargs["use_cookies"] is True
        request_headers = download.call_args.kwargs["request_headers"]
        assert request_headers["Referer"] == "https://ul.subquake.com/"
        assert request_headers["User-Agent"].startswith("Mozilla/5.0 (X11; Linux x86_64; rv:156.0)")
        assert request_headers["Accept"] == "*/*"
        extract.assert_called_once()


def test_url_worker_captures_download_temp_dir_before_async_worker_runs():
    source = (Path(__file__).resolve().parents[1] / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert "cancel, pause = item.cancel_event, item.pause_event\n        temp_dir = item.temp_dir" in source
    assert "modpack_downloader.cleanup_temp_dir(temp_dir)" in source


def test_undead_legacy_archive_is_kept_after_extract_for_launcher_cleanup():
    with tempfile.TemporaryDirectory() as directory:
        temp_dir = Path(directory)
        archive = temp_dir / "download.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Mods/UndeadLegacy/ModInfo.xml", "<xml />")

        def fake_download(url, dest, **kwargs):
            assert url == MIRROR_URL
            assert dest.name == "download.zip"
            # The archive already exists; the real downloader overwrites it.

        with patch.object(downloader, "_http_download_file", side_effect=fake_download):
            extracted = downloader.download_and_extract(MIRROR_URL, temp_dir)

        assert extracted == temp_dir / "extracted"
        assert archive.is_file(), "Undead Legacy ZIP must survive extraction"


def test_url_worker_defers_undead_legacy_archive_cleanup_to_downloads_cleanup():
    source = (Path(__file__).resolve().parents[1] / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert "def _preserve_undead_legacy_archive" in source
    assert "downloads_cleanup.register_installed" in source
    assert "preserved_archive = self._preserve_undead_legacy_archive(temp_dir)" in source
    assert "# Archiwum zostało wcześniej przeniesione poza temp_dir" in source


def test_url_worker_declares_temp_dir_nonlocal_because_it_reassigns_it():
    import ast
    source = (Path(__file__).resolve().parents[1] / "src/backend/download_manager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    start = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_start_url_worker")
    worker = next(n for n in ast.walk(start) if isinstance(n, ast.FunctionDef) and n.name == "worker")
    assigned = {t.id for n in ast.walk(worker) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)}
    declared = {name for n in ast.walk(worker) if isinstance(n, ast.Nonlocal) for name in n.names}
    assert "temp_dir" in assigned and "temp_dir" in declared
