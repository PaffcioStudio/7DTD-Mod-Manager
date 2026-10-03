from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_settings_service_exposes_full_discover_default_filter_set():
    text = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
    assert '"discoverDefaultProvider": "web"' in text
    assert '"discoverDefaultCreatedAfter": ""' in text
    assert '"discoverDefaultIncludeAdult": False' in text
    assert 'def discoverDefaultProvider' in text
    assert 'def discoverDefaultCreatedAfter' in text
    assert 'def discoverDefaultIncludeAdult' in text



def test_settings_service_defaults_hero_rotation_to_enabled():
    text = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
    assert '"heroRotationEnabled": True' in text
    assert 'heroRotationEnabledChanged = Signal()' in text
    assert 'def heroRotationEnabled' in text
