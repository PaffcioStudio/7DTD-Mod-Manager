from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dashboard():
    return (ROOT / "qml/pages/DashboardPage.qml").read_text(encoding="utf-8")


def _mod_manager():
    return (ROOT / "src/backend/mod_manager.py").read_text(encoding="utf-8")


def test_dashboard_uses_full_width_instance_and_conflict_panels():
    text = _dashboard()
    assert 'title: I18n.t("dashboard.activeInstance.title")' in text
    assert 'title: I18n.t("dashboard.conflicts.title")' in text
    assert 'Layout.preferredWidth: 1' in text
    assert 'Layout.minimumHeight: 252 * Dimensions.scale' in text
    assert 'title: "Ostatnio zaktualizowane"' not in text


def test_dashboard_no_longer_contains_non_interactive_recent_rows():
    text = _dashboard()
    assert "Mods.recentUpdated" not in text
    assert 'Bus.openMod(recentRow.modelData.id)' not in text


def test_mod_filter_uses_non_deprecated_filter_change_api():
    text = _mod_manager()
    assert "beginFilterChange()" in text
    assert "endFilterChange(QSortFilterProxyModel.Direction.Rows)" in text
    assert "invalidateRowsFilter()" not in text
    assert "invalidateFilter()" not in text
