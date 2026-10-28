"""Ręczne kody Steam korzystają z normalnego pobierania i rejestru gry."""
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from backend import game_versions as gv

CODE = '251570 251576 1234567890123456789'
BRANCH = 'manifest-251576-1234567890123456789'


@pytest.fixture
def manager(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(gv.fs, 'data_dir', lambda: tmp_path / 'state')
    monkeypatch.setattr(gv, 'ensure_tool', lambda: tmp_path / 'DepotDownloader')
    monkeypatch.setattr(gv.GameVersionsManager, '_cleanup_stale_depot_processes', lambda *args: 0)
    result = gv.GameVersionsManager()
    yield result
    thread = result._worker_thread
    if thread:
        thread.join(timeout=3)
        assert not thread.is_alive()
    app.processEvents()


def finish(manager):
    thread = manager._worker_thread
    if thread:
        thread.join(timeout=3)
        assert not thread.is_alive()
    QCoreApplication.processEvents()


def write_game(cmd):
    target = Path(cmd[cmd.index('-dir') + 1])
    (target / '7DaysToDie.exe').write_bytes(b'MZ')
    managed = target / '7DaysToDie_Data' / 'Managed'
    managed.mkdir(parents=True, exist_ok=True)
    (managed / 'Assembly-CSharp.dll').write_bytes(b'game')


@pytest.mark.parametrize('code', [CODE, '  251570\t251576\n1234567890123456789  ', 'download_depot ' + CODE])
def test_codes_are_normalized_and_survive_restart(code):
    assert gv.branch_for_depot_code(code) == BRANCH
    source = gv.manifest_source(BRANCH)
    assert source == {'app_id': '251570', 'depot': '251576', 'manifest': '1234567890123456789', 'osarch': '64'}
    assert len(gv.branch_for_depot_code('251570 4294967295 18446744073709551615')) <= 40
    cmd = gv.build_download_command(Path('/tool'), BRANCH, Path('/target'), 'user', False)
    assert cmd[cmd.index('-manifest') + 1] == source['manifest']
    assert cmd[cmd.index('-depot') + 1] == source['depot']
    assert '-branch' not in cmd


@pytest.mark.parametrize('code', ['', '251570 251576', CODE + ' extra', CODE + '; touch /tmp/test',
                                 '-1 251576 1', '251570 0 1', '251570 251576 0',
                                 '251570 4294967296 1', '251570 251576 18446744073709551616',
                                 '251570 251576 ' + '9' * 5000])
def test_invalid_codes_are_rejected_without_starting_worker(manager, code):
    assert manager.downloadCode(code) is False
    assert 'steamReleases.code.invalid' in manager.status
    assert not manager.busy
    assert not gv.load_versions()


def test_other_apps_and_unavailable_depots_are_rejected(manager):
    assert manager.downloadCode('730 251576 123') is False
    assert 'steamReleases.code.wrongApp' in manager.status
    for code in ('251570 251574 7417461347934718866', '251570 251574 123'):
        assert manager.downloadCode(code) is False
        assert 'steamReleases.legacy.downloadUnavailable' in manager.status
    assert not manager.busy


def test_known_code_uses_existing_catalog_branch(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(manager, 'download', lambda branch: calls.append(branch) or True)
    assert manager.downloadCode('251570 251576 1730022800995997518') is True
    assert calls == ['alpha7.0']


def test_success_registers_exact_manifest_and_duplicate_is_not_downloaded(manager, monkeypatch):
    calls = []
    events = []
    manager.gameDownloadStarted.connect(lambda *args: events.append(('start', args)))
    manager.gameDownloadFinished.connect(lambda *args: events.append(('finish', args)))
    def run(cmd, branch, status):
        calls.append(cmd)
        assert not gv.load_versions()
        write_game(cmd)
        manager._set_busy(False)
        return ''
    monkeypatch.setattr(manager, '_run_depot', run)
    assert manager.downloadCode(CODE) is True
    finish(manager)
    record, = gv.load_versions()
    assert record['branch'] == BRANCH
    assert record['dir'] == str(gv.versions_root() / BRANCH)
    assert record['app_id'] == '251570'
    assert record['depot'] == '251576'
    assert record['manifest'] == '1234567890123456789'
    assert record['origin'] == 'steam_manifest'
    assert gv.resolve_downloaded_branch(BRANCH) == BRANCH
    assert BRANCH in {item['branch'] for item in manager.branchChoices}
    assert events[0][0] == 'start'
    assert events[-1][1][1] == 'completed'
    assert manager.downloadCode(CODE) is False
    assert len(calls) == 1
    assert 'alreadyDownloaded' in manager.status


def test_paused_code_resumes_in_new_manager_and_can_be_reinstalled(manager, monkeypatch):
    def paused(cmd, branch, status):
        manager._pause_requested.set()
        manager._set_busy(False)
        return ''
    monkeypatch.setattr(manager, '_run_depot', paused)
    assert manager.downloadCode(CODE)
    finish(manager)
    assert not gv.load_versions()
    restarted = gv.GameVersionsManager()
    calls = []
    def success(cmd, branch, status):
        calls.append(cmd)
        write_game(cmd)
        restarted._set_busy(False)
        return ''
    monkeypatch.setattr(restarted, '_run_depot', success)
    assert restarted.resume(BRANCH)
    finish(restarted)
    assert restarted.reinstall(BRANCH)
    finish(restarted)
    assert len(calls) == 2
    assert all(cmd[cmd.index('-manifest') + 1] == '1234567890123456789' for cmd in calls)
    assert calls[-1][calls[-1].index('-dir') + 1].endswith('.reinstall')
    assert gv.resolve_downloaded_branch(BRANCH) == BRANCH


@pytest.mark.parametrize('failure', ['error', 'incomplete'])
def test_failed_or_incomplete_code_is_not_registered(manager, monkeypatch, failure):
    def run(cmd, branch, status):
        manager._set_busy(False)
        return 'test failure' if failure == 'error' else ''
    monkeypatch.setattr(manager, '_run_depot', run)
    assert manager.downloadCode(CODE)
    finish(manager)
    assert not gv.load_versions()
    assert gv.resolve_downloaded_branch(BRANCH) == ''
