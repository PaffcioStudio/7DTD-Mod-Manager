from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _catalog_keys():
    text = (ROOT / "qml" / "i18n" / "translations.js").read_text(encoding="utf-8")
    pl = text.split("var pl = {", 1)[1].split("\n}\n\nvar en = {", 1)[0]
    en = text.split("var en = {", 1)[1].rsplit("\n};", 1)[0]
    key_re = re.compile(r'^\s*"([^"]+)":', re.M)
    return set(key_re.findall(pl)), set(key_re.findall(en))


def _python_marker_keys():
    keys = set()
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "i18n_message":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("__I18N__:"):
                match = re.match(r"^__I18N__:([^|]+)", node.value)
                if match:
                    keys.add(match.group(1))
    return keys


def test_all_static_python_i18n_keys_exist_in_both_catalogs():
    pl, en = _catalog_keys()
    used = _python_marker_keys()
    assert used - pl == {"date.relative"}
    assert used - en == {"date.relative"}


def test_i18n_resolver_consumes_the_full_marker_prefix():
    qml = (ROOT / "qml" / "i18n" / "I18n.qml").read_text(encoding="utf-8")
    assert 'raw.slice("__I18N__:".length)' in qml


def test_default_instance_and_dynamic_instance_labels_use_i18n_markers():
    backend = (ROOT / "src" / "backend" / "profile_manager.py").read_text(encoding="utf-8")
    qml = (ROOT / "qml" / "components" / "DropdownButton.qml").read_text(encoding="utf-8")
    assert 'i18n_message("instances.defaultName") if i.is_default else i.name' in backend
    assert 'I18n.resolveMessage(String(options[i].label))' in qml
    assert 'I18n.resolveMessage(item.modelData.label)' in qml


def test_qml_has_no_polish_user_facing_literals_outside_the_catalog():
    pattern = re.compile(
        r"(?:Anuluj|Pobierz|Gotowe|Błąd|błąd|Zapisz|Usuń|Przywróć|Przywracanie|W kolejce|Nie znaleziono|Nie można|Brak|Ustawienia|Instancje|Mody|Biblioteka|Główna|ręcznie dodany|nie istnieje)"
    )
    attribute = re.compile(r'^\s*(?:text|title|placeholderText|placeholder|label|description|caption|message|toolTip)\s*:\s*["\']')
    hits = []
    for path in (ROOT / "qml").rglob("*.qml"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if attribute.search(line) and pattern.search(line):
                hits.append(f"{path}:{line_no}")
    assert hits == []


def test_i18n_defaults_to_english_and_interpolates_qvariant_values():
    i18n = (ROOT / "qml" / "i18n" / "I18n.qml").read_text(encoding="utf-8")
    settings = (ROOT / "src" / "services" / "settings_service.py").read_text(encoding="utf-8")
    assert 'property string language: "en"' in i18n
    assert '"language": "en"' in settings
    assert 'self._values["language"] = "en"' in settings
    assert r'const matches = text.match(/\{([A-Za-z0-9_.-]+)\}/g) || []' in i18n
    assert 'value = values[name]' in i18n


def test_library_refresh_toast_formats_count_through_the_i18n_path():
    manager = (ROOT / "src" / "backend" / "mod_manager.py").read_text(encoding="utf-8")
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    catalog = (ROOT / "qml" / "i18n" / "translations.js").read_text(encoding="utf-8")
    i18n = (ROOT / "qml" / "i18n" / "I18n.qml").read_text(encoding="utf-8")
    assert 'self._bus.toastKey("toast.mods.libraryRefreshed", {"count": len(self._library_entries)}, "success")' in manager
    assert 'toasts.show(I18n.format(key, values), level)' in main
    assert '"toast.mods.libraryRefreshed": "Library refreshed: {count} mods"' in catalog
    assert 'value = values[name]' in i18n
