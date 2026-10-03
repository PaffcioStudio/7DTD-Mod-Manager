from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend import library_ops


def _make_mod(folder: Path, name: str) -> Path:
    root = folder / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "ModInfo.xml").write_text(
        "<xml><Name value=\"%s\"/><DisplayName value=\"%s\"/></xml>" % (name, name),
        encoding="utf-8",
    )
    (root / "Config.xml").write_text("x", encoding="utf-8")
    return root


class FolderImportDiscovery(unittest.TestCase):
    def test_detects_root_mod_and_nested_modpack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_mod(root / "Mods", "Alpha")
            _make_mod(root / "Mods", "Beta")
            self.assertEqual(
                [p.name for p in library_ops.discover_mod_folders(root / "Mods")],
                ["Alpha", "Beta"],
            )

            single = _make_mod(root / "SingleParent", "Gamma")
            self.assertEqual(library_ops.discover_mod_folders(single), [single.resolve()])

    def test_does_not_descend_inside_a_found_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mod = _make_mod(root, "Parent")
            _make_mod(mod, "NestedShouldNotBeSeparate")
            found = library_ops.discover_mod_folders(root)
            self.assertEqual([p.name for p in found], ["Parent"])

    def test_skips_common_build_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_mod(root / "node_modules", "Nope")
            _make_mod(root / "build", "AlsoNope")
            _make_mod(root / "Mods", "Yes")
            found = library_ops.discover_mod_folders(root)
            self.assertEqual([p.name for p in found], ["Yes"])


if __name__ == "__main__":
    unittest.main()
