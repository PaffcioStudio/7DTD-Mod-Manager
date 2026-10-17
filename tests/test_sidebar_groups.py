"""Regressions for the compact sidebar and persisted section state."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = (ROOT / "qml/components/AppSidebar.qml").read_text(encoding="utf-8")
SETTINGS = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
LANGUAGE = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
NOTES = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")


def _group_pages(property_name):
    match = re.search(rf'readonly property var {property_name}: \[(.*?)\n    \]', SIDEBAR, re.S)
    assert match, property_name
    return re.findall(r'\{ page: "([^"]+)"', match.group(1))


def test_every_original_sidebar_page_occurs_exactly_once():
    assert _group_pages("navItems") == [
        "dashboard", "profiles", "mods", "discover", "downloads"
    ]
    assert _group_pages("gameItems") == ["steam_releases", "protons"]
    assert _group_pages("toolItems") == ["game_profiles", "modpacks", "updates"]
    all_pages = (_group_pages("navItems") + _group_pages("gameItems") +
                 _group_pages("toolItems"))
    assert len(all_pages) == len(set(all_pages)) == 10
    assert 'pageName: "settings"' in SIDEBAR


def test_independent_sections_are_saved_by_the_settings_service():
    for name in ("sidebarGameExpanded", "sidebarToolsExpanded"):
        assert f'"{name}": False' in SETTINGS
        assert f'def {name}(self) -> bool:' in SETTINGS
        assert f'@{name}.setter' in SETTINGS
        preview = 'previewGameExpanded' if name == 'sidebarGameExpanded' else 'previewToolsExpanded'
        assert f'expanded: sidebar.screenshotPreview ? sidebar.{preview} : Settings.{name}' in SIDEBAR
        assert f'Settings.{name} = !Settings.{name}' in SIDEBAR
    assert "self.sidebarGroupsChanged" in SETTINGS
    assert 'self._save_timer.start()' in SETTINGS


def test_active_pages_open_the_matching_group_and_are_scrolled_into_view():
    assert 'onActivePageChanged: {' in SIDEBAR
    assert 'Settings.sidebarGameExpanded = true' in SIDEBAR
    assert 'Settings.sidebarToolsExpanded = true' in SIDEBAR
    assert 'gameGroup.itemForPage(activePage) || toolsGroup.itemForPage(activePage)' in SIDEBAR
    assert 'activeItemScrollTimer.restart()' in SIDEBAR
    assert 'onNavigateRequested: (page) => sidebar.navigateRequested(page)' in SIDEBAR
    assert 'onNavigateRequested: (page) => pageStack.go(page)' in MAIN


def test_navigation_is_scrollable_but_settings_remains_pinned():
    assert 'Layout.fillHeight: true\n            clip: true\n            contentHeight:' in SIDEBAR
    assert 'flickableDirection: Flickable.VerticalFlick' in SIDEBAR
    assert SIDEBAR.index('id: navigationFlickable') < SIDEBAR.index('pageName: "settings"')
    assert 'badgeCount: expanded ? -1 : sidebar.updatesCount' in SIDEBAR
    assert 'showDot: modelData.badge === "dot" && sidebar.downloadsActive > 0' in SIDEBAR
    assert 'duration: Theme.animationsEnabled ? 160 : 0' in SIDEBAR


def test_labels_exist_in_both_languages_and_release_version_is_unchanged():
    for key in ('nav.gameEnvironment', 'nav.tools'):
        assert LANGUAGE.count(f'"{key}"') == 2
    assert '"nav.gameEnvironment": "Gra i środowisko"' in LANGUAGE
    assert '"nav.gameEnvironment": "Game & Environment"' in LANGUAGE
    assert NOTES.count('## (latest)') == 1
    assert '## (latest) 1.0.45\n' in NOTES
    assert '## (old) 1.0.44\n' in NOTES
    assert NOTES.index('Reorganized the sidebar') < NOTES.index('## (old) 1.0.44')
    assert 'APP_VERSION = "1.0.45"' in (ROOT / 'src/services/app_info.py').read_text()
