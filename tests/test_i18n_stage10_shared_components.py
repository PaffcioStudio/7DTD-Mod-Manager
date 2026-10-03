from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_shared_components_use_i18n_for_user_facing_polish_text():
    qml_files = [
        "qml/components/GlobalSearchPopup.qml",
        "qml/components/FolderPickerModal.qml",
        "qml/components/SteamAccountModal.qml",
        "qml/components/Toast.qml",
        "qml/components/ConfirmModal.qml",
        "qml/components/EmptyState.qml",
        "qml/components/AppHeader.qml",
        "qml/components/ModalBase.qml",
        "qml/pages/ProfilesPage.qml",
    ]
    forbidden = [
        '"Wyniki wyszukiwania"', '"Odkrywaj..."', '"Brak wyników dla',
        '"Importuj folder"', '"Miejsca"', '"Dyski i urządzenia"',
        '"Anuluj"', '"Skanuj i importuj"', '"Konto Steam"',
        '"Zaloguj ponownie"', '"Wyloguj"', '"Zamknij"',
        '"Minimalizuj"', '"Maksymalizuj"', '"Przywróć"',
        '"Potwierdź"', '"Tu jest pusto"',
    ]
    offenders = []
    for rel in qml_files:
        text = _read(rel)
        for needle in forbidden:
            if needle in text:
                offenders.append((rel, needle))
    assert offenders == []


def test_stage10_catalog_has_common_keys_in_both_languages():
    text = _read("qml/i18n/translations.js")
    pl, en = text.split("var en = {", 1)
    keys = [
        "common.confirm.confirm", "common.confirm.cancel", "common.close",
        "header.settingsTooltip", "globalSearch.title", "folderPicker.title",
        "steamAccount.title", "steamAccount.logout", "main.multiMod.title",
        "profiles.modsEmptyTitle",
    ]
    for key in keys:
        assert f'"{key}"' in pl
        assert f'"{key}"' in en


def test_previous_polish_archive_catalog_entries_are_not_overwritten():
    text = _read("qml/i18n/translations.js")
    pl = text.split("var en = {", 1)[0]
    for key in [
        "settings.download.archives.none",
        "settings.download.archives.confirmTitle",
        "settings.download.archives.confirmMessage",
    ]:
        assert pl.count(f'"{key}"') == 1
