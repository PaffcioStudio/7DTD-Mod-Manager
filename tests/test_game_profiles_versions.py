from pathlib import Path

from PySide6.QtCore import QCoreApplication

from backend import game_profiles
from backend import instances as inst


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _instance(tmp_path: Path, branch: str) -> inst.Instance:
    data = tmp_path / (branch.replace("/", "_") or "steam")
    data.mkdir(parents=True, exist_ok=True)
    return inst.Instance(
        instance_id=branch or "steam",
        name=branch or "Steam",
        data_dir=str(data),
        game_branch=branch,
    )


def test_central_presets_only_v3_and_newer(tmp_path):
    assert not game_profiles._instance_supports_central_presets(_instance(tmp_path, "alpha12.5"))
    assert not game_profiles._instance_supports_central_presets(_instance(tmp_path, "v2.6"))
    assert game_profiles._instance_supports_central_presets(_instance(tmp_path, "v3.0"))
    assert game_profiles._instance_supports_central_presets(_instance(tmp_path, "v4.1"))
    assert game_profiles._instance_supports_central_presets(_instance(tmp_path, "public"))
    assert game_profiles._instance_supports_central_presets(_instance(tmp_path, ""))


def _manager_with_profile(instance, source):
    _app()
    profile_id = game_profiles.GameProfileManager._profile_id(source.name)
    profile = game_profiles.GameProfile(profile_id, source.name, source.stem, source)
    manager = game_profiles.GameProfileManager()
    manager._instances = [instance]
    manager._profiles = {profile_id: profile}
    manager._global_ids = set()
    manager._instance_ids = {}
    return manager, profile_id


def test_old_version_managed_preset_symlink_is_removed_but_file_is_kept(tmp_path):
    instance = _instance(tmp_path, "alpha13.8")
    presets = instance.data_path / "Presets"
    presets.mkdir(exist_ok=True)
    central = tmp_path / "profiles"
    central.mkdir()
    source = central / "Survivor.xml"
    source.write_text("<profile/>", encoding="utf-8")
    managed = presets / source.name
    managed.symlink_to(source)

    manager, _ = _manager_with_profile(instance, source)
    manager._sync_instance_links()

    assert not managed.is_symlink()
    assert not managed.exists()
    assert source.is_file()


def test_v3_instance_receives_managed_preset_symlink(tmp_path):
    instance = _instance(tmp_path, "v3.0")
    presets = instance.data_path / "Presets"
    presets.mkdir(exist_ok=True)
    central = tmp_path / "profiles"
    central.mkdir()
    source = central / "Survivor.xml"
    source.write_text("<profile/>", encoding="utf-8")

    manager, profile_id = _manager_with_profile(instance, source)
    manager._global_ids = {profile_id}
    manager._sync_instance_links()

    managed = presets / source.name
    assert managed.is_symlink()
    assert managed.resolve(strict=False) == source.resolve(strict=False)


def test_instance_assignment_is_ignored_for_old_versions(tmp_path):
    instance = _instance(tmp_path, "v2.6")
    presets = instance.data_path / "Presets"
    presets.mkdir(exist_ok=True)
    source = tmp_path / "Survivor.xml"
    source.write_text("<profile/>", encoding="utf-8")

    manager, profile_id = _manager_with_profile(instance, source)
    manager.setInstanceEnabled(profile_id, instance.instance_id, True)

    assert manager._instance_ids == {}


def test_preset_sync_ignores_old_alpha_even_when_profile_is_globally_enabled(tmp_path):
    instance = _instance(tmp_path, "alpha17.4")
    presets = instance.data_path / "Presets"
    presets.mkdir(exist_ok=True)
    central = tmp_path / "profiles"
    central.mkdir(exist_ok=True)
    source = central / "OldBuild.xml"
    source.write_text("<profile/>", encoding="utf-8")

    manager, profile_id = _manager_with_profile(instance, source)
    manager._global_ids = {profile_id}
    manager._sync_instance_links()

    managed = presets / source.name
    assert not managed.is_symlink()
    assert source.is_file()
