from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
HEADER = (ROOT / "qml/components/AppHeader.qml").read_text(encoding="utf-8")


def test_global_header_shows_page_descriptions_below_title():
    assert 'pageTitle: window.pageTitles[pageStack.currentPage]' in MAIN
    assert 'pageSubtitle: window.pageMeta[pageStack.currentPage]' in MAIN
    assert 'id: headerSubtitle' in HEADER
    assert 'text: header.pageSubtitle' in HEADER
    assert 'ToolTip.text: header.pageSubtitle' in HEADER
    assert 'elide: Text.ElideRight' in HEADER
    assert 'maximumLineCount: 1' in HEADER


def test_old_inline_page_descriptions_are_removed():
    for relative in (
        "DashboardPage.qml", "ModsPage.qml", "ProfilesPage.qml",
        "SteamReleasesPage.qml", "GameProfilesPage.qml", "BackupsPage.qml",
        "DownloadsPage.qml", "DiscoverPage.qml", "UpdatesPage.qml",
        "ConflictsPage.qml", "SettingsPage.qml", "ProtonsPage.qml",
    ):
        source = (ROOT / "qml/pages" / relative).read_text(encoding="utf-8")
        assert 'PageDescription {' not in source, relative


def test_every_page_has_translated_header_subtitle():
    for page in ('dashboard', 'mods', 'profiles', 'protons', 'steam_releases',
                 'game_profiles', 'modpacks', 'downloads', 'discover', 'updates',
                 'conflicts', 'settings'):
        assert f'"{page}": [' in MAIN
