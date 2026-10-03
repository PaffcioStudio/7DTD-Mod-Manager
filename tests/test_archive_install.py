from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from backend import library_ops
from backend.fileops import OperationCancelled
from backend.modpack_downloader import (
    DownloadError, _extract_zip, find_mods_root_in_extracted,
    mods_root_has_valid_mods,
)


class ArchiveInstallTests(unittest.TestCase):
    def test_windows_and_standard_zip_paths_install_and_deduplicate(self):
        for separator in ("\\", "/"):
            with self.subTest(separator=separator), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "test.zip"
                with zipfile.ZipFile(archive, "w") as zf:
                    zf.writestr(separator.join(("VanillaPlus", "")), b"")
                    zf.writestr(separator.join(("VanillaPlus", "ModInfo.xml")),
                                '<xml><Name value="VanillaPlus"/><Version value="1.7.1"/></xml>')
                    zf.writestr(separator.join(("VanillaPlus", "Config", "blocks.xml")), "<configs/>")
                extracted = root / "extracted"
                _extract_zip(archive, extracted)
                mods = find_mods_root_in_extracted(extracted)
                self.assertIsNotNone(mods)
                self.assertTrue(mods_root_has_valid_mods(mods))
                self.assertEqual((extracted / "VanillaPlus/Config/blocks.xml").read_text(), "<configs/>")
                with patch.object(Path, "home", return_value=root):
                    report = library_ops.install_modpack_to_library(mods)
                    self.assertFalse(report.errors)
                    self.assertEqual(len(report.imported), 1)
                    repeated = library_ops.install_modpack_to_library(mods)
                    self.assertEqual(len(repeated.already_present), 1)

    def test_normalized_paths_cannot_escape_destination(self):
        for name in ("../escape", "..\\escape", "mod\\..\\..\\escape", "/escape", "C:\\escape"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "test.zip"
                with zipfile.ZipFile(archive, "w") as zf:
                    zf.writestr("valid.txt", "should not be extracted")
                    zf.writestr(name, "bad")
                with self.assertRaises(DownloadError):
                    _extract_zip(archive, root / "extracted")
                self.assertFalse((root / "extracted/valid.txt").exists())
                self.assertFalse((root / "escape").exists())

    def test_cancel_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "test.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("mod/ModInfo.xml", "<xml/>")
            event = threading.Event()
            event.set()
            with self.assertRaises(OperationCancelled):
                _extract_zip(archive, Path(directory) / "out", cancel_event=event)


if __name__ == "__main__":
    unittest.main()
