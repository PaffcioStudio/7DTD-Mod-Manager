from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from services.app_info import AppInfo, APP_VERSION


class _Bus:
    def __init__(self):
        self.messages = []

    def toast(self, message, level):
        self.messages.append((message, level))

    def toastKey(self, key, values=None, level="info"):
        self.messages.append((key, values or {}, level))


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def test_app_version_bumped():
    assert APP_VERSION == "1.0.43"


def test_search_mod_online_builds_expected_7daystodiemods_url():
    _app()
    bus = _Bus()
    info = AppInfo(bus)
    with patch("services.app_info.QDesktopServices.openUrl", return_value=True) as opened:
        info.searchModOnline("Mini Traders")
    assert opened.call_count == 1
    assert opened.call_args.args[0].toString() == "https://7daystodiemods.com/discover?q=mini+traders"


def test_search_mod_online_normalizes_whitespace_and_case():
    _app()
    bus = _Bus()
    info = AppInfo(bus)
    with patch("services.app_info.QDesktopServices.openUrl", return_value=True) as opened:
        info.searchModOnline("  Mini   Traders  ")
    assert opened.call_args.args[0].toString() == "https://7daystodiemods.com/discover?q=mini+traders"


def test_search_mod_online_rejects_empty_name():
    _app()
    bus = _Bus()
    info = AppInfo(bus)
    with patch("services.app_info.QDesktopServices.openUrl", return_value=True) as opened:
        info.searchModOnline("   ")
    opened.assert_not_called()
    assert bus.messages == [("toast.app.modNameMissing", {}, "warning")]
