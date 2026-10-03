from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_search_placeholder_uses_catalog():
    assert 'placeholder: I18n.t("globalSearch.placeholder")' in read("qml/components/AppHeader.qml")
    assert 'placeholder: I18n.t("globalSearch.placeholder")' in read("qml/components/SearchBar.qml")


def test_main_has_one_steam_account_connection():
    text = read("qml/Main.qml")
    assert text.count('function onAccountConnected(username)') == 1
    assert 'Połączono z kontem Steam: ' not in text


def test_global_search_uses_localized_sections_and_errors():
    py = read("src/backend/global_search.py")
    qml = read("qml/components/GlobalSearchPopup.qml")
    assert 'sectionKey' in py
    assert 'globalSearch.gameInstance' in py
    assert '__I18N__:discover.fetchFailed' in py
    assert 'I18n.t((modelData && modelData.sectionKey) || "globalSearch.title")' in qml
    assert 'root.errorKey !== ""' in qml


def test_backend_toast_calls_are_key_based():
    files=[
        "src/backend/game_detector.py", "src/backend/profile_manager.py",
        "src/backend/download_manager.py", "src/backend/mod_manager.py",
        "src/services/app_info.py",
    ]
    offenders=[]
    for rel in files:
        text=read(rel)
        if '.toast(' in text:
            offenders.append(rel)
    assert offenders == []


def test_folder_picker_user_strings_are_catalogued():
    qml=read("qml/components/FolderPickerModal.qml")
    assert 'I18n.t("folderPicker.root")' in qml
    assert 'I18n.t("folderPicker.downloads")' in qml
    assert 'actionText: I18n.t("folderPicker.refresh")' in qml


def test_notification_catalog_has_both_languages():
    text=read("qml/i18n/translations.js")
    pl,en=text.split("var en = {",1)
    keys=["globalSearch.placeholder","discover.fetchFailed","toast.account.connected","toast.instances.created","toast.downloads.completed","toast.mods.allUpToDate","common.operationFailed"]
    for key in keys:
        assert f'"{key}"' in pl
        assert f'"{key}"' in en
