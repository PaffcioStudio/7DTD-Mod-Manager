from pathlib import Path
from unittest.mock import Mock

from backend import mod_thumbs
from backend.scraper_client import SevenDaysModsClient


def test_known_web_mod_uses_exact_slug_and_downloads_once(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_thumbs.fs, 'thumbs_dir', lambda: tmp_path)
    metadata = Mock(return_value={'thumbnail': 'https://example.test/cover.png'})
    monkeypatch.setattr(SevenDaysModsClient, 'get_metadata', metadata)
    def download(url, mod_id):
        result = tmp_path / (mod_id + '.png')
        result.write_bytes(b'image')
        return result
    fetch = Mock(side_effect=download)
    monkeypatch.setattr(mod_thumbs, 'download_thumb', fetch)
    monkeypatch.setattr(mod_thumbs, 'search_thumb_url', Mock(side_effect=AssertionError('Nie szukamy po nazwie')))
    mod_thumbs.cache_web_thumbnails('no-cheat-commands', ['first', 'second'])
    metadata.assert_called_once_with('no-cheat-commands')
    fetch.assert_called_once_with('https://example.test/cover.png', 'first')
    assert (tmp_path / 'second.png').read_bytes() == b'image'
    mod_thumbs.cache_web_thumbnails('no-cheat-commands', ['first', 'second'])
    fetch.assert_called_once()


def test_thumbnail_from_download_metadata_needs_no_page_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_thumbs.fs, 'thumbs_dir', lambda: tmp_path)
    metadata = Mock(side_effect=AssertionError('Adres obrazka już znamy'))
    monkeypatch.setattr(SevenDaysModsClient, 'get_metadata', metadata)
    fetch = Mock(return_value=None)
    monkeypatch.setattr(mod_thumbs, 'download_thumb', fetch)
    mod_thumbs.cache_web_thumbnails('slug', ['mod'], 'https://example.test/cover.png')
    fetch.assert_called_once()
    metadata.assert_not_called()


def test_unavailable_thumbnail_does_not_break_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_thumbs.fs, 'thumbs_dir', lambda: tmp_path)
    monkeypatch.setattr(SevenDaysModsClient, 'get_metadata', Mock(side_effect=RuntimeError('offline')))
    mod_thumbs.cache_web_thumbnails('slug', ['mod'])
    assert mod_thumbs.thumb_path('mod') is None


def test_mod_mapping_keeps_import_source_independent_from_web_match():
    from datetime import datetime
    from types import SimpleNamespace
    from backend.mod_manager import ModManager, ModListModel
    from backend.library import LibraryModEntry, ActivationState
    entries = [LibraryModEntry('web', 'a', 'Online', 'a', source='web:no-cheat-commands'),
               LibraryModEntry('manual', 'b', 'Manual', 'b', source='import', web_slug='found-online')]
    manager = SimpleNamespace(_loader=SimpleNamespace(load_state=lambda: {}),
                              _library_entries=entries, _activation=ActivationState(), _modified_files={})
    mods = ModManager._build_mods_from_library(manager)
    assert [m.source for m in mods] == ['web:no-cheat-commands', 'import']
    model = ModListModel()
    model.set_mods(mods)
    assert model.data(model.index(0), model.SourceRole) == 'web:no-cheat-commands'
    assert model.data(model.index(1), model.SourceRole) == 'import'
