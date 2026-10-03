"""Conflict detection between enabled mods.

Two ENABLED mods conflict when they modify the same game file (e.g. both
rewrite ``loot.xml``).  The detector recomputes the pair list whenever the
mod list changes and exposes it to QML as ``Conflicts``.
"""

from __future__ import annotations

from services.i18n_message import message as i18n_message

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    QObject,
    Qt,
    Signal,
    Slot,
)

from models.mod import Mod

MAX_PAIRS = 24


class ConflictListModel(QAbstractListModel):
    ModAIdRole = Qt.ItemDataRole.UserRole + 1
    ModBIdRole = ModAIdRole + 1
    ModANameRole = ModAIdRole + 2
    ModBNameRole = ModAIdRole + 3
    FileRole = ModAIdRole + 4
    ReasonRole = ModAIdRole + 5
    ModACategoryRole = ModAIdRole + 6
    ModBCategoryRole = ModAIdRole + 7

    ROLES = {
        ModAIdRole: b"modAId",
        ModBIdRole: b"modBId",
        ModANameRole: b"modAName",
        ModBNameRole: b"modBName",
        FileRole: b"fileText",
        ReasonRole: b"reasonText",
        ModACategoryRole: b"modACategory",
        ModBCategoryRole: b"modBCategory",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pairs: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._pairs)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._pairs)):
            return None
        pair = self._pairs[index.row()]
        return pair.get(self.ROLES.get(role, b"").decode(), None)

    def set_pairs(self, pairs: list[dict]) -> None:
        self.beginResetModel()
        self._pairs = list(pairs)
        self.endResetModel()


class ConflictDetector(QObject):
    """Exposed to QML as ``Conflicts``."""

    conflictsChanged = Signal()
    resolveRequested = Signal(str, str)   # keepId, disableId

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = ConflictListModel(self)
        self._pairs: list[dict] = []
        self._affected_ids: set[str] = set()
        self._partners: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ #
    @Property("QVariant", constant=True)
    def model(self) -> QAbstractListModel:
        return self._model

    @Property(int, notify=conflictsChanged)
    def count(self) -> int:
        return len(self._pairs)

    @Property(int, notify=conflictsChanged)
    def affectedCount(self) -> int:
        return len(self._affected_ids)

    @property
    def affected_ids(self) -> set[str]:
        return self._affected_ids

    # ------------------------------------------------------------------ #
    def pair_keys(self) -> list[tuple[str, str]]:
        return [(p["modAId"], p["modBId"]) for p in self._pairs]

    def partners_of(self, mod_id: str) -> list[str]:
        return list(self._partners.get(mod_id, []))

    # ------------------------------------------------------------------ #
    def recompute(self, mods: list[Mod]) -> list[dict]:
        """Rebuild the conflict list from the current mod set."""
        by_file: dict[str, list[Mod]] = {}
        for mod in mods:
            if not mod.enabled:
                continue
            for file_name in mod.modified_files:
                by_file.setdefault(file_name, []).append(mod)

        pair_map: dict[tuple[str, str], dict] = {}
        partners: dict[str, set[str]] = {}
        for file_name, file_mods in sorted(by_file.items()):
            if len(file_mods) < 2:
                continue
            file_mods = sorted(file_mods, key=lambda m: m.name.casefold())
            for i in range(len(file_mods)):
                for j in range(i + 1, len(file_mods)):
                    a, b = file_mods[i], file_mods[j]
                    key = (a.id, b.id)
                    partners.setdefault(a.id, set()).add(b.name)
                    partners.setdefault(b.id, set()).add(a.name)
                    if key in pair_map:
                        pair_map[key]["fileText"] += f", {file_name}"
                        continue
                    pair_map[key] = {
                        "modAId": a.id,
                        "modBId": b.id,
                        "modAName": a.name,
                        "modBName": b.name,
                        "fileText": file_name,
                        "reasonText": i18n_message("conflicts.card.reasonDetails", {"file": file_name}),
                        "modACategory": a.category,
                        "modBCategory": b.category,
                    }

        pairs = sorted(pair_map.values(),
                       key=lambda p: (p["modAName"], p["modBName"]))[:MAX_PAIRS]
        self._pairs = pairs
        self._partners = {k: sorted(v) for k, v in partners.items()}
        self._affected_ids = set()
        for pair in pairs:
            self._affected_ids.add(pair["modAId"])
            self._affected_ids.add(pair["modBId"])
        self._model.set_pairs(pairs)
        self.conflictsChanged.emit()
        return pairs

    # ------------------------------------------------------------------ #
    @Slot(str, str)
    def resolveKeep(self, keep_id: str, disable_id: str) -> None:
        """Convenience slot - the QML page wires this to ModManager.setEnabled."""
        self.resolveRequested.emit(keep_id, disable_id)
