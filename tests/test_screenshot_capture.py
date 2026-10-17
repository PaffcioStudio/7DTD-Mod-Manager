"""Screenshots use the live GUI and a language override that cannot be saved."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from services import settings_service
from services.settings_service import SettingsService

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('screenshot_en', ROOT / 'tests/screenshot_en.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def test_capture_targets_include_new_pages_and_backups_alias():
    assert capture.selected_targets(['protons']) == [('protons-en.png', 'protons', 2500)]
    assert capture.selected_targets(['modpacks']) == [('backups-en.png', 'modpacks', 1800)]
    assert capture.selected_targets(['steam-releases-en.png'])[0][1] == 'steam_releases'
    with pytest.raises(ValueError):
        capture.selected_targets(['does-not-exist'])


def test_sidebar_targets_have_independent_names_and_modes():
    sidebar_names = list(capture.SIDEBAR_MODES)
    assert sidebar_names == ['sidebar-default-en.png', 'sidebar-game-en.png', 'sidebar-tools-en.png']
    assert len(capture.selected_targets([])) == 16
    assert capture.selected_targets(['dashboard']) == [('dashboard-en.png', 'dashboard', 1800)]
    for name in sidebar_names:
        assert capture.selected_targets([name]) == [
            (name, 'dashboard', 1800)
        ]
        assert capture.selected_targets([name.removesuffix('-en.png')]) == [
            (name, 'dashboard', 1800)
        ]
    assert capture.selected_targets(['protons', 'sidebar-tools']) == [
        ('protons-en.png', 'protons', 2500),
        ('sidebar-tools-en.png', 'dashboard', 1800),
    ]


def test_screenshot_capture_never_writes_settings_json():
    with patch.object(SettingsService, '_load'):
        settings = SettingsService(persist=False)
    settings._values['sidebarGameExpanded'] = True
    settings._values['sidebarToolsExpanded'] = True
    with patch.object(settings_service.fs, 'write_json') as write:
        settings._save()
    write.assert_not_called()
    assert settings._values['sidebarGameExpanded']
    assert settings._values['sidebarToolsExpanded']


def test_screenshot_driver_passes_sidebar_preview_to_the_main_app():
    source = (ROOT / 'src/main.py').read_text()
    qml = (ROOT / 'qml/components/AppSidebar.qml').read_text()
    assert 'settings = SettingsService(persist=not bool(args.screenshot))' in source
    assert 'def sidebarPreview(self)' in source
    assert 'if (screenshotPreview)' in qml
    assert 'sidebar.previewGameExpanded' in qml
    assert 'sidebar.previewToolsExpanded' in qml


def test_session_language_does_not_leak_into_saved_settings():
    # The override must remain transient even when another setting is saved.
    with patch.object(SettingsService, '_load'):
        settings = SettingsService()
    settings._values['language'] = 'pl'
    settings.set_session_language('en')
    assert settings.language == 'en'
    settings._values['windowWidth'] = 1400
    with patch.object(settings_service.fs, 'write_json') as write:
        settings._save()
        assert write.call_args.args[1]['language'] == 'pl'
    assert settings._values['language'] == 'pl'


def test_capture_script_does_not_rewrite_sources():
    source = (ROOT / 'tests/screenshot_en.py').read_text()
    assert 'REPLACEMENTS' not in source
    assert '.write_text(' not in source
    assert "'--language', 'en'" in source
    assert '--open-drawer' in source
