from pathlib import Path
from unittest.mock import patch

import pytest

from backend import game_process, mod_dedup


def mod(root, folder, name):
    path = root / "Mods" / folder
    path.mkdir(parents=True)
    (path / "ModInfo.xml").write_text(f'<xml><Name value="{name}"/></xml>')
    (path / "Resources").mkdir()
    (path / "Resources" / "asset").write_bytes(b"resource")
    return path


def test_pack_wins_and_other_instance_restores_game_copy(tmp_path):
    game, instance = tmp_path / "game", tmp_path / "instance"
    original = mod(game, "0_TFP_Harmony", "TFP_Harmony")
    pack = mod(instance, "renamed", "tfp_harmony")
    unique = mod(game, "Other", "Other")
    for _ in range(2):
        assert mod_dedup.sync_game_dir(game, instance) == [original.name]
        assert not (original / "ModInfo.xml").exists()
        assert (original / "Resources" / "asset").read_bytes() == b"resource"
        assert (pack / "ModInfo.xml").is_file()
        assert (unique / "ModInfo.xml").is_file()
    mod_dedup.sync_game_dir(game, tmp_path / "empty-instance")
    assert (original / "ModInfo.xml").is_file()
    mod_dedup.sync_game_dir(game, instance)
    mod_dedup.sync_game_dir(game, None)
    assert (original / "ModInfo.xml").is_file()


def test_harmony_aliases_and_library_symlink(tmp_path):
    game, instance = tmp_path / "game", tmp_path / "instance"
    original = mod(game, "harmony-game", "game-wrapper")
    library = mod(tmp_path / "library", "harmony-pack", "pack-wrapper")
    for folder in (original, library):
        (folder / "0Harmony.dll").write_bytes(b"dll")
        (folder / "TfpHarmony.dll").write_bytes(b"dll")
    (instance / "Mods").mkdir(parents=True)
    (instance / "Mods" / "pack").symlink_to(library, target_is_directory=True)
    mod_dedup.sync_game_dir(game, instance)
    assert not (original / "ModInfo.xml").exists()
    assert (library / "ModInfo.xml").exists()


def test_recreated_descriptor_blocks_without_overwriting(tmp_path):
    original = mod(tmp_path / "game", "Harmony", "Harmony")
    mod(tmp_path / "instance", "Harmony", "Harmony")
    mod_dedup.sync_game_dir(tmp_path / "game", tmp_path / "instance")
    (original / "ModInfo.xml").write_text("new from Steam")
    with pytest.raises(FileExistsError):
        mod_dedup.sync_game_dir(tmp_path / "game", None)
    assert (original / "ModInfo.xml").read_text() == "new from Steam"
    assert (tmp_path / "game" / mod_dedup.BACKUP_DIR / "Harmony" / "ModInfo.xml").exists()


def test_rollback_and_no_changes_to_symlinked_game_mod(tmp_path):
    game, instance = tmp_path / "game", tmp_path / "instance"
    first = mod(game, "A", "A")
    external = mod(tmp_path / "library", "B", "B")
    (game / "Mods" / "B").symlink_to(external, target_is_directory=True)
    mod(instance, "A", "A")
    mod(instance, "B", "B")
    with pytest.raises(OSError):
        mod_dedup.sync_game_dir(game, instance)
    assert (first / "ModInfo.xml").is_file()
    assert (external / "ModInfo.xml").is_file()


def test_same_mods_root_is_not_disabled(tmp_path):
    original = mod(tmp_path, "Harmony", "Harmony")
    assert mod_dedup.sync_game_dir(tmp_path, tmp_path) == []
    assert (original / "ModInfo.xml").exists()


def test_case_insensitive_folder_and_descriptor_and_resource_only_mod(tmp_path):
    game, instance = tmp_path / "game", tmp_path / "instance"
    original = mod(game, "Example", "old-name")
    pack = mod(instance, "example", "new-name")
    (pack / "ModInfo.xml").rename(pack / "modinfo.XML")
    # Resource links deployed by BepInEx are not loadable mods.
    resources = mod(game, "OnlyResources", "unused")
    (resources / "ModInfo.xml").unlink()
    mod(instance, "OnlyResources", "unused")
    assert mod_dedup.sync_game_dir(game, instance) == ["Example"]
    assert not (original / "ModInfo.xml").exists()
    assert (resources / "Resources" / "asset").exists()


def test_running_game_blocks_preparation(tmp_path):
    with patch.object(game_process, "is_game_running", return_value=True), \
         patch.object(mod_dedup, "sync_game_dir") as sync:
        assert not game_process._prepare_game_mods(tmp_path, None)
        sync.assert_not_called()


def test_steam_launch_reconciles_actual_library(tmp_path):
    game, instance = tmp_path / "library" / "steamapps" / "common" / "7 Days To Die", tmp_path / "instance"
    original = mod(game, "Harmony", "Harmony")
    mod(instance, "Harmony", "Harmony")
    manifest = game.parents[1] / "appmanifest_251570.acf"
    manifest.write_text('"AppState" { "installdir" "7 Days To Die" }')
    with patch.object(game_process, "_steam_library_roots", return_value=[tmp_path / "library"]), \
         patch.object(game_process, "_find_steam_binary", return_value="steam"), \
         patch.object(game_process, "is_game_running", return_value=False), \
         patch.object(game_process.subprocess, "Popen") as popen:
        assert game_process.launch_game_via_steam(instance)
        assert not (original / "ModInfo.xml").exists()
        popen.assert_called_once()
        (original / "ModInfo.xml").write_text("recreated")
        popen.reset_mock()
        assert not game_process.launch_game_via_steam(instance)
        popen.assert_not_called()
