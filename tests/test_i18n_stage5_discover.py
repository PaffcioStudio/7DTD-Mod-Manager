from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
DISCOVER = (ROOT / "qml/pages/DiscoverPage.qml").read_text(encoding="utf-8")
WEB = (ROOT / "qml/components/WebModDrawer.qml").read_text(encoding="utf-8")
LOCAL = (ROOT / "qml/components/LocalModDrawer.qml").read_text(encoding="utf-8")
BACKEND = (ROOT / "src/backend/discover.py").read_text(encoding="utf-8")


KEYS = (
    "discover.search.webPlaceholder", "discover.search.localPlaceholder",
    "discover.refresh", "discover.downloads", "discover.provider.web",
    "discover.provider.local", "discover.filter.allCategories",
    "discover.filter.allVersions", "discover.time.any", "discover.time.7d",
    "discover.time.30d", "discover.time.365d", "discover.adult",
    "discover.saveDefaults.tooltip", "discover.saveDefaults.toast",
    "discover.searching", "discover.results.one", "discover.results.few",
    "discover.results.many", "discover.offline", "discover.downloadsCount",
    "discover.openModPage", "discover.download.queued",
    "discover.download.completed", "discover.download.action",
    "discover.loading", "discover.empty", "discover.retry",
    "discover.pagination.previous", "discover.pagination.next",
    "discover.error.fetchFailed", "discover.drawer.openModPage",
    "discover.drawer.openSource", "discover.drawer.close",
    "discover.drawer.detailsError", "discover.drawer.filesTitle",
    "discover.drawer.fileType.main", "discover.drawer.fileType.optional",
    "discover.drawer.fileType.old", "discover.drawer.fileType.external",
    "discover.drawer.description", "discover.drawer.changelog",
    "discover.local.overhaul", "discover.local.noDescription",
    "discover.local.downloadOverhaul",
)


def test_all_discover_stage_five_keys_exist_in_both_catalogs():
    for key in KEYS:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_discover_page_is_catalog_driven():
    assert 'import "../i18n"' in DISCOVER
    for needle in (
        'I18n.t("discover.search.webPlaceholder")',
        'I18n.t("discover.search.localPlaceholder")',
        'I18n.t("discover.refresh")',
        'I18n.t("discover.downloads")',
        'I18n.t("discover.provider.web")',
        'I18n.t("discover.provider.local")',
        'I18n.t("discover.adult")',
        'I18n.t("discover.time.any")',
        'I18n.t("discover.time.7d")',
        'options: page.categoryOptions',
        'options: page.versionOptions',
        'I18n.t("discover.saveDefaults.tooltip")',
        'I18n.t("discover.searching")',
        'page.resultsLabel(Discover.total)',
        'I18n.t("discover.offline")',
        'I18n.format("discover.downloadsCount"',
        'I18n.t("discover.openModPage")',
        'I18n.t("discover.download.queued")',
        'I18n.t("discover.download.completed")',
        'I18n.t("discover.download.action")',
        'I18n.t("discover.loading")',
        'I18n.t("discover.empty")',
        'I18n.t("discover.retry")',
        'I18n.t("discover.pagination.previous")',
        'I18n.t("discover.pagination.next")',
        'function refreshI18nOptions()',
        'function onLanguageChanged() { page.refreshI18nOptions() }',
    ):
        assert needle in DISCOVER, needle


def test_discover_drawers_are_catalog_driven():
    assert 'import "../i18n"' in WEB
    assert 'import "../i18n"' in LOCAL
    for source in (WEB, LOCAL):
        assert 'I18n.t("discover.drawer.close")' in source
        assert 'I18n.t("discover.drawer.description")' in source
        assert 'I18n.t("discover.download.queued")' in source
    for needle in (
        'I18n.t("discover.drawer.filesTitle")',
        'I18n.t("discover.drawer.fileType.main")',
        'I18n.t("discover.drawer.fileType.optional")',
        'I18n.t("discover.drawer.fileType.old")',
        'I18n.t("discover.drawer.fileType.external")',
        'I18n.t("discover.download.completed")',
        'I18n.t("discover.download.action")',
        'I18n.t("discover.drawer.changelog")',
    ):
        assert needle in WEB, needle
    for needle in (
        'I18n.t("discover.drawer.openSource")',
        'I18n.t("discover.local.overhaul")',
        'I18n.t("discover.local.noDescription")',
        'I18n.t("discover.local.downloadOverhaul")',
    ):
        assert needle in LOCAL, needle


def test_discover_backend_uses_stable_i18n_error_code():
    assert '"discover.error.fetchFailed"' in BACKEND
    assert 'Serwis zwrócił nierozpoznany katalog modów.' not in BACKEND


def test_mod_card_web_search_test_matches_i18n_design():
    source = (ROOT / "qml/components/ModCard.qml").read_text(encoding="utf-8")
    assert 'text: I18n.t("mod.card.searchOnline")' in source



def test_discover_has_no_remaining_user_visible_polish_ui_assignments():
    for source in (DISCOVER, WEB, LOCAL):
        for marker in (
            'text: "Szukaj', 'placeholder: "Szukaj', 'text: "Odśwież"',
            'text: "Pobieranie"', 'label: "Dowolny czas"',
            'label: "Ostatni tydzień"', 'label: "Ostatni miesiąc"',
            'label: "Ostatni rok"', 'tooltip: "Zapisz aktualne filtry Odkrywaj jako domyślne"',
            'text: "Wyszukiwanie...', 'text: "Pobrano"', 'text: "Pobierz"',
            'text: "W kolejce"', 'text: "Ładowanie katalogu...',
            'text: "Spróbuj ponownie"', 'tooltip: "Poprzednia strona"',
            'tooltip: "Następna strona"', 'tooltip: "Otwórz stronę moda"',
            'tooltip: "Zamknij"', 'text: "PLIKI DO POBRANIA"',
            'text: "OPIS"', 'text: "HISTORIA WERSJI"',
            'text: "Brak opisu."', 'text: "Pobierz overhaul"',
        ):
            assert marker not in source, marker
