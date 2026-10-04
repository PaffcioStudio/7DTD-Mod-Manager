from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_global_search_has_window_level_focus_dismiss_handler():
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "TapHandler" in main
    assert "header.closeSearch()" in main
    assert "header.searchLeft" in main
    assert "header.searchWidth" in main


def test_search_bar_clears_text_input_focus_explicitly():
    search = (ROOT / "qml" / "components" / "SearchBar.qml").read_text(encoding="utf-8")
    assert "input.deselect()" in search
    assert "input.focus = false" in search
    assert "root.forceActiveFocus()" in search


def test_global_search_tap_handler_can_observe_grabbed_taps():
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "grabPermissions: PointerHandler.CanTakeOverFromAnything" in main
