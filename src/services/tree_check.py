"""Startup sanity checks for the QML/i18n layer.

* purge_compiled_cache() removes stale precompiled QML (*.qmlc, *.jsc,
  *.aotstats) that Qt may have written next to the sources.  Qt loads such
  files instead of the .qml/.js sources, so a leftover from an older version
  can silently run old code (missing I18n functions, old hard-coded strings).
* i18n_sanity() verifies the hard preconditions of the translation layer.
* report() logs the result at startup (never raises).
"""
from __future__ import annotations

import re
from pathlib import Path

_CACHE_SUFFIXES = (".qmlc", ".jsc", ".aotstats")


def purge_compiled_cache(root: Path, log) -> int:
    """Delete precompiled QML artifacts under qml/. They are pure cache."""
    removed = 0
    try:
        for p in (root / "qml").rglob("*"):
            if p.is_file() and p.suffix in _CACHE_SUFFIXES:
                try:
                    p.unlink()
                    removed += 1
                except OSError as exc:
                    log.warning("Could not remove QML cache file %s: %s", p, exc)
        if removed:
            log.warning("Removed %d precompiled QML cache files next to the sources "
                        "(they may have served an old version of the code)", removed)
    except Exception:
        log.exception("QML cache cleanup failed")
    return removed


def i18n_sanity(root: Path) -> list[str]:
    """Return a list of problems that would break the translation layer."""
    problems: list[str] = []
    qml = root / "qml" / "i18n" / "I18n.qml"
    js = root / "qml" / "i18n" / "translations.js"
    try:
        text = qml.read_text(encoding="utf-8")
        if not re.search(r"function\s+resolveMessage\s*\(", text):
            problems.append("I18n.qml does not define resolveMessage()")
        if not re.search(r'property\s+string\s+language:\s*"en"', text):
            problems.append('I18n.qml: default language is not "en"')
    except OSError as exc:
        problems.append(f"cannot read I18n.qml: {exc}")
    try:
        body = js.read_text(encoding="utf-8")
        en = body[body.index("var en = {"):]
        for key in ("hero.gameDetected", "app.gameDetectedTooltip",
                    "globalSearch.placeholder", "instances.defaultName"):
            if f'"{key}"' not in en:
                problems.append(f"translations.js: EN catalog is missing key {key}")
    except (OSError, ValueError) as exc:
        problems.append(f"translations.js: {exc}")
    return problems


def report(root: Path, log) -> None:
    try:
        problems = i18n_sanity(root)
        for problem in problems:
            log.error("I18n check: %s", problem)
        if not problems:
            log.info("I18n check: OK")
    except Exception:  # diagnostics must never break the app
        log.exception("I18n check failed")
