from pathlib import Path

from backend import instances as inst


def test_suggest_data_dir_preserves_version_dot(tmp_path, monkeypatch):
    monkeypatch.setattr(inst.fs, "instances_root", lambda: tmp_path / "instances")
    assert inst.suggest_data_dir_for_name("15.5") == tmp_path / "instances" / "15.5"


def test_suggest_data_dir_strips_leading_dot_but_keeps_name_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(inst.fs, "instances_root", lambda: tmp_path / "instances")
    assert inst.suggest_data_dir_for_name(".fajnagierka") == tmp_path / "instances" / "fajnagierka"
    assert inst.suggest_data_dir_for_name("...fajnagierka") == tmp_path / "instances" / "fajnagierka"


def test_suggest_data_dir_keeps_internal_dots(tmp_path, monkeypatch):
    monkeypatch.setattr(inst.fs, "instances_root", lambda: tmp_path / "instances")
    assert inst.suggest_data_dir_for_name("Alpha 15.5 Test") == tmp_path / "instances" / "alpha-15.5-test"


def test_new_instance_rejects_existing_data_directory(tmp_path):
    instances = [inst.make_default_instance()]
    data_dir = tmp_path / "existing"
    data_dir.mkdir()
    error = inst.validate_instance_data_dir(str(data_dir), instances)
    assert error is not None
    assert error.startswith("__I18N__:instances.dataPathExists|")


def test_editing_instance_allows_its_own_existing_data_directory(tmp_path):
    data_dir = tmp_path / "existing"
    data_dir.mkdir()
    current = inst.Instance("current", "15.5", str(data_dir))
    instances = [inst.make_default_instance(), current]
    assert inst.validate_instance_data_dir(str(data_dir), instances, current_id="current") is None


def test_editing_instance_rejects_other_existing_unregistered_directory(tmp_path):
    own = tmp_path / "own"
    other = tmp_path / "other"
    own.mkdir()
    other.mkdir()
    current = inst.Instance("current", "Current", str(own))
    instances = [inst.make_default_instance(), current]
    error = inst.validate_instance_data_dir(str(other), instances, current_id="current")
    assert error is not None
    assert error.startswith("__I18N__:instances.targetExists|")


def test_suggest_data_dir_does_not_create_hidden_directory_for_dot_name(tmp_path, monkeypatch):
    monkeypatch.setattr(inst.fs, "instances_root", lambda: tmp_path / "instances")
    path = inst.suggest_data_dir_for_name(".7")
    assert path.name == "7"
    assert not path.name.startswith(".")


def test_imported_pack_defaults_disable_eos_and_eac():
    import backend.instances as instances

    item = {
        "instance_id": "pack",
        "name": "Alpha 20 Pack",
        "description": "Zestaw alpha20 z 7daystodiemods.com",
        "flags": {"noeos": False, "noeac": False},
    }
    inst = instances._instance_from_dict(item)
    assert inst.flag_noeos is True
    assert inst.flag_noeac is True


def test_favorite_instances_load_first_and_preserve_nonfavorite_order(tmp_path, monkeypatch):
    import backend.instances as instances

    path = tmp_path / "instances.json"
    monkeypatch.setattr(instances.fs, "instances_path", lambda: path)
    raw = {
        "instances": [
            {"instance_id": "a", "name": "A", "favorite": False},
            {"instance_id": "b", "name": "B", "favorite": True},
            {"instance_id": "c", "name": "C", "favorite": False},
        ]
    }
    path.write_text(__import__("json").dumps(raw), encoding="utf-8")
    loaded = instances.load_instances()
    assert [x.instance_id for x in loaded] == ["b", "a", "c"]


def test_favorite_is_persisted_by_instance_serialization():
    import backend.instances as instances

    obj = instances.Instance("fav", "Ulubiona", "/tmp/fav", favorite=True)
    raw = instances._instance_to_dict(obj)
    assert raw["favorite"] is True
    restored = instances._instance_from_dict(raw)
    assert restored.favorite is True
