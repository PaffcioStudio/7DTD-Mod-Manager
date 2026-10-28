"""Statyczne regresje integracji reinstalacji i wyboru folderu."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_and_regular_releases_have_reinstall_controls():
    qml = (ROOT / 'qml/pages/SteamReleasesPage.qml').read_text(encoding='utf-8')
    assert 'GameVersions.reinstall(branch)' in qml
    assert 'GameVersions.reinstall' in qml
    assert 'I18n.t("steamReleases.reinstall")' in qml
    assert 'page.askReinstallRelease(page.selectedHistoricalBranch)' in qml
    assert 'page.askReinstallRelease(branchRow.modelData.branch)' in qml


def test_folder_picker_buttons_follow_application_language():
    browser = (ROOT / 'qml/components/FolderPickerModal.qml').read_text(encoding='utf-8')
    assert 'I18n.t("folderPicker.cancel")' in browser
    assert 'root.confirmText' in browser
    releases = (ROOT / 'qml/pages/SteamReleasesPage.qml').read_text(encoding='utf-8')
    assert 'FolderPickerModal {' in releases
    settings = (ROOT / 'qml/pages/SettingsPage.qml').read_text(encoding='utf-8')
    assert 'FolderPickerModal {' in settings
    locale = (ROOT / 'qml/i18n/translations.js').read_text(encoding='utf-8')
    for item in ('"folderPicker.cancel": "Cancel"',
                 '"folderPicker.chooseFile": "Choose file"',
                 '"folderPicker.chooseFolder": "Choose folder"',
                 '"steamReleases.reinstall": "Reinstall"'):
        assert item in locale


def test_staged_reinstall_and_validated_download_only():
    code = (ROOT / 'src/backend/game_versions.py').read_text(encoding='utf-8')
    assert 'reinstall_stage(branch)' in code
    assert '_replace_version_after_download(branch, target, installed_target)' in code
    assert 'if not _game_files_look_complete(target):' in code
    assert 'entry["installed"] = self.is_installed' in code
