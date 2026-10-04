from pathlib import Path

from backend.game_versions import required_game_branch
from backend.scraper_client import select_concrete_game_version


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


def _fake_branch(root, name):
    d = root / name
    d.mkdir()
    (d / "7DaysToDie.exe").write_bytes(b"MZ")
    (d / "steam_appid.txt").write_text("251570", encoding="utf-8")


def test_major_only_slug_resolves_to_downloaded_patch_branch(tmp_path, monkeypatch):
    import backend.game_versions as gv

    monkeypatch.setattr(gv, "versions_root", lambda: tmp_path)
    assert gv.resolve_downloaded_branch("v2") == ""
    _fake_branch(tmp_path, "v2.6")
    _fake_branch(tmp_path, "v2.5")
    assert gv.resolve_downloaded_branch("v2") == "v2.6"
    assert gv.resolve_downloaded_branch("V2 Mods") == "v2.6"
    assert gv.resolve_downloaded_branch("v2.5") == "v2.5"
    assert gv.resolve_downloaded_branch("v1") == ""
    assert gv.resolve_downloaded_branch("v3") == ""
    _fake_branch(tmp_path, "latest_experimental")
    assert gv.resolve_downloaded_branch("v3") == "latest_experimental"


def test_every_catalog_tab_resolves_to_downloaded_steam_branch(tmp_path, monkeypatch):
    import backend.game_versions as gv

    monkeypatch.setattr(gv, "versions_root", lambda: tmp_path)
    for name in ("v1.4", "v2.6", "alpha17.4", "alpha18.4", "alpha19.6",
                 "alpha20.7", "alpha21.2", "v3.0", "v3.1", "public"):
        _fake_branch(tmp_path, name)
    expected = {
        "v1": "v1.4", "V2 Mods": "v2.6",
        "alpha17": "alpha17.4", "Alpha 18": "alpha18.4",
        "alpha19": "alpha19.6", "alpha20": "alpha20.7",
        "Alpha 21": "alpha21.2",
        "v3": "public", "v3.1": "v3.1",
    }
    for given, want in expected.items():
        assert gv.resolve_downloaded_branch(given) == want, given
    # alpha21 nie może trafić w inną alphę
    (tmp_path / "alpha21.2" / "steam_appid.txt").unlink()
    assert gv.resolve_downloaded_branch("alpha21") == ""
    # v3 bez public -> numerowany, potem experimental
    (tmp_path / "public" / "steam_appid.txt").unlink()
    assert gv.resolve_downloaded_branch("v3") == "v3.1"


def test_full_steam_branch_names_are_preserved(tmp_path, monkeypatch):
    import backend.game_versions as gv

    assert gv.required_game_branch("v3.2.0") == "v3.2.0"
    assert gv.required_game_branch("v3.0.1") == "v3.0.1"
    assert gv.required_game_branch("alpha21.2") == "alpha21.2"
    assert gv.required_game_branch("V2 Mods") == "v2"

    monkeypatch.setattr(gv, "versions_root", lambda: tmp_path)
    for name in ("v3.0.1", "v3.1.0", "v3.2.0"):
        _fake_branch(tmp_path, name)
    assert gv.resolve_downloaded_branch("v3.1") == "v3.1.0"
    assert gv.resolve_downloaded_branch("v3.0.1") == "v3.0.1"
    # bez public: najnowszy numerowany
    assert gv.resolve_downloaded_branch("v3") == "v3.2.0"


def test_select_concrete_game_version_prefers_file_patch_over_v2_family():
    assert select_concrete_game_version("v2", ["v2.6"]) == "v2.6"


def test_select_concrete_game_version_keeps_exact_patch():
    assert select_concrete_game_version("v2.6", ["v2.6"]) == "v2.6"


def test_select_concrete_game_version_rejects_ambiguous_no_selection():
    assert select_concrete_game_version("", ["v2.5", "v2.6"]) == ""


def test_single_external_artifact_without_filter_is_selected_for_branch_inference():
    from backend.download_manager import DownloadManager
    from backend.scraper_client import ExternalLink

    class Info:
        game_versions = ["V2 Mods"]

    link = ExternalLink(
        "mf",
        "https://www.mediafire.com/file/gm61vfy91x5l3lq/Your_End_2.4.1.7_Stable_V2.6(b14).zip/file",
        "Your End 2.4.1.7 Stable V2.6(b14).zip",
    )
    selected = DownloadManager._select_external_for_download([link], "", Info())
    assert selected is link


def test_multiple_external_artifacts_without_filter_are_not_guessed():
    from backend.download_manager import DownloadManager
    from backend.scraper_client import ExternalLink

    class Info:
        game_versions = ["V2 Mods", "V3 Mods"]

    links = [
        ExternalLink("v2", "https://example.invalid/v2.zip", "Overhaul V2.6.zip"),
        ExternalLink("v3", "https://example.invalid/v3.zip", "Overhaul V3.zip"),
    ]
    assert DownloadManager._select_external_for_download(links, "", Info()) is None


def test_single_external_artifact_without_version_data_is_not_guessed():
    from backend.download_manager import DownloadManager
    from backend.scraper_client import ExternalLink

    class Info:
        game_versions = ["V2 Mods", "V3 Mods"]

    link = ExternalLink(
        "mf", "https://example.invalid/download", "Download",
    )
    assert DownloadManager._select_external_for_download([link], "", Info()) is None
