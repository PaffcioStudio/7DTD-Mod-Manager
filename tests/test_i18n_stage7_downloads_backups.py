from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
CAT = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
BACKUPS = (ROOT / "qml/pages/BackupsPage.qml").read_text(encoding="utf-8")
DOWNLOADS = (ROOT / "qml/pages/DownloadsPage.qml").read_text(encoding="utf-8")
CARD = (ROOT / "qml/components/DownloadCard.qml").read_text(encoding="utf-8")
BUS = (ROOT / "src/backend/events.py").read_text(encoding="utf-8")
BACKEND = (ROOT / "src/backend/modpack_manager.py").read_text(encoding="utf-8")

BACKUP_KEYS = (
    "backups.title", "backups.caption", "backups.create", "backups.items",
    "backups.created", "backups.updated", "backups.update", "backups.restore",
    "backups.delete.tooltip", "backups.delete.title", "backups.delete.message",
    "backups.delete.confirm", "backups.empty.title", "backups.empty.subtitle",
    "backups.empty.create", "backups.create.title", "backups.create.description",
    "backups.instance", "backups.noInstance", "backups.noInstance.message",
    "backups.goInstances", "backups.restore.title", "backups.restore.instance",
    "backups.restore.created", "backups.restore.warning", "backups.cancel",
    "backups.restore.action", "backups.error.instanceNotFound",
    "backups.error.backupInstanceNotFound", "backups.warning.defaultInstance",
    "backups.warning.gameRunning", "backups.success.created", "backups.success.updated",
    "backups.success.restored", "backups.success.deleted", "backups.error.operation",
)
DOWNLOAD_KEYS = (
    "downloads.title", "downloads.caption", "downloads.caption.none", "downloads.clearCompleted",
    "downloads.url.placeholder", "downloads.url.action", "downloads.active", "downloads.completed",
    "downloads.completed.subtitle", "downloads.completed.status", "downloads.empty.title",
    "downloads.empty.subtitle", "downloads.empty.action", "downloads.eta.seconds",
    "downloads.eta.minutes", "downloads.control.pause", "downloads.control.pauseUnavailable",
    "downloads.control.resume", "downloads.control.retry", "downloads.control.cancel",
    "downloads.control.completed",
)


def test_stage7_keys_exist_in_both_catalogs():
    for key in BACKUP_KEYS + DOWNLOAD_KEYS:
        assert CAT.count(f'"{key}"') == 2, key


def test_backups_page_is_fully_catalog_driven():
    assert '"modpacks": [I18n.t("backups.title")' in MAIN
    assert 'import "../i18n"' in BACKUPS
    for needle in (
        'I18n.t("backups.create")', 'I18n.format("backups.items"',
        'I18n.format("backups.created"', 'I18n.format("backups.updated"',
        'I18n.t("backups.update")', 'I18n.t("backups.restore")',
        'I18n.t("backups.delete.tooltip")', 'I18n.format("backups.delete.message"',
        'I18n.t("backups.empty.title")', 'I18n.t("backups.empty.subtitle")',
        'I18n.t("backups.create.title")', 'I18n.t("backups.create.description")',
        'I18n.t("backups.instance")', 'I18n.t("backups.noInstance")',
        'I18n.t("backups.noInstance.message")', 'I18n.t("backups.goInstances")',
        'I18n.t("backups.restore.title")', 'I18n.format("backups.restore.instance"',
        'I18n.t("backups.restore.warning")', 'I18n.t("backups.cancel")',
        'I18n.t("backups.restore.action")',
    ):
        assert needle in BACKUPS, needle
    # The page title is intentionally supplied by AppHeader; page content keeps only actions.
    assert 'title: "Kopie zapasowe"' not in BACKUPS
    for marker in (
        'text: "Utwórz kopię"',
        'text: "Aktualizuj"', 'text: "Przywróć"', 'tooltip: "Usuń kopię zapasową"',
        'title: "Brak kopii zapasowych"', 'title: "Nowa kopia zapasowa"',
        'title: "Przywróć kopię zapasową"', 'text: "Anuluj"',
    ):
        assert marker not in BACKUPS, marker


def test_downloads_page_and_card_are_catalog_driven():
    assert '"downloads": [I18n.t("downloads.title")' in MAIN
    assert 'import "../i18n"' in DOWNLOADS
    assert 'import "../i18n"' in CARD
    for needle in (
        'I18n.t("downloads.clearCompleted")',
        'I18n.t("downloads.url.placeholder")', 'I18n.t("downloads.url.action")',
        'I18n.t("downloads.active")', 'I18n.t("downloads.completed")',
        'I18n.t("downloads.empty.title")', 'I18n.t("downloads.empty.subtitle")',
        'I18n.t("downloads.empty.action")',
    ):
        assert needle in DOWNLOADS, needle
    for needle in (
        'I18n.t("downloads.control.pause")', 'I18n.t("downloads.control.pauseUnavailable")',
        'I18n.t("downloads.control.resume")', 'I18n.t("downloads.control.retry")',
        'I18n.t("downloads.control.cancel")', 'I18n.format("downloads.eta.seconds"',
        'I18n.format("downloads.eta.minutes"',
    ):
        assert needle in CARD, needle


def test_backup_backend_uses_translatable_toasts():
    assert 'toastKey("backups.' in BACKEND
    assert '__I18N__:backups.' in BACKEND
    assert 'Nie znaleziono instancji' not in BACKEND


def test_event_bus_exposes_keyed_toasts():
    assert 'notifyKey = Signal(str, "QVariantMap", str)' in BUS
    assert 'def toastKey(' in BUS
