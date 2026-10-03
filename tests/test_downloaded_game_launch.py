import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend import game_process


class TestDownloadedGameLaunch(unittest.TestCase):
    def test_launch_builds_proton_command_and_env(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / ".7dtd_modmanager"
            game_dir = root / "game-versions" / "alpha12.5"
            game_dir.mkdir(parents=True)
            (game_dir / "7DaysToDie.exe").write_bytes(b"MZ")
            (game_dir / "steam_appid.txt").write_text("251570", encoding="utf-8")

            proton = Path(td) / "Proton 10" / "proton"
            proton.parent.mkdir(parents=True)
            proton.write_text("#!/bin/sh\n", encoding="utf-8")
            proton.chmod(0o755)
            steam_root = Path(td) / "SteamLibrary"
            steam_root.mkdir()
            steam_client_root = Path(td) / "SteamClient"
            steam_client_root.mkdir()
            (steam_client_root / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            steam_bin = Path(td) / "steam"
            steam_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            steam_bin.chmod(0o755)

            captured = {}

            class Result:
                returncode = 0
                stdout = str(steam_bin) + "\n"

            def fake_run(args, **kwargs):
                if args[0] == "which":
                    return Result()
                if args[:2] == ["pgrep", "-x"]:
                    return Result()
                raise AssertionError(args)

            class DummyLog:
                def write(self, *_a, **_k): pass
                def close(self): pass
                def __enter__(self): return self
                def __exit__(self, *_a): pass

            def fake_open(*_a, **_k): return DummyLog()

            def fake_popen(command, **kwargs):
                captured["command"] = command
                captured["kwargs"] = kwargs
                return object()

            with patch.object(game_process, "_manager_data_root", return_value=root), \
                 patch.object(game_process, "find_proton", return_value=(proton, steam_root)), \
                 patch.object(game_process, "_find_steam_client_root", return_value=steam_client_root), \
                 patch.object(game_process.subprocess, "run", side_effect=fake_run), \
                 patch.object(game_process.subprocess, "Popen", side_effect=fake_popen), \
                 patch.object(game_process, "open", side_effect=fake_open):
                ok = game_process._launch_downloaded_windows_version(
                    "alpha12.5", str(root / "instance-data"), noeac=True,
                    skip_intro=True,
                )

            self.assertTrue(ok)
            self.assertEqual(captured["command"][0], str(proton))
            self.assertEqual(captured["command"][1], "run")
            self.assertTrue(captured["command"][2].endswith("7DaysToDie.exe"))
            self.assertIn(
                f'-UserDataFolder=Z:{root / "instance-data"}', captured["command"]
            )
            self.assertIn("-skipintro", captured["command"])
            env = captured["kwargs"]["env"]
            self.assertEqual(env["STEAM_COMPAT_CLIENT_INSTALL_PATH"], str(steam_client_root))
            self.assertEqual(env["STEAM_COMPAT_LIBRARY_PATHS"], str(steam_root))
            self.assertEqual(env["STEAM_COMPAT_INSTALL_PATH"], str(game_dir))
            self.assertEqual(env["STEAM_COMPAT_APP_ID"], "251570")
            self.assertEqual(env["SteamAppId"], "251570")
            self.assertEqual(env["SteamGameId"], "251570")
            self.assertEqual(env["WINEPREFIX"], str(root / "compatdata" / "alpha12.5" / "pfx"))
            self.assertEqual(env["STEAM_EXTRA_COMPAT_TOOLS_PATHS"], str(proton.parent))
            self.assertEqual(captured["kwargs"]["cwd"], str(game_dir))

    def test_imports_re_for_proton_detection(self):
        # Regression test for NameError in _steam_client_roots()/find_proton().
        self.assertTrue(game_process.re.search(r"proton", "Proton Experimental", game_process.re.IGNORECASE))

    def test_client_root_not_confused_with_external_library(self):
        with tempfile.TemporaryDirectory() as td:
            lib = Path(td) / "SteamLibrary"
            lib.mkdir()
            (lib / "steamapps").mkdir()
            client = Path(td) / "SteamClient"
            client.mkdir()
            (client / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(game_process.Path, "home", return_value=Path(td) / "home"):
                    home = Path(td) / "home"
                    (home / ".steam").mkdir(parents=True)
                    (home / ".steam" / "root").symlink_to(client, target_is_directory=True)
                    self.assertEqual(
                        game_process._find_steam_client_root(), client.resolve(strict=False)
                    )

    def test_old_build_user_data_locations_are_mapped_to_instance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / ".7dtd_modmanager"
            compat = root / "compatdata" / "alpha12.5"
            instance = root / "instances" / "12-5"
            instance.mkdir(parents=True)
            (instance / "Presets").mkdir()
            legacy = compat / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "7DaysToDie"
            legacy.mkdir(parents=True)
            (legacy / "Saves").mkdir()
            (legacy / "Saves" / "old.txt").write_text("old", encoding="utf-8")

            game_process._prepare_instance_user_data_compat(instance, compat)

            self.assertTrue(legacy.is_symlink())
            self.assertEqual(legacy.resolve(strict=False), instance.resolve(strict=False))
            self.assertEqual(
                (instance / "Saves" / "old.txt").read_text(encoding="utf-8"),
                "old",
            )
            for legacy_path in (
                compat / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "7 Days To Die",
                compat / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "7 Days To Die",
            ):
                self.assertTrue(legacy_path.is_symlink())
                self.assertEqual(legacy_path.resolve(strict=False), instance.resolve(strict=False))

    def test_missing_proton_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / ".7dtd_modmanager" / "game-versions" / "alpha12.5"
            root.mkdir(parents=True)
            (root / "7DaysToDie.exe").write_bytes(b"MZ")
            with patch.object(game_process, "_manager_data_root", return_value=Path(td) / ".7dtd_modmanager"), \
                 patch.object(game_process, "find_proton", return_value=(None, None)):
                self.assertFalse(game_process._launch_downloaded_windows_version("alpha12.5"))


def test_main_has_backend_boot_stage_logging():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "src" / "main.py").read_text(encoding="utf-8")
    assert 'logger.info("BOOT: %s", name)' in source
    assert 'logger.info("BOOT: %s OK", name)' in source


if __name__ == "__main__":
    unittest.main()
