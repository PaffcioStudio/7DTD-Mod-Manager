"""Static guardrails for the combined local and 7daystodiemods.com search.

These run even on machines without Qt installed. The dedicated global-search
unit tests additionally exercise worker/Qt behavior where PySide6 is present.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_header_enter_searches_online_instead_of_local_library_only():
    main = read("qml/Main.qml")
    discover = read("qml/pages/DiscoverPage.qml")
    assert 'onSearchAccepted: window.openOnlineSearch(GlobalSearch.query)' in main
    assert 'discoverPage.searchFromHeader(phrase)' in main
    assert 'page.provider = "web"' in discover
    assert 'page.category = ""' in discover
    assert 'page.version = ""' in discover
    assert 'page.createdAfter = ""' in discover


def test_combined_dropdown_shows_live_online_matches_and_full_results_link():
    main = read("qml/Main.qml")
    popup = read("qml/components/GlobalSearchPopup.qml")
    search = read("src/backend/global_search.py")
    assert 'item.onlineChecked = Qt.binding(function() { return GlobalSearch.onlineChecked })' in main
    assert 'item.onlineOffline = Qt.binding(function() { return GlobalSearch.onlineOffline })' in main
    assert 'item.showOnlineRequested.connect(window.openOnlineSearch)' in main
    assert 'root.showOnlineRequested(root.query)' in popup
    assert 'root.onlineOffline' in popup
    assert 'root.busy' in popup
    assert 'fetch_catalog(query, "", "", 1, False)' in search
    assert '"sectionKey": "globalSearch.website"' in search
    assert '"sectionKey": "globalSearch.localMods"' in search


def test_opening_website_result_forces_online_provider():
    main = read("qml/Main.qml")
    assert 'discoverPage.provider = "web"' in main
    assert 'discoverPage.version = ""' in main
    assert 'discoverPage.openDetails(itemId)' in main


def test_bilingual_search_labels_and_release_note_are_present():
    translations = read("qml/i18n/translations.js")
    assert translations.count('"globalSearch.viewAllWebsite"') == 2
    assert translations.count('"globalSearch.website"') == 2
    notes = read("RELEASE_NOTES.md")
    current = notes.split("## (latest) 1.0.46", 1)[1].split("## (old) 1.0.45", 1)[0]
    assert "7daystodiemods.com" in current
    assert "Pressing Enter" in current
