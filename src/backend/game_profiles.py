"""Centralna biblioteka profili 7 Days to Die (Presets/*.xml).

Profil gracza jest zwykłym plikiem XML tworzonym przez grę. Menedżer nie
zmienia jego zawartości: zbiera profile do ~/.7dtd_modmanager/profiles,
a następnie przypina je do instancji przez symlinki w Presets/ tylko dla V3+.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, Property, QObject, QTimer, Qt, Signal, Slot

from backend import instances as inst
from services import filesystem_service as fs

logger = logging.getLogger(__name__)


def _instance_supports_central_presets(instance: inst.Instance) -> bool:
    """Czy ta wersja 7 Days to Die obsługuje centralne Presets/.

    Stare Alphy/V1/V2 mają własny układ danych i nie powinny dostawać
    zarządzanych dowiązań z ~/.7dtd_modmanager/profiles. Dla V3 i nowszych
    (w tym public/latest) centralne profile są wspierane. Brak game_branch
    oznacza zwykłą współczesną instalację Steam, więc traktujemy ją jak V3+.
    """
    branch = (instance.game_branch or "").strip().casefold()
    if not branch or branch in {"public", "latest", "latest_experimental"}:
        return True
    match = re.match(r"^v(\d+)(?:[._-]|$)", branch)
    if match:
        return int(match.group(1)) >= 3
    if branch.startswith("alpha") or branch.startswith("v1") or branch.startswith("v2"):
        return False
    # Nieznane przyszłe nazewnictwo traktujemy zachowawczo: tylko jawne V3+
    # dostaje centralne profile.
    return False

@dataclass(slots=True)
class GameProfile:
    profile_id: str
    filename: str
    name: str
    path: Path
    global_enabled: bool = False
    assigned_instance_ids: tuple[str, ...] = ()
    source_instance_ids: tuple[str, ...] = ()

    @property
    def assigned_count(self) -> int:
        return len(self.assigned_instance_ids)

    @property
    def source_count(self) -> int:
        return len(self.source_instance_ids)


class GameProfileListModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    FilenameRole = IdRole + 1
    NameRole = IdRole + 2
    GlobalRole = IdRole + 3
    AssignedCountRole = IdRole + 4
    SourceCountRole = IdRole + 5
    AssignedRole = IdRole + 6
    SourcesRole = IdRole + 7

    ROLES = {
        IdRole: b"profileId",
        FilenameRole: b"filename",
        NameRole: b"name",
        GlobalRole: b"globalEnabled",
        AssignedCountRole: b"assignedCount",
        SourceCountRole: b"sourceCount",
        AssignedRole: b"assignedInstanceIds",
        SourcesRole: b"sourceInstanceIds",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[GameProfile] = []

    @property
    def items(self) -> list[GameProfile]:
        return self._items

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        values = {
            self.IdRole: item.profile_id,
            self.FilenameRole: item.filename,
            self.NameRole: item.name,
            self.GlobalRole: item.global_enabled,
            self.AssignedCountRole: item.assigned_count,
            self.SourceCountRole: item.source_count,
            self.AssignedRole: list(item.assigned_instance_ids),
            self.SourcesRole: list(item.source_instance_ids),
        }
        return values.get(role)

    def set_items(self, items: list[GameProfile]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def touch_all(self) -> None:
        if self._items:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._items) - 1, 0))


class GameProfileManager(QObject):
    """Exposed to QML as ``GameProfiles``."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = GameProfileListModel(self)
        self._profiles: dict[str, GameProfile] = {}
        self._global_ids: set[str] = set()
        self._instance_ids: dict[str, set[str]] = {}
        self._instances: list[inst.Instance] = []
        self._ignored_delete: set[str] = set()
        self._refreshing = False
        self._load_state()
        # Profiles live in per-instance directories and may be on a slow or
        # removable filesystem. Build the initial model after the GUI starts.
        # Profile XMLs may live on a removable/slow disk; never block the first frame.
        QTimer.singleShot(1200, self.refresh)

    @Property("QVariant", constant=True)
    def model(self) -> QAbstractListModel:
        return self._model

    @Property(int, notify=changed)
    def count(self) -> int:
        return len(self._model.items)

    @Property(str, constant=True)
    def directory(self) -> str:
        return str(fs.profiles_dir())

    @Slot()
    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._instances = inst.load_instances()
            self._collect_instance_profiles()
            self._load_state()
            self._prune_state()
            self._sync_instance_links()
            self._rebuild_model()
        finally:
            self._refreshing = False

    def _load_state(self) -> None:
        raw = fs.read_json(fs.profile_state_path(), {}) or {}
        global_ids = raw.get("global", []) if isinstance(raw, dict) else []
        per_instance = raw.get("instances", {}) if isinstance(raw, dict) else {}
        ignored = raw.get("ignored", []) if isinstance(raw, dict) else []
        self._global_ids = {str(v) for v in global_ids if v}
        self._instance_ids = {
            str(instance_id): {str(v) for v in ids if v}
            for instance_id, ids in per_instance.items()
            if isinstance(ids, list)
        }
        self._ignored_delete = {str(v) for v in ignored if v}

    def _save_state(self) -> None:
        payload = {
            "schema": 1,
            "global": sorted(self._global_ids),
            "instances": {k: sorted(v) for k, v in sorted(self._instance_ids.items()) if v},
            "ignored": sorted(self._ignored_delete),
        }
        fs.write_json(fs.profile_state_path(), payload)

    @staticmethod
    def _profile_id(filename: str) -> str:
        return hashlib.sha256(filename.casefold().encode("utf-8", "surrogatepass")).hexdigest()[:20]

    def _collect_instance_profiles(self) -> None:
        root = fs.profiles_dir()
        candidates: dict[str, tuple[float, Path, str]] = {}
        source_ids: dict[str, set[str]] = {}
        valid_instance_ids = {i.instance_id for i in self._instances if not i.is_default}

        for instance in self._instances:
            if instance.is_default or instance.data_path is None:
                continue
            presets = instance.data_path / "Presets"
            fs.ensure_dir(presets)
            for path in presets.glob("*.xml"):
                try:
                    # Managed links always point at the central library. They
                    # are outputs of this manager and must not become sources.
                    if path.is_symlink():
                        continue
                    if not path.is_file():
                        continue
                    stat = path.stat()
                    filename = path.name
                    source_ids.setdefault(filename, set()).add(instance.instance_id)
                    current = candidates.get(filename)
                    if current is None or stat.st_mtime > current[0]:
                        candidates[filename] = (stat.st_mtime, path, instance.instance_id)
                except OSError:
                    logger.debug("Cannot read profile %s", path, exc_info=True)

        for filename, (_mtime, source, _instance_id) in candidates.items():
            target = root / filename
            try:
                changed = not target.exists() or target.read_bytes() != source.read_bytes()
                if changed:
                    tmp = target.with_suffix(target.suffix + ".tmp")
                    shutil.copy2(source, tmp)
                    os.replace(tmp, target)
            except OSError:
                logger.warning("Failed to copy profile to the library: %s", filename, exc_info=True)

        self._profiles = {}
        for path in sorted(root.glob("*.xml"), key=lambda p: p.name.casefold()):
            try:
                stat = path.stat()
                if not path.is_file() or path.is_symlink():
                    continue
                filename = path.name
                profile_id = self._profile_id(filename)
                self._profiles[profile_id] = GameProfile(
                    profile_id=profile_id,
                    filename=filename,
                    name=path.stem,
                    path=path,
                    source_instance_ids=tuple(sorted(source_ids.get(filename, set()))),
                )
            except OSError:
                continue

        # Nie pozostawiamy wpisu jako aktywnego po ręcznym usunięciu pliku.
        self._ignored_delete &= set(self._profiles)
        valid_instance_ids &= {i.instance_id for i in self._instances}
        self._instance_ids = {
            iid: ids for iid, ids in self._instance_ids.items() if iid in valid_instance_ids
        }

    def _prune_state(self) -> None:
        profile_ids = set(self._profiles)
        self._global_ids &= profile_ids
        self._instance_ids = {
            instance_id: ids & profile_ids
            for instance_id, ids in self._instance_ids.items()
            if ids & profile_ids
        }
        self._save_state()

    @staticmethod
    def _same_target(target: Path, central: Path) -> bool:
        if not target.is_symlink():
            return False
        try:
            return target.resolve(strict=False) == central.resolve(strict=False)
        except OSError:
            return False

    def _desired_for_instance(self, profile_id: str, instance_id: str) -> bool:
        return profile_id in self._global_ids or profile_id in self._instance_ids.get(instance_id, set())

    def _sync_instance_links(self) -> None:
        managed_targets = {
            p.filename: p for p in self._profiles.values()
        }
        for instance in self._instances:
            if instance.is_default or instance.data_path is None:
                continue
            presets = fs.ensure_dir(instance.data_path / "Presets")

            # V3+ używa centralnej biblioteki profili. W starszych wersjach
            # pozostawiamy Presets lokalne; jeśli wcześniej istniały nasze
            # symlinki, usuwamy wyłącznie te, które wskazują na centralną
            # bibliotekę, nie naruszając fizycznych plików użytkownika.
            if not _instance_supports_central_presets(instance):
                for path in presets.glob("*.xml"):
                    try:
                        central = managed_targets.get(path.name)
                        if central and path.is_symlink() and self._same_target(path, central.path):
                            path.unlink()
                            logger.info(
                                "Removed central Presets link for older version %s: %s",
                                instance.game_branch or "Steam", path)
                    except OSError:
                        logger.warning(
                            "Failed to remove central profile link %s",
                            path, exc_info=True)
                continue

            desired_names = {
                profile.filename
                for profile in self._profiles.values()
                if self._desired_for_instance(profile.profile_id, instance.instance_id)
            }

            # Usuń tylko linki należące do tej centralnej biblioteki.
            for path in presets.glob("*.xml"):
                try:
                    central = managed_targets.get(path.name)
                    if central and path.is_symlink() and not central.path.exists():
                        path.unlink()
                    elif central and path.is_symlink() and path.name not in desired_names and self._same_target(path, central.path):
                        path.unlink()
                except OSError:
                    logger.warning("Failed to remove profile link %s", path, exc_info=True)

            for profile in self._profiles.values():
                if profile.filename not in desired_names:
                    continue
                target = presets / profile.filename
                if target.is_file() and not target.is_symlink():
                    try:
                        # Użytkownik jawnie przypiął profil w UI. Zastępujemy
                        # fizyczny plik zarządzanym linkiem do kopii centralnej.
                        target.unlink()
                    except OSError:
                        logger.warning("Cannot replace profile %s", target, exc_info=True)
                        continue
                if target.exists() or target.is_symlink():
                    continue
                try:
                    target.symlink_to(profile.path)
                except OSError:
                    # Na systemach bez symlinków działamy jako zwykła kopia.
                    try:
                        shutil.copy2(profile.path, target)
                    except OSError:
                        logger.warning("Failed to pin profile %s", profile.filename, exc_info=True)

    def _rebuild_model(self) -> None:
        items: list[GameProfile] = []
        for profile in self._profiles.values():
            assigned = tuple(sorted(
                iid for iid, ids in self._instance_ids.items() if profile.profile_id in ids
            ))
            items.append(GameProfile(
                profile_id=profile.profile_id,
                filename=profile.filename,
                name=profile.name,
                path=profile.path,
                global_enabled=profile.profile_id in self._global_ids,
                assigned_instance_ids=assigned,
                source_instance_ids=profile.source_instance_ids,
            ))
        items.sort(key=lambda p: p.name.casefold())
        self._model.set_items(items)
        self.changed.emit()

    def _apply(self, profile_id: str) -> None:
        self._save_state()
        self._sync_instance_links()
        self._rebuild_model()

    def _profile(self, profile_id: str) -> GameProfile | None:
        return self._profiles.get(str(profile_id))

    @Slot(str, bool)
    def setGlobalEnabled(self, profile_id: str, enabled: bool) -> None:
        profile = self._profile(profile_id)
        if profile is None:
            return
        if enabled:
            self._global_ids.add(profile.profile_id)
        else:
            self._global_ids.discard(profile.profile_id)
        self._apply(profile.profile_id)

    @Slot(str, str, bool)
    def setInstanceEnabled(self, profile_id: str, instance_id: str, enabled: bool) -> None:
        profile = self._profile(profile_id)
        instance = inst.find_instance(self._instances, instance_id)
        if (profile is None or instance is None or instance.is_default
                or not _instance_supports_central_presets(instance)):
            return
        ids = self._instance_ids.setdefault(instance_id, set())
        if enabled:
            ids.add(profile.profile_id)
        else:
            ids.discard(profile.profile_id)
        if not ids:
            self._instance_ids.pop(instance_id, None)
        self._apply(profile.profile_id)

    @Slot(str)
    def removeProfile(self, profile_id: str) -> None:
        profile = self._profile(profile_id)
        if profile is None:
            return
        # Usunięcie jest jawne: profil znika z centralnej biblioteki oraz z
        # Presets każdej zarządzanej instancji. Użytkownik nadal może potem
        # stworzyć nowy profil w grze, który zostanie wykryty jako nowy plik.
        for instance in self._instances:
            if instance.is_default or instance.data_path is None:
                continue
            target = instance.data_path / "Presets" / profile.filename
            try:
                if target.exists() or target.is_symlink():
                    target.unlink()
            except OSError:
                logger.warning("Failed to delete profile %s from %s", profile.filename, instance.name, exc_info=True)
        try:
            profile.path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to delete profile %s: %s", profile.filename, exc)
            return
        self._global_ids.discard(profile.profile_id)
        self._instance_ids = {iid: ids - {profile.profile_id} for iid, ids in self._instance_ids.items()}
        self._instance_ids = {iid: ids for iid, ids in self._instance_ids.items() if ids}
        self._save_state()
        self.refresh()

    @Slot(str, result="QVariantList")
    def instanceOptions(self, profile_id: str) -> list:
        profile = self._profile(profile_id)
        if profile is None:
            return []
        return [
            {
                "instanceId": instance.instance_id,
                "name": instance.name,
                "enabled": profile.profile_id in self._instance_ids.get(instance.instance_id, set()),
                "effective": profile.profile_id in self._global_ids
                or profile.profile_id in self._instance_ids.get(instance.instance_id, set()),
                "global": profile.profile_id in self._global_ids,
                "supported": _instance_supports_central_presets(instance),
            }
            for instance in self._instances
            if not instance.is_default
        ]
