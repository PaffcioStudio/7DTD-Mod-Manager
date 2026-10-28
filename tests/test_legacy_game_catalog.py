"""Sprawdza archiwalne manifesty 7DTD używane przez DepotDownloader."""
from backend.legacy_game_catalog import RELEASES, RELEASE_BY_BRANCH, release_options


def test_historical_versions_are_unique_and_complete():
    assert len(RELEASES) == 32
    assert len(RELEASE_BY_BRANCH) == len(RELEASES)
    assert len(release_options()) == len(RELEASES)
    assert RELEASES[0].branch == "alpha5.0"
    assert RELEASES[-1].branch == "alpha8.8"
    for release in RELEASES:
        assert release.depot in {"251571", "251574", "251576"}
        assert release.manifest.isdecimal()
        assert release.osarch in {"32", "64"}


def test_manifest_hotfixes_use_new_id_not_previous_id():
    assert RELEASE_BY_BRANCH["alpha5.0"].manifest == "8674858241122065491"
    assert RELEASE_BY_BRANCH["alpha5.0-fix2"].manifest == "5316387393437744190"
    assert RELEASE_BY_BRANCH["alpha6.4"].manifest == "862254068326349864"
    assert RELEASE_BY_BRANCH["alpha7.3-v2"].manifest == "2677701425442127837"
    assert RELEASE_BY_BRANCH["alpha7.7-b7"].manifest == "2595209504322754915"
    assert RELEASE_BY_BRANCH["alpha8.6-ninja"].manifest == "6738103586104812619"
    assert RELEASE_BY_BRANCH["alpha8.7"].manifest == "7508090567390550102"
    assert RELEASE_BY_BRANCH["alpha8.8"].steam_branch


def test_legacy_depots_match_windows_release_family():
    for release in RELEASES:
        if release.branch.startswith("alpha5"):
            assert release.depot == "251571"
        elif release.branch.startswith("alpha6"):
            assert release.depot == "251574"
        else:
            assert release.depot == "251576"


def test_special_release_labels_use_translation_keys():
    expected = {
        "alpha5.0-fix1", "alpha5.0-fix2", "alpha7.3-v2",
        "alpha7.7-b7", "alpha8.6-ninja", "alpha8.8",
    }
    options = release_options()
    assert {item["branch"] for item in options if item["label_key"]} == expected
    assert all(not item["label_key"] or item["label_key"].startswith(
        "steamReleases.legacy.release.") for item in options)
    assert all("poprawki" not in item["label"] for item in options)


def test_ui_translates_release_labels_and_covers_both_catalogs():
    from pathlib import Path
    import re

    root = Path(__file__).resolve().parents[1]
    js = (root / "qml/i18n/translations.js").read_text(encoding="utf-8")
    qml = (root / "qml/pages/SteamReleasesPage.qml").read_text(encoding="utf-8")
    catalogs = re.split(r"\bvar (?:pl|en) = \{", js)[1:]
    assert len(catalogs) == 2
    labels = [item["label_key"] for item in release_options() if item["label_key"]]
    keys = labels + [
        "steamReleases.legacy.importSuccess",
        "steamReleases.legacy.error.busy",
        "steamReleases.legacy.error.importFailed",
        "steamReleases.legacy.error.invalidFolder",
        "steamReleases.legacy.error.incompleteFolder",
        "steamReleases.legacy.error.invalidName",
        "steamReleases.legacy.error.chooseRelease",
        "steamReleases.legacy.error.duplicateRelease",
        "steamReleases.legacy.error.alreadyManaged",
        "steamReleases.legacy.error.duplicateLocation",
        "steamReleases.legacy.error.duplicateContent",
        "steamReleases.legacy.error.wrongAppId",
        "steamReleases.legacy.error.writeAppId",
    ]
    for catalog in catalogs:
        for key in keys:
            assert f'"{key}":' in catalog
    assert 'I18n.t(release.label_key)' in qml


def test_unavailable_downloads_match_the_audited_alpha6_depot():
    options = release_options()
    unavailable = {item['branch'] for item in options if not item['download_available']}
    assert unavailable == {'alpha6.0', 'alpha6.1', 'alpha6.2', 'alpha6.3', 'alpha6.4'}
    assert all(item['download_available'] for item in options if item['depot'] != '251574')


def test_release_dates_are_displayed_day_month_year():
    from datetime import date, datetime

    for release, option in zip(RELEASES, release_options()):
        assert datetime.strptime(option['date'], '%d-%m-%Y').date() == date.fromisoformat(release.date)
    assert next(item for item in release_options() if item['branch'] == 'alpha7.3-v2')['date'] == '07-03-2014'
