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


def test_game_download_queue_is_persisted_and_not_started_by_http_pool():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    persist = source[source.index("def _persist_queue"):source.index("def _restore_queue")]
    restore = source[source.index("def _restore_queue"):source.index("def reset_demo")]
    promote = source[source.index("def _promote_queued"):source.index("def _on_completed")]
    assert 'item.kind == "game"' not in persist.split('if not item.real', 1)[1].split('continue', 1)[0]
    assert '"total_bytes": int(item.total_bytes or 0)' in persist
    assert '"progress": float(item.progress)' in persist
    assert 'if kind != "game" and not rec.get("url")' in restore
    assert 'item.restored_from_queue = True' in restore
    assert 'if item.kind == "game":' in promote
    assert 'self._start_url_worker(item)' in promote


def test_restored_game_downloads_have_explicit_auto_resume_hook():
    source = (ROOT / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
    main = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    assert "def resumeRestoredGameDownloads" in source
    assert 'and i.restored_from_queue' in source
    assert 'self._game_versions.resume(item.ref_id)' in source
    assert 'QTimer.singleShot(0, downloads.resumeRestoredGameDownloads)' in main
