from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
SIDEBAR = (ROOT / "qml" / "components" / "AppSidebar.qml").read_text(encoding="utf-8")
INSTANCES = (ROOT / "qml" / "pages" / "ProfilesPage.qml").read_text(encoding="utf-8")
PAGE = (ROOT / "qml" / "pages" / "SteamReleasesPage.qml").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "qml" / "i18n" / "translations.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_steam_releases_is_a_first_class_navigation_page():
    assert 'page: "steam_releases"' in SIDEBAR
    assert 'key: "nav.steamReleases"' in SIDEBAR
    assert 'SteamReleasesPage { id: steamReleasesPage' in MAIN
    assert '"steam_releases": I18n.t("steamReleases.title")' in MAIN
    assert 'pageSubtitle: ""' in MAIN


def test_instances_no_longer_owns_steam_release_management():
    assert "GameVersionsModal" not in INSTANCES
    assert "gameVersionsModal" not in INSTANCES
    assert "openGameVersions" not in INSTANCES
    assert "instances.gameVersions" not in INSTANCES


def test_steam_releases_page_contains_full_management_surface():
    for needle in (
        'pageName: "steam_releases"',
        'GameVersions.refreshAvailable()',
        'GameVersions.startAuth()',
        'GameVersions.download(',
        'GameVersions.cancel()',
        'GameVersions.deleteVersion(',
        'I18n.t("steamReleases.refresh")',
    ):
        assert needle in PAGE


def test_steam_releases_has_polish_and_english_strings():
    for key in (
        "nav.steamReleases",
        "steamReleases.title",
        "steamReleases.subtitle",
        "steamReleases.connectSteam",
        "steamReleases.qrHint",
        "steamReleases.qrRefresh",
        "steamReleases.cancelAuth",
        "steamReleases.account",
        "steamReleases.connected",
        "steamReleases.loggedInAs",
        "steamReleases.savedSession",
        "steamReleases.relogin",
        "steamReleases.downloading",
        "steamReleases.downloadStatus",
        "steamReleases.downloadCancel",
        "steamReleases.installedTitle",
        "steamReleases.installedCaption",
        "steamReleases.installedBadge",
        "steamReleases.deleteInstalled",
        "steamReleases.availableTitle",
        "steamReleases.availableCaption",
        "steamReleases.availableBadge",
        "steamReleases.stable",
        "steamReleases.downloaded",
        "steamReleases.download",
        "steamReleases.loading",
        "steamReleases.storageInfo",
        "steamReleases.refresh",
    ):
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_legacy_instances_game_versions_path_is_gone_from_ui_and_docs():
    forbidden = (
        "Instancje → Wersje gry",
        "Instances → Game Versions",
        'I18n.t("instances.gameVersions")',
        'text: I18n.t("instances.gameVersions")',
        'I18n.t("gameVersions.title")',
    )
    ui_and_docs = MAIN + SIDEBAR + INSTANCES + PAGE + TRANSLATIONS + README
    for phrase in forbidden:
        assert phrase not in ui_and_docs, phrase

    assert "**Steam Releases**" in README


def test_steam_releases_delete_is_confirmed():
    assert 'ConfirmModal {' in PAGE
    assert 'deleteInstalledModal.ask(' in PAGE
    assert 'GameVersions.deleteVersion(branch)' in PAGE
    assert 'steamReleases.deleteTitle' in PAGE
    assert 'steamReleases.deleteMessage' in PAGE
    assert 'steamReleases.deleteConfirm' in PAGE
