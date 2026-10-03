from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_human_size_clamps_negative_and_uses_human_units():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from models.mod import human_size

    assert human_size(-2_095_160_201) == "0 B"
    assert human_size(2_095_160_201) == "2.0 GB"
    assert human_size(1_572_864) == "1.5 MB"


def test_download_item_progress_source_has_non_negative_clamp():
    source = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    progress_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "progress":
            progress_names.append(ast.get_source_segment(source, node) or "")
    assert progress_names
    assert "max(0.0, min(1.0" in source


def test_url_progress_uses_bytes_only_for_transfer_and_ignores_archive_counters():
    source = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert 'phase.startswith(("__I18N__:download.mod.extracting|", "__I18N__:download.mod.cloning|"))' in source
    assert "done_i = max(0, int(done or 0))" in source
    assert "done_i = min(done_i, effective_total)" in source


def test_scraper_human_size_also_clamps_negative_values():
    source = (ROOT / "src/backend/scraper_client.py").read_text(encoding="utf-8")
    assert "value = max(0.0, float(num_bytes or 0))" in source


def test_url_progress_signal_uses_object_payloads_for_large_byte_counts():
    source = (ROOT / "src/backend/download_manager.py").read_text(encoding="utf-8")
    assert 'urlProgress = Signal(str, object, object, str)' in source
    assert 'modMeta = Signal(str, str, str, object)' in source
    assert 'urlProgress = Signal(str, int, int, str)' not in source


def test_human_size_handles_multi_gigabyte_values_without_raw_bytes_display():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from models.mod import human_size

    assert human_size(2_199_807_095) == "2.0 GB"
    assert human_size(3_221_225_472) == "3.0 GB"
