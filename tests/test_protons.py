import hashlib
import io
import tarfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from backend import game_process, protons
from backend.instances import Instance, _instance_from_dict, _instance_to_dict, launch_instance_via_steam
from backend.instance_logs import collect_logs, InstanceLogs


def executable(folder):
    folder.mkdir(parents=True)
    path = folder / 'proton'
    path.write_text('#!/bin/sh\n')
    path.chmod(0o755)
    return path


def test_discovery_covers_libraries_custom_tools_and_managed(tmp_path):
    root = tmp_path / 'steam'
    stable = executable(root / 'steamapps/common/Proton 10')
    ge = executable(root / 'compatibilitytools.d/GE-Proton11-7-x86_64')
    managed = executable(tmp_path / 'managed/GE-Proton10-34')
    with patch.object(game_process, '_steam_library_roots', return_value=[root, root]), patch.object(protons, 'managed_root', return_value=tmp_path / 'managed'):
        found = protons.installed_protons()
        assert {p['path'] for p in found} == {str(stable), str(ge), str(managed)}
        assert next(p for p in found if p['path'] == str(managed))['managed']
        assert not next(p for p in found if p['path'] == str(ge))['managed']


def test_explicit_missing_version_never_falls_back(tmp_path):
    with patch.object(protons, 'installed_protons', return_value=[]), patch.object(game_process, 'find_proton') as auto:
        assert protons.resolve_proton(str(tmp_path / 'missing/proton')) == (None, None)
        auto.assert_not_called()
        protons.resolve_proton('')
        auto.assert_called_once()


def test_instance_storage_and_launch_preserve_selection():
    instance = Instance('test', 'Test', '/tmp/instance', game_branch='public', proton_path='/tools/GE/proton')
    assert _instance_from_dict(_instance_to_dict(instance)).proton_path == instance.proton_path
    assert _instance_from_dict({'instance_id': 'old', 'name': 'Old'}).proton_path == ''
    with patch('backend.instances.launch_game_via_steam', return_value=True) as launch:
        assert launch_instance_via_steam(instance)
        assert launch.call_args.kwargs['proton_path'] == instance.proton_path


def test_explicit_steam_version_uses_direct_launch(tmp_path):
    with patch.object(game_process, '_steam_game_dir', return_value=tmp_path), patch.object(game_process, '_launch_downloaded_windows_version', return_value=True) as launch:
        assert game_process.launch_game_via_steam('/instance', proton_path='/tools/proton')
        assert launch.call_args.args[0] == 'steam'
        assert launch.call_args.kwargs['game_directory'] == tmp_path
        assert launch.call_args.kwargs['proton_path'] == '/tools/proton'


def catalog():
    def asset(name): return {'name': name, 'browser_download_url': 'https://github.com/' + name, 'size': 100}
    return protons.release_catalog([{'tag_name': 'GE-Proton11-7', 'assets': [asset('GE-Proton11-7-aarch64.tar.gz'), asset('GE-Proton11-7-x86_64.tar.gz'), asset('GE-Proton11-7-x86_64.sha512sum')]}])


def archive_bytes(unsafe=False):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as archive:
        data = b'#!/bin/sh\n'
        member = tarfile.TarInfo('../escaped' if unsafe else 'GE-Proton11-7/proton')
        member.size = len(data)
        member.mode = 0o755
        archive.addfile(member, io.BytesIO(data))
    return out.getvalue()


class Response:
    def __init__(self, data):
        self.data = data
        self.headers = {'Content-Length': str(len(data))}
        self.text = data.decode(errors='replace')
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def raise_for_status(self): pass
    def iter_content(self, *_): yield self.data


class Session:
    def __init__(self, data, good=True): self.data, self.good = data, good
    def get(self, url, **kwargs):
        if url.endswith('.sha512sum'):
            return Response(((hashlib.sha512(self.data).hexdigest() if self.good else '0'*128) + '  archive.tar.gz').encode())
        return Response(self.data)


def test_download_checksum_atomic_install_and_permissions(tmp_path):
    with patch.object(protons, 'managed_root', return_value=tmp_path):
        target = protons.install_release(catalog()[0], threading.Event(), lambda _: None, lambda _: None, Session(archive_bytes()))
        assert target.name == 'GE-Proton11-7-x86_64'
        assert (target / 'proton').stat().st_mode & 0o111
        assert not list(tmp_path.glob('.download-*'))


@pytest.mark.parametrize('failure', ['checksum', 'unsafe', 'cancel'])
def test_failed_install_does_not_publish_or_leave_staging(tmp_path, failure):
    event = threading.Event()
    if failure == 'cancel': event.set()
    with patch.object(protons, 'managed_root', return_value=tmp_path):
        with pytest.raises((ValueError, tarfile.FilterError, protons.Cancelled)):
            protons.install_release(catalog()[0], event, lambda _: None, lambda _: None,
                                    Session(archive_bytes(failure == 'unsafe'), failure != 'checksum'))
    assert not list(tmp_path.iterdir())
    assert not (tmp_path.parent / 'escaped').exists()


def test_logs_include_nested_unity_crash_and_instance_proton(tmp_path):
    instance = Instance('test', 'Test', str(tmp_path / 'instance'), game_branch='public')
    roots = [instance.data_path / 'BacktraceLogs', instance.data_path / 'logs',
             tmp_path / 'compatdata/public/pfx/drive_c/users/steamuser/AppData/Local/Temp/The Fun Pimps/7 Days To Die/Crashes/Crash_test']
    for root in roots: root.mkdir(parents=True)
    (roots[0] / 'Player.log').write_text('game')
    (roots[1] / 'steam-251570.log').write_text('proton')
    (roots[2] / 'Player.log').write_text('Crash!!!')
    (roots[2] / 'crash.dmp').write_bytes(b'dump')
    with patch.object(game_process, '_manager_data_root', return_value=tmp_path):
        files = collect_logs(instance)
    assert len(files) == 4
    assert {f['kind'] for f in files} == {'game', 'instance', 'crash'}
    assert not next(f for f in files if f['name'] == 'crash.dmp')['text']
    logs = InstanceLogs()
    logs._files = files
    logs.preview(str(roots[2] / 'Player.log'))
    assert logs.previewText == 'Crash!!!'
    logs.preview('/etc/passwd')
    assert logs.previewText == 'Crash!!!'
