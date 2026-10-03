"""Global search across the local library, instances and online catalog."""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer

from backend.discover import fetch_catalog

logger = logging.getLogger(__name__)


class GlobalSearchManager(QObject):
    """Shared search used by the header search field.

    Local results are calculated immediately from installed mods and game
    instances. The online "Odkrywaj" section is queried in a worker thread
    with the same cached catalog code as the Discover page.
    """

    changed = Signal()
    resultOpened = Signal(str, str, str)  # kind, id, title

    def __init__(self, mods, profiles, parent=None) -> None:
        super().__init__(parent)
        self._mods = mods
        self._profiles = profiles
        self._query = ""
        self._results: list[dict] = []
        self._busy = False
        self._error = ""
        self._errorKey = ""
        self._errorValues: dict = {}
        self._generation = 0
        self._pending_query: str | None = None
        self._thread: threading.Thread | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)
        self._debounce.timeout.connect(self._start_pending_from_timer)
        self._closed = False
        self._apply_online.connect(self._finish_online)

    @Property(str, notify=changed)
    def query(self) -> str:
        return self._query

    @query.setter
    def query(self, value: str) -> None:
        value = (value or "").strip()
        if value == self._query:
            return
        self._query = value
        self._generation += 1
        generation = self._generation
        if not value:
            self._pending_query = None
            self._results = []
            self._busy = False
            self._error = ""
            self._errorKey = ""
            self._errorValues = {}
            self.changed.emit()
            return
        self._results = self._local_results(value)
        self._error = ""
        self._errorKey = ""
        self._errorValues = {}
        self._pending_query = value if len(value) >= 2 else None
        self._busy = self._pending_query is not None
        self.changed.emit()
        if self._pending_query is not None:
            self._debounce.start()

    @Property("QVariantList", notify=changed)
    def results(self) -> list[dict]:
        return self._results

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Property(str, notify=changed)
    def errorKey(self) -> str:
        return self._errorKey

    @Property("QVariantMap", notify=changed)
    def errorValues(self) -> dict:
        return self._errorValues

    def _local_results(self, query: str) -> list[dict]:
        needle = query.casefold()
        mods = []
        instances = []

        for mod in self._mods.all_mods():
            haystack = " ".join([
                str(getattr(mod, "name", "")),
                str(getattr(mod, "author", "")),
                str(getattr(mod, "id", "")),
                str(getattr(mod, "category", "")),
                str(getattr(mod, "description", "")),
                " ".join(str(x) for x in getattr(mod, "tags", []) or []),
            ]).casefold()
            if needle not in haystack:
                continue
            subtitle = str(getattr(mod, "author", "") or "")
            version = str(getattr(mod, "version", "") or "")
            if version:
                subtitle = f"{subtitle} - v{version}" if subtitle else f"v{version}"
            mods.append({
                "kind": "mod", "sectionKey": "nav.mods",
                "id": str(getattr(mod, "id", "")),
                "title": str(getattr(mod, "name", "")),
                "subtitle": subtitle,
                "icon": "package",
            })
            if len(mods) >= 6:
                break

        instance_records = getattr(self._profiles, "all_instances_for_search", lambda: [])()
        for item in instance_records:
            haystack = " ".join([
                str(item.get("name", "")),
                str(item.get("description", "")),
                str(item.get("gameBranch", "")),
                str(item.get("id", "")),
            ]).casefold()
            if needle not in haystack:
                continue
            instances.append({
                "kind": "instance", "sectionKey": "nav.instances",
                "id": str(item.get("id", "")),
                "title": str(item.get("name", "")),
                "subtitle": str(item.get("gameBranch", "")),
                "subtitleKey": "globalSearch.gameInstance" if not str(item.get("gameBranch", "")) else "",
                "icon": "layers",
            })
            if len(instances) >= 6:
                break

        return mods + instances

    def _start_pending_from_timer(self) -> None:
        if self._closed or self._thread is not None or not self._pending_query:
            return
        self._start_pending(self._generation)

    def _start_pending(self, generation: int) -> None:
        if self._closed or self._thread is not None:
            return
        query = self._pending_query
        self._pending_query = None
        if not query:
            self._busy = False
            self.changed.emit()
            return

        def worker() -> None:
            result = None
            error = ""
            try:
                result = fetch_catalog(query, "", "", 1, False)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Global online search failed: %s", exc)
                error = "__I18N__:discover.fetchFailed"
            self._apply_online.emit(generation, result, error)

        self._thread = threading.Thread(target=worker, daemon=True, name="GlobalSearch")
        self._thread.start()

    _apply_online = Signal(int, object, str)

    def _finish_online(self, generation: int, result, error: str) -> None:
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join()
        self._thread = None

        current_generation = generation == self._generation and self._query != ""
        if not self._closed and current_generation:
            current = [r for r in self._results if r.get("kind") != "discover"]
            discover_results = []
            if result is not None:
                for item in result.get("items", [])[:6]:
                    discover_results.append({
                        "kind": "discover", "sectionKey": "nav.discover",
                        "id": str(item.get("slug", "")),
                        "title": str(item.get("title", "")),
                        "subtitle": str(item.get("author", "") or ""),
                        "icon": "compass",
                    })
            mods = [r for r in current if r.get("kind") == "mod"]
            instances = [r for r in current if r.get("kind") == "instance"]
            self._results = mods + discover_results + instances
            if error.startswith("__I18N__:"):
                self._error = ""
                self._errorKey = error.split(":", 1)[1]
                self._errorValues = {}
            else:
                self._error = error
                self._errorKey = ""
                self._errorValues = {}

        if self._closed:
            return

        pending = self._pending_query
        if pending:
            self._busy = True
            self.changed.emit()
            self._debounce.start()
        else:
            self._busy = False
            if current_generation:
                self.changed.emit()

    @Slot(str, str, str)
    def openResult(self, kind: str, item_id: str, title: str) -> None:
        self.resultOpened.emit(kind, item_id, title)

    @Slot()
    def clear(self) -> None:
        self._debounce.stop()
        self.query = ""

    def shutdown(self) -> None:
        self._closed = True
        self._debounce.stop()
        self._pending_query = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

