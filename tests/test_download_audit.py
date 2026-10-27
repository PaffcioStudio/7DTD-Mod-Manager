"""Behavioral regressions from the download/instance audit; isolated user data."""
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from PySide6.QtCore import QCoreApplication, QObject, Signal

from backend import google_drive_download as drive
from backend import download_manager as dm, game_versions as gv, game_process as gp
from backend import modpack_downloader as pack
from backend.scraper_client import SevenDaysModsClient
from services.settings_service import SettingsService
from services import filesystem_service as fs
from backend.events import EventBus


class Mods(QObject):
    demoReset = Signal()


@pytest.fixture
def manager(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(dm.DownloadManager, '_start_mod_worker', Mock())
    monkeypatch.setattr(dm.DownloadManager, '_start_url_worker', Mock())
    mods = Mods()
    obj = dm.DownloadManager(mods, EventBus(), SettingsService())
    yield obj
    obj.shutdown()


def item(kind='mod', status='queued', branch=''):
    return dm.DownloadItem(kind, 'test', 'Test', '', 100, status=status,
                           real=True, url='' if kind == 'game' else 'https://example.test/a.zip',
                           flavor='mod' if kind == 'mod' else 'zip', game_version=branch)


@pytest.mark.parametrize('kind', ['mod', 'url', 'game', 'update'])
@pytest.mark.parametrize('status', ['failed', 'completed', 'paused', 'downloading'])
def test_history_survives_restart(manager, kind, status):
    entry = item(kind, status)
    entry.subtitle = 'preserved error/details'
    manager._model.append(entry)
    manager._persist_queue()
    manager._model.clear()
    manager._restore_queue()
    restored, = manager._model.items
    assert restored.kind == kind
    assert restored.status == ('queued' if kind == 'game' and status == 'downloading'
                               else 'downloading' if status == 'downloading' else status)
    assert restored.subtitle == entry.subtitle


def test_clear_history_keeps_every_pending_item_and_all_files(manager, tmp_path):
    statuses = ['completed', 'failed', 'paused', 'queued', 'downloading']
    for status in statuses:
        manager._model.append(item(status=status))
    archive = tmp_path / 'keep.zip'
    archive.write_bytes(b'keep')
    manager.clearCompleted()
    assert [i.status for i in manager._model.items] == statuses[2:]
    assert archive.read_bytes() == b'keep'
    manager.removeCompletedAt(manager._model.items[0].id)
    assert len(manager._model.items) == 3


def test_failed_card_can_be_removed_without_removing_other_items(manager):
    failed, pending = item(status='failed'), item()
    manager._model.append(failed)
    manager._model.append(pending)
    manager.removeCompletedAt(failed.id)
    assert manager._model.items == [pending]


def test_missing_game_requires_confirmation_and_blocks_mod_until_installed(manager, monkeypatch):
    monkeypatch.setattr(dm, 'resolve_downloaded_branch', lambda _: '')
    installed = set()
    monkeypatch.setattr(manager, '_is_downloaded_game_version', lambda b: b in installed)
    steam = SimpleNamespace(busy=False, download=Mock())
    manager.setGameVersionsManager(steam)
    requests_seen = []
    manager.missingGameVersion.connect(lambda token, branch: requests_seen.append((token, branch)))
    manager.startModDownloadWithVersion('example-mod', 'alpha19')
    assert manager._model.items == []
    token, branch = requests_seen.pop()
    assert branch == 'alpha19.6'
    manager.resolveMissingGame(token, True)
    queued, = manager._model.items
    assert queued.status == 'queued'
    steam.download.assert_called_once_with('alpha19.6')
    manager._promote_queued()
    steam.download.assert_called_once()
    installed.add('alpha19.6')
    manager._promote_queued()
    assert queued.status == 'downloading'
    manager._start_mod_worker.assert_called_once_with(queued)


def test_declining_missing_game_does_not_enqueue(manager, monkeypatch):
    monkeypatch.setattr(dm, 'resolve_downloaded_branch', lambda _: '')
    seen = []
    manager.missingGameVersion.connect(lambda t, b: seen.append(t))
    manager.startModDownloadWithFileVersion('example-mod', 'hosted:1', 'alpha19')
    manager.resolveMissingGame(seen[0], False)
    assert manager._model.items == []
    assert manager._pending_requests == {}


def test_shutdown_preserves_active_state_and_partial_files(manager, tmp_path):
    entry = item(status='downloading')
    part = tmp_path / 'data.zip.part'
    part.write_bytes(b'partial')
    manager._model.append(entry)
    manager.shutdown()
    assert entry.pause_event.is_set()
    assert not entry.cancel_event.is_set()
    assert fs.read_json(fs.downloads_queue_path(), {})['items'][0]['status'] == 'downloading'
    assert part.read_bytes() == b'partial'


class Response:
    def __init__(self, data=b'abc', code=200, headers=None):
        self.data = data
        self.status_code = code
        self.headers = {'Content-Length': str(len(data)), 'Content-Type': 'application/octet-stream'}
        self.headers.update(headers or {})
        self.closed = False
    def iter_content(self, chunk_size):
        yield self.data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))
    def close(self): self.closed = True
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


DRIVE_URL = 'https://drive.google.com/file/d/test_ID-123/view'


def test_drive_confirmation_retains_session_and_range():
    page = Response(b'<form id="download-form" action="https://drive.usercontent.google.com/download">'
                    b'<input name="id" value="test_ID-123"><input name="confirm" value="t">'
                    b'<input name="uuid" value="a&amp;b"></form>', headers={'Content-Type': 'text/html'})
    archive = Response(b'7z', 206)
    session = SimpleNamespace(headers={}, get=Mock(side_effect=[page, archive]))
    assert drive.open_download(session, DRIVE_URL, headers={'Range':'bytes=100-'}, timeout=1) is archive
    assert page.closed
    call = session.get.call_args
    assert 'uuid=a%26b' in call.args[0]
    assert call.kwargs['headers'] == {'Range': 'bytes=100-'}


@pytest.mark.parametrize('body', [b'<html>Quota exceeded</html>', b'<html>Sign in</html>',
    b'<form id="download-form" action="https://evil.test/download"><input name="id" value="test_ID-123"><input name="confirm" value="t"></form>'])
def test_drive_html_errors_are_never_saved_as_archives(body):
    response = Response(body, headers={'Content-Type':'text/html'})
    session = SimpleNamespace(headers={}, get=Mock(return_value=response))
    with pytest.raises(ValueError, match='download.drive.unavailable'):
        drive.open_download(session, DRIVE_URL, headers={}, timeout=1)
    assert response.closed


@pytest.mark.parametrize('url', ['https://drive.google.com.evil.test/file/d/abc/view',
    'https://evil.test/?id=abc', 'file:///abc', 'https://drive.google.com/drive/folders/abc'])
def test_drive_only_accepts_public_file_links(url):
    assert drive.file_id(url) == ''


def test_drive_direct_link_is_supported():
    assert pack.detect_source_kind(DRIVE_URL) == pack.DownloadSourceKind.DIRECT_ZIP


def test_stream_resume_appends_correct_range(tmp_path):
    dest = tmp_path / 'test.zip'
    dest.with_suffix('.zip.part').write_bytes(b'abc')
    session = SimpleNamespace(headers={}, get=Mock(return_value=Response(b'def', 206, {'Content-Range':'bytes 3-5/6'})))
    SevenDaysModsClient(session=session).download_to('https://example.test/a.zip', dest)
    assert dest.read_bytes() == b'abcdef'
    assert session.get.call_args.kwargs['headers']['Range'] == 'bytes=3-'


@pytest.mark.parametrize('content_range', ['', 'bytes 0-2/6', 'bytes */6'])
def test_stream_refuses_wrong_resume_range_without_altering_part(tmp_path, content_range):
    dest = tmp_path / 'test.zip'
    part = dest.with_suffix('.zip.part')
    part.write_bytes(b'abc')
    session = SimpleNamespace(headers={}, get=Mock(return_value=Response(b'def', 206, {'Content-Range':content_range})))
    with pytest.raises(ValueError, match='invalidRange'):
        SevenDaysModsClient(session=session).download_to('https://example.test/a.zip', dest)
    assert part.read_bytes() == b'abc'
    assert not dest.exists()


def test_416_is_not_proof_of_complete_download(tmp_path):
    dest = tmp_path / 'test.zip'
    part = dest.with_suffix('.zip.part')
    part.write_bytes(b'abc')
    session = SimpleNamespace(headers={}, get=Mock(return_value=Response(b'',416,{'Content-Range':'bytes */2'})))
    with pytest.raises(requests.HTTPError):
        SevenDaysModsClient(session=session).download_to('https://example.test/a.zip', dest)
    assert part.read_bytes() == b'abc'
    assert not dest.exists()


def test_truncated_transfer_preserves_partial_for_retry(tmp_path):
    dest = tmp_path / 'test.zip'
    session = SimpleNamespace(headers={}, get=Mock(return_value=Response(b'abc',headers={'Content-Length':'10'})))
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        SevenDaysModsClient(session=session).download_to('https://example.test/a.zip', dest, max_retries=0)
    assert not dest.exists()
    assert dest.with_suffix('.zip.part').read_bytes() == b'abc'


def test_all_branches_are_chronological_and_named_branches_survive():
    branches=['alpha8.8','v2.6','alpha21.2','alpha10.4','v3.3.0','public','latest_experimental','legacy_test']
    ordered = sorted(branches, key=gv.branch_sort_key, reverse=True)
    assert ordered == ['latest_experimental','public','v3.3.0','v2.6','alpha21.2','alpha10.4','alpha8.8','legacy_test']


def test_executable_choices_exclude_crash_reporters_and_subfolders(tmp_path):
    for name in ['7DaysToDie.exe','7DaysToDie_EAC.exe','7dLauncher.exe','UnityCrashHandler64.exe', 'UnityCrashHandler32.exe','backup.exe.bak']:
        (tmp_path / name).write_bytes(b'MZ')
    (tmp_path / 'folder.exe').mkdir()
    assert gp.game_executables(tmp_path) == ['7DaysToDie.exe','7DaysToDie_EAC.exe','7dLauncher.exe']


def test_instance_prefix_is_stable_and_different_for_same_branch(monkeypatch, tmp_path):
    monkeypatch.setattr(gp, '_manager_data_root', lambda: tmp_path)
    a=gp.instance_compat_root('alpha14.7','a')
    assert a == gp.instance_compat_root('alpha14.7','a')
    assert a != gp.instance_compat_root('alpha14.7','b')
    assert gp.instance_compat_root('alpha14.7','../../escape').is_relative_to(tmp_path / 'compatdata/instances')


def test_executable_persists_and_reaches_launch(tmp_path, monkeypatch):
    from backend import instances
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    instance=instances.create_instance('Custom', str(tmp_path/'instance'), game_branch='alpha14.7', executable='7dLauncher.exe')
    instances.save_instances([instance])
    loaded=next(i for i in instances.load_instances() if i.instance_id==instance.instance_id)
    assert loaded.executable == '7dLauncher.exe'
    launch=Mock(return_value=True)
    monkeypatch.setattr(instances,'launch_game_via_steam',launch)
    assert instances.launch_instance_via_steam(loaded)
    assert launch.call_args.kwargs['executable']=='7dLauncher.exe'
    assert launch.call_args.kwargs['instance_id']==instance.instance_id


def test_archive_payload_corruption_is_detected(tmp_path):
    from backend.archive_extractor import archive_is_complete
    fixture=Path(__file__).parent/'fixtures/InstantScrap.7z'
    data=bytearray(fixture.read_bytes())
    data[40] ^= 0xFF
    corrupt=tmp_path/'corrupt.7z'
    corrupt.write_bytes(data)
    assert not archive_is_complete(corrupt)


def test_drive_archive_without_extension_is_extracted_by_signature(tmp_path, monkeypatch):
    from shutil import copyfile
    fixture=Path(__file__).parent/'fixtures/InstantScrap.7z'
    monkeypatch.setattr(pack,'_http_download_file',lambda url,dest,**kw: copyfile(fixture,dest))
    result=pack.download_and_extract(DRIVE_URL,tmp_path/'work')
    assert (result/'InstantScrap/ModInfo.xml').exists()


def test_all_settings_survive_immediate_close(tmp_path, monkeypatch):
    from services.settings_service import DEFAULTS
    app=QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(Path,'home',lambda:tmp_path)
    settings=SettingsService()
    special={'language':'pl','maxConcurrentDownloads':5,'autoCleanDownloads':'7d',
             'themeMode':'stalker-light','uiScale':1.25,'accentColor':'#123456'}
    for key,default in DEFAULTS.items():
        value=special.get(key, not default if isinstance(default,bool)
                          else default+10 if isinstance(default,int)
                          else str(tmp_path/key) if isinstance(default,str) else default)
        setattr(settings,key,value)
    expected={key:getattr(settings,key) for key in DEFAULTS}
    settings.flush()
    restored=SettingsService()
    assert {key:getattr(restored,key) for key in DEFAULTS} == expected
    restored.flush()


@pytest.mark.parametrize('error',[requests.ConnectionError('offline'),requests.Timeout('timeout'),requests.HTTPError('429 Too Many Requests')])
def test_app_update_errors_and_startup_opt_out(manager, monkeypatch, error):
    from backend import app_updates as updates
    class Immediate:
        def __init__(self,target,**kw): self.target=target
        def start(self): self.target()
    monkeypatch.setattr(updates.threading,'Thread',Immediate)
    fetch=Mock(side_effect=error)
    monkeypatch.setattr(updates,'fetch_latest',fetch)
    checker=updates.AppUpdates(SimpleNamespace(autoCheckAppUpdates=False))
    failures=[]
    checker.checkFailed.connect(failures.append)
    checker.checkOnStartup()
    fetch.assert_not_called()
    checker.checkNow()
    assert failures==[str(error)]
    assert not checker.busy


def test_major_requirement_selects_latest_available_patch(manager):
    manager.setGameVersionsManager(SimpleNamespace(available=[{'branch':x} for x in ['v2.5','v2.6','v3.3.0']]))
    assert manager._game_branch_for_download('v2') == 'v2.6'
    assert manager._game_branch_for_download('alpha19') == 'alpha19.6'


def test_unconfirmed_restored_requirement_never_downloads_game(manager,monkeypatch):
    steam=SimpleNamespace(busy=False,available=[],download=Mock())
    manager.setGameVersionsManager(steam)
    monkeypatch.setattr(manager,'_is_downloaded_game_version',lambda _:False)
    entry=item(branch='alpha19.6')
    manager._model.append(entry)
    seen=[]
    manager.missingGameVersion.connect(lambda t,b:seen.append((t,b)))
    manager._promote_queued()
    assert entry.status=='failed'
    steam.download.assert_not_called()
    assert seen[0][1]=='alpha19.6'


def test_game_retry_reaches_depot_owner(manager):
    steam=SimpleNamespace(resume=Mock())
    manager.setGameVersionsManager(steam)
    entry=item('game','failed')
    entry.ref_id='alpha19.6'
    manager._model.append(entry)
    manager.retryAt(entry.id)
    steam.resume.assert_called_once_with('alpha19.6')
    manager._start_url_worker.assert_not_called()


def test_depot_shutdown_cancellation_does_not_erase_history(manager):
    entry=item('game','downloading')
    manager._model.append(entry)
    manager.shutdown()
    manager.finishGameVersionDownload(entry.ref_id,'cancelled','')
    assert manager._model.items == [entry]
    assert fs.read_json(fs.downloads_queue_path(),{})['items'][0]['status']=='downloading'


def test_retry_does_not_duplicate_active_mod(manager):
    failed, active=item(status='failed'),item(status='downloading')
    manager._model.append(failed)
    manager._model.append(active)
    manager.retryAt(failed.id)
    assert failed.status=='failed'
    manager._start_mod_worker.assert_not_called()


def test_install_enable_conflicts_profile_backup_restore_and_launch(manager,tmp_path,monkeypatch):
    import zipfile
    from backend import library_ops,library,instances,modpacks,game_profiles
    from backend.conflict_detector import ConflictDetector
    from models.mod import Mod
    from backend.archive_extractor import extract_archive
    monkeypatch.setattr(instances,'find_game_processes',lambda:[])
    archive=tmp_path/'mods.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for name in ['A','B']:
            z.writestr(f'{name}/ModInfo.xml',f'<xml><Name value="{name}"/></xml>')
            z.writestr(f'{name}/Config/blocks.xml','<configs/>')
    extract_archive(archive,tmp_path/'extracted')
    report=library_ops.install_modpack_to_library(tmp_path/'extracted')
    assert len(report.imported)==2 and not report.errors
    instance=instances.create_instance('Workflow',str(tmp_path/'instance'),game_branch='v3.3.0',
        executable='7dLauncher.exe',proton_path='/test/proton')
    instances.save_instances([instance])
    entries=library.load_library_entries()
    activation=library.load_activation_state()
    for entry in entries:
        activation.set_instance_inclusion(entry.library_id,instance.instance_id,True)
    library.save_activation_state(activation)
    instances.build_mods_for_instance(instance,entries,activation)
    assert len([p for p in instance.mods_dir.iterdir() if p.is_dir()])==2
    mods=[Mod(e.library_id,e.mod_name,'Test',modified_files=['blocks.xml']) for e in entries]
    detector=ConflictDetector()
    assert len(detector.recompute(mods))==1
    activation.set_instance_exclusion(entries[0].library_id,instance.instance_id,True)
    library.save_activation_state(activation)
    instances.build_mods_for_instance(instance,entries,activation)
    mods[0].enabled=False
    assert len(detector.recompute(mods))==0
    assert len([p for p in instance.mods_dir.iterdir() if p.is_dir()])==1
    source=fs.profiles_dir()/'Survivor.xml'
    source.write_text('<profile/>')
    profiles=game_profiles.GameProfileManager()
    profiles.refresh()
    pid=profiles._profile_id(source.name)
    profiles.setInstanceEnabled(pid,instance.instance_id,True)
    assert (instance.data_path/'Presets/Survivor.xml').exists()
    save=instance.data_path/'Saves/world.sav'
    save.parent.mkdir(); save.write_text('original')
    backup=modpacks.create_backup_from_instance(instance)
    instances.save_instances([i for i in instances.load_instances() if i.instance_id!=instance.instance_id])
    save.write_text('changed')
    restored=modpacks.restore_backup(backup)
    assert save.read_text()=='original'
    assert restored.executable==instance.executable and restored.proton_path==instance.proton_path
    monkeypatch.setattr(instances,'launch_game_via_steam',Mock(return_value=True))
    assert instances.launch_instance_via_steam(restored)
    assert instances.launch_game_via_steam.call_args.kwargs['executable']=='7dLauncher.exe'


def test_app_update_does_not_interpret_build_number_as_version():
    from backend import app_updates
    assert app_updates.parse_release({'name':'Maintenance build 2026'}) is None
    assert app_updates.parse_release({'name':'Release 1.0.48'})['version']=='1.0.48'


def test_server_partial_tail_is_not_mistaken_for_finished_file(tmp_path):
    dest=tmp_path/'tail.zip'
    dest.with_suffix('.zip.part').write_bytes(b'abc')
    session=SimpleNamespace(headers={},get=Mock(return_value=Response(b'd',206,{'Content-Range':'bytes 3-3/6'})))
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        SevenDaysModsClient(session=session).download_to('https://example.test/a.zip',dest,max_retries=0)
    assert not dest.exists()
    assert dest.with_suffix('.zip.part').read_bytes()==b'abcd'


def test_cached_zip_with_corrupted_payload_is_rejected(tmp_path):
    import zipfile
    dest=tmp_path/'bad.zip'
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_STORED) as z:
        z.writestr('payload.txt',b'unique payload marker')
    data=bytearray(dest.read_bytes())
    data[data.index(b'unique payload marker')] ^= 0xFF
    dest.write_bytes(data)
    assert zipfile.is_zipfile(dest)
    assert not pack._zip_already_complete(dest)
