import json
import unittest
from pathlib import Path

from backend.discover import MANIFEST_DIR, fetch_local_catalog


class LocalCatalogEnglishTests(unittest.TestCase):
    def test_every_overhaul_has_english_description(self):
        data = json.loads((MANIFEST_DIR / "manifest_overhaul.json")
                          .read_text(encoding="utf-8"))
        for entry in data["overhauls"]:
            self.assertTrue(str(entry.get("description_en", "")).strip(),
                            f"missing description_en: {entry.get('name')}")

    def test_catalog_exposes_both_languages(self):
        items = fetch_local_catalog()["items"]
        self.assertTrue(items)
        for item in items:
            self.assertTrue(item["summary"])
            self.assertTrue(item["summaryEn"])

    def test_search_matches_english_description(self):
        titles = [i["title"] for i in fetch_local_catalog("virtual reality")["items"]]
        self.assertIn("7DVR", titles)


if __name__ == "__main__":
    unittest.main()
