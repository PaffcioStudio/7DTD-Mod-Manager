from pathlib import Path


def _settings_qml() -> str:
    return (Path(__file__).resolve().parents[1] / "qml/pages/SettingsPage.qml").read_text(encoding="utf-8")


def test_about_section_is_after_advanced_and_uses_paffcio_identity():
    text = _settings_qml()
    assert '{ key: "advanced"' in text
    assert '{ key: "about", label: I18n.t("settings.section.about")' in text
    catalog = (Path(__file__).resolve().parents[1] / "qml/i18n/translations.js").read_text(encoding="utf-8")
    assert 'text: "Paffcio"' in text
    assert '"settings.about.github"' in catalog
    assert 'https://github.com/paffciostudio' in text


def test_settings_qml_has_balanced_braces():
    text = _settings_qml()
    assert text.count("{") == text.count("}")
    assert text.rstrip().endswith("}")


def test_about_faq_explains_optional_steam_login_and_legal_use():
    text = _settings_qml()
    catalog = (Path(__file__).resolve().parents[1] / "qml/i18n/translations.js").read_text(encoding="utf-8")
    assert 'I18n.t("settings.about.faq.steamQ")' in text
    assert '"Czy muszę łączyć konto Steam?"' in catalog
    assert 'Konto Steam jest potrzebne tylko do pobierania wersji gry' in catalog
    assert 'Steam musi potwierdzić, że posiadasz 7 Days to Die.' in catalog
    assert 'Logowanie do Steam tego nie naprawi.' in catalog


def test_about_contains_version_technologies_and_correct_app_update_guidance():
    text = _settings_qml()
    assert 'label: "v" + App.version' in text
    assert 'model: ["Python", "PySide6", "Qt / QML", "Steam", "DepotDownloader", "Proton"]' in text
    catalog = (Path(__file__).resolve().parents[1] / "qml/i18n/translations.js").read_text(encoding="utf-8")
    assert '"Czy menedżer sprawdza aktualizacje samego programu?"' in catalog
    assert 'Domyślnie menedżer sprawdza przy uruchomieniu' in catalog
    assert 'it does not update itself automatically' in catalog
    assert 'Aktualizacje aplikacji nie są automatycznie sprawdzane.' not in catalog


def test_about_layout_uses_responsive_grids_and_wrapped_faq():
    text = _settings_qml()
    assert 'columns: width >= 720 ? 2 : 1' in text
    assert 'Layout.columnSpan: aboutTopGrid.columns' in text
    assert 'wrapMode: Text.WordWrap' in text
    assert 'implicitHeight: Math.max(46, questionRow.implicitHeight + 20)' in text



def test_faq_answers_cover_real_failures_in_polish_and_english():
    text = _settings_qml()
    catalog = (Path(__file__).resolve().parents[1] / "qml/i18n/translations.js").read_text(encoding="utf-8")
    for key in ("steam", "gameDownload", "modDownload", "modVersion", "instance",
                "modsMissing", "gameLaunch", "playtime", "presets", "appUpdates",
                "modUpdates", "logs", "downloadStorage", "backup"):
        assert f'I18n.t("settings.about.faq.{key}Q")' in text
        assert f'I18n.t("settings.about.faq.{key}A")' in text
        assert catalog.count(f'"settings.about.faq.{key}Q"') == 2
        assert catalog.count(f'"settings.about.faq.{key}A"') == 2
    for group in ("steam", "instances", "maintenance"):
        assert f'I18n.t("settings.about.faq.group.{group}")' in text
        assert catalog.count(f'"settings.about.faq.group.{group}"') == 2
    assert "DepotDownloader" in catalog and "403" in catalog
