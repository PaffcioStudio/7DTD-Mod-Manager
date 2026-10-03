from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
PAGE = (ROOT / "qml/pages/UpdatesPage.qml").read_text(encoding="utf-8")
CARD = (ROOT / "qml/components/UpdateCard.qml").read_text(encoding="utf-8")

KEYS = (
    "updates.title", "updates.caption.withUpdates", "updates.caption.current",
    "updates.check", "updates.checkBusy", "updates.updateAll",
    "updates.noneToStart", "updates.queuedToast", "updates.allDone.title",
    "updates.allDone.subtitle", "updates.card.downloading", "updates.card.queued",
    "updates.card.released", "updates.card.done", "updates.card.update",
)


def test_all_update_stage_keys_exist_in_both_catalogs():
    for key in KEYS:
        assert TRANSLATIONS.count(f'"{key}"') == 2, key


def test_updates_page_is_catalog_driven():
    assert 'import "../i18n"' in PAGE
    for needle in (
        'I18n.t("updates.noneToStart")',
        'I18n.format("updates.queuedToast"',
        'I18n.t("updates.checkBusy")',
        'I18n.t("updates.check")',
        'I18n.t("updates.updateAll")',
        'I18n.t("updates.allDone.title")',
        'I18n.t("updates.allDone.subtitle")',
    ):
        assert needle in PAGE, needle


def test_update_card_is_catalog_driven():
    assert 'import "../i18n"' in CARD
    for needle in (
        'I18n.format("updates.card.downloading"',
        'I18n.t("updates.card.queued")',
        'I18n.format("updates.card.released"',
        'I18n.t("updates.card.done")',
        'I18n.t("updates.card.update")',
    ):
        assert needle in CARD, needle
    for phrase in ('"Pobieranie aktualizacji… "', '"W kolejce do pobrania"', '"Wydano "', '"Gotowe"', '"Aktualizuj"'):
        assert phrase not in CARD, phrase
