import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests
from PySide6.QtCore import QCoreApplication

from backend.discover import DiscoverManager, fetch_catalog, parse_catalog
from backend.modpack_downloader import DownloadSourceKind, detect_source_kind
from backend.undead_legacy import MIRROR_URL, fetch_latest_release


def catalog_html(items=None):
    # Encode a small, realistic Nuxt fixture with indexed values.
    values = []
    def encode(value):
        index = len(values)
        values.append(None)
        if isinstance(value, dict):
            values[index] = {k: encode(v) for k, v in value.items()}
        elif isinstance(value, list):
            values[index] = [encode(v) for v in value]
        else:
            values[index] = value
        return index
    mods = [{"slug": "test-mod", "title": "Test mod", "summary": "Summary",
             "categories": [{"slug": "overhaul", "name": "Overhaul"}],
             "game_versions": [{"slug": "v3", "name": "V3 Mods"}],
             "author": {"display_name": "Author"}, "thumbnail": None}]
    encode({"mods-list": {"items": mods if items is None else items,
                          "page": 2, "total_pages": 3, "total": 41},
            "metadata": {"categories": [{"slug": "overhaul", "name": "Overhaul"}],
                         "gameVersions": [{"slug": "v3", "name": "V3 Mods"}]}})
    return '<script id="__NUXT_DATA__">' + json.dumps(values) + '</script>'


class DiscoverTests(unittest.TestCase):

    def test_azure_devops_items_api_zip_url_is_supported(self):
        url = (
            "https://dev.azure.com/KhaineUK/f8438d9f-d741-420b-9429-f0838ed77e7f/"
            "_apis/git/repositories/80d717da-eb1e-4211-b0c2-eae2d478e749/items"
            "?path=/&versionDescriptor%5BversionOptions%5D=0"
            "&versionDescriptor%5BversionType%5D=0&versionDescriptor%5Bversion%5D=main"
            "&resolveLfs=true&%24format=zip&api-version=5.0&download=true"
        )
        self.assertEqual(detect_source_kind(url), DownloadSourceKind.DIRECT_ZIP)

    def test_azure_devops_items_api_without_zip_format_is_not_treated_as_zip(self):
        url = (
            "https://dev.azure.com/KhaineUK/f8438d9f-d741-420b-9429-f0838ed77e7f/"
            "_apis/git/repositories/80d717da-eb1e-4211-b0c2-eae2d478e749/items"
            "?path=/&versionDescriptor%5Bversion%5D=main"
        )
        self.assertEqual(detect_source_kind(url), DownloadSourceKind.UNSUPPORTED)

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_parser_filters_actual_membership_and_keeps_pagination(self):
        result = parse_catalog(catalog_html(), "overhaul", "v3")
        self.assertEqual(result["items"][0]["author"], "Author")
        self.assertEqual(result["items"][0]["thumbnail"], "")
        self.assertEqual(result["page"], 2)
        self.assertEqual(parse_catalog(catalog_html(), "vehicle")["items"], [])
        self.assertEqual(parse_catalog(catalog_html(), version="v2")["items"], [])
        self.assertEqual(parse_catalog(catalog_html([]))["items"], [])
        with self.assertRaises(ValueError):
            parse_catalog("<html>Unavailable</html>")

    def test_created_after_and_adult_filters_are_added_to_discover_url(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("backend.discover.fs.cache_dir", return_value=Path(directory)), \
                patch("backend.discover.requests.get") as get:
            get.return_value = Mock(text=catalog_html())
            fetch_catalog(category="overhaul", version="v3", created_after="30d", include_adult=True)
            url = get.call_args.args[0]
            self.assertIn("game_version=v3", url)
            self.assertIn("category=overhaul", url)
            self.assertIn("created_after=30d", url)
            self.assertIn("include_adult=true", url)

    def test_time_filter_values_are_encoded_and_invalid_values_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("backend.discover.fs.cache_dir", return_value=Path(directory)), \
                patch("backend.discover.requests.get") as get:
            get.return_value = Mock(text=catalog_html())
            fetch_catalog(created_after="7d")
            self.assertIn("created_after=7d", get.call_args.args[0])
            get.reset_mock()
            fetch_catalog(created_after="365d")
            self.assertIn("created_after=365d", get.call_args.args[0])
            get.reset_mock()
            fetch_catalog(created_after="999d", include_adult=False)
            url = get.call_args.args[0]
            self.assertNotIn("created_after=", url)
            self.assertNotIn("include_adult=", url)

    def test_cache_reuse_force_refresh_and_offline_fallback(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("backend.discover.fs.cache_dir", return_value=Path(directory)), \
                patch("backend.discover.requests.get") as get:
            get.return_value = Mock(text=catalog_html())
            self.assertFalse(fetch_catalog(query="a & b")["offline"])
            self.assertIn("q=a+%26+b", get.call_args.args[0])
            fetch_catalog(query="a & b")
            self.assertEqual(get.call_count, 1)
            get.side_effect = requests.ConnectionError("offline")
            self.assertTrue(fetch_catalog(query="a & b", refresh=True)["offline"])
            with self.assertRaises(requests.ConnectionError):
                fetch_catalog(query="uncached")

    def test_latest_search_wins_without_parallel_request_storm(self):
        started, release = threading.Event(), threading.Event()
        calls = []
        def fetch(query, *args):
            calls.append(query)
            if query == "first":
                started.set()
                release.wait(2)
            result = parse_catalog(catalog_html())
            result["items"][0]["title"] = query
            return dict(result, offline=False)
        manager = DiscoverManager()
        with patch("backend.discover.fetch_catalog", side_effect=fetch):
            manager.search("first", "", "", 1, False)
            self.assertTrue(started.wait(1))
            manager.search("superseded", "", "", 1, False)
            manager.search("latest", "", "", 1, False)
            release.set()
            deadline = time.monotonic() + 3
            while manager.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            manager.shutdown()
        self.assertFalse(manager.busy)
        self.assertEqual(calls, ["first", "latest"])
        self.assertEqual(manager.items[0]["title"], "latest")

    def test_undead_legacy_mirror_source_is_supported(self):
        self.assertEqual(detect_source_kind(MIRROR_URL), DownloadSourceKind.UNDEAD_LEGACY_MIRROR)

    def test_undead_legacy_mirror_uses_zip_download_flavor(self):
        downloads = (Path(__file__).resolve().parents[1] / "src" / "backend" / "download_manager.py").read_text(encoding="utf-8")
        assert 'DownloadSourceKind.UNDEAD_LEGACY_MIRROR: "zip"' in downloads

    def test_undead_legacy_page_parser_extracts_v26_release_and_mirror(self):
        html = """
        <table><tr><th>Game Version</th><th>Undead Legacy Version</th><th>Downloads</th></tr>
        <tr><td>v2.6</td><td>2026.09.28 - 2.7.40</td><td>
          <a href=\"/dl?v=exp_part1\">Download Part 1</a>
          <a href=\"/dl?v=mirror\" title=\"Experimental Version of Undead Legacy\">Download (Mirror)</a>
        </td></tr></table>
        """
        fake = Mock(text=html)
        with patch("backend.undead_legacy.requests.get", return_value=fake):
            result = fetch_latest_release(refresh=True)
        self.assertEqual(result["version"], "2.7.40")
        self.assertEqual(result["game_version"], "v2.6")
        self.assertEqual(result["download_url"], MIRROR_URL)

    def test_local_catalog_uses_per_entry_game_version_and_dynamic_version(self):
        html = """
        <table><tr><td>Game Version</td><td>Undead Legacy Version</td><td>Downloads</td></tr>
        <tr><td>v2.6</td><td>2026.09.29 - 2.7.41</td><td><a href=\"/dl?v=mirror\">Download (Mirror)</a></td></tr>
        </table>
        """
        fake = Mock(text=html)
        with patch("backend.discover.fetch_latest_release", return_value={
            "version": "2.7.41", "game_version": "v2.6",
            "release_date": "2026.09.29", "download_url": MIRROR_URL,
        }), patch("backend.discover.MANIFEST_DIR", Path(__file__).resolve().parents[1] / "assets" / "manifests"):
            from backend.discover import fetch_local_catalog
            items = fetch_local_catalog("Undead Legacy", refresh=True)["items"]
        undead = next(item for item in items if item["title"] == "Undead Legacy")
        self.assertEqual(undead["version"], "2.7.41")
        self.assertEqual(undead["game_version"], "v2.6")
        self.assertEqual(undead["versions"], "v2.6")
        self.assertEqual(undead["url"], MIRROR_URL)


class AzureExternalDownloadTests(unittest.TestCase):
    AZURE_URL = (
        "https://dev.azure.com/KhaineUK/f8438d9f-d741-420b-9429-f0838ed77e7f/"
        "_apis/git/repositories/80d717da-eb1e-4211-b0c2-eae2d478e749/items"
        "?path=/&versionDescriptor%5BversionOptions%5D=0"
        "&versionDescriptor%5BversionType%5D=0&versionDescriptor%5Bversion%5D=main"
        "&resolveLfs=true&%24format=zip&api-version=5.0&download=true"
    )

    def test_azure_items_link_is_direct_file_in_scraper(self):
        from backend.scraper_client import ExternalLink

        link = ExternalLink("azure", self.AZURE_URL, "Darkness Falls Mod")
        self.assertTrue(link.is_direct_file)
        self.assertEqual(link.filename, "azure-repository.zip")

    def test_azure_items_link_resolves_without_network_probe(self):
        from backend.scraper_client import ExternalLink, SevenDaysModsClient

        link = ExternalLink("azure", self.AZURE_URL, "Darkness Falls Mod")
        client = SevenDaysModsClient()
        url, size, name = client.resolve_external_url(link)
        self.assertEqual(url, self.AZURE_URL)
        self.assertEqual(size, 0)
        self.assertEqual(name, "azure-repository.zip")



class GameVersionFileDetectionTests(unittest.TestCase):

    def test_detects_game_version_after_for_and_ignores_mod_version(self):
        from backend.scraper_client import detect_file_game_versions

        detected = detect_file_game_versions(
            label="Darkness Falls V6 for V1.4 b8 (V1)"
        )
        self.assertIn("v1.4", detected)
        self.assertNotIn("v6", detected)

    def test_mod_version_is_not_mistaken_for_game_version(self):
        from backend.scraper_client import detect_file_game_versions

        detected = detect_file_game_versions(
            label="Darkness Falls V6",
            filename="DarknessFallsV6.zip",
            mod_version="6.0.0-DEV-B20",
        )
        self.assertEqual(detected, [])

    def test_detects_alpha21_even_when_author_uses_short_a21_name(self):
        from backend.scraper_client import detect_file_game_versions

        detected = detect_file_game_versions(
            label="Darkness Falls V5.1.0 for A21.2 (Alpha 21)"
        )
        self.assertEqual(detected, ["alpha21.2", "alpha21"])

    def test_matches_broad_game_filter_to_specific_patch(self):
        from backend.scraper_client import game_version_matches

        self.assertTrue(game_version_matches("alpha21", ["alpha21.2"]))
        self.assertTrue(game_version_matches("v1", ["v1.4"]))
        self.assertTrue(game_version_matches("v1.4", ["v1"]))
        self.assertFalse(game_version_matches("alpha21", ["v1.4"]))
        self.assertFalse(game_version_matches("v1.4", ["v1.3"]))

    def test_unknown_file_is_not_safe_when_mod_supports_multiple_game_versions(self):
        from backend.download_manager import DownloadManager
        from backend.scraper_client import ModFile

        class Info:
            game_versions = ["V1 Mods", "Alpha 21"]

        file = ModFile(
            id="1", media_id="", filename="DarknessFalls.zip", size=1,
            label="Darkness Falls release", file_type="main", version="6.0",
            scan_status="clean"
        )
        self.assertFalse(
            DownloadManager._file_matches_selected_game_version(
                file, "alpha21", Info()
            )
        )

    def test_unknown_file_can_use_single_declared_mod_version(self):
        from backend.download_manager import DownloadManager
        from backend.scraper_client import ModFile

        class Info:
            game_versions = ["Alpha 21"]

        file = ModFile(
            id="1", media_id="", filename="release.zip", size=1,
            label="Release", file_type="main", version="1.0",
            scan_status="clean"
        )
        self.assertTrue(
            DownloadManager._file_matches_selected_game_version(
                file, "alpha21", Info()
            )
        )


class MediaFireExternalDownloadTests(unittest.TestCase):
    MEDIAFIRE_URL = (
        "https://www.mediafire.com/file/gm61vfy91x5l3lq/"
        "Your_End_2.4.1.7_Stable_V2.6%2528b14%2529.zip/file"
    )
    DIRECT_URL = (
        "https://download1581.mediafire.com/vuix0j7isrigbatyCMemR95GQPpCcEFgywG1vs8rOxqHlHPjlWCv_xtDNSPKWN5kDmWwmQz0qi9qj-M97BZRYepMs1EAYeZ8iGjsAdszGXlruThN6_O0PVvPEIzE-qdy_Mxajj-2IGPFrbizY68JTIiIJPfsONGpnFeClAz_hWef/"
        "gm61vfy91x5l3lq/Your+End+2.4.1.7+Stable+V2.6%28b14%29.zip"
    )

    def test_mediafire_share_url_is_not_mistaken_for_direct_zip(self):
        from backend.scraper_client import ExternalLink, _is_mediafire_share_url

        link = ExternalLink("mf", self.MEDIAFIRE_URL, "Your End 2.4.1.7 Stable V2.6(b14).zip")
        self.assertTrue(_is_mediafire_share_url(self.MEDIAFIRE_URL))
        self.assertFalse(link.is_direct_file)

    def test_mediafire_html_resolves_to_temporary_download_host(self):
        from backend.scraper_client import ExternalLink, SevenDaysModsClient

        html = (
            '<html><a id="downloadButton" href="'
            + self.DIRECT_URL
            + '">Download</a></html>'
        )
        response = Mock(status_code=200, text=html)
        client = SevenDaysModsClient()
        client.session.get = Mock(return_value=response)
        link = ExternalLink("mf", self.MEDIAFIRE_URL, "Your End 2.4.1.7 Stable V2.6(b14).zip")

        url, size, name = client.resolve_external_url(link)

        self.assertEqual(url, self.DIRECT_URL)
        self.assertEqual(size, 0)
        self.assertEqual(name, "Your End 2.4.1.7 Stable V2.6(b14).zip")
        client.session.get.assert_called_once()

    def test_mediafire_version_is_taken_from_file_label_not_hoster_url(self):
        from backend.scraper_client import detect_file_game_versions

        detected = detect_file_game_versions(
            label="Your End 2.4.1.7 Stable V2.6(b14).zip",
            filename="",
            mod_version="2.6",
        )
        self.assertEqual(detected, [])

    def test_mediafire_artifact_version_can_override_same_mod_version_when_family_matches(self):
        from backend.scraper_client import detect_artifact_game_versions

        detected = detect_artifact_game_versions(
            label="Your End 2.4.1.7 Stable V2.6(b14).zip",
            filename="Your End 2.4.1.7 Stable V2.6(b14).zip",
            declared_versions=["V2 Mods"],
            mod_version="2.6",
        )
        self.assertEqual(detected, ["v2.6"])

    def test_mediafire_share_url_exposes_real_archive_filename_for_version_detection(self):
        from backend.scraper_client import ExternalLink, detect_artifact_game_versions

        link = ExternalLink(
            "mf", self.MEDIAFIRE_URL, "MediaFire", version="2.6"
        )
        self.assertEqual(
            link.filename, "Your End 2.4.1.7 Stable V2.6(b14).zip"
        )
        self.assertEqual(
            detect_artifact_game_versions(
                label=link.label,
                filename=link.filename,
                declared_versions=["V2 Mods"],
                mod_version=link.version,
            ),
            ["v2.6"],
        )

    def test_mediafire_external_matches_concrete_v2_branch(self):
        from backend.download_manager import DownloadManager
        from backend.scraper_client import ExternalLink

        class Info:
            game_versions = ["V2 Mods"]

        link = ExternalLink(
            "mf", self.MEDIAFIRE_URL, "MediaFire", version="2.6"
        )
        self.assertTrue(
            DownloadManager._external_matches_selected_game_version(
                link, "v2.6", Info()
            )
        )


    def test_mediafire_external_falls_back_to_single_declared_game_version(self):
        from backend.download_manager import DownloadManager
        from backend.scraper_client import ExternalLink

        class Info:
            game_versions = ["Alpha 21"]

        link = ExternalLink(
            "mf", self.MEDIAFIRE_URL,
            "Your End 2.4.1.7 Stable V2.6(b14).zip",
            version="2.6",
        )
        self.assertTrue(
            DownloadManager._external_matches_selected_game_version(
                link, "alpha21", Info()
            )
        )




    def test_mediafire_link_is_recovered_from_raw_mod_page_when_payload_has_no_external_links(self):
        from backend.scraper_client import SevenDaysModsClient

        # Przypadek z Your End: strona pokazuje plik MediaFire, ale payload
        # Nuxt nie wystawia go w ``external_links``. Wcześniej kończyło się to
        # na download.mod.noFiles.
        html = (
            '<script id="__NUXT_DATA__">'
            + json.dumps([{
                "id": "01KQK241ZK81CRWJ8F05P77HEG",
                "slug": "your-end",
                "title": "Your End",
                "game_versions": ["V2 Mods"],
                "mod_files": [],
                "external_links": [],
            }])
            + '</script>'
            '<a href="https://www.mediafire.com/file/gm61vfy91x5l3lq/'
            'Your_End_2.4.1.7_Stable_V2.6%2528b14%2529.zip/file">Download</a>'
        )
        response = Mock(status_code=200, text=html)
        client = SevenDaysModsClient()
        client.session.get = Mock(return_value=response)

        mod, page_url = client._fetch_mod("your-end")

        self.assertEqual(page_url, "https://7daystodiemods.com/mods/your-end")
        self.assertEqual(len(mod["external_links"]), 1)
        self.assertEqual(mod["external_links"][0]["url"], self.MEDIAFIRE_URL)
        self.assertEqual(
            mod["external_links"][0]["label"],
            "Your End 2.4.1.7 Stable V2.6(b14).zip",
        )

    def test_mediafire_fallback_is_visible_through_get_mod(self):
        from backend.scraper_client import SevenDaysModsClient

        html = (
            '<script id="__NUXT_DATA__">'
            + json.dumps([{
                "id": "mod-id",
                "slug": "your-end",
                "title": "Your End",
                "game_versions": ["V2 Mods"],
                "mod_files": [],
            }])
            + '</script>'
            '<a href="' + self.MEDIAFIRE_URL + '">MediaFire</a>'
        )
        response = Mock(status_code=200, text=html)
        client = SevenDaysModsClient()
        client.session.get = Mock(return_value=response)

        info = client.get_mod("your-end")

        self.assertEqual(len(info.external_links), 1)
        self.assertEqual(info.external_links[0].url, self.MEDIAFIRE_URL)
        self.assertFalse(info.external_links[0].is_direct_file)


if __name__ == "__main__":
    unittest.main()
