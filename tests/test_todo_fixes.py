"""Testy regresyjne poprawek z przeglądu kodu (download_manager, library_ops,
migration, game_process, profile_manager, modinfo).

Każdy test działa na izolowanym HOME (tymczasowy katalog), więc nie dotyka
prawdziwej Biblioteki ani rejestru instancji użytkownika.
"""
from pathlib import Path
import os
import json
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

# pozwala odpalić plik wprost (python3 tests/test_todo_fixes.py) bez PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend import library, library_ops
from backend import instances as inst_mod
from backend.fileops import OperationCancelled
from backend.modinfo import find_modinfo
from services import filesystem_service as fs


def _make_mod(parent: Path, name: str, version: str = "1.0",
              modinfo_name: str = "ModInfo.xml", payload: str = "a") -> Path:
    folder = parent / name
    folder.mkdir(parents=True)
    (folder / modinfo_name).write_text(
        f'<xml><Name value="{name}"/><Version value="{version}"/></xml>',
        encoding="utf-8")
    (folder / "Config").mkdir()
    (folder / "Config" / "blocks.xml").write_text(payload, encoding="utf-8")
    return folder


class IsolatedHome(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)
        self.src = self.home / "src"
        self.src.mkdir()


class UpdateCancelRestoresOldMod(IsolatedHome):
    def test_cancel_after_swap_restores_original(self):
        """Anulowanie tuż po target.rename(old) nie może skasować moda."""
        mod = _make_mod(self.src, "ModA", payload="original")
        entry = library_ops.import_mod_to_library(mod)
        target = entry.path
        self.assertEqual((target / "Config" / "blocks.xml").read_text(), "original")

        new_src = _make_mod(self.home / "new", "ModA", version="2.0", payload="changed")

        real_rename = Path.rename

        def cancelling_rename(self_path, dest):
            result = real_rename(self_path, dest)
            # po wstawieniu stagingu pod target: symuluj anulowanie
            if Path(dest) == target:
                raise OperationCancelled("cancel")
            return result

        with patch.object(Path, "rename", cancelling_rename):
            with self.assertRaises(OperationCancelled):
                library_ops.update_entry_content(entry.library_id, new_src)

        self.assertTrue(target.is_dir(), "oryginalny mod zniknął z Biblioteki")
        self.assertEqual((target / "Config" / "blocks.xml").read_text(), "original")
        leftovers = [p.name for p in target.parent.iterdir() if p.name.startswith(".update-")]
        self.assertEqual(leftovers, [])

    def test_cancel_during_copy_keeps_original(self):
        mod = _make_mod(self.src, "ModB", payload="orig")
        entry = library_ops.import_mod_to_library(mod)
        new_src = _make_mod(self.home / "new", "ModB", version="2.0", payload="x")
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(OperationCancelled):
            library_ops.update_entry_content(
                entry.library_id, new_src, cancel_event=cancel)
        self.assertEqual((entry.path / "Config" / "blocks.xml").read_text(), "orig")

    def test_successful_update_still_works(self):
        mod = _make_mod(self.src, "ModC", payload="v1")
        entry = library_ops.import_mod_to_library(mod)
        new_src = _make_mod(self.home / "new", "ModC", version="2.0", payload="v2")
        updated, changed = library_ops.update_entry_content(entry.library_id, new_src)
        self.assertTrue(changed)
        self.assertEqual((updated.path / "Config" / "blocks.xml").read_text(), "v2")



class ModinfoCaseInsensitive(IsolatedHome):
    def test_lowercase_modinfo_is_found_everywhere(self):
        from backend import mod_thumbs, modpack_downloader
        mods_root = self.home / "x" / "Mods"
        _make_mod(mods_root, "LowerMod", modinfo_name="modinfo.xml")
        self.assertIsNotNone(find_modinfo(mods_root / "LowerMod"))
        self.assertTrue(modpack_downloader.mods_root_has_valid_mods(mods_root))
        self.assertEqual(
            modpack_downloader.find_mods_root_in_extracted(mods_root.parent), mods_root)
        # sam korzeń jako sztuczny Mods-root (mod bezpośrednio w korzeniu)
        self.assertEqual(
            modpack_downloader.find_mods_root_in_extracted(mods_root), mods_root)
        # local_banner nie może odpaść na małych literach (brak Banner -> None)
        self.assertIsNone(mod_thumbs.local_banner(mods_root / "LowerMod"))


class GameProcessNative(unittest.TestCase):
    def _fake_proc(self, tmp: Path, pid: str, comm: str, exe_target: str, cmdline: list):
        d = tmp / pid
        d.mkdir()
        (d / "comm").write_text(comm + "\n")
        (d / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmdline) + b"\0")
        (d / "stat").write_text(
            f"{pid} ({comm}) S 1 1 1 0 -1 0 0 0 0 0 1 1 0 0 20 0 1 0 100 1000 10 0")
        (d / "statm").write_text("100 10 0 0 0 0 0")
        try:
            os.symlink(exe_target, d / "exe")
        except OSError:
            pass

    def test_native_detected_via_exe_when_comm_truncated(self):
        from backend import game_process
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            # comm ucięte do 15 znaków; exe wskazuje na natywną binarkę
            self._fake_proc(tmp, "4242", "7DaysToDie.x86_",
                            "/home/u/Steam/steamapps/common/7 Days To Die/7DaysToDie.x86_64",
                            ["./7DaysToDie.x86_64"])
            # proces wine: exe = preloader, gra tylko w argumentach
            self._fake_proc(tmp, "4343", "7DaysToDie.exe",
                            "/usr/bin/wine64-preloader",
                            ["Z:\\games\\7 Days To Die\\7DaysToDie.exe"])
            # niezwiązany proces
            self._fake_proc(tmp, "4444", "bash", "/usr/bin/bash", ["bash"])
            with patch.object(game_process, "_PROC", tmp), \
                 patch.object(game_process, "_OWN_PID", -1):
                found = {p.pid: p.matched_by for p in game_process.find_game_processes()}
        self.assertEqual(found.get(4242), "native")
        self.assertNotIn(4444, found)
        # proces wine z comm == nazwa .exe nadal łapany (jak dotąd)
        self.assertIn(4343, found)


class MultiModInstance(IsolatedHome):
    def _manager(self):
        """Wołamy metodę bez tworzenia całego DownloadManagera (Qt)."""
        from backend import download_manager
        return download_manager.DownloadManager._install_multi_as_instance

    def test_creates_registered_instance_and_enables_already_present(self):
        func = self._manager()
        pack = self.home / "pack"
        m1 = _make_mod(pack, "PackModOne", payload="1")
        m2 = _make_mod(pack, "PackModTwo", payload="2")
        # m2 jest już w Bibliotece (identyczna zawartość) -> already_present
        pre = library_ops.import_mod_to_library(m2)

        count = func(None, "my-pack", "My Pack", [str(m1), str(m2)], threading.Event())

        self.assertEqual(count, 2, "powinny być włączone OBA mody (nowy + już obecny)")
        registry = inst_mod.load_instances()
        created = [i for i in registry if i.name == "My Pack"]
        self.assertEqual(len(created), 1, "instancja musi być zapisana w rejestrze")
        instance = created[0]
        self.assertFalse(instance.is_default)
        self.assertEqual(instance.description, "Zestaw my-pack z 7daystodiemods.com")

        state = library.load_activation_state()
        enabled = state.enabled_for_instance(instance.instance_id)
        self.assertIn(pre.library_id, enabled)
        self.assertEqual(len(enabled), 2)
        mods_dir = instance.mods_dir
        self.assertTrue(mods_dir.is_dir())
        self.assertEqual(sorted(p.name for p in mods_dir.iterdir()
                                if not p.name.startswith(".")),
                         ["PackModOne", "PackModTwo"])


class InstanceModStatesNoDuplicates(IsolatedHome):
    def test_built_mod_is_listed_once_and_description_saved(self):
        from backend import profile_manager
        m1 = _make_mod(self.src, "OnlyMod")
        entry = library_ops.import_mod_to_library(m1)
        instance = inst_mod.create_instance(
            "Test", str(inst_mod.suggest_data_dir_for_name("Test")), description="stary")
        inst_mod.save_instances(inst_mod.load_instances() + [instance])
        state = library.load_activation_state()
        state.set_instance_inclusion(entry.library_id, instance.instance_id, True)
        library.save_activation_state(state)
        inst_mod.build_mods_for_instance(
            instance, library.load_library_entries(), library.load_activation_state())

        # lekki stub zamiast pełnego ProfileManager (Qt/ModManager)
        pm = profile_manager.ProfileManager.__new__(profile_manager.ProfileManager)
        pm._instances = inst_mod.load_instances()

        class _Mods:
            def all_mods(self_inner):
                class M:
                    id = entry.library_id
                    name = "OnlyMod"
                    version = "1.0"
                return [M()]
        pm._mods = _Mods()
        pm._instance = lambda iid: next((i for i in pm._instances if i.instance_id == iid), None)

        rows = profile_manager.ProfileManager.instanceModStates(pm, instance.instance_id)
        ids = [r["modId"] for r in rows]
        self.assertEqual(ids.count(entry.library_id), 1, f"duplikat na liście: {rows}")


class GameVersionsAuth(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    def test_qr_refresh_clears_previous_frame_and_collects_new_one(self):
        from PySide6.QtCore import QCoreApplication
        from backend.game_versions import GameVersionsManager

        app = QCoreApplication.instance() or QCoreApplication([])
        manager = GameVersionsManager()
        events = []
        manager.qrChanged.connect(lambda: events.append(manager.qrText))

        manager._consume_line("Use the Steam Mobile App to sign in with this QR code:")
        manager._consume_line("OLD-QR ███")
        self.assertIn("OLD-QR", manager.qrText)

        manager._consume_line("The QR code has changed:")
        self.assertEqual(manager.qrText, "")
        manager._consume_line("Use the Steam Mobile App to sign in with this QR code:")
        manager._consume_line("NEW-QR ███")

        self.assertNotIn("OLD-QR", manager.qrText)
        self.assertIn("NEW-QR", manager.qrText)
        self.assertGreaterEqual(len(events), 4)

    def test_success_message_is_only_pending_until_process_exits_successfully(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        manager = GameVersionsManager()
        self.assertFalse(manager.hasSavedSession)

        connected = []
        manager.accountConnected.connect(lambda username: connected.append(username))
        manager._consume_line(
            "Success! Next time you can login with -username paffciostudio -remember-password instead of -qr."
        )

        # Sam napis "Success!" pochodzi z etapu autoryzacji QR. Następny krok
        # InitializeSteam może jeszcze zakończyć się błędem, więc tutaj nic
        # nie zapisujemy i nie emitujemy accountConnected.
        self.assertEqual(manager.steamUsername, "")
        self.assertFalse(manager.hasSavedSession)
        self.assertEqual(connected, [])
        self.assertEqual(game_versions.load_steam_username(), "")

        # Dopiero poprawne zakończenie procesu zatwierdza konto.
        class FakeProc:
            stdout = [
                "Success! Next time you can login with -username paffciostudio -remember-password instead of -qr."
            ]
            returncode = 0
            def wait(self):
                return self.returncode

        # Zatwierdzenie przez cały przebieg procesu.
        with patch.object(game_versions.subprocess, "Popen", return_value=FakeProc()):
            error = manager._run_depot(["fake"], "auth", "Konto Steam połączone.")

        self.assertEqual(error, "")
        self.assertEqual(manager.steamUsername, "paffciostudio")
        self.assertTrue(manager.hasSavedSession)
        self.assertEqual(connected, ["paffciostudio"])
        self.assertEqual(game_versions.load_steam_username(), "paffciostudio")

        # Fallback dla wariantu bez komunikatu "Success!".
        manager2 = GameVersionsManager()
        manager2._steam_username = ""
        manager2._consume_line("Logging 'fallback_user' into Steam3...")
        self.assertEqual(manager2._pending_username, "fallback_user")

    def test_start_auth_retries_even_when_cancelled_qr_left_session_files(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        manager = GameVersionsManager()
        self.assertFalse(manager.hasSavedSession)

        captured = {}
        fake_binary = self.home / "DepotDownloader"
        fake_binary.write_text("", encoding="utf-8")

        def fake_run(cmd, branch, finish_status):
            captured["cmd"] = cmd
            captured["branch"] = branch
            manager._set_busy(False)

        class ImmediateThread:
            def __init__(self, target, daemon=True, **kwargs):
                self.target = target
            def start(self):
                self.target()

        with patch.object(game_versions, "ensure_tool", return_value=fake_binary), \
             patch.object(game_versions.GameVersionsManager, "_run_depot", side_effect=fake_run), \
             patch.object(game_versions.threading, "Thread", ImmediateThread):
            manager.startAuth()

        self.assertEqual(captured["branch"], "auth")
        self.assertIn("-qr", captured["cmd"])
        self.assertIn("-remember-password", captured["cmd"])
        self.assertIn("-manifest-only", captured["cmd"])
        self.assertIn("-loginid", captured["cmd"])
        self.assertNotIn("-username", captured["cmd"])

    def test_saved_account_file_is_enough_for_ui_session_state(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        game_versions.save_steam_username("paffciostudio")
        manager = GameVersionsManager()
        self.assertTrue(manager.hasSavedSession)
        self.assertEqual(manager.steamUsername, "paffciostudio")

    def test_cancelled_process_143_is_not_reported_as_error(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        class FakeProc:
            stdout = []
            returncode = 143
            def wait(self):
                return self.returncode
            def terminate(self):
                pass
            def kill(self):
                pass

        manager = GameVersionsManager()
        manager._cancel.set()
        with patch.object(game_versions.subprocess, "Popen", return_value=FakeProc()):
            manager._run_depot(["fake"], "auth", "Konto Steam połączone")
        self.assertTrue(manager.status.startswith("__I18N__:gameVersions.status.authCancelled|"))

    def test_download_uses_saved_username_instead_of_qr(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        session_dir = self.home / ".local" / "share" / "DepotDownloader"
        session_dir.mkdir(parents=True)
        (session_dir / "account.config").write_bytes(b"placeholder")
        game_versions.save_steam_username("paffciostudio")

        manager = GameVersionsManager()
        captured = {}
        done = threading.Event()

        fake_binary = self.home / "DepotDownloader"
        fake_binary.write_text("", encoding="utf-8")

        def fake_run(cmd, branch, finish_status):
            captured["cmd"] = cmd
            manager._set_busy(False)
            done.set()

        with patch.object(game_versions, "ensure_tool", return_value=fake_binary), \
             patch.object(game_versions.GameVersionsManager, "_run_depot", side_effect=fake_run), \
             patch.object(game_versions.GameVersionsManager, "is_installed", return_value=False):
            manager.download("v2.6")

        self.assertTrue(done.wait(2), "worker pobierania nie zakończył się w teście")
        manager.shutdown()
        self.assertIn("-username", captured["cmd"])
        self.assertIn("paffciostudio", captured["cmd"])
        self.assertNotIn("-qr", captured["cmd"])
        self.assertIn("-loginid", captured["cmd"])


class SteamFailureGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    def test_qr_success_followed_by_initialize_failure_does_not_save_account(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        class FakeProc:
            stdout = [
                "Success! Next time you can login with -username paffciostudio -remember-password instead of -qr.",
                "Error: InitializeSteam failed",
            ]
            returncode = 1
            terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        manager = GameVersionsManager()
        connected = []
        manager.accountConnected.connect(lambda username: connected.append(username))

        with patch.object(game_versions.subprocess, "Popen", return_value=FakeProc()):
            error = manager._run_depot(["fake"], "auth", "Konto Steam połączone.")

        self.assertTrue(error.startswith("__I18N__:gameVersions.status.depotExit|"))
        payload = json.loads(error.split("|", 1)[1])
        self.assertEqual(payload["code"], 1)
        self.assertEqual(manager.steamUsername, "")
        self.assertFalse(manager.hasSavedSession)
        self.assertEqual(connected, [])
        self.assertEqual(game_versions.load_steam_username(), "")

    def test_rate_limit_stops_depot_process_instead_of_waiting_for_internal_retries(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        class FakeProc:
            stdout = ["Unable to login to Steam3: RateLimitExceeded"]
            returncode = 1
            terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        proc = FakeProc()
        manager = GameVersionsManager()
        with patch.object(game_versions.subprocess, "Popen", return_value=proc):
            error = manager._run_depot(["fake"], "auth", "Konto Steam połączone.")

        self.assertTrue(proc.terminated)
        self.assertTrue(error.startswith("__I18N__:gameVersions.status.rateLimit|"))
        payload = json.loads(error.split("|", 1)[1])
        self.assertGreater(payload["seconds"], 0)
        self.assertGreater(manager._rate_limit_remaining(), 0)

    def test_manifest_asyncjob_storm_terminates_depot_process(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        manifest_error = (
            "Encountered error downloading manifest for depot 251576 "
            "2807835339043437499: Exception of type "
            "'SteamKit2.AsyncJobFailedException' was thrown."
        )

        class FakeProc:
            stdout = [manifest_error, manifest_error, manifest_error]
            returncode = 1
            terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        proc = FakeProc()
        manager = GameVersionsManager()
        manager._download_branch = "alpha8.8"

        with patch.object(game_versions.subprocess, "Popen", return_value=proc):
            error = manager._run_depot(["fake"], "alpha8.8", "Wersja alpha8.8 pobrana.")

        self.assertTrue(proc.terminated)
        self.assertTrue(error.startswith("__I18N__:gameVersions.status.manifestFailed|"))


class DepotDownloaderRetry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    def test_transient_chunk_error_restarts_without_full_validation(self):
        from PySide6.QtCore import QCoreApplication
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        app = QCoreApplication.instance() or QCoreApplication([])
        manager = GameVersionsManager()
        manager._download_branch = "alpha8.8"

        calls = []

        class FakeProc:
            def __init__(self, lines, returncode):
                self.stdout = lines
                self.returncode = returncode
                self.terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        first_process = FakeProc(
            ["Encountered unexpected error downloading chunk abc: Error while copying content to a stream."], 1
        )
        processes = [
            first_process,
            FakeProc(["100.00% /tmp/7DaysToDie.exe"], 0),
        ]

        def fake_popen(cmd, **kwargs):
            calls.append(list(cmd))
            return processes.pop(0)

        with patch.object(game_versions.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(game_versions, "DOWNLOAD_RETRY_DELAY", 0):
            error = manager._run_depot(["depotdownloader", "-dir", str(self.home / "game")], "alpha8.8", "Wersja alpha8.8 pobrana.")

        self.assertEqual(error, "")
        self.assertTrue(first_process.terminated)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("-validate", calls[0])
        self.assertNotIn("-validate", calls[1])
        idx = calls[1].index("-max-downloads")
        self.assertEqual(calls[1][idx + 1], "1")



    def test_stream_chunk_error_switches_to_fallback_downloader_immediately(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        chunk_line = (
            "Encountered unexpected error downloading chunk abc: "
            "Error while copying content to a stream."
        )

        class FakeProc:
            def __init__(self, lines, returncode):
                self.stdout = lines
                self.returncode = returncode
                self.terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        calls=[]
        processes=[FakeProc([chunk_line],1), FakeProc(["100.00% /tmp/game/7DaysToDie.exe"],0)]
        def fake_popen(cmd, **kwargs):
            calls.append(list(cmd))
            return processes.pop(0)

        fallback = self.home / "DepotDownloader-3.3.0"
        fallback.write_text("", encoding="utf-8")
        manager=GameVersionsManager()
        manager._download_branch="alpha8.8"
        with patch.object(game_versions.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(game_versions, "ensure_fallback_tool", return_value=fallback), \
             patch.object(game_versions, "DOWNLOAD_RETRY_DELAY", 0):
            error=manager._run_depot(["depotdownloader", "-dir", str(self.home / "game")], "alpha8.8", "Wersja alpha8.8 pobrana.")

        self.assertEqual(error, "")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], str(fallback))
        self.assertNotIn("-validate", calls[1])
        idx=calls[1].index("-max-downloads")
        self.assertEqual(calls[1][idx + 1], "1")

    def test_second_stream_chunk_failure_tries_second_fallback(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        chunk_line = (
            "Encountered unexpected error downloading chunk abc: "
            "Error while copying content to a stream."
        )

        class FakeProc:
            def __init__(self, lines, returncode):
                self.stdout = lines
                self.returncode = returncode
                self.terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        calls=[]
        processes=[
            FakeProc([chunk_line],1),
            FakeProc([chunk_line],1),
            FakeProc(["100.00% /tmp/game/7DaysToDie.exe"],0),
        ]
        def fake_popen(cmd, **kwargs):
            calls.append(list(cmd))
            return processes.pop(0)

        fallback33 = self.home / "DepotDownloader-3.3.0"
        fallback31 = self.home / "DepotDownloader-3.1.0"
        fallback33.write_text("", encoding="utf-8")
        fallback31.write_text("", encoding="utf-8")
        manager=GameVersionsManager()
        manager._download_branch="alpha8.8"
        with patch.object(game_versions.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(game_versions, "ensure_fallback_tool", side_effect=[fallback33, fallback31]), \
             patch.object(game_versions, "DOWNLOAD_RETRY_DELAY", 0):
            error=manager._run_depot(["depotdownloader", "-dir", str(self.home / "game")], "alpha8.8", "Wersja alpha8.8 pobrana.")

        self.assertEqual(error, "")
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1][0], str(fallback33))
        self.assertEqual(calls[2][0], str(fallback31))
        for cmd in calls[1:]:
            self.assertNotIn("-validate", cmd)

    def test_file_lock_switches_to_single_download_and_retries(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        class FakeProc:
            def __init__(self, lines, returncode):
                self.stdout = lines
                self.returncode = returncode
            def wait(self):
                return self.returncode
            def terminate(self):
                pass

        lock_line = (
            "Unhandled exception. System.IO.IOException: The process cannot access "
            "the file '/tmp/game/Data/Bundles/TerrainTextures' because it is being used by another process."
        )
        calls = []
        processes = [
            FakeProc([lock_line], 6),
            FakeProc(["100.00% /tmp/game/7DaysToDie.exe"], 0),
        ]

        def fake_popen(cmd, **kwargs):
            calls.append(list(cmd))
            return processes.pop(0)

        manager = GameVersionsManager()
        manager._download_branch = "alpha8.8"
        fuser_result = type("FuserResult", (), {"stdout": "", "stderr": "", "returncode": 0})()
        with patch.object(game_versions.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(game_versions.subprocess, "run", return_value=fuser_result), \
             patch.object(game_versions, "FILE_LOCK_RETRY_DELAY", 0):
            error = manager._run_depot(
                ["depotdownloader", "-dir", "/tmp/game", "-max-downloads", "4"],
                "alpha8.8",
                "Wersja alpha8.8 pobrana.",
            )

        self.assertEqual(error, "")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("-validate", calls[1])
        idx = calls[1].index("-max-downloads")
        self.assertEqual(calls[1][idx + 1], "1")

    def test_file_lock_terminates_current_depot_process_early(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        class FakeProc:
            def __init__(self):
                self.stdout = [
                    "Unhandled exception. System.IO.IOException: The process cannot access "
                    "the file '/tmp/game/Data/Bundles/TerrainTextures' because it is being used by another process."
                ]
                self.returncode = 1
                self.terminated = False
            def wait(self):
                return self.returncode
            def terminate(self):
                self.terminated = True

        proc = FakeProc()
        manager = GameVersionsManager()
        manager._download_branch = "alpha8.8"
        with patch.object(game_versions.subprocess, "Popen", return_value=proc), \
             patch.object(game_versions.subprocess, "run", return_value=type("R", (), {"stdout": ""})()), \
             patch.object(game_versions, "FILE_LOCK_RETRY_DELAY", 0):
            manager._run_depot(
                ["depotdownloader", "-dir", "/tmp/game"],
                "alpha8.8",
                "Wersja alpha8.8 pobrana.",
            )
        self.assertTrue(proc.terminated)

    def test_file_lock_diagnostic_uses_fuser_when_available(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        manager = GameVersionsManager()
        result = type("R", (), {"stdout": "                     USER        PID ACCESS COMMAND\n/tmp/a:             user       1234 f.... python3\n"})()
        with patch.object(game_versions.subprocess, "run", return_value=result) as run:
            text = manager._file_lock_holders("/tmp/a")
        self.assertIn("1234", text)
        run.assert_called_once()


class GameVersionDownloadQueue(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    def test_download_progress_is_forwarded_to_common_queue(self):
        from PySide6.QtCore import QCoreApplication
        from backend.download_manager import DownloadManager
        from backend.game_versions import GameVersionsManager
        from backend.events import EventBus
        from services.settings_service import SettingsService

        app = QCoreApplication.instance() or QCoreApplication([])
        downloads = DownloadManager.__new__(DownloadManager)
        QObject = __import__('PySide6.QtCore', fromlist=['QObject']).QObject
        # Minimal manager instance without starting timers / workers.
        QObject.__init__(downloads)
        downloads._model = __import__('backend.download_manager', fromlist=['DownloadListModel']).DownloadListModel(downloads)
        downloads._last_queue_json = ""
        downloads._settings = type("S", (), {"maxConcurrentDownloads": 2})()
        downloads._bus = EventBus()
        manager = GameVersionsManager()
        manager.gameDownloadStarted.connect(downloads.startGameVersionDownload)
        manager.gameDownloadProgress.connect(downloads.updateGameVersionDownload)
        manager.gameDownloadFinished.connect(downloads.finishGameVersionDownload)

        manager._available = [{"branch": "v2.6", "size_bytes": 1000}]
        manager._download_branch = "v2.6"
        manager._set_busy(True)
        manager.gameDownloadStarted.emit("v2.6", 1000)
        manager._set_progress(37.5)
        manager._set_status("Pobieram 7DaysToDie.exe")
        manager._set_progress(38.0)
        # Postęp i status są zbijane w jedną paczkę (throttling UI) -
        # poczekaj na flush z pętli zdarzeń zamiast zakładać emisję synchroniczną.
        import time
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not any(
                i.kind == "game" and i.progress >= 0.37 for i in downloads._model.items):
            app.processEvents()
            time.sleep(0.01)

        item = next(i for i in downloads._model.items if i.kind == "game")
        self.assertEqual(item.title, "7 Days to Die - v2.6")
        self.assertGreaterEqual(item.progress, 0.37)
        self.assertIn("7DaysToDie.exe", item.subtitle)


    def test_game_download_speed_does_not_flicker_on_status_only_update(self):
        from PySide6.QtCore import QCoreApplication
        from backend.download_manager import DownloadManager, DownloadListModel
        from backend.game_versions import GameVersionsManager
        from backend.events import EventBus
        from services.settings_service import SettingsService

        app = QCoreApplication.instance() or QCoreApplication([])
        downloads = DownloadManager.__new__(DownloadManager)
        from PySide6.QtCore import QObject
        QObject.__init__(downloads)
        downloads._model = DownloadListModel(downloads)
        downloads._last_queue_json = ""
        downloads._settings = type("S", (), {"maxConcurrentDownloads": 2})()
        downloads._bus = EventBus()
        manager = GameVersionsManager()
        manager.gameDownloadStarted.connect(downloads.startGameVersionDownload)
        manager.gameDownloadProgress.connect(downloads.updateGameVersionDownload)

        manager._download_branch = "alpha17.4"
        manager._set_busy(True)
        manager.gameDownloadStarted.emit("alpha17.4", 7_200_000_000)

        item = downloads._model.items[0]
        import time as _time
        item._last_sample = (_time.monotonic() - 1.0, 6_900_000_000)
        item.downloaded = 6_900_000_000
        item.speed = 40_000_000
        downloads.updateGameVersionDownload("alpha17.4", 95.9, "Pobieram file-a")
        speed = item.speed
        downloads.updateGameVersionDownload("alpha17.4", 95.9, "Pobieram file-b")
        self.assertGreater(item.speed, 0)
        self.assertAlmostEqual(item.speed, speed, delta=speed * 0.01)

    def test_game_download_accepts_depot_size_over_32bit_limit(self):
        from PySide6.QtCore import QCoreApplication, QObject
        from backend.download_manager import DownloadManager, DownloadListModel
        app = QCoreApplication.instance() or QCoreApplication([])
        downloads = DownloadManager.__new__(DownloadManager)
        QObject.__init__(downloads)
        downloads._model = DownloadListModel(downloads)
        downloads._last_queue_json = ""
        downloads._settings = type("S", (), {"maxConcurrentDownloads": 2})()
        downloads._bus = type("Bus", (), {"toast": lambda *args, **kwargs: None, "toastKey": lambda *args, **kwargs: None})()

        # This is larger than a signed 32-bit C++ int and mirrors the size
        # class of the real 7 Days to Die depot.
        total = 5_000_000_000
        downloads.startGameVersionDownload("v2.6", total)

        item = downloads._model.items[0]
        self.assertEqual(item.total_bytes, total)
        self.assertEqual(item.kind, "game")

    def test_game_download_cancel_does_not_stay_as_active_queue_item(self):
        from PySide6.QtCore import QCoreApplication
        from backend.download_manager import DownloadManager
        app = QCoreApplication.instance() or QCoreApplication([])
        downloads = DownloadManager.__new__(DownloadManager)
        from PySide6.QtCore import QObject
        from backend.download_manager import DownloadListModel
        QObject.__init__(downloads)
        downloads._model = DownloadListModel(downloads)
        downloads._last_queue_json = ""
        downloads._settings = type("S", (), {"maxConcurrentDownloads": 2})()
        downloads._bus = type("Bus", (), {"toast": lambda *args, **kwargs: None, "toastKey": lambda *args, **kwargs: None})()
        downloads.startGameVersionDownload("public", 100)
        self.assertEqual(downloads.activeCount, 1)
        downloads.finishGameVersionDownload("public", "cancelled", "")
        self.assertEqual(downloads.activeCount, 0)
        self.assertEqual(downloads._model.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()


class DepotDownloaderLifecycle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._patch = patch.object(Path, "home", return_value=self.home)
        self._patch.start()
        # Najpierw przywróć prawdziwe Path.home, dopiero potem usuń katalog.
        # Część testowanych workerów działa asynchronicznie; pozostawienie
        # monkeypatcha aktywnego podczas cleanupu pozwalałoby spóźnionemu
        # workerowi utworzyć plik w już sprzątanym TemporaryDirectory.
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._patch.stop)

    def test_stale_process_matches_exact_target(self):
        from backend import game_versions
        from backend.game_versions import GameVersionsManager

        tool = self.home / ".7dtd_modmanager" / "tools" / "DepotDownloader"
        tool.parent.mkdir(parents=True)
        target = self.home / ".7dtd_modmanager" / "game-versions" / "alpha8.8"
        target.mkdir(parents=True)

        manager = GameVersionsManager()
        with patch.object(manager, "_managed_depot_processes", return_value=[
            (123, [str(tool), "-dir", str(target)])
        ]), patch.object(manager, "_terminate_os_pid", return_value=True) as kill:
            self.assertEqual(manager._cleanup_stale_depot_processes(target), 1)
            kill.assert_called_once_with(123)

    def test_cleanup_stale_processes_can_clean_all_manager_downloaders(self):
        from backend.game_versions import GameVersionsManager

        manager = GameVersionsManager()
        with patch.object(manager, "_managed_depot_processes", return_value=[
            (123, ["/tmp/DepotDownloader", "-dir", "/tmp/a"]),
            (456, ["/tmp/DepotDownloader", "-dir", "/tmp/b"]),
        ]), patch.object(manager, "_terminate_os_pid", return_value=True) as kill:
            self.assertEqual(manager._cleanup_stale_depot_processes(), 2)
            self.assertEqual(kill.call_count, 2)

    def test_qml_contains_no_em_dash(self):
        root = Path(__file__).resolve().parents[1] / "qml"
        files = list(root.rglob("*.qml"))
        offenders = [str(p) for p in files if "\u2014" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])

    def test_shutdown_sets_cancel_and_stops_active_process(self):
        from backend.game_versions import GameVersionsManager

        manager = GameVersionsManager()
        class Worker:
            def __init__(self):
                self.alive = True
            def is_alive(self):
                return self.alive
            def join(self, timeout=None):
                self.alive = False
        worker = Worker()
        manager._worker_thread = worker
        with patch.object(manager, "_terminate_process") as stop, \
             patch.object(manager, "_cleanup_stale_depot_processes") as cleanup:
            manager.shutdown()
        self.assertTrue(manager._cancel.is_set())
        stop.assert_called_once()
        cleanup.assert_called_once_with(None)
        self.assertFalse(worker.alive)


def test_depot_fallback_release_tag_uses_real_github_tag():
    from backend import game_versions
    source = Path(game_versions.__file__).read_text(encoding="utf-8")
    assert 'f"DepotDownloader_{version}"' in source
    assert 'DEPOTDOWNLOADER_FALLBACK_VERSIONS = ("3.3.0", "3.2.0", "3.1.0")' in source


def test_transient_chunk_retry_forces_single_download():
    from backend import game_versions
    source = Path(game_versions.__file__).read_text(encoding="utf-8")
    assert 'cmd[idx + 1] = "1"' in source


class GameVersionsThreadSafety(unittest.TestCase):
    """Sygnały z wątku DepotDownloadera muszą trafiać do wątku GUI."""

    def test_worker_thread_emits_are_delivered_in_gui_thread(self):
        import threading
        import time
        from PySide6.QtCore import QCoreApplication, QThread
        from backend.game_versions import GameVersionsManager

        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QCoreApplication.instance() or QCoreApplication([])
        manager = GameVersionsManager()
        gui_thread = QThread.currentThread()
        seen = []
        manager.progressChanged.connect(lambda: seen.append(QThread.currentThread() is gui_thread))
        manager.busyChanged.connect(lambda: seen.append(QThread.currentThread() is gui_thread))
        manager._download_branch = "v2.6"

        def worker():
            manager._set_busy(True)
            for i in range(5000):  # symulacja tysięcy linii stdout
                manager._set_progress(i / 50.0)

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(seen) < 2:
            app.processEvents()
            time.sleep(0.01)
        for _ in range(20):
            app.processEvents()
            time.sleep(0.01)

        self.assertTrue(seen)
        self.assertTrue(all(seen), "sygnał wyemitowany poza wątkiem GUI")
        # throttling: 5000 aktualizacji nie może dać 5000 sygnałów do UI
        self.assertLess(len(seen), 50)
