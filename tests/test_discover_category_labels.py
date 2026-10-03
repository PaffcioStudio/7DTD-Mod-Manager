import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / "qml" / "pages" / "DiscoverPage.qml").read_text(encoding="utf-8")


class DiscoverCategoryLabelTests(unittest.TestCase):
    def test_dropdown_keeps_original_server_labels(self):
        body = PAGE[PAGE.index("function localizeCatalogOptions"):PAGE.index("function refreshI18nOptions")]
        self.assertNotIn("category.", body)
        self.assertIn("opt.label", body)
        self.assertIn("allKey", body)


if __name__ == "__main__":
    unittest.main()
