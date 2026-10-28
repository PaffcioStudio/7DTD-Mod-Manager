"""Bez Qt: kontrola powiązania nowego filtra z UI i tłumaczeniami."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VALUES = ("featured", "trending", "updated", "likes", "downloads", "views")
KEYS = ("label", "newest", *VALUES)


def test_sort_options_connect_ui_and_backend():
    qml = (ROOT / "qml/pages/DiscoverPage.qml").read_text(encoding="utf-8")
    backend = (ROOT / "src/backend/discover.py").read_text(encoding="utf-8")
    assert 'property string sortFilter: Settings.discoverDefaultSort' in qml
    assert 'value: page.sortFilter' in qml
    assert 'onPicked: (value) => { page.sortFilter = value; page.search(1, false) }' in qml
    assert 'createdAfter, includeAdult, sortFilter' in qml
    assert 'Settings.discoverDefaultSort = page.sortFilter' in qml
    assert '"sort": "newest"' not in backend
    for value in VALUES:
        assert f'value: "{value}", label: I18n.t("discover.sort.{value}")' in qml
        assert f'"{value}"' in backend
    assert 'value: "", label: I18n.t("discover.sort.newest")' in qml
    assert 'params["filter"] = sort_filter' in backend


def test_sort_strings_are_present_in_both_languages():
    text = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
    for key in KEYS:
        assert len(re.findall(fr'"discover\.sort\.{re.escape(key)}"\s*:', text)) == 2


def test_setting_is_persistent_and_sanitized():
    text = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
    assert '"discoverDefaultSort": ""' in text
    assert 'def discoverDefaultSort' in text
    assert 'if value not in ("", "featured", "trending", "updated",' in text
