"""Regression for valid V3 mods rejected with Steam branch 'public'."""

from backend.scraper_client import (
    ModFile, detect_artifact_game_versions, game_version_matches,
    select_concrete_game_version,
)


def test_public_matches_v3_catalog_label_and_specific_artifact():
    assert game_version_matches("public", ["V3 Mods"])
    assert game_version_matches("public", ["v3"])
    assert game_version_matches("public", ["v3.3"])
    assert game_version_matches("V3 Mods", ["public"])
    assert game_version_matches("v3.3", ["V3 Mods"])


def test_experimental_aliases_match_only_the_v3_family():
    for branch in ("latest", "latest_experimental", "latest_experimental_fallback"):
        assert game_version_matches(branch, ["V3 Mods"])
        assert not game_version_matches(branch, ["V2 Mods"])
        assert not game_version_matches(branch, ["Alpha 21"])


def test_other_catalog_families_are_still_supported():
    assert game_version_matches("v2.6", ["V2 Mods"])
    assert game_version_matches("alpha21.2", ["Alpha 21"])
    assert not game_version_matches("public", ["v2.6"])
    assert not game_version_matches("v2.6", ["V3 Mods"])
    assert not game_version_matches("alpha21", ["V3 Mods"])


def test_file_without_explicit_game_version_uses_single_page_declaration():
    # Mod Removal Guard has a generic archive name but the catalog reports V3.
    file = ModFile(id="file-1", media_id="", filename="ModRemovalGuard.zip",
                   size=37200, label="Mod Removal Guard", file_type="main",
                   version="1.0.0", scan_status="clean")
    assert detect_artifact_game_versions(
        label=file.label, filename=file.filename,
        declared_versions=["V3 Mods"], mod_version=file.version,
    ) == ["v3"]
    assert game_version_matches("public", ["V3 Mods"])
    assert select_concrete_game_version("public", ["v3"]) == "v3"
    assert select_concrete_game_version("public", ["V3 Mods"]) == "v3"


def test_an_ambiguous_catalog_label_is_not_used_to_bypass_version_filter():
    assert not game_version_matches("public", ["V2 Mods / Alpha 21"])
    assert not game_version_matches("public", [])
