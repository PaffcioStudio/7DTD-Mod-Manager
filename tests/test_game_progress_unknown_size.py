"""Test postępu archiwalnych depotów bez rozmiaru w Steam API."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _data_function():
    tree = ast.parse((ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8"))
    clazz = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DownloadListModel")
    func = next(node for node in clazz.body if isinstance(node, ast.FunctionDef) and node.name == "data")
    # Nie potrzebujemy Qt do sprawdzenia generowania wartości ról modelu.
    func.decorator_list = []
    func.args.defaults = []
    classdef = ast.ClassDef(name="Model", bases=[], keywords=[], body=[func], decorator_list=[])
    code = ast.fix_missing_locations(ast.Module(body=[classdef], type_ignores=[]))
    ns = {"human_size": lambda size: f"{size} B"}
    exec(compile(code, "<download_roles>", "exec"), ns)
    model = ns["Model"]()
    for i, key in enumerate(("IdRole", "TitleRole", "SubtitleRole", "ProgressRole", "ProgressTextRole", "TotalTextRole", "DownloadedTextRole", "SpeedTextRole", "EtaTextRole", "EtaSecondsRole", "StatusKeyRole", "StatusTextRole", "KindRole", "PausableRole"), start=100):
        setattr(model, key, i)
    return model


def _record(total, kind, fraction):
    return SimpleNamespace(
        id="game-1", title="Alpha", subtitle="file.dll", total_bytes=total,
        downloaded=int(total * fraction), kind=kind, status="downloading",
        progress=fraction, _progress_override=fraction if kind == "game" else None,
        speed_text="-", eta_text="", eta_seconds=0, status_text="Downloading",
        pausable=True,
    )


def _index():
    return SimpleNamespace(isValid=lambda: True, row=lambda: 0)


def test_historical_depot_percentage_visible_even_with_unknown_bytes():
    model = _data_function()
    model._items = [_record(0, "game", .366)]
    assert model.data(_index(), model.ProgressRole) == .366
    assert model.data(_index(), model.ProgressTextRole) == "36.6%"
    assert model.data(_index(), model.DownloadedTextRole) == "36.6%"
    assert model.data(_index(), model.TotalTextRole) == ""


def test_mod_with_unknown_size_remains_indeterminate():
    model = _data_function()
    model._items = [_record(0, "url", .366)]
    assert model.data(_index(), model.ProgressRole) == 0.0
    assert model.data(_index(), model.ProgressTextRole) == ""


def test_known_size_still_reports_bytes():
    model = _data_function()
    model._items = [_record(1000, "game", .5)]
    assert model.data(_index(), model.ProgressRole) == .5
    assert model.data(_index(), model.DownloadedTextRole) == "500 B / 1000 B"


def test_game_download_card_does_not_force_indeterminate_mode():
    qml = (ROOT / "qml/components/DownloadCard.qml").read_text(encoding="utf-8")
    assert 'root.kind !== "game"' in qml
    assert "value: root.progress" in qml
