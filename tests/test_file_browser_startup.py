from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from backend.file_browser import FileBrowser


def test_file_browser_constructor_does_not_scan_filesystem_synchronously():
    QCoreApplication.instance() or QCoreApplication([])

    with patch.object(FileBrowser, "_refresh_drives") as refresh_drives, \
         patch.object(FileBrowser, "_refresh_entries") as refresh_entries:
        browser = FileBrowser()

    assert browser.currentPath == browser.homePath
    refresh_drives.assert_not_called()
    refresh_entries.assert_not_called()


def test_file_browser_initial_scan_is_not_started_during_construction():
    QCoreApplication.instance() or QCoreApplication([])

    class FakeThread:
        created = False
        def __init__(self, target, daemon=True, name=None):
            FakeThread.created = True
            self.target = target
        def start(self):
            pass

    with patch("backend.file_browser.threading.Thread", FakeThread):
        browser = FileBrowser()

    assert FakeThread.created is False
    assert browser.ready is False


def test_file_browser_initial_scan_is_deferred_to_a_worker():
    QCoreApplication.instance() or QCoreApplication([])

    class FakeThread:
        created = False
        def __init__(self, target, daemon=True, name=None):
            FakeThread.created = True
            self.target = target
        def start(self):
            pass

    with patch.object(FileBrowser, "_collect_drives") as collect_drives, \
         patch.object(FileBrowser, "_collect_entries") as collect_entries, \
         patch("backend.file_browser.threading.Thread", FakeThread):
        browser = FileBrowser()
        browser.ensureInitialized()

    assert FakeThread.created is True
    collect_drives.assert_not_called()
    collect_entries.assert_not_called()
    assert browser._scan_in_progress is True
