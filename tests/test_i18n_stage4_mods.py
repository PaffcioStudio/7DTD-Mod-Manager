from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS_PAGE = (ROOT / "qml/pages/ModsPage.qml").read_text(encoding="utf-8")
MOD_CARD = (ROOT / "qml/components/ModCard.qml").read_text(encoding="utf-8")
DETAILS = (ROOT / "qml/components/ModDetailsDrawer.qml").read_text(encoding="utf-8")
STATUS = (ROOT / "qml/components/StatusBadge.qml").read_text(encoding="utf-8")
THEME = (ROOT / "qml/theme/Theme.qml").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")

KEYS = (
    "mods.title", "mods.caption", "mods.refresh", "mods.importFolder",
    "mods.searchPlaceholder", "mods.filter.all", "mods.filter.enabled",
    "mods.filter.disabled", "mods.filter.updates", "mods.filter.conflicts",
    "mods.sort.custom", "mods.sort.name", "mods.sort.installed",
    "mods.sort.updated", "mods.sort.author", "mods.sort.size",
    "mods.sort.desc", "mods.sort.asc", "mods.loadOrder.fetchingIcons",
    "mods.loadOrder.hint", "mods.empty.title", "mods.empty.search",
    "mods.empty.category", "mods.empty.clearFilters", "mods.uninstall.title",
    "mods.uninstall.message", "mods.uninstall.confirm", "mod.card.conflict",
    "mod.card.meta", "mod.card.gameSuffix", "mod.card.more", "mod.card.openFolder",
    "mod.card.checkUpdates", "mod.card.updateQueued", "mod.card.current",
    "mod.card.copyVersion", "mod.card.searchOnline", "mod.card.uninstall",
    "mod.card.details", "mod.drawer.close", "mod.drawer.author", "mod.drawer.size",
    "mod.drawer.rating", "mod.drawer.downloads", "mod.drawer.installed",
    "mod.drawer.updated", "mod.drawer.game", "mod.drawer.description",
    "mod.drawer.tags", "mod.drawer.requirements", "mod.drawer.dependencies",
    "mod.drawer.noDependencies", "mod.drawer.conflicts", "mod.drawer.conflictsWith",
    "mod.drawer.viewConflicts", "mod.drawer.enable", "mod.drawer.disable",
    "mod.drawer.openFolder", "mod.drawer.uninstall", "mod.drawer.uninstallTitle",
    "mod.drawer.uninstallMessage", "mod.drawer.unnamed",
    "status.enabled", "status.disabled", "status.update", "status.conflict",
    "status.completed", "status.failed", "status.paused", "status.queued",
    "status.downloading", "status.cancelled", "status.success", "status.error",
    "status.warning", "status.info",
    "category.Overhaul", "category.Gameplay", "category.UI", "category.Graphics",
    "category.Vehicles", "category.Zombies", "category.Items", "category.Magic",
    "category.World",
)


def test_every_mods_stage_four_key_exists_in_both_catalogs():
    for key in KEYS:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_mods_page_is_fully_catalog_driven_for_stage_four_text():
    assert 'import "../i18n"' in MODS_PAGE
    for needle in (
        'I18n.t("mods.refresh")',
        'I18n.t("mods.importFolder")',
        'placeholder: I18n.t("mods.searchPlaceholder")',
        'I18n.t("mods.sort.desc")',
        'I18n.t("mods.sort.asc")',
        'I18n.format("mods.loadOrder.fetchingIcons"',
        'I18n.t("mods.loadOrder.hint")',
        'I18n.t("mods.empty.title")',
        'I18n.format("mods.empty.search"',
        'I18n.t("mods.empty.category")',
        'I18n.t("mods.empty.clearFilters")',
        'I18n.t("mods.uninstall.title")',
        'I18n.format("mods.uninstall.message"',
        'I18n.t("mods.uninstall.confirm")',
        'function onLanguageChanged() { modsPage.refreshI18nOptions() }',
    ):
        assert needle in MODS_PAGE, needle


def test_mod_card_is_fully_catalog_driven():
    assert 'import "../i18n"' in MOD_CARD
    for needle in (
        'I18n.t("mod.card.conflict")', 'I18n.format("mod.card.meta"',
        'I18n.format("mod.card.gameSuffix"', 'I18n.t("mod.card.more")',
        'I18n.t("mod.card.openFolder")', 'I18n.t("mod.card.checkUpdates")',
        'I18n.format("mod.card.updateQueued"', 'I18n.format("mod.card.current"',
        'I18n.t("mod.card.copyVersion")', 'I18n.t("mod.card.searchOnline")',
        'I18n.t("mod.card.uninstall")', 'I18n.t("mod.card.details")',
    ):
        assert needle in MOD_CARD, needle
    for phrase in ('"Konflikt"', '"Więcej akcji"', '"Otwórz folder"', '"Sprawdź aktualizacje"',
                   '"Kopiuj wersję"', '"Wyszukaj w sieci"', '"Odinstaluj"', '"Szczegóły"'):
        assert phrase not in MOD_CARD, phrase


def test_mod_details_drawer_uses_i18n_for_all_labels_and_actions():
    assert 'import "../i18n"' in DETAILS
    for needle in (
        'I18n.format("mod.drawer.author"', 'I18n.t("mod.drawer.close")',
        'I18n.t("mod.drawer.size")', 'I18n.t("mod.drawer.rating")',
        'I18n.t("mod.drawer.downloads")', 'I18n.t("mod.drawer.installed")',
        'I18n.t("mod.drawer.updated")', 'I18n.t("mod.drawer.game")',
        'I18n.t("mod.drawer.description")', 'I18n.t("mod.drawer.tags")',
        'I18n.t("mod.drawer.requirements")', 'I18n.t("mod.drawer.dependencies")',
        'I18n.t("mod.drawer.noDependencies")', 'I18n.t("mod.drawer.conflicts")',
        'I18n.format("mod.drawer.conflictsWith"', 'I18n.t("mod.drawer.viewConflicts")',
        'I18n.t("mod.drawer.disable")', 'I18n.t("mod.drawer.enable")',
        'I18n.t("mod.drawer.openFolder")', 'I18n.t("mod.drawer.uninstall")',
        'I18n.t("mod.drawer.uninstallTitle")', 'I18n.format("mod.drawer.uninstallMessage"',
    ):
        assert needle in DETAILS, needle


def test_status_badge_and_categories_are_localized():
    assert 'import "../i18n"' in STATUS
    assert 'I18n.t("status." + key)' in STATUS
    assert 'import "../i18n"' in THEME
    assert 'I18n.t("category." + key)' in THEME
