from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "qml/pages/DashboardPage.qml").read_text(encoding="utf-8")
HERO = (ROOT / "qml/components/HeroCard.qml").read_text(encoding="utf-8")
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
I18N = (ROOT / "qml/i18n/I18n.qml").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")


KEYS = (
    "dashboard.title", "dashboard.subtitle",
    "dashboard.stat.installed", "dashboard.stat.enabled",
    "dashboard.stat.conflicts", "dashboard.stat.updates",
    "dashboard.stopGame.title", "dashboard.stopGame.message", "dashboard.stopGame.confirm",
    "dashboard.activeInstance.title", "dashboard.activeInstance.caption",
    "dashboard.activeInstance.enabledMods", "dashboard.activeInstance.ready",
    "dashboard.activeInstance.none", "dashboard.activeInstance.manage",
    "dashboard.conflicts.title", "dashboard.conflicts.attention",
    "dashboard.conflicts.loadingOrder", "dashboard.conflicts.detected",
    "dashboard.conflicts.none", "dashboard.conflicts.checkOrder",
    "dashboard.conflicts.safe", "dashboard.conflicts.view",
    "dashboard.conflicts.openList",
    "hero.kicker", "hero.gameDetected", "hero.gameNotDetected",
    "hero.mods", "hero.enabled", "hero.conflicts", "hero.updates",
    "hero.launchGame", "hero.stopGame", "hero.manageMods",
)


def test_dashboard_catalog_has_polish_and_english_for_every_stage_two_key():
    for key in KEYS:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_i18n_has_safe_placeholder_formatting():
    assert "function format(key, values)" in I18N
    assert r'const matches = text.match(/\{([A-Za-z0-9_.-]+)\}/g) || []' in I18N
    assert 'value = values[name]' in I18N


def test_dashboard_uses_translation_keys_for_user_visible_text():
    assert 'import "../i18n"' in DASHBOARD
    assert 'title: I18n.t(modelData.titleKey)' in DASHBOARD
    assert 'I18n.format("dashboard.activeInstance.enabledMods"' in DASHBOARD
    assert 'I18n.format("dashboard.conflicts.attention"' in DASHBOARD
    assert 'I18n.format("dashboard.conflicts.detected"' in DASHBOARD
    forbidden = (
        "Zatrzymać grę?", "Proces gry zostanie zakończony", "Zatrzymaj grę",
        "Aktywna instancja", "Wybierz profil, na którym chcesz pracować",
        "modów włączonych", "Aktywna instancja jest gotowa do uruchomienia",
        "Brak wybranej instancji", "Zarządzaj instancjami", "Konflikty",
        "konfliktów wymaga Twojej uwagi", "Stan kolejności ładowania modów",
        "wykrytych konfliktów", "Brak wykrytych konfliktów",
        "Sprawdź kolejność ładowania i zależności modów.",
        "Możesz spokojnie uruchomić bieżącą instancję.",
        "Zobacz konflikty", "Otwórz listę konfliktów",
    )
    for text in forbidden:
        assert text not in DASHBOARD, text


def test_hero_card_uses_translation_keys_for_user_visible_text():
    assert 'import "../i18n"' in HERO
    for key in (
        "hero.kicker", "hero.gameDetected", "hero.gameNotDetected", "hero.mods",
        "hero.enabled", "hero.conflicts", "hero.updates", "hero.launchGame",
        "hero.stopGame", "hero.manageMods",
    ):
        assert f'I18n.t("{key}")' in HERO, key
    assert "MENEDŻER MODÓW" not in HERO
    assert "Gra wykryta" not in HERO
    assert "Gra niewykryta" not in HERO
    assert "ZARZĄDZAJ MODAMI" not in HERO


def test_main_uses_i18n_for_dashboard_header():
    assert '"dashboard": I18n.t("dashboard.title")' in MAIN
