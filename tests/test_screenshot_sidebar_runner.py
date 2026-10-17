"""Headless tests of screenshot selection and command construction (no Qt required)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('screenshot_en', ROOT / 'tests/screenshot_en.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def test_sidebar_snapshots_and_page_aliases():
    assert len(capture.selected_targets([])) == 16
    assert capture.selected_targets(['dashboard']) == [('dashboard-en.png', 'dashboard', 1800)]
    for name, mode in capture.SIDEBAR_MODES.items():
        assert mode in ('default', 'game', 'tools')
        assert capture.selected_targets([name]) == [(name, 'dashboard', 1800)]
        assert capture.selected_targets([name.removesuffix('-en.png')]) == [(name, 'dashboard', 1800)]
    assert capture.selected_targets(['modpacks']) == [('backups-en.png', 'modpacks', 1800)]
    assert capture.selected_targets(['backups']) == [('backups-en.png', 'modpacks', 1800)]
    with pytest.raises(ValueError, match='Unknown screenshot targets'):
        capture.selected_targets(['invalid-sidebar'])


def test_command_uses_nonpersistent_sidebar_preview(monkeypatch, tmp_path):
    screenshots = tmp_path / 'docs' / 'screenshots'
    captured_calls = []

    def run(command, **kwargs):
        captured_calls.append((command, kwargs))
        filename = Path(command[command.index('--screenshot') + 1])
        filename.write_bytes(b'\x89PNG\r\n\x1a\n' + b'fixture')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(capture, 'ROOT', tmp_path)
    monkeypatch.setattr(capture, 'first_mod_id', lambda: '')
    monkeypatch.setattr(capture, 'app_python', lambda: '/usr/bin/python3')
    monkeypatch.setattr(capture.subprocess, 'run', run)
    monkeypatch.setattr(capture.sys, 'argv', ['screenshot_en.py', 'sidebar-game', 'protons', 'dashboard'])
    capture.main()

    assert screenshots.is_dir()
    modes = {Path(cmd[cmd.index('--screenshot')+1]).name: cmd[cmd.index('--sidebar-preview')+1]
             for cmd, _ in captured_calls}
    assert modes == {
        'dashboard-en.png': 'default',
        'protons-en.png': 'default',
        'sidebar-game-en.png': 'game',
    }
    for command, kwargs in captured_calls:
        assert command[command.index('--language')+1] == 'en'
        assert kwargs['env']['QT_QPA_PLATFORM'] == 'offscreen'
        assert kwargs['env']['QT_QUICK_BACKEND'] == 'software'
        assert kwargs['timeout'] == 120


def test_sidebar_capture_selection_does_not_accidentally_include_previews():
    assert capture.selected_targets(['profiles']) == [('profiles-en.png', 'profiles', 1800)]
    assert capture.selected_targets(['steam_releases']) == [('steam-releases-en.png', 'steam_releases', 6000)]
    assert capture.selected_targets(['sidebar-default', 'sidebar-tools']) == [
        ('sidebar-default-en.png', 'dashboard', 1800),
        ('sidebar-tools-en.png', 'dashboard', 1800),
    ]
