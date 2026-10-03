import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from backend import downloads_cleanup as cleanup
from services import filesystem_service as fs


class ArchiveCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = patch.object(Path, "home", return_value=self.root)
        self.home.start()
        self.addCleanup(self.home.stop)

    def archive(self, name, installed=False, days=2):
        path = fs.downloads_dir() / name
        path.write_bytes(b"archive")
        age = time.time() - days * 86400
        os.utime(path, (age, age))
        if installed:
            cleanup.register_installed(name, path.stat().st_size)
        return path

    def test_auto_removes_only_old_successfully_installed_archives(self):
        old = self.archive("old.zip", installed=True)
        fresh = self.archive("fresh.zip", installed=True, days=0)
        unknown = self.archive("unknown.zip")
        partial = self.archive("partial.zip.part", installed=True)
        changed = self.archive("changed.zip", installed=True)
        changed.write_bytes(b"replacement")
        self.assertEqual(cleanup.auto_clean(1), (7, 1, ["old.zip"]))
        self.assertFalse(old.exists())
        self.assertTrue(all(p.exists() for p in (fresh, unknown, partial, changed)))

    def test_cleanup_refuses_active_workers_even_after_cancellation(self):
        archive = self.archive("active.zip", installed=True)
        with cleanup.archive_use():
            with self.assertRaises(RuntimeError):
                cleanup.clean_all()
            with self.assertRaises(RuntimeError):
                cleanup.auto_clean(1)
        self.assertTrue(archive.exists())
        self.assertEqual(cleanup.clean_all(), (7, 1))

    def test_manual_cleanup_preserves_external_files_and_directories(self):
        self.archive("download.zip")
        outside = self.root / "outside.zip"
        outside.write_bytes(b"keep")
        (fs.downloads_dir() / "link.zip").symlink_to(outside)
        (fs.downloads_dir() / "folder").mkdir()
        self.assertEqual(cleanup.stats()["count"], 1)
        self.assertEqual(cleanup.clean_all(), (7, 1))
        self.assertEqual(outside.read_bytes(), b"keep")
        self.assertTrue((fs.downloads_dir() / "folder").is_dir())

    def test_invalid_registry_and_legacy_entries_are_not_deleted_automatically(self):
        self.archive("legacy.zip")
        fs.write_json(fs.installed_archives_path(), {
            "installed": [None, "broken", {"file": "legacy.zip", "size": 7}]})
        self.assertEqual(cleanup.auto_clean(1)[1], 0)


if __name__ == "__main__":
    unittest.main()
