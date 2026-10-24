"""ZIP z plikami moda luzem musi instalować się jak pojedynczy mod / overhaul."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from backend import library_ops
from backend.modpack_downloader import (
    _extract_zip,
    mods_root_has_valid_mods,
    prepare_mods_root_in_extracted,
)


ROOT_MODINFO = b'''<?xml version="1.0" encoding="UTF-8"?>
<xml>
  <Name value="ExpandedEquipmentOverhaul"/>
  <DisplayName value="Expanded Equipment &amp; Modification Overhaul"/>
  <Version value="0.27.1"/>
  <SkipWithAntiCheat value="true"/>
</xml>'''


def _extract(tmp_path: Path, files: dict[str, bytes]) -> Path:
    archive = tmp_path / "example-mod.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    target = tmp_path / "extracted"
    _extract_zip(archive, target)
    return target


def test_root_modinfo_is_wrapped_without_losing_any_mod_files(tmp_path):
    files = {
        "ModInfo.xml": ROOT_MODINFO,
        "ExpandedEquipmentOverhaul.dll": b"DLL-CONTENT",
        "Settings.xml": b"<settings />",
        "Config/items.xml": b"<configs />",
        "Resources/custom.unity3d": b"resource",
        "UIAtlases/ui.png": b"png",
        "ThirdParty/helper.dll": b"helper",
        "Prefabs/POIs/test.tts": b"poi",
        "READ-ME-FIRST.txt": b"manual",
    }
    extracted = _extract(tmp_path, files)
    mods_root = prepare_mods_root_in_extracted(extracted, fallback_name="cod-zombies-mod")
    assert mods_root_has_valid_mods(mods_root)
    mod = mods_root / "ExpandedEquipmentOverhaul"
    assert {p.relative_to(mod).as_posix(): p.read_bytes() for p in mod.rglob("*") if p.is_file()} == files

    # Ścieżka używana przez instalację overhaul: przeniesienie do Mods/ instancji.
    instance_mods = tmp_path / "instance" / "Mods"
    instance_mods.mkdir(parents=True)
    shutil.move(str(mod), str(instance_mods / mod.name))
    assert (instance_mods / "ExpandedEquipmentOverhaul" / "ModInfo.xml").read_bytes() == ROOT_MODINFO
    assert (instance_mods / "ExpandedEquipmentOverhaul" / "ThirdParty/helper.dll").read_bytes() == b"helper"


def test_root_modinfo_wins_over_nested_mods_directory_that_is_part_of_mod(tmp_path):
    extracted = _extract(tmp_path, {
        "ModInfo.xml": ROOT_MODINFO,
        "Mods/extra.txt": b"this is content within the single mod",
        "Config/blocks.xml": b"<configs/>",
    })
    mods_root = prepare_mods_root_in_extracted(extracted)
    assert (mods_root / "ExpandedEquipmentOverhaul" / "Mods/extra.txt").read_bytes() == b"this is content within the single mod"


def test_normal_mods_zip_and_mod_folder_zip_keep_original_layout(tmp_path):
    for prefix in ("Mods/MyMod", "MyMod", "wrapper/Mods/MyMod"):
        subdir = tmp_path / prefix.replace("/", "_")
        subdir.mkdir()
        extracted = _extract(subdir, {f"{prefix}/ModInfo.xml": b'<xml><Name value="MyMod"/></xml>'})
        mods_root = prepare_mods_root_in_extracted(extracted)
        assert mods_root_has_valid_mods(mods_root)
        assert (extracted / f"{prefix}/ModInfo.xml").exists()
        assert not list(extracted.glob(".mm-single-mod-*"))


def test_root_mod_without_name_falls_back_to_sanitized_slug(tmp_path):
    extracted = _extract(tmp_path, {"ModInfo.xml": b"<xml/>", "Config/a.xml": b"yes"})
    mods_root = prepare_mods_root_in_extracted(extracted, fallback_name="the/mod? name")
    assert (mods_root / "the_mod_name" / "Config/a.xml").read_bytes() == b"yes"


def test_hostile_name_cannot_escape_extraction_directory(tmp_path):
    extracted = _extract(tmp_path, {
        "ModInfo.xml": b'<xml><Name value="../../outside\\mod" /></xml>',
        "Config/a.xml": b"safe",
    })
    mods_root = prepare_mods_root_in_extracted(extracted)
    [mod_dir] = [path for path in mods_root.iterdir() if path.is_dir()]
    assert mod_dir.parent == mods_root
    assert (mod_dir / "Config/a.xml").read_bytes() == b"safe"
    assert not (tmp_path / "outside").exists()


def test_arbitrary_zip_without_modinfo_is_not_a_mod(tmp_path):
    extracted = _extract(tmp_path, {"Config/a.xml": b"<configs/>", "readme.txt": b"hello"})
    assert prepare_mods_root_in_extracted(extracted) is None


def test_root_mod_from_web_can_be_imported_to_normal_library(tmp_path, monkeypatch):
    extracted = _extract(tmp_path, {"ModInfo.xml": ROOT_MODINFO, "Config/blocks.xml": b"<configs/>"})
    mods_root = prepare_mods_root_in_extracted(extracted)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    report = library_ops.install_modpack_to_library(mods_root, source="web:test", enable=False)
    assert report.errors == []
    assert len(report.imported) == 1
    assert (report.imported[0].path / "Config/blocks.xml").read_bytes() == b"<configs/>"


def test_both_download_paths_use_root_mod_normalization():
    manager_source = (Path(__file__).resolve().parents[1] / "src/backend/download_manager.py").read_text()
    assert "prepare_mods_root_in_extracted(\n                    temp_dir, fallback_name=info.slug)" in manager_source
    assert "prepare_mods_root_in_extracted(\n                    extracted, fallback_name=item.title)" in manager_source
