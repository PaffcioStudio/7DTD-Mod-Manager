"""Regression tests for standalone prefab ZIPs such as 'the shack'."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from backend.modpack_downloader import _extract_zip, mods_root_has_valid_mods
from backend.prefab_archives import prepare_loose_prefab_mod


def _zip_extract(tmp_path: Path, entries: dict[str, bytes]) -> Path:
    archive = tmp_path / "the-shack.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for name, data in entries.items():
            zipf.writestr(name, data)
    extracted = tmp_path / "extracted"
    _extract_zip(archive, extracted)
    return extracted


def test_loose_poi_zip_gets_installed_as_standard_modlet(tmp_path):
    extracted = _zip_extract(tmp_path, {
        "the shack/shack.xml": b"<prefab/>",
        "the shack/shack.tts": b"\x00ttsprefabbytes",
        "the shack/shack.blocks.nim": b"nim-data",
        "the shack/shack.mesh": b"mesh",
        "the shack/README.txt": b"manual installation only",
    })
    root = prepare_loose_prefab_mod(extracted, slug="the-shack", title="the shack",
                                    author="cornishtank", version="1")
    assert root is not None
    assert mods_root_has_valid_mods(root)
    mod = root / "MM_Prefab_the-shack"
    assert (mod / "Prefabs/POIs/shack.xml").read_bytes() == b"<prefab/>"
    assert (mod / "Prefabs/POIs/shack.tts").read_bytes() == b"\x00ttsprefabbytes"
    assert (mod / "Prefabs/POIs/shack.blocks.nim").is_file()
    assert not (mod / "Prefabs/POIs/README.txt").exists()
    assert (extracted / "the shack/shack.tts").exists()  # archive remains intact
    xml = ET.parse(mod / "ModInfo.xml").getroot()
    assert xml.tag == "xml"
    assert xml.find("Name").get("value") == "MM_Prefab_the-shack"
    assert xml.find("Version").get("value") == "1.0"
    assert xml.find("Author").get("value") == "cornishtank"


def test_nested_pois_keep_relative_filenames_and_directories(tmp_path):
    extracted = _zip_extract(tmp_path, {
        "export/Prefabs/POIs/prefab1.xml": b"<prefab/>",
        "export/Prefabs/POIs/prefab1.tts": b"data",
        "export/Prefabs/POIs/VanillaTagOverrides/prefab2.xml": b"<prefab/>",
        "export/Prefabs/POIs/VanillaTagOverrides/prefab2.tts": b"data2",
    })
    root = prepare_loose_prefab_mod(extracted, slug="test-poi", title="Test POI")
    assert root is not None
    mod = root / "MM_Prefab_test-poi" / "Prefabs/POIs"
    assert (mod / "prefab1.tts").read_bytes() == b"data"
    assert (mod / "VanillaTagOverrides/prefab2.xml").read_bytes() == b"<prefab/>"


def test_nested_single_wrapper_is_removed(tmp_path):
    extracted = _zip_extract(tmp_path, {
        "wrapper/a/b/poix.xml": b"<prefab/>",
        "wrapper/a/b/poix.tts": b"data",
    })
    root = prepare_loose_prefab_mod(extracted, slug="poix", title="POI X")
    assert root is not None
    assert (root / "MM_Prefab_poix/Prefabs/POIs/poix.tts").exists()


def test_xml_only_archive_and_unrelated_zip_are_not_falsely_installed(tmp_path):
    extracted = _zip_extract(tmp_path, {
        "settings.xml": b"<root/>",
        "readme.txt": b"Nothing installable here",
    })
    assert prepare_loose_prefab_mod(extracted, slug="anything", title="Anything") is None


def test_existing_modlet_is_never_synthesized_or_replaced(tmp_path):
    extracted = _zip_extract(tmp_path, {
        "MyMod/ModInfo.xml": b"<xml/>",
        "MyMod/Prefabs/POIs/test.xml": b"<prefab/>",
        "MyMod/Prefabs/POIs/test.tts": b"data",
    })
    assert prepare_loose_prefab_mod(extracted, slug="anything", title="Anything") is None


def test_generated_modinfo_escapes_untrusted_catalog_fields(tmp_path):
    extracted = _zip_extract(tmp_path, {"p.xml": b"<p/>", "p.tts": b"data"})
    root = prepare_loose_prefab_mod(extracted, slug="a/../../bad", title="<The & Best>",
                                    author="T & S", version="release")
    assert root is not None
    folder = next(root.iterdir())
    assert folder.parent == root
    xml = ET.parse(folder / "ModInfo.xml").getroot()
    assert xml.find("DisplayName").get("value") == "<The & Best>"
    assert xml.find("Author").get("value") == "T & S"
    assert xml.find("Version").get("value") == "1.0"


def test_prepared_poi_installs_and_deduplicates_in_library(tmp_path):
    from unittest.mock import patch
    from backend import library_ops

    extracted = _zip_extract(tmp_path, {
        "TheShack/POI.tts": b"prefab-data",
        "TheShack/POI.xml": b"<prefab/>",
    })
    mod_root = prepare_loose_prefab_mod(extracted, slug="the-shack", title="the shack")
    with patch.object(Path, "home", return_value=tmp_path):
        report = library_ops.install_modpack_to_library(mod_root, source="web:the-shack",
                                                        enable=False, game_version="public")
        assert report.errors == []
        assert len(report.imported) == 1
        entry = report.imported[0]
        assert entry.game_version == "public"
        assert entry.display_name == "the shack"
        repeated = library_ops.install_modpack_to_library(mod_root, source="web:the-shack",
                                                          enable=False, game_version="public")
        assert repeated.already_present
        assert not repeated.imported
