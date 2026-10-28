"""Widoczna reakcja UI na nieprawidłowy folder i brakujące pliki gry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_import_result_shows_error_and_success():
    qml = (ROOT / "qml/pages/SteamReleasesPage.qml").read_text()
    assert 'const failure = GameVersions.importVersion(' in qml
    assert 'page.importFeedback = I18n.resolveMessage(failure)' in qml
    assert 'Bus.toast(page.importFeedback, "error")' in qml
    assert 'Bus.toast(page.importFeedback, "success")' in qml
    assert 'visible: page.importFeedback !== ""' in qml


def test_import_requires_game_assembly_and_translations():
    code = (ROOT / "src/backend/game_versions.py").read_text()
    translations = (ROOT / "qml/i18n/translations.js").read_text()
    assert '"Managed" / "Assembly-CSharp.dll"' in code
    assert translations.count('"steamReleases.legacy.error.invalidGameFiles"') == 2


def test_restored_game_queue_has_pause_cancel_and_recovery():
    card = (ROOT / "qml/components/DownloadCard.qml").read_text()
    manager = (ROOT / "src/backend/download_manager.py").read_text()
    assert 'root.kind === "game" && root.statusKey === "queued"' in card
    assert 'self.resumeRestoredGameDownloads()' in manager
    assert 'item.status = "downloading"' in manager
