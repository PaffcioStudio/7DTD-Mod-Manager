from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_QML = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
HEADER_QML = (ROOT / "qml" / "components" / "AppHeader.qml").read_text(encoding="utf-8")


def test_global_search_popup_is_anchored_below_header_search():
    assert 'Popup {' in MAIN_QML
    assert 'parent: Overlay.overlay' in MAIN_QML
    assert 'header.mapToItem(Overlay.overlay, header.searchLeft, header.searchBottom)' in MAIN_QML
    assert 'y: header.mapToItem(Overlay.overlay, header.searchLeft, header.searchBottom).y + 8' in MAIN_QML


def test_global_search_popup_closes_outside_escape_and_navigation():
    assert 'Popup.CloseOnPressOutside | Popup.CloseOnEscape' in MAIN_QML
    assert 'function onPageChanged() {' in MAIN_QML
    assert 'globalSearchPopup.close()' in MAIN_QML
    assert 'header.closeSearch()' in MAIN_QML


def test_search_header_exposes_anchor_geometry_and_can_clear_focus():
    assert 'readonly property real searchLeft: searchBox.x' in HEADER_QML
    assert 'readonly property real searchBottom: searchBox.y + searchBox.height' in HEADER_QML
    assert 'function closeSearch() {' in HEADER_QML



def test_global_search_popup_background_is_transparent():
    assert 'background: Rectangle {' in MAIN_QML
    assert 'color: "transparent"' in MAIN_QML
    assert 'border.width: 0' in MAIN_QML


def test_game_profiles_ui_marks_old_versions_as_unsupported():
    qml = (Path(__file__).parents[1] / "qml" / "pages" / "GameProfilesPage.qml").read_text(encoding="utf-8")
    assert 'enabled: modelData.supported === true' in qml
    assert 'text: I18n.t("gameProfiles.requiresV3")' in qml


def test_header_account_button_remains_clickable_and_changes_tint_when_connected():
    assert 'header.accountRequested()' in HEADER_QML
    assert 'tint: GameVersions.hasSavedSession ? Theme.success : Theme.textSecondary' in HEADER_QML
    assert 'enabled: !GameVersions.busy' not in HEADER_QML


def test_game_status_badge_opens_game_settings_section():
    assert 'signal gameStatusRequested()' in HEADER_QML
    assert 'TapHandler { onTapped: header.gameStatusRequested() }' in HEADER_QML
    assert 'onGameStatusRequested:' in MAIN_QML
    assert 'settingsPage.openSection("game")' in MAIN_QML


def test_modal_captures_clicks_inside_card():
    modal = (ROOT / "qml" / "components" / "ModalBase.qml").read_text(encoding="utf-8")
    assert 'acceptedButtons: Qt.AllButtons' in modal
    assert 'z: -1' in modal
    assert 'id: card' in modal


def test_account_modal_is_separate_from_game_version_modal():
    account = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    profiles = (ROOT / "qml" / "pages" / "ProfilesPage.qml").read_text(encoding="utf-8")
    assert 'SteamAccountModal {' in MAIN_QML
    assert 'onAccountRequested: steamAccountModal.open()' in MAIN_QML
    assert 'onClicked: gameVersionsModal.open()' in profiles
    assert 'steamAccount.downloadControlHint' in account


def test_steam_account_modal_imports_controls_for_busy_indicator():
    account = (ROOT / "qml" / "components" / "SteamAccountModal.qml").read_text(encoding="utf-8")
    assert "import QtQuick.Controls.Basic" in account
    assert "BusyIndicator {" in account


def test_game_versions_modal_uses_compact_modern_layout():
    qml = (ROOT / "qml" / "components" / "GameVersionsModal.qml").read_text(encoding="utf-8")
    assert 'cardWidth: 900' in qml
    assert 'title: I18n.t("gameVersions.title")' in qml
    assert 'GridLayout {' in qml
    assert 'StatusBadge {' in qml
    assert 'footer: [' in qml
    assert 'text: I18n.t("gameVersions.refresh")' in qml
    assert 'text: I18n.t("gameVersions.close")' in qml


def test_game_versions_modal_keeps_download_cancel_in_modal():
    qml = (ROOT / "qml" / "components" / "GameVersionsModal.qml").read_text(encoding="utf-8")
    assert 'text: I18n.t("gameVersions.downloadCancel")' in qml
    assert 'onClicked: GameVersions.cancel()' in qml
    assert 'GameVersions.downloadingBranch !== ""' in qml


def test_mod_card_has_web_search_action():
    qml = (ROOT / "qml" / "components" / "ModCard.qml").read_text(encoding="utf-8")
    assert 'text: I18n.t("mod.card.searchOnline")' in qml
    assert 'onTriggered: App.searchModOnline(card.name)' in qml
