"""Kopie zapasowe instancji - manager wystawiony do QML jako ``Modpacks``
(etap 19: NOWA semantyka - pełna kopia 1:1, jedna kopia na instancję).

Logika plikowa w backend/modpacks.py; manager dodaje warstwę UI:
- operacje długo-trwające (create/update/restore/delete) w wątkach,
  z toastami (nigdy w wątku GUI),
- twarda blokada mutujących operacji gdy gra działa (dotykają danych
  czytanych przez grę),
- karty kopii (instancja, rozmiar, daty utworzenia/aktualizacji).

Przywrócenie kopii ODTWARZA instancję 1:1 (także po jej usunięciu) -
profile.refreshFromDisk() po udanej operacji.
"""

from __future__ import annotations

import json
import logging
import threading

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    QObject,
    Qt,
    Signal,
    Slot,
)

from backend import modpacks
from backend.events import EventBus
from backend.game_process import is_game_running
from backend.profile_manager import ProfileManager
from services import filesystem_service as fs

logger = logging.getLogger(__name__)


class BackupListModel(QAbstractListModel):
    InstanceIdRole = Qt.ItemDataRole.UserRole + 1
    InstanceNameRole = InstanceIdRole + 1
    PathDisplayRole = InstanceIdRole + 2
    SizeTextRole = InstanceIdRole + 3
    ItemCountRole = InstanceIdRole + 4
    CreatedTextRole = InstanceIdRole + 5
    UpdatedTextRole = InstanceIdRole + 6

    ROLES = {
        InstanceIdRole: b"instanceId",
        InstanceNameRole: b"packName",
        PathDisplayRole: b"packPath",
        SizeTextRole: b"packSizeText",
        ItemCountRole: b"packItemCount",
        CreatedTextRole: b"packCreatedText",
        UpdatedTextRole: b"packUpdatedText",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[modpacks.BackupRecord] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        attr = {
            self.InstanceIdRole: record.instance_id,
            self.InstanceNameRole: record.instance_name,
            self.PathDisplayRole: fs.display_path(record.path),
            self.SizeTextRole: modpacks.format_size(record.size_bytes),
            self.ItemCountRole: record.item_count,
            self.CreatedTextRole: modpacks.format_when(record.created_at),
            self.UpdatedTextRole: modpacks.format_when(record.updated_at),
        }
        return attr.get(role)

    @property
    def records(self) -> list[modpacks.BackupRecord]:
        return self._records

    def set_records(self, records: list[modpacks.BackupRecord]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def row_of(self, instance_id: str) -> int:
        for row, record in enumerate(self._records):
            if record.instance_id == instance_id:
                return row
        return -1


class ModpackManager(QObject):
    """Exposed to QML as ``Modpacks`` - kopie zapasowe instancji."""

    modpacksChanged = Signal()
    busyChanged = Signal()
    operationFinished = Signal(str, str)   # instance_id, summary ("" = ok)
    backupRestored = Signal(str)           # instance_id - wyemitowany z wątku

    def __init__(self, profiles: ProfileManager, bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._profiles = profiles
        self._bus = bus
        self._model = BackupListModel(self)
        self._busy = False
        self.operationFinished.connect(self._on_operation_finished)
        self.backupRestored.connect(self._on_backup_restored)
        modpacks.migrate_legacy_layout()
        self.refresh()

    # ------------------------------------------------------------------ #
    @Property("QVariant", constant=True)
    def model(self) -> QAbstractListModel:
        return self._model

    @Property(int, notify=modpacksChanged)
    def count(self) -> int:
        return len(self._model.records)

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _reload(self) -> None:
        self._model.set_records(modpacks.load_backups())
        self.modpacksChanged.emit()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.busyChanged.emit()

    def _record_for(self, instance_id: str):
        return next(
            (r for r in modpacks.load_backups() if r.instance_id == instance_id), None)

    def _instance_or_toast(self, instance_id: str):
        """Instancja z rejestru albo None (z toastem) - instancja musi mieć
        izolowany katalog danych (domyślna nie ma czego kopiować)."""
        instance = self._profiles.get_instance(instance_id)
        if instance is None:
            self._bus.toastKey("backups.error.instanceNotFound", {}, "error")
            return None
        if instance.is_default:
            self._bus.toastKey("backups.warning.defaultInstance", {}, "warning")
            return None
        return instance

    def _guard_game(self) -> bool:
        """True = zablokowano (gra działa) - kopiujemy/przywracamy dane
        czytane przez grę."""
        if is_game_running():
            self._bus.toastKey("backups.warning.gameRunning", {}, "warning")
            return True
        return False

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #
    @Slot()
    def refresh(self) -> None:
        self._reload()
        self.modpacksChanged.emit()

    @Slot(str, result=bool)
    def createBackup(self, instance_id: str) -> bool:
        """Pełna KOPIA danych instancji. JEDNA kopia na instancję - druga
        próba jest blokowana (do tego służą Aktualizuj i Przywróć)."""
        instance = self._instance_or_toast(instance_id)
        if instance is None or self._busy:
            return False
        if self._guard_game():
            return False

        self._set_busy(True)
        instance_snapshot = instance

        def worker() -> None:
            try:
                record = modpacks.create_backup_from_instance(instance_snapshot)
                self.operationFinished.emit(
                    instance_id,
                    "__I18N__:backups.success.created|" + json.dumps({
                        "name": record.instance_name,
                        "size": modpacks.format_size(record.size_bytes),
                    }, ensure_ascii=False))
            except FileExistsError as exc:
                self.operationFinished.emit(instance_id, "__I18N__:backups.error.operation|" + json.dumps({"error": str(exc)}, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Backup creation failed")
                self.operationFinished.emit(instance_id, "__I18N__:backups.error.operation|" + json.dumps({"error": str(exc)}, ensure_ascii=False))

        threading.Thread(target=worker, daemon=True).start()
        return True

    @Slot(str)
    def updateBackup(self, instance_id: str) -> None:
        """Odświeża kopię bieżącym stanem instancji (pełna kopia 1:1)."""
        record = self._record_for(instance_id)
        if record is None or self._busy:
            return
        instance = self._profiles.get_instance(instance_id)
        if instance is None:
            self._bus.toastKey("backups.error.backupInstanceNotFound", {}, "error")
            return
        if self._guard_game():
            return

        self._set_busy(True)

        def worker() -> None:
            try:
                updated = modpacks.update_backup_from_instance(record, instance)
                self.operationFinished.emit(
                    instance_id,
                    "__I18N__:backups.success.updated|" + json.dumps({
                        "name": updated.instance_name,
                        "size": modpacks.format_size(updated.size_bytes),
                    }, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Backup update failed")
                self.operationFinished.emit(instance_id, "__I18N__:backups.error.operation|" + json.dumps({"error": str(exc)}, ensure_ascii=False))

        threading.Thread(target=worker, daemon=True).start()
        return

    @Slot(str)
    def restoreBackup(self, instance_id: str) -> None:
        """Przywraca kopię 1:1: czyści dane instancji i odtwarza zawartość
        kopii. Usunięta instancja jest ODTWARZANA z metadanych kopii."""
        record = self._record_for(instance_id)
        if record is None or self._busy:
            return
        if self._guard_game():
            return

        self._set_busy(True)

        def worker() -> None:
            try:
                target = modpacks.restore_backup(record)
                # odświeżenie rejestru instancji (odtworzonych) NA GUI -
                # emit z wątku trafia do slotu w GUI przez kolejkę
                self.backupRestored.emit(instance_id)
                self.operationFinished.emit(
                    instance_id,
                    "__I18N__:backups.success.restored|" + json.dumps({"name": target.name}, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Backup restore failed")
                self.operationFinished.emit(instance_id, "__I18N__:backups.error.operation|" + json.dumps({"error": str(exc)}, ensure_ascii=False))

        threading.Thread(target=worker, daemon=True).start()
        return

    def _on_backup_restored(self, instance_id: str) -> None:
        self._profiles.refreshFromDisk()

    @Slot(str)
    def deleteBackup(self, instance_id: str) -> None:
        record = self._record_for(instance_id)
        if record is None or self._busy:
            return

        self._set_busy(True)

        def worker() -> None:
            try:
                modpacks.delete_backup(record)
                self.operationFinished.emit(
                    instance_id,
                    "__I18N__:backups.success.deleted|" + json.dumps({"name": record.instance_name}, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Backup delete failed")
                self.operationFinished.emit(instance_id, "__I18N__:backups.error.operation|" + json.dumps({"error": str(exc)}, ensure_ascii=False))

        threading.Thread(target=worker, daemon=True).start()
        return

    def _on_operation_finished(self, instance_id: str, summary: str) -> None:
        self._set_busy(False)
        self._reload()
        if summary.startswith("__I18N__:"):
            try:
                key, raw_values = summary[len("__I18N__:"):].split("|", 1)
                values = json.loads(raw_values) if raw_values else {}
            except (ValueError, json.JSONDecodeError):
                self._bus.toast(summary, "error")
            else:
                level = "error" if key.startswith("backups.error.") else "success"
                self._bus.toastKey(key, values, level)
        elif summary.startswith("error:"):
            self._bus.toast(summary, "error")
        elif summary:
            self._bus.toast(summary, "success")
