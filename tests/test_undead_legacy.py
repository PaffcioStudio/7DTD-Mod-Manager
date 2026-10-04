import tempfile
from pathlib import Path
from unittest.mock import patch

from backend import modpack_downloader as downloader
from backend.undead_legacy import MIRROR_URL


def test_download_and_extract_resolves_undead_legacy_mirror_before_transfer():
    with tempfile.TemporaryDirectory() as directory:
        temp_dir = Path(directory)
        with patch.object(downloader, "resolve_mirror_url", return_value="https://cdn.example/current.zip") as resolve, \
             patch.object(downloader, "_http_download_file") as download, \
             patch.object(downloader, "_extract_zip") as extract:
            result = downloader.download_and_extract(MIRROR_URL, temp_dir)
        assert result == temp_dir / "extracted"
        resolve.assert_called_once_with(MIRROR_URL)
        assert download.call_args.args[0] == "https://cdn.example/current.zip"
        request_headers = download.call_args.kwargs["request_headers"]
        assert request_headers["Referer"] == "https://ul.subquake.com/"
        assert request_headers["User-Agent"].startswith("Mozilla/5.0 (X11; Linux x86_64; rv:156.0)")
        assert request_headers["Accept"] == "*/*"
        extract.assert_called_once()
