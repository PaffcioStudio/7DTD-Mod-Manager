from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_global_search_placeholder_uses_i18n():
    qml = (ROOT / "qml" / "components" / "AppHeader.qml").read_text(encoding="utf-8")
    assert 'placeholder: I18n.t("globalSearch.placeholder")' in qml


def test_folder_picker_errors_are_localized():
    qml = (ROOT / "qml" / "components" / "FolderPickerModal.qml").read_text(encoding="utf-8")
    backend = (ROOT / "src" / "backend" / "file_browser.py").read_text(encoding="utf-8")
    assert 'I18n.resolveMessage(FileBrowser.error)' in qml
    assert 'folderPicker.error.read' in backend
    assert 'folderPicker.error.invalidPath' in backend


def test_file_dialog_titles_and_filters_use_i18n():
    qml = (ROOT / "qml" / "pages" / "SettingsPage.qml").read_text(encoding="utf-8")
    assert 'title: I18n.t("settings.game.fileDialog.exe")' in qml
    assert 'title: I18n.t("settings.game.fileDialog.gameDir")' in qml
    assert 'title: I18n.t("settings.game.fileDialog.modsDir")' in qml
    assert 'title: I18n.t("settings.game.fileDialog.downloadDir")' in qml
    assert 'I18n.t("settings.game.fileDialog.exeFilter")' in qml


def test_game_version_statuses_are_not_hardcoded_polish():
    py = (ROOT / "src" / "backend" / "game_versions.py").read_text(encoding="utf-8")
    for phrase in ("Zeskanuj kod QR w aplikacji mobilnej Steam", "Pobieram wersję", "Pobieranie anulowane.", "Nie udało się pobrać listy wersji"):
        assert phrase not in py
