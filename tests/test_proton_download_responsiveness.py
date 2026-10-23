"""Keep torrent/Proton downloads responsive without needing a Qt display.

The simple progress limiters are evaluated in isolation so this suite can be
run even on build agents without the PySide6 desktop runtime.
"""
from __future__ import annotations

import ast
import io
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_class(source: str, classname: str):
    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname)
    scope = {"time": __import__("time"), "DOWNLOAD_PROGRESS_EVENT_INTERVAL": 0.125,
             "PROGRESS_INTERVAL_SECONDS": 0.125}
    exec(compile(ast.Module(body=[node], type_ignores=[]), source, "exec"), scope)
    return scope[classname]


def test_proton_progress_does_not_flood_qt():
    limiter_cls = load_class("src/backend/protons.py", "ProgressLimiter")
    clock = [0.0]
    events = []
    limiter = limiter_cls(events.append, clock=lambda: clock[0])
    for i in range(1000):
        clock[0] = i / 1000
        limiter(i / 10)
    assert 6 <= len(events) <= 11, len(events)
    assert events[0] == 0
    assert 75 <= events[-1] <= 99.9
    limiter(100)
    assert events[-1] == 100
    limiter(100)
    assert events.count(100) == 1


def test_mod_download_progress_limits_events_but_keeps_phase_changes():
    limiter_cls = load_class("src/backend/download_manager.py", "DownloadProgressLimiter")
    clock = [0.0]
    events = []
    limiter = limiter_cls(lambda *args: events.append(args), clock=lambda: clock[0])
    for i in range(1000):
        clock[0] = i / 1000
        limiter(i, 1000, "")
    assert len(events) <= 11, len(events)
    clock[0] += 0.001
    limiter(1000, 1000, "")
    assert events[-1] == (1000, 1000, "")
    clock[0] += 0.001
    limiter(1000, 1000, "__I18N__:download.mod.extracting|name=first")
    assert events[-1][2].startswith("__I18N__:download.mod.extracting")
    count = len(events)
    for i in range(20):
        clock[0] += 0.001
        limiter(1000, 1000, f"__I18N__:download.mod.extracting|name={i}")
    assert len(events) == count


def make_tar(path: Path, name: str, *, link: bool = False):
    with tarfile.open(path, "w:gz") as archive:
        if link:
            member = tarfile.TarInfo(name)
            member.type = tarfile.SYMTYPE
            member.linkname = "../../escaped"
            archive.addfile(member)
        else:
            data = b"#!/bin/sh\n"
            member = tarfile.TarInfo(name)
            member.mode = 0o755
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def run_extract(tmp_path: Path, *, name: str, link: bool = False):
    archive = tmp_path / "archive.tar.gz"
    output = tmp_path / "output"
    output.mkdir()
    make_tar(archive, name, link=link)
    helper = ROOT / "src/backend/proton_extract_worker.py"
    result = subprocess.run([sys.executable, str(helper), str(archive), str(output)],
                            capture_output=True, text=True, timeout=15)
    return result, output


def test_proton_extract_process_preserves_file_modes(tmp_path):
    result, output = run_extract(tmp_path, name="GE-Proton11-7/proton")
    assert result.returncode == 0, result.stderr
    assert (output / "GE-Proton11-7" / "proton").stat().st_mode & 0o111


def test_proton_extract_process_blocks_path_escape(tmp_path):
    result, output = run_extract(tmp_path, name="../escaped")
    assert result.returncode != 0
    assert not (tmp_path / "escaped").exists()
    assert not list(output.rglob("escaped"))


def test_proton_extract_process_blocks_symlink_escape(tmp_path):
    result, output = run_extract(tmp_path, name="GE-Proton11-7/leak", link=True)
    assert result.returncode != 0
    assert not (tmp_path / "escaped").exists()
    assert not list(output.rglob("leak"))


def test_proton_backend_moves_blocking_tasks_off_gui_thread():
    source = (ROOT / "src/backend/protons.py").read_text(encoding="utf-8")
    assert "extract_in_process(archive, extracted, cancel)" in source
    assert "ProgressLimiter(lambda p: self._event.emit('progress', p))" in source
    assert "progressChanged = Signal()" in source
    assert "statusChanged = Signal()" in source
    assert "self._start(lambda: shutil.rmtree(target))" in source
    assert "threading.Thread(target=scan" in source
    assert "self._event.emit('done', versions)" in source
