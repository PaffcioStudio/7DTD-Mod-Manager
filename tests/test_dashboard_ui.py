from pathlib import Path


def test_dashboard_lower_panels_reserve_space_for_bottom_actions():
    qml = (Path(__file__).resolve().parents[1] / "qml/pages/DashboardPage.qml").read_text(encoding="utf-8")
    assert qml.count("Layout.minimumHeight: 252 * Dimensions.scale") == 2
    assert "Layout.minimumHeight: 6 * Dimensions.scale" in qml
