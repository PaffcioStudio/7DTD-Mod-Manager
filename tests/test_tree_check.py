"""QML cache purge and I18n preconditions."""
import logging
from pathlib import Path

from services import tree_check

ROOT = Path(__file__).resolve().parent.parent


def test_i18n_layer_sane():
    assert tree_check.i18n_sanity(ROOT) == []


def test_compass_icon_exists():
    assert (ROOT / "assets" / "icons" / "compass.svg").is_file()


def test_purge_compiled_cache_removes_only_cache_files(tmp_path):
    q = tmp_path / "qml" / "components"
    q.mkdir(parents=True)
    (q / "A.qml").write_text("Item {}")
    for name in ("A.qmlc", "A.qmlc.aotstats", "B.jsc"):
        (q / name).write_text("stale")
    assert tree_check.purge_compiled_cache(tmp_path, logging.getLogger("t")) == 3
    assert [p.name for p in q.iterdir()] == ["A.qml"]


def test_log_messages_are_english():
    """No Polish diacritics inside logger/install_log call arguments."""
    import ast
    import re
    pl = re.compile("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
    bad = []
    for f in (ROOT / "src").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("debug", "info", "warning", "error",
                                        "critical", "exception")):
                owner = ast.get_source_segment(src, n.func.value) or ""
                seg = ast.get_source_segment(src, n) or ""
                if "log" in owner.lower() and pl.search(seg):
                    bad.append(f"{f.name}:{n.lineno}")
    assert bad == []
