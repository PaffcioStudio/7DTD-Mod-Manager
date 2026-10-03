from pathlib import Path


def _discover_qml() -> str:
    return (Path(__file__).resolve().parents[1] / "qml/pages/DiscoverPage.qml").read_text(encoding="utf-8")


def test_web_provider_exposes_i18n_time_filter_and_adult_toggle():
    text = _discover_qml()
    assert 'value: "7d", label: I18n.t("discover.time.7d")' in text
    assert 'value: "30d", label: I18n.t("discover.time.30d")' in text
    assert 'value: "365d", label: I18n.t("discover.time.365d")' in text
    assert 'text: I18n.t("discover.adult")' in text
    assert 'page.provider === "web"' in text
    assert 'createdAfter, includeAdult' in text


def test_saved_discover_filters_include_provider_time_and_adult_and_use_save_icon():
    text = _discover_qml()
    assert 'Settings.discoverDefaultProvider' in text
    assert 'Settings.discoverDefaultCreatedAfter' in text
    assert 'Settings.discoverDefaultIncludeAdult' in text
    assert 'icon: "save"' in text
    assert 'Settings.discoverDefaultProvider = page.provider' in text
    assert 'Settings.discoverDefaultCreatedAfter = page.createdAfter' in text
    assert 'Settings.discoverDefaultIncludeAdult = page.includeAdult' in text


def test_discover_initial_state_reads_saved_full_filter_set():
    text = _discover_qml()
    assert 'property string category: Settings.discoverDefaultCategory' in text
    assert 'property string version: Settings.discoverDefaultVersion' in text
    assert 'property string createdAfter: Settings.discoverDefaultCreatedAfter' in text
    assert 'property bool includeAdult: Settings.discoverDefaultIncludeAdult' in text
