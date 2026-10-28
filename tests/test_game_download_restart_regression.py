"""Testy kolejki po restarcie bez uruchamiania PySide6 i Steam."""
from __future__ import annotations

import ast
import logging
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class Timer:
    pending = []

    @classmethod
    def singleShot(cls, _delay, fn):
        cls.pending.append(fn)

    @classmethod
    def flush(cls):
        for _ in range(20):
            if not cls.pending:
                break
            cls.pending.pop(0)()
        assert not cls.pending, 'Kolejka uruchomień wpadła w pętlę'


class Model:
    def __init__(self, items):
        self.items = items

    def row_of(self, ident):
        return next((n for n, item in enumerate(self.items) if item.id == ident), -1)

    def touch(self, _row):
        pass

    def touch_all(self):
        pass

    def append(self, item):
        self.items.append(item)

    def remove(self, ident):
        self.items[:] = [item for item in self.items if item.id != ident]


def game_item(branch, status='queued', progress=.37):
    return SimpleNamespace(
        id=branch, kind='game', ref_id=branch, status=status, title=branch,
        total_bytes=1000, downloaded=round(progress * 1000),
        _progress_override=progress, speed=0, _last_sample=None,
        subtitle='test', pausable=True, restored_from_queue=True,
        restored_paused=False, real=True, flavor='game', reinstall_game=False,
        progress=progress,
    )


def manager_with_methods(items):
    # Wykonujemy prawdziwe funkcje z menedżera bez Qt. To wychwytuje błędy
    # stanu kolejki, nawet gdy środowisko CI nie ma biblioteki PySide6.
    tree = ast.parse((ROOT / 'src/backend/download_manager.py').read_text())
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == 'DownloadManager')
    names = {'resumeRestoredGameDownloads', 'startGameVersionDownload',
             'finishGameVersionDownload', '_schedule_next_game_download',
             'cancelAt', 'pauseAt', 'resumeAt', 'retryAt'}
    functions = [node for node in klass.body if isinstance(node, ast.FunctionDef)
                 and node.name in names]
    for node in functions:
        node.decorator_list = []
    generated = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name='Manager', bases=[], keywords=[], body=functions,
        decorator_list=[])], type_ignores=[]))
    class DummyDownloadItem:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = kwargs['ref_id']
            self.downloaded = 0
            self.speed = 0
            self._progress_override = 0
            self._last_sample = None

    env = {
        'QTimer': Timer, 'DownloadItem': DummyDownloadItem,
        'RELEASE_BY_BRANCH': {}, 'time': time, 'i18n_message': lambda *args: 'status',
        'logger': logging.getLogger('test'),
    }
    exec(compile(generated, '<download_manager_methods>', 'exec'), env)
    manager = env['Manager']()
    manager._model = Model(items)
    manager._shutting_down = False
    manager._bus = SimpleNamespace(toastKey=lambda *a: None)
    manager._emit_counts = lambda: None
    manager._find = lambda ident: next((i for i in items if i.id == ident), None)
    manager._is_downloaded_game_version = lambda _branch: False
    Timer.pending = []
    return manager


class Owner:
    def __init__(self, manager):
        self.manager = manager
        self.busy = False
        self.downloadingBranch = ''
        self.status = ''
        self.calls = []

    def resume(self, branch):
        if self.busy:
            return False
        self.calls.append(branch)
        self.busy = True
        self.downloadingBranch = branch
        self.manager.startGameVersionDownload(branch, 1000)
        return True

    def reinstall(self, branch):
        self.calls.append('reinstall:' + branch)
        self.busy = True
        self.downloadingBranch = branch
        self.manager.startGameVersionDownload(branch, 1000)
        return True

    def cancel(self):
        self.calls.append('cancel')

    def pause(self):
        self.calls.append('pause')


def test_resume_restored_game_activates_card_and_keeps_progress():
    item = game_item('alpha7.0', progress=.07)
    manager = manager_with_methods([item])
    owner = Owner(manager)
    manager._game_versions = owner
    manager.resumeRestoredGameDownloads()
    assert owner.calls == ['alpha7.0']
    assert item.status == 'downloading'
    assert item._progress_override == .07


def test_next_queued_game_starts_after_previous_finished():
    a, b = game_item('alpha7.0'), game_item('alpha8.0')
    manager = manager_with_methods([a, b])
    owner = Owner(manager)
    manager._game_versions = owner
    manager.resumeRestoredGameDownloads()
    assert owner.calls == ['alpha7.0']
    assert b.status == 'queued'
    owner.busy = False
    owner.downloadingBranch = ''
    manager.finishGameVersionDownload('alpha7.0', 'completed', '')
    Timer.flush()
    assert owner.calls == ['alpha7.0', 'alpha8.0']
    assert a.status == 'completed'
    assert b.status == 'downloading'


def test_cancel_queued_game_without_live_process_removes_it():
    a = game_item('alpha7.0')
    manager = manager_with_methods([a])
    owner = Owner(manager)
    manager._game_versions = owner
    manager.cancelAt('alpha7.0')
    Timer.flush()
    assert not manager._model.items
    assert owner.calls == []


def test_cancel_active_game_starts_next_after_old_process_exits():
    a, b = game_item('alpha7.0', 'downloading'), game_item('alpha8.0')
    manager = manager_with_methods([a, b])
    owner = Owner(manager)
    owner.busy = True
    owner.downloadingBranch = 'alpha7.0'
    manager._game_versions = owner
    manager.cancelAt('alpha7.0')
    assert a not in manager._model.items
    assert owner.calls == ['cancel']
    Timer.flush()
    assert owner.calls == ['cancel']   # proces nadal pracuje
    owner.busy = False
    owner.downloadingBranch = ''
    manager.finishGameVersionDownload('alpha7.0', 'cancelled', '')
    Timer.flush()
    assert owner.calls == ['cancel', 'alpha8.0']


def test_failed_resume_does_not_leave_gray_infinite_queue():
    a = game_item('alpha6.0')
    manager = manager_with_methods([a])
    owner = Owner(manager)
    owner.resume = lambda _branch: False
    owner.status = 'Steam odmówił dostępu'
    manager._game_versions = owner
    manager.resumeRestoredGameDownloads()
    Timer.flush()
    assert a.status == 'failed'
    assert a.subtitle == 'Steam odmówił dostępu'


def test_pause_and_resume_unstarted_game():
    a = game_item('alpha7.0')
    manager = manager_with_methods([a])
    owner = Owner(manager)
    manager._game_versions = owner
    manager.pauseAt(a.id)
    assert a.status == 'paused'
    assert not owner.calls
    manager.resumeAt(a.id)
    assert owner.calls == ['alpha7.0']
    assert a.status == 'downloading'


def test_restored_active_owner_keeps_live_status_after_recovery():
    item = game_item('alpha7.0', progress=.42)
    manager = manager_with_methods([item])
    owner = Owner(manager)
    manager._game_versions = owner
    manager.resumeRestoredGameDownloads()
    assert item.status == 'downloading'
    assert item._progress_override == .42
    manager.cancelAt(item.id)
    assert owner.calls == ['alpha7.0', 'cancel']
    assert not manager._model.items


def test_orphan_cancel_without_owner_is_immediate():
    item = game_item('alpha7.0', status='downloading')
    manager = manager_with_methods([item])
    manager._game_versions = None
    manager.cancelAt(item.id)
    assert not manager._model.items


def test_reinstall_queue_after_restart_starts_correct_mode():
    item = game_item('alpha7.0', progress=.38)
    item.reinstall_game = True
    manager = manager_with_methods([item])
    owner = Owner(manager)
    owner.reinstallingBranch = 'alpha7.0'
    manager._game_versions = owner
    manager.resumeRestoredGameDownloads()
    assert owner.calls == ['reinstall:alpha7.0']
    assert item.status == 'downloading'
    assert item.reinstall_game is True

