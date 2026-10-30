"""Sprawdzenie powiązania czytnika z zakładką Profile bez uruchamiania Qt."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_profile_editor_exposes_sandbox_dialog():
    page = (ROOT / 'qml/pages/ProfilesPage.qml').read_text(encoding='utf-8')
    assert 'onClicked: sandboxModal.openFor(editorModal.instanceId)' in page
    assert 'id: sandboxModal' in page
    assert 'Profiles.sandboxWorlds(instanceId)' in page
    assert 'Profiles.sandboxInspect(instanceId, worldId, sandboxInput.text)' in page
    assert 'Profiles.saveSandboxCode(sandboxModal.instanceId,' in page
    assert 'I18n.language === "pl" ? modelData.pl : modelData.en' in page


def test_sandbox_translation_keys_exist_for_both_languages():
    source = (ROOT / 'qml/i18n/translations.js').read_text(encoding='utf-8')
    pl, en = source.split('var en = {', 1)
    for key in ('title', 'open', 'world', 'preview', 'save', 'sourceSaved',
                'sourceInput', 'sourceGame', 'error.no_world', 'error.no_code'):
        expected = f'"instances.sandbox.{key}":'
        assert expected in pl, key
        assert expected in en, key


def test_new_code_only_writes_launchers_json():
    code = (ROOT / 'src/backend/profile_manager.py').read_text(encoding='utf-8')
    assert '"sandbox-codes.json"' in code
    assert 'fs.write_json(self._sandbox_storage_path(), payload)' in code
    assert 'gameOptions.sdf' not in code


def test_sandbox_accessible_from_profile_card():
    card = (ROOT / 'qml/components/ProfileCard.qml').read_text(encoding='utf-8')
    page = (ROOT / 'qml/pages/ProfilesPage.qml').read_text(encoding='utf-8')
    assert 'signal sandboxRequested()' in card
    assert 'onClicked: root.sandboxRequested()' in card
    assert 'onSandboxRequested: sandboxModal.openFor(profileDelegate.profileId)' in page


def test_sandbox_is_shown_only_for_eligible_branches_and_steam_releases():
    card = (ROOT / 'qml/components/ProfileCard.qml').read_text(encoding='utf-8')
    page = (ROOT / 'qml/pages/ProfilesPage.qml').read_text(encoding='utf-8')
    steam = (ROOT / 'qml/pages/SteamReleasesPage.qml').read_text(encoding='utf-8')
    main = (ROOT / 'qml/Main.qml').read_text(encoding='utf-8')
    assert 'visible: Profiles.sandboxSupportsBranch(root.gameBranch)' in card
    assert 'Profiles.sandboxSupportsBranch(editorBranch.value)' in page
    assert 'Profiles.sandboxSupportsBranch(installedCard.modelData.branch)' in steam
    assert 'Profiles.sandboxSupportsBranch(branchRow.modelData.branch)' in steam
    assert 'page.sandboxRequested(installedCard.modelData.branch)' in steam
    assert 'page.sandboxRequested(branchRow.modelData.branch)' in steam
    assert 'profilesPage.openSandboxForBranch(branch)' in main


def test_sandbox_clipboard_and_auto_game_code_ui():
    page = (ROOT / 'qml/pages/ProfilesPage.qml').read_text(encoding='utf-8')
    backend = (ROOT / 'src/backend/profile_manager.py').read_text(encoding='utf-8')
    for phrase in ('instances.sandbox.copyCode', 'instances.sandbox.fromGame',
                   'Profiles.copySandboxCode(sandboxModal.preview.code)',
                   'sandboxInput.text = ""', 'description_short_pl', 'cardWidth: 720'):
        assert phrase in page
    assert 'clipboard.setText(normalized)' in backend
    assert 'def sandboxInstancesForBranch' in backend
    assert 'def sandboxSupportsBranch' in backend


def test_release_notes_latest_contains_sandbox_feature():
    notes = (ROOT / 'RELEASE_NOTES.md').read_text(encoding='utf-8')
    assert '## (latest) 1.0.50' in notes
    latest = notes.split('## (latest) 1.0.50', 1)[1].split('## 1.0.49', 1)[0]
    assert 'Sandbox settings for 7 Days to Die V3' in latest
    assert 'one-click copying' in latest


def test_sandbox_modal_is_compact_and_height_adaptive():
    page = (ROOT / 'qml/pages/ProfilesPage.qml').read_text(encoding='utf-8')
    block = page.split('id: sandboxModal', 1)[1].split('id: editorModFilter', 1)[0]
    assert 'cardWidth: 720' in page
    assert 'Math.max(120, Math.min(250, sandboxModal.height - 520))' in block
    assert 'description_short_en' in block
    assert 'modelData.description_en' not in block
    assert 'modelData.description_pl' not in block
