import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication

from backend.global_search import GlobalSearchManager
from models.mod import Mod


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


class ModsStub:
    def all_mods(self):
        return [
            Mod(id="a", name="Trader Sanctuary", author="Paffcio", tags=["trader"]),
            Mod(id="b", name="12 Slot Toolbelt", author="Tester"),
        ]


class ProfilesStub:
    def all_instances_for_search(self):
        return [
            {"id": "i1", "name": "Vanilla Alpha 8.8", "description": "stara wersja", "gameBranch": "alpha8.8"},
            {"id": "i2", "name": "Modded 17.4", "description": "", "gameBranch": "alpha17.4"},
        ]


def test_local_global_search_finds_mods_and_instances():
    _app()
    manager = GlobalSearchManager(ModsStub(), ProfilesStub())
    with patch("backend.global_search.fetch_catalog", return_value={"items": [], "total": 0, "page": 1, "pages": 1, "offline": False}):
        manager.query = "alpha 8.8"
    # Only local records are guaranteed here; online section is async.
    assert any(r["kind"] == "instance" and r["id"] == "i1" for r in manager.results)
    manager.shutdown()


def test_online_results_are_merged(monkeypatch):
    _app()
    manager = GlobalSearchManager(ModsStub(), ProfilesStub())

    fake = {
        "items": [{"slug": "trader-sanctuary", "title": "Trader Sanctuary Expanded", "author": "Someone"}],
        "total": 1, "page": 1, "pages": 1, "offline": False,
    }
    with patch("backend.global_search.fetch_catalog", return_value=fake):
        manager.query = "Trader Sanctuary"
        manager._debounce.stop()
        manager._start_pending(manager._generation)
        manager._thread.join(timeout=3)
        # Signal delivery needs the Qt event loop. Invoke the slot directly to
        # make this test deterministic.
        manager._finish_online(manager._generation, fake, "")
    assert any(r["kind"] == "discover" and r["id"] == "trader-sanctuary" for r in manager.results)
    manager.shutdown()


def test_global_search_uses_qtimer_start_not_restart():
    source = (Path(__file__).parents[1] / "src" / "backend" / "global_search.py").read_text(encoding="utf-8")
    assert "self._debounce.start()" in source
    assert "self._debounce.restart()" not in source


def test_latest_query_wins_while_online_search_is_running():
    _app()
    manager = GlobalSearchManager(ModsStub(), ProfilesStub())
    manager.query = "Trader"
    # Before the debounce fires, typing more should replace the pending query
    # rather than queueing one network request per keystroke.
    manager.query = "Trader Sanctuary"
    assert manager._pending_query == "Trader Sanctuary"
    assert manager.busy
    manager.shutdown()



def test_main_loads_global_search_popup_lazily():
    qml = (Path(__file__).parents[1] / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert 'source: active ? Qt.resolvedUrl("components/GlobalSearchPopup.qml") : ""' in qml
    assert 'parent: Overlay.overlay' not in qml.split("id: globalSearchLoader", 1)[1].split("// ---- overlays", 1)[0]


def test_global_search_qml_does_not_use_undefined_delegate_identifier():
    from pathlib import Path

    qml = (Path(__file__).parents[1] / "qml" / "components" / "GlobalSearchPopup.qml").read_text(encoding="utf-8")
    assert "delegate.index" not in qml
    assert "delegate.modelData" not in qml


def test_app_header_exposes_search_focus_for_global_popup():
    from pathlib import Path

    qml = (Path(__file__).parents[1] / "qml" / "components" / "AppHeader.qml").read_text(encoding="utf-8")
    assert "property bool searchFocused" in qml or "property alias searchFocused" in qml or "readonly property bool searchFocused" in qml
