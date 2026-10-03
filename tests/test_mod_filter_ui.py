from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from backend.events import EventBus
from backend.conflict_detector import ConflictDetector
from backend.mod_manager import ModManager
from services.settings_service import SettingsService


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def test_filter_mode_change_notifies_qml_facing_manager():
    _app()
    manager = ModManager(SettingsService(), EventBus(), ConflictDetector())
    seen = []
    manager.filterModeChanged.connect(lambda: seen.append(manager.filterMode))

    manager.filterMode = "conflicts"

    assert manager.filterMode == "conflicts"
    assert seen == ["conflicts"]
