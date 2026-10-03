from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = (ROOT / "qml/components/AppSidebar.qml").read_text(encoding="utf-8")
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
SETTINGS_QML = (ROOT / "qml/pages/SettingsPage.qml").read_text(encoding="utf-8")
SETTINGS_PY = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
I18N = (ROOT / "qml/i18n/I18n.qml").read_text(encoding="utf-8")


def test_i18n_module_is_registered_as_singleton():
    qmldir = (ROOT / "qml/i18n/qmldir").read_text(encoding="utf-8")
    assert "singleton I18n 1.0 I18n.qml" in qmldir
    assert 'pragma Singleton' in I18N


def test_polish_and_english_catalogs_cover_stage_one_navigation():
    keys = (
        "brand.manager",
        "nav.dashboard",
        "nav.instances",
        "nav.gameProfiles",
        "nav.discover",
        "nav.mods",
        "nav.backups",
        "nav.updates",
        "nav.downloads",
        "nav.settings",
    )
    for key in keys:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_sidebar_uses_translation_keys_instead_of_hardcoded_navigation_labels():
    assert 'label: modelData.label' not in SIDEBAR
    assert 'label: I18n.t(modelData.key)' in SIDEBAR
    for polish in ("Pulpit", "Instancje", "Odkrywaj", "Mody", "Kopie zapasowe", "Aktualizacje", "Pobieranie"):
        assert f'label: "{polish}"' not in SIDEBAR
    assert 'label: I18n.t("nav.settings")' in SIDEBAR
    assert 'text: I18n.t("brand.manager")' in SIDEBAR


def test_language_setting_accepts_both_requested_languages():
    assert 'not in ("pl", "en")' in SETTINGS_PY
    assert 'value = "en" if str(value) == "en" else "pl"' in SETTINGS_PY
    assert 'I18n.t("settings.language.pl")' in SETTINGS_QML
    assert 'I18n.t("settings.language.en")' in SETTINGS_QML
    assert 'Settings.language = value' in SETTINGS_QML


def test_main_binds_translation_language_to_persisted_setting():
    assert 'import "i18n"' in MAIN
    assert 'Binding { target: I18n; property: "language"; value: Settings.language }' in MAIN
