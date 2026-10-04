from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAIN = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")


def test_global_header_does_not_receive_page_subtitles():
    assert 'pageSubtitle: ""' in MAIN
    assert 'pageMeta[pageStack.currentPage] || I18n.t("dashboard.title")' in MAIN


def test_page_description_component_wraps_and_limits_copy():
    comp = (ROOT / "qml" / "components" / "PageDescription.qml").read_text(encoding="utf-8")
    assert 'wrapMode: Text.WordWrap' in comp
    assert 'maximumLineCount: 2' in comp
    assert 'elide: Text.ElideRight' in comp


def test_long_page_descriptions_are_inside_pages():
    for relative, key in (
        ("qml/pages/DashboardPage.qml", "dashboard.subtitle"),
        ("qml/pages/ModsPage.qml", "mods.caption"),
        ("qml/pages/ProfilesPage.qml", "instances.subtitle"),
        ("qml/pages/SteamReleasesPage.qml", "steamReleases.subtitle"),
        ("qml/pages/GameProfilesPage.qml", "gameProfiles.subtitle"),
        ("qml/pages/BackupsPage.qml", "backups.caption"),
        ("qml/pages/DownloadsPage.qml", "downloads.caption.none"),
        ("qml/pages/DiscoverPage.qml", "discover.subtitle"),
        ("qml/pages/UpdatesPage.qml", "updates.pageSubtitle.current"),
        ("qml/pages/ConflictsPage.qml", "conflicts.subtitle.none"),
        ("qml/pages/SettingsPage.qml", "settings.subtitle"),
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert 'PageDescription {' in source, relative
        assert key in source, (relative, key)
