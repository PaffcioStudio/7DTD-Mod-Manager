from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_completed_mod_state_checks_real_installation_and_can_be_invalidated():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    assert "def _completed_mod_is_still_installed" in source
    assert "inst_mod.load_instances()" in source
    assert "library.load_library_entries()" in source
    assert 'if item.status == "completed" and not self._completed_mod_is_still_installed(item):' in source
    assert "self._model.remove(item.id)" in source


def test_completed_overhaul_requires_matching_live_instance_and_mod_folder():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    assert 'prefix = f"overhaul {slug}"' in source
    assert "description.startswith(prefix + \" \")" in source
    assert "instance.mods_dir" in source
    assert "child.is_dir() and find_modinfo(child) is not None" in source


def test_discover_refreshes_download_state_when_instance_registry_changes():
    main = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    assert "profiles.instancesChanged.connect(downloads.refreshModDownloadStates)" in main
    assert 'profiles.instanceRemoved.connect(lambda _id: downloads.refreshModDownloadStates())' in main
    dm = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    assert "def refreshModDownloadStates" in dm
    assert "self.activeMapChanged.emit()" in dm


def test_queue_restart_keeps_history_without_treating_it_as_install_proof():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    persist = source[source.index("def _persist_queue"):source.index("def _restore_queue")]
    assert 'if item.status == "completed" and item.kind != "mod":' in persist
    state = source[source.index("def modDownloads"):source.index("def activeMap")]
    assert "_completed_mod_is_still_installed(item)" in state
