from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLORS = (ROOT / "qml/theme/Colors.qml").read_text(encoding="utf-8")
THEME = (ROOT / "qml/theme/Theme.qml").read_text(encoding="utf-8")
SETTINGS_QML = (ROOT / "qml/pages/SettingsPage.qml").read_text(encoding="utf-8")
SETTINGS_PY = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
HERO = (ROOT / "qml/components/HeroCard.qml").read_text(encoding="utf-8")


def test_stalker_theme_is_a_first_class_theme_mode():
    assert 'mode === "stalker"' in COLORS
    assert '"#0B0A08"' in COLORS
    assert '"#E05A2A"' in COLORS
    assert '"#C33D36"' in COLORS
    assert '"#A8B84D"' in COLORS


def test_stalker_theme_is_supported_by_settings_backend_and_ui():
    assert '"dark", "light", "stalker", "stalker-light"' in SETTINGS_PY
    assert 'value: "stalker"' in SETTINGS_QML
    assert 'I18n.t("settings.theme.stalker")' in SETTINGS_QML
    assert 'I18n.t("settings.theme.stalkerLight")' in SETTINGS_QML


def test_stalker_theme_keeps_hero_in_night_palette():
    assert 'Colors.mode === "light"' in HERO
    assert 'hero-night-${root.heroImageIndex}.png' in HERO
    assert 'mode === "stalker"' in THEME


def test_theme_exposes_dynamic_stalker_hero_tokens():
    assert 'heroChipBg' in THEME
    assert 'heroChipBorder' in THEME
    assert 'heroOverlay' in THEME
    assert 'imageOverlay' in THEME
    assert 'mode === "stalker"' in THEME


def test_image_details_overlay_uses_theme_palette():
    drawer = (ROOT / "qml/components/ModDetailsDrawer.qml").read_text(encoding="utf-8")
    assert 'Theme.rgba(Theme.imageOverlay, 0.38)' in drawer
    assert 'Theme.rgba(Theme.imageOverlay, 0.8)' in drawer


def test_stalker_light_theme_is_light_and_stalker_consistent():
    assert 'mode === "stalker-light"' in COLORS
    assert '#E9E3D8' in COLORS
    assert '#C9542C' in COLORS
    assert '#718D32' in COLORS
    assert 'mode === "stalker-light"' in THEME


def test_stalker_light_uses_daytime_hero_artwork():
    assert 'Colors.mode === "stalker-light"' in HERO



def test_hero_uses_all_five_day_and_night_assets_and_periodic_setting():
    assert 'heroImageCount: 5' in HERO
    assert 'hero-day-${root.heroImageIndex}.png' in HERO
    assert 'hero-night-${root.heroImageIndex}.png' in HERO
    assert 'Settings.heroRotationEnabled' in HERO
    assert 'heroRotationIntervalMs: 15 * 60 * 1000' in HERO
    dashboard = (ROOT / "qml/pages/DashboardPage.qml").read_text(encoding="utf-8")
    assert 'periodicRotationActive: page.active' in dashboard
    for prefix in ("hero-day", "hero-night"):
        for index in range(1, 6):
            assert (ROOT / "assets/images" / f"{prefix}-{index}.png").is_file()
