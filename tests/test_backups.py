"""Instance backups: create / update / restore / delete and the one-time
migration of the backup folders from modpacks/ to backups/."""
from pathlib import Path

import pytest

from backend import instances as inst_mod
from backend import modpacks
from services import filesystem_service as fs


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _make_instance(home: Path, instance_id="inst1", name="Test") -> inst_mod.Instance:
    data = home / "data" / instance_id
    (data / "Mods" / "ModA").mkdir(parents=True)
    (data / "Mods" / "ModA" / "ModInfo.xml").write_text("<xml/>")
    (data / "Saves").mkdir()
    (data / "Saves" / "world.sav").write_text("original-save")
    instance = inst_mod.Instance(instance_id=instance_id, name=name, data_dir=str(data))
    inst_mod.save_instances([instance])
    return instance


def _tree(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): p.read_text()
            for p in sorted(path.rglob("*")) if p.is_file()}


# --------------------------------------------------------------- layout --- #
def test_backup_lives_under_backups_not_modpacks(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    assert Path(record.path) == home / ".7dtd_modmanager" / "backups" / "inst1"
    assert not (home / ".7dtd_modmanager" / "modpacks").exists()
    assert _tree(Path(record.path)) == _tree(instance.data_path)


def test_second_backup_for_same_instance_is_blocked(home):
    instance = _make_instance(home)
    modpacks.create_backup_from_instance(instance)
    with pytest.raises(FileExistsError):
        modpacks.create_backup_from_instance(instance)


# -------------------------------------------------------------- restore --- #
def test_restore_brings_back_deleted_and_changed_files(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    original = _tree(instance.data_path)

    (instance.data_path / "Saves" / "world.sav").write_text("corrupted")
    (instance.data_path / "Mods" / "ModA" / "ModInfo.xml").unlink()
    (instance.data_path / "junk.txt").write_text("not in backup")

    modpacks.restore_backup(record)
    assert _tree(instance.data_path) == original


def test_restore_recreates_deleted_instance(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    original = _tree(instance.data_path)
    inst_mod.save_instances([])                       # instance removed from registry
    import shutil
    shutil.rmtree(instance.data_path)

    target = modpacks.restore_backup(record)
    assert target.instance_id == "inst1" and target.name == "Test"
    assert inst_mod.find_instance(inst_mod.load_instances(), "inst1") is not None
    assert _tree(instance.data_path) == original


def test_update_refreshes_backup_content(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    (instance.data_path / "Saves" / "new.sav").write_text("later")
    modpacks.update_backup_from_instance(record, instance)
    assert (Path(record.path) / "Saves" / "new.sav").read_text() == "later"


# --------------------------------------------------------------- delete --- #
def test_delete_removes_folder_and_record(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    modpacks.delete_backup(record)
    assert not Path(record.path).exists()
    assert modpacks.load_backups() == []
    assert instance.data_path.exists()                # the instance itself is untouched


def test_delete_refuses_path_outside_backup_roots(home):
    instance = _make_instance(home)
    record = modpacks.create_backup_from_instance(instance)
    record.path = str(instance.data_path)             # tampered record
    with pytest.raises(ValueError):
        modpacks.delete_backup(record)
    assert instance.data_path.exists()


# ------------------------------------------------------------ migration --- #
def _legacy_backup(home: Path, instance_id="inst1") -> modpacks.BackupRecord:
    """A backup as written by the previous version (folder in modpacks/)."""
    legacy = fs.legacy_modpacks_root() / instance_id
    (legacy / "Saves").mkdir(parents=True)
    (legacy / "Saves" / "world.sav").write_text("legacy-save")
    record = modpacks.BackupRecord(
        instance_id=instance_id, instance_name="Legacy",
        data_dir=str(home / "data" / instance_id), flags={}, path=str(legacy),
        created_at="2026-09-01T10:00:00", updated_at="2026-09-01T10:00:00")
    modpacks.save_backups([record])
    return record


def test_migration_moves_folder_and_rewrites_path(home):
    _legacy_backup(home)
    assert modpacks.migrate_legacy_layout() == 1
    new = fs.backups_root() / "inst1"
    assert (new / "Saves" / "world.sav").read_text() == "legacy-save"
    assert [r.path for r in modpacks.load_backups()] == [str(new)]
    assert not fs.legacy_modpacks_root().exists()     # empty legacy folder removed


def test_migration_is_idempotent(home):
    _legacy_backup(home)
    assert modpacks.migrate_legacy_layout() == 1
    assert modpacks.migrate_legacy_layout() == 0


def test_migrated_backup_can_be_restored_and_deleted(home):
    instance = _make_instance(home, name="Legacy")
    legacy = _legacy_backup(home)
    modpacks.migrate_legacy_layout()
    record = modpacks.load_backups()[0]
    modpacks.restore_backup(record)
    assert (instance.data_path / "Saves" / "world.sav").read_text() == "legacy-save"
    modpacks.delete_backup(record)
    assert not Path(record.path).exists() and modpacks.load_backups() == []


def test_migration_repoints_record_after_interrupted_run(home):
    legacy = _legacy_backup(home)
    fs.backups_root().mkdir(parents=True)
    (fs.legacy_modpacks_root() / "inst1").rename(fs.backups_root() / "inst1")  # moved, record not saved
    modpacks.migrate_legacy_layout()
    assert modpacks.load_backups()[0].path == str(fs.backups_root() / "inst1")


def test_migration_never_overwrites_existing_target(home):
    _legacy_backup(home)
    existing = fs.backups_root() / "inst1"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("do not touch")
    assert modpacks.migrate_legacy_layout() == 0
    assert (existing / "keep.txt").read_text() == "do not touch"
    assert (fs.legacy_modpacks_root() / "inst1" / "Saves" / "world.sav").exists()
    # not migrated, but still deletable thanks to the legacy root being allowed
    record = modpacks.load_backups()[0]
    modpacks.delete_backup(record)
    assert not (fs.legacy_modpacks_root() / "inst1").exists()


def test_migration_keeps_unknown_content_in_legacy_folder(home):
    _legacy_backup(home)
    stray = fs.legacy_modpacks_root() / "something-else"
    stray.mkdir()
    (stray / "x.txt").write_text("user file")
    modpacks.migrate_legacy_layout()
    assert (stray / "x.txt").read_text() == "user file"   # legacy folder kept, not deleted


def test_migration_without_legacy_folder_is_noop(home):
    assert modpacks.migrate_legacy_layout() == 0
