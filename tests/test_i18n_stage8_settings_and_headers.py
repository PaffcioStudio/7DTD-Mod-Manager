from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_settings_page_has_i18n_for_user_facing_sections():
    qml = (ROOT / "qml" / "pages" / "SettingsPage.qml").read_text(encoding="utf-8")
    required = [
        'I18n.t("settings.section.general")',
        'I18n.t("settings.section.game")',
        'I18n.t("settings.section.downloads")',
        'I18n.t("settings.section.appearance")',
        'I18n.t("settings.section.advanced")',
        'I18n.t("settings.about.title")',
        'I18n.t("settings.about.faq")',
    ]
    for item in required:
        assert item in qml


def test_page_headers_are_not_duplicated_inside_content():
    pages = {
        "ModsPage.qml": 'title: I18n.t("mods.title")',
        "ProfilesPage.qml": 'title: I18n.t("instances.title")',
        "BackupsPage.qml": 'title: I18n.t("backups.title")',
        "DownloadsPage.qml": 'title: I18n.t("downloads.title")',
        "UpdatesPage.qml": 'title: I18n.t("updates.title")',
        "GameProfilesPage.qml": 'title: I18n.t("gameProfiles.title")',
        "ConflictsPage.qml": 'title: I18n.t("conflicts.title")',
    }
    for filename, old_header_title in pages.items():
        qml = (ROOT / "qml" / "pages" / filename).read_text(encoding="utf-8")
        assert old_header_title not in qml, filename


def test_settings_catalog_keys_exist_in_both_languages():
    catalog = (ROOT / "qml" / "i18n" / "translations.js").read_text(encoding="utf-8")
    keys = [
        "settings.section.general", "settings.section.game", "settings.section.downloads",
        "settings.section.appearance", "settings.section.advanced", "settings.section.about",
        "settings.language.label", "settings.theme.label", "settings.startMinimized.label",
        "settings.game.detectNow", "settings.game.file.notSet", "settings.game.browse",
        "settings.download.archives.clear", "settings.download.archives.confirmMessage",
        "settings.updates.auto.description", "settings.appearance.scale.description",
        "settings.advanced.reset.message", "settings.about.faq.steamA",
    ]
    for key in keys:
        assert catalog.count(f'"{key}"') == 2, key
