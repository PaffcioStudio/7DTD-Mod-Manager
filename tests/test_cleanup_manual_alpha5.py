"""Cofanie ręcznej Alpha 5 bez kasowania wersji pobranych przez launcher."""
import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'cleanup_manual_alpha5.py'
spec = importlib.util.spec_from_file_location('cleanup_manual_alpha5', MODULE)
cleanup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup_module)


def setup_manual(home):
    source = home / 'Gry' / '7DTD-Alpha-5.0'
    (source / '7DaysToDie_Data').mkdir(parents=True)
    (source / '7DaysToDie.exe').write_bytes(b'old alpha 5')
    versions = home / '.7dtd_modmanager' / 'game-versions'
    versions.mkdir(parents=True)
    link = versions / 'alpha5.0'
    link.symlink_to(source, target_is_directory=True)
    reg = versions.parent / 'game-versions.json'
    reg.write_text(json.dumps({'versions': [
        {'branch': 'alpha5.0', 'dir': str(link), 'size_bytes': 0,
         'downloaded_at': '2026-10-28T15:00:00'},
        {'branch': 'alpha6.0', 'dir': str(versions / 'alpha6.0'), 'origin': 'downloaded'},
    ]}), encoding='utf-8')
    return source, link, reg


def test_preview_is_safe(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    before = reg.read_bytes()
    report = cleanup_module.cleanup(tmp_path)
    assert 'Podgląd' in report[-1]
    assert source.exists() and link.is_symlink()
    assert reg.read_bytes() == before


def test_apply_only_removes_manual_items(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    cleanup_module.cleanup(tmp_path, apply=True)
    assert not source.exists() and not link.is_symlink()
    assert [row['branch'] for row in json.loads(reg.read_text())['versions']] == ['alpha6.0']
    assert len(list(reg.parent.glob('game-versions.json.bak-manual-alpha5-*'))) == 1
    cleanup_module.cleanup(tmp_path, apply=True)


def test_does_not_touch_managed_alpha5_directory(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    link.unlink()
    link.mkdir()
    (link / '7DaysToDie.exe').write_bytes(b'manager install')
    data = json.loads(reg.read_text())
    data['versions'][0]['origin'] = 'downloaded'
    reg.write_text(json.dumps(data))
    cleanup_module.cleanup(tmp_path, apply=True)
    assert link.is_dir() and (link / '7DaysToDie.exe').exists()
    assert not source.exists()  # Stara kopia poza menedżerem nie jest już potrzebna.
    assert len(json.loads(reg.read_text())['versions']) == 2


def test_other_registered_import_protects_source(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    also = link.parent / 'custom-test'
    also.symlink_to(source)
    data = json.loads(reg.read_text())
    data['versions'].append({'branch': 'custom-test', 'dir': str(also),
                             'source_dir': str(source), 'origin': 'imported'})
    reg.write_text(json.dumps(data))
    cleanup_module.cleanup(tmp_path, apply=True)
    assert source.exists() and also.is_symlink()
    assert not link.is_symlink()
    assert len(json.loads(reg.read_text())['versions']) == 2


def test_instance_retained_with_warning(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    inst = reg.parent / 'instances.json'
    inst.write_text(json.dumps({'instances': [{'name': 'Alpha nostalgia',
                                              'game_branch': 'alpha5.0'}]}))
    report = cleanup_module.cleanup(tmp_path, apply=True)
    assert any('Instancja "Alpha nostalgia"' in item for item in report)
    assert inst.exists()
    assert not source.exists()


def test_never_follows_mismatched_symlink(tmp_path):
    source, link, reg = setup_manual(tmp_path)
    link.unlink()
    other = tmp_path / 'other'
    other.mkdir()
    link.symlink_to(other)
    try:
        cleanup_module.cleanup(tmp_path, apply=True)
        assert False, 'Should reject unexpected symlink'
    except cleanup_module.UnsafeCleanup:
        pass
    assert source.exists() and link.is_symlink()
