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


if __name__ == "__main__":
    unittest.main()
