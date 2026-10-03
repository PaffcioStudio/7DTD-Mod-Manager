from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTANCES = (ROOT / "qml/pages/ProfilesPage.qml").read_text(encoding="utf-8")
INSTANCES_CODE = "\n".join(line.split("//", 1)[0] for line in INSTANCES.splitlines())
CARD = (ROOT / "qml/components/ProfileCard.qml").read_text(encoding="utf-8")
VERSIONS = (ROOT / "qml/components/GameVersionsModal.qml").read_text(encoding="utf-8")
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")


KEYS = (
    "instances.title", "instances.subtitle", "instances.gameVersions",
    "instances.stopGame.title", "instances.stopGame.message", "instances.stopGame.confirm",
    "instances.newInstance", "instances.createNew", "instances.folderPicker.title",
    "instances.editor.editTitle", "instances.editor.newTitle", "instances.editor.newStatus",
    "instances.editor.status", "instances.editor.newDescription",
    "instances.editor.defaultDescription", "instances.editor.existingDescription",
    "instances.editor.draft", "instances.editor.default", "instances.editor.instance",
    "instances.info.title", "instances.info.nameDescription", "instances.info.name",
    "instances.info.namePlaceholder", "instances.info.mods", "instances.info.description",
    "instances.info.descriptionPlaceholder", "instances.gameVersion.label",
    "instances.gameVersion.default", "instances.gameVersion.help",
    "instances.dataDir.title", "instances.dataDir.meta", "instances.dataDir.placeholder",
    "instances.dataDir.select", "instances.dataDir.defaultNotice",
    "instances.launchOptions.title", "instances.launchOptions.subtitle",
    "instances.launchOptions.noeos", "instances.launchOptions.noeosHint",
    "instances.launchOptions.noeac", "instances.launchOptions.noeacHint",
    "instances.launchOptions.skipNews", "instances.launchOptions.skipNewsHint",
    "instances.launchOptions.skipIntro", "instances.launchOptions.skipIntroHint",
    "instances.launchOptions.commandPreview", "instances.mods.title",
    "instances.mods.newCaption", "instances.mods.existingCaption", "instances.mods.refresh",
    "instances.mods.running", "instances.stats.managed", "instances.stats.enabled",
    "instances.stats.disabled", "instances.stats.manual", "instances.mods.searchPlaceholder",
    "instances.mods.enable", "instances.mods.disable", "instances.mods.filterAll",
    "instances.mods.filterEnabled", "instances.mods.filterDisabled", "instances.mods.filterManual",
    "instances.mods.results.one", "instances.mods.results.many", "instances.mods.emptySearch",
    "instances.mods.emptyAll", "instances.mods.emptySearchHint", "instances.mods.emptyAllHint",
    "instances.mods.manualNote", "instances.mod.status.manual", "instances.mod.status.enabled",
    "instances.mod.status.disabled", "instances.mod.location.manual", "instances.mod.location.present",
    "instances.mod.location.ready", "instances.mod.info", "instances.mod.toast",
    "instances.mod.toast.manual", "instances.mod.toast.enabled", "instances.mod.toast.disabled",
    "instances.footer.cancel", "instances.footer.createClose", "instances.footer.save",
    "instances.delete.title", "instances.delete.message", "instances.delete.confirm",
    "instances.delete.option", "instances.profile.favorite.remove",
    "instances.profile.favorite.add", "instances.profile.running", "instances.profile.active",
    "instances.profile.gameVersion", "instances.profile.modsCount", "instances.profile.launch",
    "instances.profile.activeButton", "instances.profile.activate", "instances.profile.buildLocked",
    "instances.profile.build", "instances.profile.openFolder", "instances.profile.editLocked",
    "instances.profile.edit", "instances.profile.duplicateLocked", "instances.profile.duplicate",
    "instances.profile.removeLocked", "instances.profile.removeDefault",
    "instances.profile.removeFavoriteFirst", "instances.profile.remove", "instances.profile.new",
    "gameVersions.title", "gameVersions.connectSteam", "gameVersions.qrHint",
    "gameVersions.qrRefresh", "gameVersions.cancelAuth", "gameVersions.account",
    "gameVersions.connected", "gameVersions.loggedInAs", "gameVersions.savedSession",
    "gameVersions.relogin", "gameVersions.downloading", "gameVersions.downloadStatus",
    "gameVersions.downloadCancel", "gameVersions.installedTitle", "gameVersions.installedCaption",
    "gameVersions.installedBadge", "gameVersions.deleteInstalled", "gameVersions.availableTitle",
    "gameVersions.availableCaption", "gameVersions.availableBadge", "gameVersions.stable",
    "gameVersions.downloaded", "gameVersions.download", "gameVersions.loading",
    "gameVersions.storageInfo", "gameVersions.refresh", "gameVersions.close",
)


def test_instances_stage_three_catalog_has_polish_and_english_for_every_key():
    for key in KEYS:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_instances_page_uses_translation_catalog_for_user_visible_text():
    assert 'import "../i18n"' in INSTANCES
    assert '"instances.mods.results.one"' in INSTANCES and '"instances.mods.results.many"' in INSTANCES
    assert 'I18n.format("instances.delete.message"' in INSTANCES
    assert 'I18n.format("instances.mod.toast"' in INSTANCES

    forbidden = (
        '"Instancje"', '"Wersje gry"', '"Nowa instancja"',
        '"Wybierz katalog danych instancji"', '"Edytuj instancję"',
        '"Konfiguracja instancji"', '"Informacje"', '"Nazwa i opis"',
        '"Wersja gry (przypisana instancji)"', '"Domyślna (Steam)"',
        '"Katalog danych"', '"Parametry uruchamiania"', '"Bez EOS"',
        '"Bez EAC"', '"Pomiń wiadomości"', '"Pomiń intro"',
        '"Podgląd komendy"', '"Mody instancji"', '"Odśwież listę modów"',
        '"Włącz"', '"Wyłącz"', '"Wszystkie"', '"Włączone"',
        '"Wyłączone"', '"Ręczne"', '"Brak wyników"',
        '"Brak modów do wyświetlenia"', '"Anuluj"', '"Zapisz zmiany"',
        '"Usuń instancję"',
    )
    for phrase in forbidden:
        assert phrase not in INSTANCES_CODE, phrase


def test_profile_card_uses_translation_catalog_for_labels_and_tooltips():
    assert 'import "../i18n"' in CARD
    for needle in (
        'I18n.t("instances.profile.favorite.remove")',
        'I18n.t("instances.profile.favorite.add")',
        'I18n.t("instances.profile.running")',
        'I18n.t("instances.profile.active")',
        'I18n.format("instances.profile.gameVersion"',
        'I18n.format("instances.profile.modsCount"',
        'I18n.t("instances.profile.launch")',
        'I18n.t("instances.profile.activate")',
        'I18n.t("instances.profile.build")',
        'I18n.t("instances.profile.openFolder")',
        'I18n.t("instances.profile.edit")',
        'I18n.t("instances.profile.duplicate")',
        'I18n.t("instances.profile.remove")',
    ):
        assert needle in CARD, needle

    for phrase in ('"DZIAŁA"', '"AKTYWNA"', '"Uruchom"', '"Aktywna"', '"Aktywuj"', '"Edytuj"', '"Duplikuj"'):
        assert phrase not in CARD, phrase


def test_game_versions_modal_is_part_of_instances_i18n_stage():
    assert 'import "../i18n"' in VERSIONS
    for needle in (
        'title: I18n.t("gameVersions.title")',
        'I18n.t("gameVersions.connectSteam")',
        'I18n.t("gameVersions.qrHint")',
        'I18n.t("gameVersions.qrRefresh")',
        'I18n.t("gameVersions.relogin")',
        'I18n.format("gameVersions.downloading"',
        'I18n.t("gameVersions.installedTitle")',
        'I18n.t("gameVersions.availableTitle")',
        'I18n.t("gameVersions.download")',
        'I18n.t("gameVersions.refresh")',
        'I18n.t("gameVersions.close")',
    ):
        assert needle in VERSIONS, needle


def test_main_instance_header_uses_i18n():
    assert '"profiles": [I18n.t("instances.title"), I18n.t("instances.subtitle")]' in MAIN
