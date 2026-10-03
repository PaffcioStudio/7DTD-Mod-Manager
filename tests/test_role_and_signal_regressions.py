"""Regresje: kolizja ról DownloadListModel i typ sygnału notifyKey."""
from backend.download_manager import DownloadListModel
from backend.events import EventBus


def test_download_model_role_ids_are_unique():
    ids = list(DownloadListModel.ROLES.keys())
    assert len(ids) == len(set(ids)) == len(DownloadListModel.ROLES)
    names = set(DownloadListModel.ROLES.values())
    assert b"statusKey" in names and b"statusText" in names


def test_download_model_declared_roles_all_present():
    declared = [v for k, v in vars(DownloadListModel).items() if k.endswith("Role")]
    assert len(declared) == len(set(declared)), "dwie role mają ten sam numer"


def test_notify_key_delivers_plain_map():
    bus = EventBus()
    got = []
    bus.notifyKey.connect(lambda key, values, level: got.append((key, values, level)))
    bus.toastKey("k", {"count": 3}, "info")
    assert got == [("k", {"count": 3}, "info")]
