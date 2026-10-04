"""Undead Legacy dostarcza obok Mods/ loader BepInEx (winhttp.dll + Doorstop).
Bez wdrożenia go do katalogu gry i WINEDLLOVERRIDES=winhttp=n,b kod overhaula
w ogóle się nie ładuje (Proton)."""
import json
from pathlib import Path

from backend import bepinex_loader as bl

ROOT = Path(__file__).resolve().parents[1]

INI = (
    "[General]\nenabled = true\n"
    "target_assembly=BepInEx\\core\\BepInEx.Preloader.dll\n\n"
    "[UnityMono]\ndllSearchPathOverride=BepInEx/core\n\n"
    "[MultiFolderLoader]\nbaseDir = Mods/"
)


def _make_pack(root: Path) -> Path:
    """Układ paczki Undead Legacy (wszystko, co zawiera archiwum)."""
    root.mkdir(parents=True)
    (root / "winhttp.dll").write_bytes(b"MZ-doorstop")
    (root / "doorstop_config.ini").write_text(INI, encoding="utf-8")
    (root / "run_bepinex.sh").write_text("#!/bin/sh\n")
    (root / "run_bepinex_server.sh").write_text("#!/bin/sh\n")
    (root / "README.md").write_text("terms")
    (root / "LICENSE").write_text("license")
    (root / "doorstop_libs").mkdir()
    for lib in ("libdoorstop.dylib", "libdoorstop_x64.so", "libdoorstop_x84.so"):
        (root / "doorstop_libs" / lib).write_bytes(b"lib")
    (root / "BepInEx/core").mkdir(parents=True)
    (root / "BepInEx/core/BepInEx.Preloader.dll").write_bytes(b"preloader")
    (root / "BepInEx/patchers").mkdir()
    (root / "BepInEx/patchers/BepInEx.MultiFolderLoader.dll").write_bytes(b"mfl")
    (root / "BepInEx/config").mkdir()
    (root / "BepInEx/config/BepInEx.cfg").write_text("[Caching]\n")
    (root / "Mods/UndeadLegacy").mkdir(parents=True)
    (root / "Mods/UndeadLegacy/ModInfo.xml").write_text("<xml/>")
    return root


def test_find_loader_root_next_to_mods_at_root_and_in_github_subfolder(tmp_path):
    flat = _make_pack(tmp_path / "flat")
    assert bl.find_loader_root(flat, flat / "Mods") == flat

    wrapped = tmp_path / "wrapped"
    pack = _make_pack(wrapped / "UndeadLegacyExperimentalPart1-main")
    assert bl.find_loader_root(wrapped, pack / "Mods") == pack
    assert bl.find_loader_root(wrapped, None) == pack


def test_find_loader_root_is_none_for_plain_modpack(tmp_path):
    (tmp_path / "Mods/Some").mkdir(parents=True)
    (tmp_path / "Mods/Some/ModInfo.xml").write_text("<xml/>")
    (tmp_path / "winhttp.dll").write_bytes(b"x")  # sam DLL bez ini/BepInEx to za mało
    assert bl.find_loader_root(tmp_path, tmp_path / "Mods") is None


def test_stash_copies_only_proton_files_not_native_linux_or_macos(tmp_path):
    pack = _make_pack(tmp_path / "pack")
    data_dir = tmp_path / "instances/ul"
    target = bl.stash_loader(pack, data_dir)
    assert target == data_dir / ".modmanager-loader"
    names = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    assert names == {
        "winhttp.dll", "doorstop_config.ini",
        "BepInEx/core/BepInEx.Preloader.dll",
        "BepInEx/patchers/BepInEx.MultiFolderLoader.dll",
        "BepInEx/config/BepInEx.cfg",
    }
    assert bl.has_loader(data_dir)
    assert not bl.has_loader(tmp_path / "other")
    assert not bl.has_loader(None)


def test_rewrite_base_dir_keeps_rest_of_file():
    out = bl.rewrite_base_dir(INI, "Z:/home/u/.7dtd_modmanager/instances/ul/Mods/")
    assert "baseDir = Z:/home/u/.7dtd_modmanager/instances/ul/Mods/\n" in out
    assert "target_assembly=BepInEx\\core\\BepInEx.Preloader.dll" in out
    assert "dllSearchPathOverride=BepInEx/core" in out
    assert out.count("baseDir") == 1
    # brak sekcji -> dopisana
    assert "[MultiFolderLoader]\nbaseDir = X/" in bl.rewrite_base_dir("[General]\nenabled = true\n", "X/")
    # klucz w innej sekcji nie jest ruszany
    other = bl.rewrite_base_dir("[Other]\nbaseDir = keep\n[MultiFolderLoader]\n", "X/")
    assert "baseDir = keep" in other and "baseDir = X/" in other


def test_sync_deploys_points_baseDir_to_instance_mods_and_cleans_up(tmp_path):
    pack = _make_pack(tmp_path / "pack")
    data_dir = tmp_path / "instances/ul"
    (data_dir / "Mods").mkdir(parents=True)
    bl.stash_loader(pack, data_dir)
    game = tmp_path / "game-versions/v2.6"
    game.mkdir(parents=True)
    (game / "7DaysToDie.exe").write_bytes(b"exe")

    assert bl.sync_game_dir(game, data_dir) is True
    assert (game / "winhttp.dll").read_bytes() == b"MZ-doorstop"
    assert (game / "BepInEx/core/BepInEx.Preloader.dll").is_file()
    ini = (game / "doorstop_config.ini").read_text()
    assert f"baseDir = Z:{(data_dir / 'Mods').as_posix()}/" in ini
    manifest = json.loads((game / ".modmanager-loader.json").read_text())
    assert "winhttp.dll" in manifest["files"]
    # powtórny start nie dubluje ani nie psuje
    assert bl.sync_game_dir(game, data_dir) is True

    # instancja BEZ loadera na tej samej wersji gry -> katalog gry wraca do czystego
    vanilla = tmp_path / "instances/vanilla"
    vanilla.mkdir(parents=True)
    assert bl.sync_game_dir(game, vanilla) is False
    assert not (game / "winhttp.dll").exists()
    assert not (game / "doorstop_config.ini").exists()
    assert not (game / "BepInEx/core").exists()
    assert not (game / ".modmanager-loader.json").exists()
    assert (game / "7DaysToDie.exe").read_bytes() == b"exe"  # pliki gry nietknięte
    assert bl.sync_game_dir(game, None) is False  # instancja domyślna


def test_sync_backs_up_foreign_file_and_restores_it(tmp_path):
    pack = _make_pack(tmp_path / "pack")
    data_dir = tmp_path / "instances/ul"
    bl.stash_loader(pack, data_dir)
    game = tmp_path / "game"
    game.mkdir()
    (game / "winhttp.dll").write_bytes(b"someone-elses")
    bl.sync_game_dir(game, data_dir)
    assert (game / "winhttp.dll").read_bytes() == b"MZ-doorstop"
    assert (game / "winhttp.dll.modmanager-backup").read_bytes() == b"someone-elses"
    bl.sync_game_dir(game, None)
    assert (game / "winhttp.dll").read_bytes() == b"someone-elses"
    assert not (game / "winhttp.dll.modmanager-backup").exists()


def test_cleanup_ignores_manifest_paths_escaping_game_dir(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    (game / ".modmanager-loader.json").write_text(json.dumps({"files": ["../victim.txt"]}))
    bl.remove_deployed(game)
    assert victim.read_text() == "keep"


def test_apply_dll_override_appends_without_losing_existing():
    env = {}
    bl.apply_dll_override(env)
    assert env["WINEDLLOVERRIDES"] == "winhttp=n,b"
    env = {"WINEDLLOVERRIDES": "mscoree=d;"}
    bl.apply_dll_override(env)
    bl.apply_dll_override(env)
    assert env["WINEDLLOVERRIDES"] == "mscoree=d;winhttp=n,b"


def test_launch_and_install_are_wired_to_loader():
    gp = (ROOT / "src/backend/game_process.py").read_text(encoding="utf-8")
    assert "bepinex_loader.sync_game_dir(game_dir, user_data_folder)" in gp
    assert "bepinex_loader.apply_dll_override(env)" in gp
    assert gp.index("sync_game_dir(game_dir") < gp.index("command = [str(proton)")
    dm = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert dm.count("loader_root=bepinex_loader.find_loader_root(") == 2
    assert "bepinex_loader.stash_loader(loader_root, instance.data_dir)" in dm
