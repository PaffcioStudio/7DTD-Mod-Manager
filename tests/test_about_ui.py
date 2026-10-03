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
    assert '<b>WYŁĄCZNIE</b>' in catalog
    assert 'legalnie posiadanej kopii 7 Days to Die z platformy Steam' in catalog


def test_about_contains_version_technologies_and_no_update_checker_claim():
    text = _settings_qml()
    assert 'label: "v" + App.version' in text
    assert 'model: ["Python", "PySide6", "Qt / QML", "Steam", "DepotDownloader", "Proton"]' in text
    catalog = (Path(__file__).resolve().parents[1] / "qml/i18n/translations.js").read_text(encoding="utf-8")
    assert '"Czy menedżer sprawdza aktualizacje samego programu?"' in catalog


def test_about_layout_uses_responsive_grids_and_wrapped_faq():
    text = _settings_qml()
    assert 'columns: width >= 720 ? 2 : 1' in text
    assert 'Layout.columnSpan: aboutTopGrid.columns' in text
    assert 'wrapMode: Text.WordWrap' in text
    assert 'implicitHeight: Math.max(46, questionRow.implicitHeight + 20)' in text

