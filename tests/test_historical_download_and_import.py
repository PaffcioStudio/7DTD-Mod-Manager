"""Regresje: polecenia DepotDownloadera, import i bezpieczeństwo katalogów."""
from pathlib import Path

from PySide6.QtCore import QCoreApplication
import pytest

from backend import game_versions


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _game(root: Path, exe: bytes = b"exe", assembly: bytes = b"managed") -> Path:
    root.mkdir(parents=True)
    (root / "7DaysToDie.exe").write_bytes(exe)
    managed = root / "7DaysToDie_Data" / "Managed"
    managed.mkdir(parents=True)
    (managed / "Assembly-CSharp.dll").write_bytes(assembly)
    return root


def test_legacy_command_uses_exact_manifest_and_right_depot(tmp_path):
    for branch, depot, manifest, arch in (
        ("alpha5.0", "251571", "8674858241122065491", "32"),
        ("alpha6.2", "251574", "3925976303593507227", "32"),
        ("alpha7.3-v2", "251576", "2677701425442127837", "64"),
        ("alpha8.7", "251576", "7508090567390550102", "64"),
    ):
        cmd = game_versions.build_download_command(
            tmp_path / "DepotDownloader", branch, tmp_path / branch,
            "testuser", False,
        )
        assert cmd[cmd.index("-depot") + 1] == depot
        assert cmd[cmd.index("-manifest") + 1] == manifest
        assert cmd[cmd.index("-osarch") + 1] == arch
        assert "-branch" not in cmd
        assert cmd[cmd.index("-username") + 1] == "testuser"


def test_alpha88_remains_standard_steam_branch(tmp_path):
    cmd = game_versions.build_download_command(
        Path("/tmp/depot"), "alpha8.8", tmp_path, "", True)
    assert "-manifest" not in cmd
    assert cmd[cmd.index("-branch") + 1] == "alpha8.8"
    assert "-qr" in cmd


def test_import_creates_link_without_copy_and_blocks_duplicate(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr(game_versions.fs, "data_dir", lambda: tmp_path / "state")
    source = _game(tmp_path / "outside")
    record = game_versions.import_game_version(str(source), "alpha5.0")
    link = tmp_path / "state" / "game-versions" / "alpha5.0"
    assert link.is_symlink()
    assert link.resolve() == source
    assert record["origin"] == "imported"
    assert (source / "steam_appid.txt").read_text() == "251570\n"
    assert game_versions.resolve_downloaded_branch("alpha5.0") == "alpha5.0"
    with pytest.raises(game_versions.GameVersionsError, match="steamReleases.legacy.error.duplicate(Location|Content)"):
        game_versions.import_game_version(str(source), "alpha5.0", "kolejna")

    manager = game_versions.GameVersionsManager()
    manager.deleteVersion("alpha5.0")
    assert not link.is_symlink()
    assert (source / "7DaysToDie.exe").is_file()


def test_import_rejects_duplicated_content_and_wrong_appid(tmp_path, monkeypatch):
    monkeypatch.setattr(game_versions.fs, "data_dir", lambda: tmp_path / "state")
    game_versions.import_game_version(str(_game(tmp_path / "one")), "alpha5.0")
    with pytest.raises(game_versions.GameVersionsError, match="steamReleases.legacy.error.duplicateContent"):
        game_versions.import_game_version(str(_game(tmp_path / "two")), "alpha5.0", "other")
    bad = _game(tmp_path / "bad", exe=b"different")
    (bad / "steam_appid.txt").write_text("730\n")
    with pytest.raises(game_versions.GameVersionsError, match="steamReleases.legacy.error.wrongAppId"):
        game_versions.import_game_version(str(bad), "alpha6.0")


def test_custom_import_name_is_sanitized(tmp_path, monkeypatch):
    monkeypatch.setattr(game_versions.fs, "data_dir", lambda: tmp_path / "state")
    record = game_versions.import_game_version(
        str(_game(tmp_path / "outside")), "alpha5.0", "Moja wersja !")
    assert record["branch"] == "custom-moja-wersja"
    assert (tmp_path / "state" / "game-versions" / "custom-moja-wersja").is_symlink()


def test_deletion_rejects_forged_registry_path(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr(game_versions.fs, "data_dir", lambda: tmp_path / "state")
    source = _game(tmp_path / "outside")
    game_versions.save_versions([{"branch": "alpha5.0", "dir": str(source)}])
    manager = game_versions.GameVersionsManager()
    manager.deleteVersion("alpha5.0")
    assert source.exists()
    assert game_versions.load_versions()


def test_import_status_messages_are_localizable(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr(game_versions.fs, "data_dir", lambda: tmp_path / "state")
    manager = game_versions.GameVersionsManager()
    assert manager.importVersion(str(tmp_path / "missing"), "alpha5.0", "")
    assert "steamReleases.legacy.error.importFailed" in manager.status
    game = _game(tmp_path / "ready")
    assert manager.importVersion(str(game), "alpha5.0", "") == ""
    assert "steamReleases.legacy.importSuccess" in manager.status


@pytest.mark.parametrize('branch', ['alpha6.0', 'alpha6.1', 'alpha6.2', 'alpha6.3', 'alpha6.4'])
@pytest.mark.parametrize('reinstall', [False, True])
def test_unavailable_release_never_starts_downloader(tmp_path, monkeypatch, branch, reinstall):
    app = _app()
    monkeypatch.setattr(game_versions.fs, 'data_dir', lambda: tmp_path / 'state')
    def unexpected_tool():
        pytest.fail('Niedostępny depot nie powinien uruchamiać downloadera')
    monkeypatch.setattr(game_versions, 'ensure_tool', unexpected_tool)
    manager = game_versions.GameVersionsManager()
    started = []
    manager.gameDownloadStarted.connect(lambda *args: started.append(args))
    action = manager.reinstall if reinstall else manager.download
    assert action(branch) is False
    assert 'steamReleases.legacy.downloadUnavailable' in manager.status
    assert '251574' in manager.status
    assert not started
    assert not manager.busy
    assert not (game_versions.versions_root() / branch).exists()


def test_unavailable_steam_release_can_still_be_imported(tmp_path, monkeypatch):
    monkeypatch.setattr(game_versions.fs, 'data_dir', lambda: tmp_path / 'state')
    source = _game(tmp_path / 'alpha6')
    record = game_versions.import_game_version(str(source), 'alpha6.2')
    assert record['origin'] == 'imported'
    assert game_versions.resolve_downloaded_branch('alpha6.2') == 'alpha6.2'
    assert source.is_dir()
