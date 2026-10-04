from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_steam_account_uses_compact_overlay_menu_for_saved_session_and_modal_for_qr():
    source = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    assert "property bool accountMenuOpen: false" in source
    assert "parent: Overlay.overlay" in source
    assert "GameVersions.hasSavedSession" in source
    assert 'I18n.t("steamAccount.loginAgain")' in source
    assert 'I18n.t("steamAccount.logout")' in source
    assert "Modal {" in source
    assert 'I18n.t("steamAccount.qrHeader")' in source


def test_profile_favorite_is_wired_to_backend_and_protected_from_delete():
    card = (ROOT / "qml" / "components" / "ProfileCard.qml").read_text(encoding="utf-8")
    page = (ROOT / "qml" / "pages" / "ProfilesPage.qml").read_text(encoding="utf-8")
    backend = (ROOT / "src" / "backend" / "profile_manager.py").read_text(encoding="utf-8")
    instances = (ROOT / "src" / "backend" / "instances.py").read_text(encoding="utf-8")
    assert "favoriteToggled" in card
    assert 'icon: root.favorite ? "star-filled" : "star"' in card
    assert "!root.favorite" in card
    assert "Profiles.toggleFavorite" in page
    assert "def toggleFavorite" in backend
    assert '"favorite": instance.favorite' in instances
    assert "if instance.favorite:" in backend


def test_game_version_preflight_is_not_limited_to_alpha_and_survives_queue_restart():
    downloads = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    discover = (ROOT / "src" / "backend" / "discover.py").read_text(encoding="utf-8")
    local_drawer = (ROOT / "qml" / "components" / "LocalModDrawer.qml").read_text(encoding="utf-8")
    web_drawer = (ROOT / "qml" / "components" / "WebModDrawer.qml").read_text(encoding="utf-8")
    page = (ROOT / "qml" / "pages" / "DiscoverPage.qml").read_text(encoding="utf-8")
    assert "def _check_required_game_version" in downloads
    assert "item.game_version = required_game_branch(item.game_version)" in downloads
    assert '"game_version": item.game_version' in downloads
    assert 'game_version=required_game_branch(str(rec.get("game_version") or ""))' in downloads
    assert '"game_version": game_version' in discover
    assert "drawer.gameVersion" in local_drawer
    assert "selectedGameVersion" in web_drawer
    assert "webDrawer.openWith(slug, page.version)" in page


def test_favorite_has_a_real_filled_star_asset():
    asset = (ROOT / "assets" / "icons" / "star-filled.svg").read_text(encoding="utf-8")
    assert 'fill="currentColor"' in asset
    assert 'stroke="currentColor"' in asset


def test_steam_account_anchor_is_bound_to_modal_anchor_item_not_readonly_alias():
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    header = (ROOT / "qml" / "components" / "AppHeader.qml").read_text(encoding="utf-8")
    assert 'property alias accountAnchor: accountButton' in header
    assert '                accountAnchor: header.accountAnchor' not in main
    assert '        anchorItem: header.accountAnchor' in main
    source = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    assert 'Qt.callLater(function()' in source
    assert 'accountMenuOpen = true' in source


def test_steam_account_menu_has_real_logout_action_and_no_popup_dependency():
    source = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    backend = (ROOT / "src" / "backend" / "game_versions.py").read_text(encoding="utf-8")
    header = (ROOT / "qml" / "components" / "AppHeader.qml").read_text(encoding="utf-8")
    assert 'property bool accountMenuOpen: false' in source
    assert 'I18n.t("steamAccount.logout")' in source
    assert 'GameVersions.logout()' in source
    assert 'parent: Overlay.overlay' in source
    assert 'Popup {' not in source
    assert '@Slot()\n    def logout' in backend
    assert 'clear_steam_username()' in backend
    assert 'onClicked: Qt.callLater(function() { header.accountRequested() })' in header


def test_account_menu_is_clickable_and_anchored_under_account_button():
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    source = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    # header jest tylko punktem odniesienia dla pozycji
    assert 'menuParent: header' in main
    # menu i warstwa zamykająca w tym samym rodzicu, menu nad warstwą
    # (inaczej warstwa połyka kliknięcia w przyciski)
    dismiss = source[source.index("id: accountDismissLayer"):source.index("id: accountMenu")]
    menu = source[source.index("id: accountMenu"):source.index("ColumnLayout {")]
    assert "parent: Overlay.overlay" in dismiss and "z: 9" in dismiss
    assert "parent: Overlay.overlay" in menu and "z: 1090" in menu
    assert "parent: root.menuParent" not in source
    # pozycja przeliczana jawnie, bo mapToItem nie jest śledzone
    assert "property int layoutTick: 0" in source
    assert menu.count("root.layoutTick") >= 2
    assert "accountAnchorRight(host)" in source
    assert "accountAnchorTopBoundary(host)" in source
    assert "return root.anchorItem.mapToItem(host, root.anchorItem.width, 0).x" in source
    assert "root.menuParent.mapToItem(host, 0, root.menuParent.height).y" in source


def test_discover_version_is_not_dropped_when_url_delegates_to_web_scraper():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    assert 'self.startModDownloadWithVersion(url, game_version)' in source


def test_instance_backup_metadata_preserves_game_branch():
    source = (ROOT / "src" / "backend" / "modpacks.py").read_text(encoding="utf-8")
    assert 'game_branch: str = ""' in source
    assert '"game_branch": r.game_branch' in source
    assert 'game_branch=str(instance.game_branch or "")' in source
    assert 'game_branch=record.game_branch' in source
