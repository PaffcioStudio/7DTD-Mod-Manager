"""Persistent runtime tracking - stable process identity and restart recovery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend.playtime import PlaytimeStore


def test_first_launch_reconnect_and_stop(tmp_path):
    path = tmp_path / "playtime.json"
    store = PlaytimeStore(path)
    assert store.seconds("a") == 0
    assert store.last_played("a") == 0
    assert not store.update({}, now=120)
    store.update({"a": (41, 100)}, now=130)
    assert store.seconds("a") == 30
    store.update({"a": (41, 100)}, now=160)
    assert store.seconds("a") == 60
    assert store.last_played("a") == 160
    # Simulate a crash/relaunch of the manager while the game continues.
    reopened = PlaytimeStore(path)
    reopened.update({"a": (41, 100)}, now=170)
    assert reopened.seconds("a") == 70
    reopened.update({}, now=171)
    assert reopened.seconds("a") == 70
    reopened.update({"a": (42, 190)}, now=200)
    assert reopened.seconds("a") == 80
    assert reopened.last_played("a") == 200


def test_separate_instances_and_deleted_instances_not_in_total(tmp_path):
    store = PlaytimeStore(tmp_path / "playtime.json")
    store.update({"a": (41, 100), "b": (55, 90)}, now=110)
    assert store.seconds("a") == 10
    assert store.seconds("b") == 20
    assert store.total_seconds({"a", "b"}) == 30
    assert store.total_seconds({"a"}) == 10
    store.update({}, now=111)
    assert store.seconds("missing") == 0


def test_invalid_processes_do_not_inflate_time(tmp_path):
    store = PlaytimeStore(tmp_path / "playtime.json")
    store.update({"a": (-1, 10), "b": (1, 0), "c": (2, 200)}, now=100)
    assert store.total_seconds() == 0
    store.update({"a": (10, 50)}, now=100)
    store.update({"a": (10, 50)}, now=100)
    assert store.seconds("a") == 50
    assert store.total_seconds() == 50


def test_process_handoff_does_not_double_count_parallel_wine_processes(tmp_path):
    store = PlaytimeStore(tmp_path / "playtime.json")
    store.update({"a": (100, 100)}, now=130)
    # A second game-related process started at 110 but is observed at 140.
    store.update({"a": (101, 110)}, now=140)
    assert store.seconds("a") == 40
    # If the game truly restarted later, do not include the gap.
    store.update({}, now=141)
    store.update({"a": (102, 160)}, now=170)
    assert store.seconds("a") == 50
