from pathlib import Path

from backend.game_versions import required_game_branch


def test_alpha20_alias_resolves_to_steam_stable_branch():
    assert required_game_branch("Alpha 20") == "alpha20.7"
    assert required_game_branch("alpha20") == "alpha20.7"
    assert required_game_branch("alpha20.7") == "alpha20.7"


def test_other_known_legacy_alpha_aliases_are_concrete():
    assert required_game_branch("Alpha 17") == "alpha17.4"
    assert required_game_branch("Alpha 19") == "alpha19.6"


def test_modern_versions_are_not_guessed():
    assert required_game_branch("v3") == "v3"
    assert required_game_branch("latest_experimental") == "latest_experimental"


def test_game_version_helper_checks_physical_install(tmp_path, monkeypatch):
    import backend.game_versions as gv

    monkeypatch.setattr(gv, "versions_root", lambda: tmp_path)
    target = tmp_path / "alpha20.7"
    target.mkdir()
    (target / "7DaysToDie.exe").write_bytes(b"MZ")
    (target / "steam_appid.txt").write_text("251570", encoding="utf-8")

    manager = gv.GameVersionsManager.__new__(gv.GameVersionsManager)
    manager._versions = []
    assert manager.is_installed("Alpha 20") is True

    (target / "steam_appid.txt").unlink()
    assert manager.is_installed("alpha20.7") is False
