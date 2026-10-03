"""Helpers for passing translatable messages from Python to the QML I18n layer."""
from __future__ import annotations

import json

PREFIX = "__I18N__:"


def message(key: str, values: dict | None = None) -> str:
    """Build the compact message envelope consumed by ``I18n.resolveMessage``."""
    payload = json.dumps(values or {}, ensure_ascii=False, separators=(",", ":"))
    return f"{PREFIX}{key}|{payload}"
