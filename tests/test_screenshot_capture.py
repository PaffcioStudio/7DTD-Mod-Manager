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
