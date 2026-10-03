from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_scroll_view_matches_discover_overlay_scrollbar_geometry():
    text = (ROOT / "qml/components/AppScrollView.qml").read_text(encoding="utf-8")
    assert "readonly property real contentRightInset: showScrollBar ? 14 : 0" in text
    assert "contentWidth: Math.max(0, width - contentRightInset)" in text
    assert "ScrollBar.vertical: AppScrollBar" in text
    assert "width: sv.contentRightInset" not in text
    assert "color: Theme.bg1" not in text
    assert "scrollBarGutter" not in text


def test_pages_do_not_reference_unscoped_scrollbar_gutter():
    qml_root = ROOT / "qml"
    offenders = []
    for path in qml_root.rglob("*.qml"):
        text = path.read_text(encoding="utf-8")
        if "scrollBarGutter" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders


def test_discover_keeps_reference_inset():
    text = (ROOT / "qml/pages/DiscoverPage.qml").read_text(encoding="utf-8")
    assert "ScrollBar.vertical: AppScrollBar {}" in text
    assert "width: results.width - 14" in text


def test_scroll_consumers_do_not_override_inset_with_full_width_content():
    consumers = [
        ROOT / "qml/pages/DashboardPage.qml",
        ROOT / "qml/pages/GameProfilesPage.qml",
        ROOT / "qml/pages/ProfilesPage.qml",
        ROOT / "qml/pages/BackupsPage.qml",
    ]
    for path in consumers:
        assert "contentWidth: width" not in path.read_text(encoding="utf-8"), path.name
