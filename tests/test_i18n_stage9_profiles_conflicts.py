from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "qml/i18n/translations.js").read_text(encoding="utf-8")
GP = (ROOT / "qml/pages/GameProfilesPage.qml").read_text(encoding="utf-8")
CP = (ROOT / "qml/pages/ConflictsPage.qml").read_text(encoding="utf-8")
CC = (ROOT / "qml/components/ConflictCard.qml").read_text(encoding="utf-8")


KEYS = [
    "gameProfiles.refresh", "gameProfiles.centralTitle", "gameProfiles.directory",
    "gameProfiles.runningHint", "gameProfiles.globalBadge", "gameProfiles.globalLabel",
    "gameProfiles.assignCount", "gameProfiles.assign", "gameProfiles.deleteTooltip",
    "gameProfiles.deleteTitle", "gameProfiles.deleteMessage", "gameProfiles.deleteConfirm",
    "gameProfiles.empty.title", "gameProfiles.empty.subtitle", "gameProfiles.assignTitle",
    "gameProfiles.assignProfile", "gameProfiles.assignMessage", "gameProfiles.assignmentGlobal",
    "gameProfiles.requiresV3", "gameProfiles.noInstances", "gameProfiles.done",
    "conflicts.empty.title", "conflicts.empty.subtitle", "conflicts.card.inConflictWith",
    "conflicts.card.reason", "conflicts.card.keepA", "conflicts.card.keepB", "conflicts.card.details",
]


def test_profile_and_conflict_stage_keys_have_both_languages():
    for key in KEYS:
        assert CATALOG.count(f'"{key}"') == 2, key


def test_game_profiles_page_uses_i18n_for_all_user_visible_polish_text():
    assert 'import "../i18n"' in GP
    for needle in (
        'I18n.t("gameProfiles.refresh")', 'I18n.t("gameProfiles.centralTitle")',
        'I18n.format("gameProfiles.directory"', 'I18n.t("gameProfiles.runningHint")',
        'I18n.t("gameProfiles.globalBadge")', 'I18n.t("gameProfiles.globalLabel")',
        'I18n.format("gameProfiles.assignCount"', 'I18n.t("gameProfiles.assign")',
        'I18n.t("gameProfiles.deleteTooltip")', 'I18n.format("gameProfiles.deleteMessage"',
        'I18n.t("gameProfiles.empty.title")', 'I18n.t("gameProfiles.assignTitle")',
        'I18n.format("gameProfiles.assignProfile"', 'I18n.t("gameProfiles.assignMessage")',
        'I18n.t("gameProfiles.assignmentGlobal")', 'I18n.t("gameProfiles.requiresV3")',
        'I18n.t("gameProfiles.noInstances")', 'I18n.t("gameProfiles.done")',
        'I18n.format("gameProfiles.sourceAssignments"', 'I18n.format("gameProfiles.assigned"',
    ):
        assert needle in GP, needle
    for phrase in ("Odśwież", "Centralne profile", "GLOBALNY", "Globalnie", "Przypisz", "Usuń profil", "Brak profili", "Przypisz profil", "globalny", "wymaga V3+"):
        assert f'"{phrase}"' not in GP, phrase


def test_conflict_page_and_card_use_i18n():
    assert 'import "../i18n"' in CP
    assert 'I18n.t("conflicts.empty.title")' in CP
    assert 'I18n.t("conflicts.empty.subtitle")' in CP
    assert 'import "../i18n"' in CC
    for needle in (
        'I18n.t("conflicts.card.inConflictWith")',
        'I18n.format("conflicts.card.reason"',
        'I18n.format("conflicts.card.keepA"',
        'I18n.format("conflicts.card.keepB"',
        'I18n.t("conflicts.card.details")',
    ):
        assert needle in CC, needle
    for phrase in ("w konflikcie z", "Przyczyna", "Zachowaj", "Szczegóły"):
        assert f'"{phrase}' not in CC, phrase
