"""Instancje gry: rejestr, karty, aktywacja, uruchamianie, build Mods.

Etap 6 migracji: dawny "profil = płaski zapis mod_states" staje się
INSTANCJĄ (backend/instances.py) - katalog danych + flagi startowe +
launcher Steam + generowany folder Mods. Karty zakładki Profile pokazują
instancje z rejestru instances.json; aktywacja modów jest globalna
(zakładka Mody + ActivationState), a per-instancja wykluczenia/włączenia
działają w warstwie danych (UI wykluczeń = osobny krok zaraz po etapie 6,
zob. D22).

Kontrakt QML zachowany wstecznie (create/rename/remove/duplicate/activate/
profileDetails + role profileId/name/...), z dodanymi rolami i slotami
instancji (dataDir, flagi, isRunning, launchInstance, buildModsFor,
launchActive). `create(...)` w starej sygnaturze tworzy instancję z
 sugerowaną ścieżką danych (instances/<slug>).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    QObject,
    Qt,
    Signal,
    Slot,
    QTimer,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from backend import instances as inst
from backend import library
from backend import library_ops
from backend.events import EventBus
from backend.mod_manager import ModManager
from backend.game_detector import GameDetector
from backend.modinfo import find_modinfo, parse_modinfo
from models.profile import Profile
from services.i18n_message import message as i18n_message
from services import filesystem_service as fs

logger = logging.getLogger(__name__)

_COLOR_TAGS = ["#FF7A38", "#5CA9FF", "#34D399", "#A78BFA", "#F5B841", "#F472B6"]


class ProfileListModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = IdRole + 1
    DescriptionRole = IdRole + 2
    ModCountRole = IdRole + 3
    EnabledCountRole = IdRole + 4
    CreatedTextRole = IdRole + 5
    IsActiveRole = IdRole + 6
    ColorTagRole = IdRole + 7
    DataDirRole = IdRole + 8
    IsDefaultRole = IdRole + 9
    FlagsTextRole = IdRole + 10
    IsRunningRole = IdRole + 11
    NoeosRole = IdRole + 12
    NoeacRole = IdRole + 13
    SkipNewsRole = IdRole + 14
    SkipIntroRole = IdRole + 15
    GameBranchRole = IdRole + 16
    FavoriteRole = IdRole + 17

    ROLES = {
        IdRole: b"profileId",
        NameRole: b"name",
        DescriptionRole: b"description",
        ModCountRole: b"modCount",
        EnabledCountRole: b"enabledCount",
        CreatedTextRole: b"createdText",
        IsActiveRole: b"isActive",
        ColorTagRole: b"colorTag",
        DataDirRole: b"dataDir",
        IsDefaultRole: b"isDefault",
        FlagsTextRole: b"flagsText",
        IsRunningRole: b"isRunning",
        NoeosRole: b"noeos",
        NoeacRole: b"noeac",
        SkipNewsRole: b"skipNews",
        SkipIntroRole: b"skipIntro",
        GameBranchRole: b"gameBranch",
        FavoriteRole: b"favorite",
    }

    def __init__(self, manager: "ProfileManager", parent=None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._profiles: list[Profile] = []
        self.active_id: str = ""

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._profiles)

    def roleNames(self) -> dict:
        return dict(self.ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._profiles)):
            return None
        profile = self._profiles[index.row()]
        if role == self.IsActiveRole:
            return profile.id == self.active_id
        if role == self.IsRunningRole:
            return profile.id == self._manager.running_instance_id
        if role in (self.ModCountRole, self.EnabledCountRole):
            total, enabled = self._manager.instance_mod_counts(profile.id)
            return total if role == self.ModCountRole else enabled
        attr = {
            self.IdRole: profile.id,
            self.NameRole: (i18n_message("instances.defaultName")
                            if profile.is_default else profile.name),
            self.DescriptionRole: profile.description,
            self.CreatedTextRole: profile.created_text,
            self.ColorTagRole: profile.color_tag,
            self.DataDirRole: profile.data_dir_display,
            self.IsDefaultRole: profile.is_default,
            self.FlagsTextRole: " ".join(self._manager.flags_summary(profile.id)),
            self.NoeosRole: profile.flag_noeos,
            self.NoeacRole: profile.flag_noeac,
            self.SkipNewsRole: profile.flag_skip_news_screen,
            self.SkipIntroRole: profile.flag_skip_intro,
            self.GameBranchRole: profile.game_branch,
            self.FavoriteRole: profile.favorite,
        }
        return attr.get(role)

    # ------------------------------------------------------------------ #
    @property
    def profiles(self) -> list[Profile]:
        return self._profiles

    def set_profiles(self, profiles: list[Profile], active_id: str) -> None:
        self.beginResetModel()
        self._profiles = list(profiles)
        self.endResetModel()
        self.active_id = active_id

    def refresh_active(self, active_id: str) -> None:
        self.active_id = active_id
        self.touch_all()

    def touch_all(self) -> None:
        if self._profiles:
            top = self.index(0, 0)
            bottom = self.index(len(self._profiles) - 1, 0)
            self.dataChanged.emit(top, bottom)

    def _row(self, profile_id: str) -> int:
        for row, profile in enumerate(self._profiles):
            if profile.id == profile_id:
                return row
        return -1

    def row_changed(self, profile_id: str) -> None:
        row = self._row(profile_id)
        if row >= 0:
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)


class ProfileManager(QObject):
    """Exposed to QML as ``Profiles`` - rejestr instancji gry."""

    SCHEMA = 3  # profiles.json holds only {"activeId"} now

    instancesChanged = Signal()
    activeInstanceChanged = Signal()
    runningInstanceChanged = Signal()
    dataWipeStarted = Signal(str)
    dataWipeFinished = Signal(str, str)   # instance name, error ("" = ok)
    instanceBuilt = Signal(str, str)   # instance_id, summary
    instanceLaunched = Signal(str)     # instance_id
    instanceCreated = Signal(str)      # instance_id
    instanceRemoved = Signal(str)      # instance_id
    launchInProgressChanged = Signal()

    def __init__(self, mods: ModManager, bus: EventBus, game: GameDetector,
                 parent=None) -> None:
        super().__init__(parent)
        self._mods = mods
        self._bus = bus
        self._game = game
        self._instances: list[inst.Instance] = []
        self._model = ProfileListModel(self)
        self._active_id = inst.DEFAULT_INSTANCE_ID
        self._running_id = ""
        self._launch_in_progress = False

        self._game.runningChanged.connect(self._refresh_running)
        mods.countsChanged.connect(self._model.touch_all)
        self.instanceBuilt.connect(self._on_instance_built)
        self.dataWipeFinished.connect(self._on_data_wipe_finished)

        # Initial registry/profile scan can touch a user-selected directory.
        # Defer it until the Qt event loop is alive so a slow filesystem never
        # blocks the first window from appearing.
        # Give Qt time to paint the first frame before touching the instance registry.
        QTimer.singleShot(900, self._load)

    # ------------------------------------------------------------------ #
    # registry / model
    # ------------------------------------------------------------------ #
    @Slot()
    def stopGame(self) -> None:
        """Zatrzymuje proces gry (UI potwierdza przed wywołaniem)."""
        self._game.stopRunningGame()

    @Slot()
    def refreshFromDisk(self) -> None:
        """Przeładuj rejestr instancji z dysku (po operacjach z wątków
        roboczych, np. tworzenie instancji dla zestawu modów - etap 18)."""
        self._load()

    def _load(self) -> None:
        self._instances = inst.load_instances()
        stored = fs.read_json(fs.profiles_path(), {}) or {}
        active = stored.get("activeId") if isinstance(stored, dict) else None
        if not inst.find_instance(self._instances, str(active or "")):
            default = inst.default_instance(self._instances)
            active = default.instance_id if default else inst.DEFAULT_INSTANCE_ID
        self._active_id = str(active)
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self._refresh_running()
        self.instancesChanged.emit()
        self.activeInstanceChanged.emit()

    def get_instance(self, instance_id: str) -> inst.Instance | None:
        """Instancja z rejestru po id (dla innych managerów, np. Modpacks)."""
        return inst.find_instance(self._instances, instance_id)

    def _to_profile(self, instance: inst.Instance, index: int = 0) -> Profile:
        return Profile(
            id=instance.instance_id,
            name=instance.name,
            description=instance.description or (
                i18n_message("instances.defaultDescription")
                if instance.is_default else ""),
            data_dir=instance.data_dir,
            flag_noeos=instance.flag_noeos,
            flag_noeac=instance.flag_noeac,
            flag_skip_news_screen=instance.flag_skip_news_screen,
            flag_skip_intro=instance.flag_skip_intro,
            created_at=self._parse_created(instance.created_at),
            color_tag=_COLOR_TAGS[index % len(_COLOR_TAGS)],
            game_branch=instance.game_branch,
            favorite=instance.favorite,
        )

    @staticmethod
    def _parse_created(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()

    def _persist_active(self) -> None:
        fs.write_json(fs.profiles_path(), {"schema": self.SCHEMA, "activeId": self._active_id})

    def _instance(self, instance_id: str) -> inst.Instance | None:
        return inst.find_instance(self._instances, instance_id)

    def instance_mod_counts(self, instance_id: str) -> tuple[int, int]:
        """(łącznie w Bibliotece, włączonych dla instancji) - live."""
        entries = self._mods.all_mods()
        state = library.load_activation_state()
        return len(entries), len(state.enabled_for_instance(instance_id))

    def flags_summary(self, instance_id: str) -> list[str]:
        instance = self._instance(instance_id)
        return instance.flags_summary() if instance else []

    # ------------------------------------------------------------------ #
    # properties
    # ------------------------------------------------------------------ #
    @Property("QVariant", constant=True)
    def model(self) -> QAbstractListModel:
        return self._model

    @Property(int, notify=instancesChanged)
    def count(self) -> int:
        return len(self._model.profiles)

    @Property(str, notify=activeInstanceChanged)
    def activeProfileId(self) -> str:
        return self._active_id

    @Property(str, notify=activeInstanceChanged)
    def activeProfileName(self) -> str:
        profile = self._model.profiles and next(
            (p for p in self._model.profiles if p.id == self._active_id), None)
        if profile is None or profile.is_default:
            return i18n_message("instances.defaultName")
        return profile.name

    @Property(str, notify=runningInstanceChanged)
    def runningInstanceId(self) -> str:
        return self._running_id

    @property
    def running_instance_id(self) -> str:
        return self._running_id

    @Property(str, notify=runningInstanceChanged)
    def runningInstanceName(self) -> str:
        instance = self._instance(self._running_id)
        return (i18n_message("instances.defaultName") if instance and instance.is_default else instance.name) if instance else ""

    @Property(bool, notify=launchInProgressChanged)
    def launchInProgress(self) -> bool:
        return self._launch_in_progress

    # ------------------------------------------------------------------ #
    # running-instance watch (stage 6; feeds off GameDetector's /proc scan)
    # ------------------------------------------------------------------ #
    def _refresh_running(self) -> None:
        # gra NIE działa -> żadna instancja nie jest "działająca";
        # gra działa BEZ -UserDataFolder -> działa instancja domyślna;
        # gra z flagą -> pierwsza pasująca ścieżka wskazuje instancję
        if not self._game.isRunning:
            running_id = ""
        else:
            folders = [f for f in self._game.runningUserDataList if f]
            if not folders:
                default = inst.default_instance(self._instances)
                running_id = default.instance_id if default else ""
            else:
                match = inst.match_instance_by_user_data_folder(folders[0], self._instances)
                running_id = match.instance_id if match else ""
        if running_id != self._running_id:
            self._running_id = running_id
        if running_id:
            # Uruchomiona instancja zawsze staje się aktywna. Dotyczy to także
            # startu gry ręcznie poza menedżerem, jeśli proces daje się powiązać
            # z jednym z katalogów UserDataFolder.
            if running_id != self._active_id:
                self._active_id = running_id
                self._persist_active()
                self._model.refresh_active(running_id)
                self.activeInstanceChanged.emit()
            if self._launch_in_progress:
                self._launch_in_progress = False
                self.launchInProgressChanged.emit()
        self.runningInstanceChanged.emit()
        self._model.touch_all()

    def _save_registry(self) -> None:
        inst.save_instances(self._instances)
        self._persist_active()

    # ------------------------------------------------------------------ #
    # slots (called from QML)
    # ------------------------------------------------------------------ #
    @Slot(str)
    def activate(self, profile_id: str) -> None:
        if self._instance(profile_id) is None:
            return
        if self._game.isRunning or self._launch_in_progress:
            self._bus.toastKey("toast.instances.cannotSwitchRunning", {}, "warning")
            return
        if profile_id == self._active_id:
            return
        self._active_id = profile_id
        self._persist_active()
        self._model.refresh_active(profile_id)
        self.activeInstanceChanged.emit()
        profile = next((p for p in self._model.profiles if p.id == profile_id), None)
        self._bus.toastKey("toast.instances.active", {"name": profile.name if profile else profile_id}, "success")

    @Slot(str, str, str, bool, bool, bool, bool, str, result=bool)
    def createInstance(self, name: str, data_dir: str, description: str,
                       noeos: bool, noeac: bool, skip_news_screen: bool,
                       skip_intro: bool, game_branch: str = "") -> bool:
        """Pełny slot tworzenia instancji (dialog edycji, Krok C)."""
        if self._game.isRunning:
            self._bus.toastKey("toast.instances.cannotCreateRunning", {}, "warning")
            return False
        try:
            instance = inst.create_instance(
                name, data_dir,
                noeos=noeos, noeac=noeac,
                skip_news_screen=skip_news_screen, skip_intro=skip_intro,
                instances=self._instances,
                description=description,
                game_branch=game_branch,
            )
        except inst.InstanceError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "error")
            return False
        self._instances = self._instances + [instance]
        self._save_registry()
        # katalog danych instancji powstaje od razu (pusty) - potem jest
        # targetem paczek/restore i user widzy go w systemie plików
        if not instance.is_default:
            fs.ensure_dir(instance.data_path)
            fs.ensure_dir(instance.data_path / "Presets")
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self.instanceCreated.emit(instance.instance_id)
        self._notify_counts()
        self._bus.toastKey("toast.instances.created", {"name": instance.name}, "success")
        return True

    @Slot(str, str, bool)
    def create(self, name: str, description: str, copy_current: bool) -> None:
        """Legacy signature from the old modal - creates an ISOLATED
        instance with a suggested data dir (instances/<slug>)."""
        del copy_current  # old "copy current mod states" has no meaning in the instance model
        self.createInstance(
            name, str(inst.suggest_data_dir_for_name(name)), description,
            True, False, True, True)

    @Slot(str)
    def toggleFavorite(self, profile_id: str) -> None:
        """Przełącza ulubioną instancję i utrzymuje ulubione na początku listy."""
        instance = self._instance(profile_id)
        if instance is None:
            return
        instance.favorite = not instance.favorite
        # stable: ulubione na górze, pozostałe zachowują dotychczasową kolejność
        self._instances = sorted(self._instances, key=lambda i: not i.favorite)
        self._save_registry()
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self._bus.toastKey("toast.instances.favoriteAdded" if instance.favorite else "toast.instances.favoriteRemoved", {"name": instance.name}, "success" if instance.favorite else "info")

    @Slot(str, str)
    def rename(self, profile_id: str, new_name: str) -> None:
        instance = self._instance(profile_id)
        new_name = (new_name or "").strip()
        if instance is None or not new_name or new_name == instance.name:
            return
        error = inst.validate_instance_name(new_name, self._instances, current_id=profile_id)
        if error:
            self._bus.toastKey("common.operationFailed", {"error": error}, "error")
            return
        instance.name = new_name
        self._save_registry()
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self.activeInstanceChanged.emit()
        self._bus.toastKey("toast.instances.rename", {"name": new_name}, "info")

    @Slot(str)
    def duplicate(self, profile_id: str) -> None:
        if self._game.isRunning:
            self._bus.toastKey("toast.instances.cannotDuplicateRunning", {}, "warning")
            return
        instance = self._instance(profile_id)
        if instance is None:
            return
        base = f"{instance.name} (kopia)"
        name = base
        counter = 2
        while inst.validate_instance_name(name, self._instances):
            name = f"{base} {counter}"
            counter += 1
        data_dir = str(inst.suggest_data_dir_for_name(name))
        try:
            copy = inst.create_instance(
                name, data_dir,
                noeos=instance.flag_noeos, noeac=instance.flag_noeac,
                skip_news_screen=instance.flag_skip_news_screen,
                skip_intro=instance.flag_skip_intro,
                description=instance.description,
                game_branch=instance.game_branch,
                instances=self._instances,
            )
        except inst.InstanceError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "error")
            return
        self._instances = self._instances + [copy]
        self._save_registry()
        if not copy.is_default:
            fs.ensure_dir(copy.data_path / "Presets")
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self.instanceCreated.emit(copy.instance_id)
        self._bus.toastKey("toast.instances.duplicated", {"name": copy.name}, "info")

    @Slot(str, bool)
    def remove(self, profile_id: str, remove_data: bool = False) -> None:
        instance = self._instance(profile_id)
        if instance is None:
            return
        if instance.favorite:
            self._bus.toastKey("toast.instances.favoriteDeleteBlocked", {"name": instance.name}, "warning")
            return
        # Overhaul jest przechowywany wyłącznie w tej instancji. Usunięcie
        # takiej instancji sprząta również jej katalog danych, niezależnie od
        # opcjonalnego checkboxa dla zwykłych instancji.
        remove_data = remove_data or instance.is_overhaul
        try:
            self._instances = inst.delete_instance(self._instances, profile_id)
        except inst.InstanceError as exc:
            self._bus.toastKey("common.operationFailed", {"error": str(exc)}, "error")
            return
        if self._active_id == profile_id:
            default = inst.default_instance(self._instances)
            self._active_id = default.instance_id if default else inst.DEFAULT_INSTANCE_ID
        self._save_registry()
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self.activeInstanceChanged.emit()
        self.instanceRemoved.emit(profile_id)
        self._bus.toastKey("toast.instances.deleted", {"name": instance.name}, "info")

        if remove_data and instance.data_path is not None:
            # zgoda uzytkownika na kasowanie folderu danych - w watku (bywa
            # duzy); bledy tylko w toaście, rejestru nie cofamy
            data_path = instance.data_path

            def wipe_worker() -> None:
                try:
                    from backend.fileops import remove_tree_with_progress
                    remove_tree_with_progress(data_path)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Instance data wipe failed")
                    self.dataWipeFinished.emit(instance.name, f"error:{exc}")
                    return
                self.dataWipeFinished.emit(instance.name, "")

            self.dataWipeStarted.emit(instance.name)
            threading.Thread(target=wipe_worker, daemon=True).start()

    def _on_data_wipe_finished(self, name: str, error: str) -> None:
        if error:
            self._bus.toastKey("toast.instances.dataDeleteFailed", {"name": name, "error": error}, "error")
        else:
            self._bus.toastKey("toast.instances.dataDeleted", {"name": name}, "info")

    @Slot(str, result="QVariantMap")
    def profileDetails(self, profile_id: str):
        instance = self._instance(profile_id)
        if instance is None:
            return {}
        total, enabled = self.instance_mod_counts(profile_id)
        profile = next((p for p in self._model.profiles if p.id == profile_id), None)
        return {
            "id": instance.instance_id,
            "name": instance.name,
            "description": instance.description,
            "dataDir": instance.data_dir,
            "dataDirDisplay": profile.data_dir_display if profile else instance.data_dir,
            "isDefault": instance.is_default,
            "noeos": instance.flag_noeos,
            "noeac": instance.flag_noeac,
            "skipNewsScreen": instance.flag_skip_news_screen,
            "skipIntro": instance.flag_skip_intro,
            "flagsSummary": instance.flags_summary(),
            "launchCommandPreview": instance.launch_command_preview(),
            "modCount": total,
            "enabledCount": enabled,
            "createdText": profile.created_text if profile else instance.created_at,
            "isActive": instance.instance_id == self._active_id,
            "isRunning": instance.instance_id == self._running_id,
            "colorTag": profile.color_tag if profile else _COLOR_TAGS[0],
            "gameBranch": instance.game_branch,
        }

    # ------------------------------------------------------------------ #
    # launch / build (stage 6)
    # ------------------------------------------------------------------ #
    @Slot(str, result=str)
    def suggestDataDir(self, name: str) -> str:
        """Propozycja katalogu danych dla nowej instancji (instances/<slug>)."""
        return str(inst.suggest_data_dir_for_name(name))

    @Slot(result="QVariantList")
    def instanceOptions(self) -> list:
        """Instancje NADAJĄCE się do paczkowania (z katalogiem danych) -
        opcje dla DropdownButton: [{value: id, label: name + ścieżka}]."""
        options: list[dict] = []
        for instance in self._instances:
            if instance.is_default:
                continue
            options.append({
                "value": instance.instance_id,
                "label": f"{instance.name} · {fs.display_path(instance.data_dir)}",
            })
        return options

    @Slot(result="QVariantList")
    def allInstanceOptions(self) -> list:
        """Wszystkie instancje (także domyślną) - opcje selektora aktywnej
        instancji na Pulpicie: [{value: id, label: name}]."""
        return [
            {
                "value": i.instance_id,
                "label": i18n_message("instances.defaultName") if i.is_default else i.name,
            }
            for i in self._instances
        ]

    @Slot(result="QVariantList")
    def all_instances_for_search(self) -> list:
        """Kompaktowe rekordy instancji dla globalnego wyszukiwania."""
        return [
            {
                "id": i.instance_id,
                "name": i18n_message("instances.defaultName") if i.is_default else i.name,
                "description": i.description,
                "gameBranch": i.game_branch,
            }
            for i in self._instances
        ]

    @Property("QVariantList", notify=instancesChanged)
    def activeInstanceOptions(self) -> list:
        """Reaktywna wersja allInstanceOptions() - QML nie śledzi zwykłych
        wywołań metod, więc selektor na Pulpicie binduje się do property
        (odświeża się po dodaniu/usunięciu/edycji instancji)."""
        return self.allInstanceOptions()

    @Slot(str, result="QVariantList")
    def instanceModStates(self, instance_id: str) -> list:
        """Mody instancji = ZAWARTOŚĆ FOLDERU Mods (to gra realnie ładuje)
        + mody Biblioteki jeszcze niewidoczne w folderze. Dla każdego:
        {modId, name, version, enabled, inFolder, managed, source}.
        - folder + wpis w Bibliotece -> zarządzany przełącznikiem (build
          dodaje/usuwa dowiązanie wg aktywacji),
        - folder bez wpisu -> "ręczny" (wrzucony z palca; tylko podgląd),
        - Biblioteka bez folderu -> dostępny do dodania przełącznikiem."""
        instance = self._instance(instance_id)
        if instance is None:
            return []
        state = library.load_activation_state()
        entries_by_folder = {e.folder_name: e for e in library.load_library_entries()}
        out: list[dict] = []
        seen_ids: set[str] = set()   # library_id modów już widocznych w folderze

        mods_dir = instance.mods_dir
        if mods_dir is not None and mods_dir.is_dir():
            for child in sorted(mods_dir.iterdir(), key=lambda p: p.name.lower()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                entry = entries_by_folder.get(child.name)
                info: dict = {}
                modinfo = find_modinfo(child)
                if modinfo is not None:
                    try:
                        info = parse_modinfo(modinfo)
                    except Exception:
                        info = {}
                if entry is not None:
                    seen_ids.add(entry.library_id)
                    out.append({
                        "modId": entry.library_id,
                        "name": entry.display_name or child.name,
                        "version": entry.version,
                        "enabled": state.is_enabled_for(entry.library_id, instance_id),
                        "inFolder": True,
                        "managed": True,
                        "source": i18n_message("instances.mod.source.library"),
                    })
                else:
                    out.append({
                        "modId": child.name,
                        "name": info.get("display_name") or child.name,
                        "version": info.get("version", ""),
                        "enabled": True,   # leży w folderze = gra go ładuje
                        "inFolder": True,
                        "managed": False,
                        "source": i18n_message("instances.mod.source.manual"),
                    })

        for m in self._mods.all_mods():
            if m.id in seen_ids:
                continue
            out.append({
                "modId": m.id,
                "name": m.name,
                "version": m.version,
                "enabled": state.is_enabled_for(m.id, instance_id),
                "inFolder": False,
                "managed": True,
                "source": i18n_message("instances.mod.source.library"),
            })
        return out

    @Slot(str, bool)
    def _instance_version_group(self, instance) -> str:
        """Grupa wersji gry instancji: przypisany game_branch albo wykryta
        instalacja Steam (appmanifest). "" = nieznana (bez blokad)."""
        from backend.game_versions import version_group
        if instance.game_branch:
            return version_group(instance.game_branch)
        return self._game.versionGroup if self._game else ""

    def _mod_version_mismatch(self, mod_id: str, instance) -> str:
        """Komunikat blokady, gdy wersja gry moda nie pasuje do wersji
        instancji/wykrytej gry; "" = dozwolone."""
        from backend.game_versions import version_group
        entry = next((e for e in library.load_library_entries()
                      if e.library_id == mod_id), None)
        mod_version = (entry.game_version if entry else "").strip()
        if not mod_version:
            return ""
        instance_group = self._instance_version_group(instance)
        if not instance_group:
            return ""
        if version_group(mod_version) != instance_group:
            instance_version = instance_group if not instance.game_branch else instance.game_branch
            return i18n_message("instances.versionMismatch", {
                "modVersion": mod_version,
                "name": instance.name,
                "instanceVersion": instance_version,
            })
        return ""

    def setInstanceModsEnabled(self, instance_id: str, enabled: bool) -> None:
        """Masowe przełączenie wszystkich modów z Biblioteki dla jednej instancji.

        Zapisuje ActivationState tylko raz, a przebudowę folderu Mods pozostawia
        warstwie QML (po zakończeniu zmiany) tak samo jak pojedynczy przełącznik.
        Mody ręczne nie są tutaj dotykane, bo nie należą do Biblioteki.
        """
        instance = self._instance(instance_id)
        if instance is None:
            return
        state = library.load_activation_state()
        skipped = 0
        for mod in self._mods.all_mods():
            if enabled and self._mod_version_mismatch(mod.id, instance):
                skipped += 1
                continue
            if enabled:
                if mod.id in state.global_enabled:
                    state.set_instance_exclusion(mod.id, instance_id, False)
                else:
                    state.set_instance_inclusion(mod.id, instance_id, True)
            else:
                if mod.id in state.global_enabled:
                    state.set_instance_exclusion(mod.id, instance_id, True)
                else:
                    state.set_instance_inclusion(mod.id, instance_id, False)
        library.save_activation_state(state)
        if skipped:
            self._bus.toastKey("toast.instances.skippedVersion", {"count": skipped}, "warning")
        self.instancesChanged.emit()

    @Slot(str, str, bool)
    def setInstanceModEnabled(self, instance_id: str, mod_id: str, enabled: bool) -> None:
        """Przełącznik per instancja (krok 7.5): dla modów włączonych
        globalnie zarządza WYKLUCZENIEM, dla wyłączonych - WŁĄCZENIEM
        punktowym. Pełne 4 przypadki semantyki siedzą w ActivationState."""
        if enabled:
            instance = self._instance(instance_id)
            if instance is not None:
                mismatch = self._mod_version_mismatch(mod_id, instance)
                if mismatch:
                    details = self._mod_version_mismatch_details(mod_id, instance)
                    self._bus.toastKey("toast.instances.versionMismatch", details, "warning")
                    return
        state = library.load_activation_state()
        if enabled:
            if mod_id in state.global_enabled:
                state.set_instance_exclusion(mod_id, instance_id, False)
            else:
                state.set_instance_inclusion(mod_id, instance_id, True)
        else:
            if mod_id in state.global_enabled:
                state.set_instance_exclusion(mod_id, instance_id, True)
            else:
                state.set_instance_inclusion(mod_id, instance_id, False)
        library.save_activation_state(state)
        self.instancesChanged.emit()

    @Slot(str)
    def openDataFolder(self, instance_id: str) -> None:
        """Otwiera katalog danych instancji w menedżerze plików."""
        instance = self._instance(instance_id)
        if instance is None or instance.is_default:
            return
        fs.ensure_dir(instance.data_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(instance.data_path)))

    @staticmethod
    def _downloaded_game_version_available(branch: str) -> bool:
        from backend.game_versions import resolve_downloaded_branch
        return bool(resolve_downloaded_branch(branch))

    @Slot(str)
    def launchInstance(self, profile_id: str) -> None:
        instance = self._instance(profile_id)
        if instance is None:
            return
        if self._game.isRunning:
            self._bus.toastKey("toast.instances.launchBlockedRunning", {}, "warning")
            return
        if self._launch_in_progress:
            self._bus.toastKey("toast.instances.launchInProgress", {}, "info")
            return
        if instance.game_branch:
            from backend.game_versions import required_game_branch, version_requirement_text
            from backend.game_versions import resolve_downloaded_branch
            required_branch = required_game_branch(instance.game_branch)
            resolved_branch = resolve_downloaded_branch(required_branch)
            if not resolved_branch:
                self._bus.toastKey("toast.instances.missingGameVersion", {"branch": version_requirement_text(required_branch) or required_branch}, "warning")
                return
            required_branch = resolved_branch
            if required_branch != instance.game_branch:
                instance.game_branch = required_branch
                self._save_registry()
                self._model.set_profiles(
                    [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)

        launch_target = instance.game_branch or "Steam"
        self._bus.toastKey("toast.instances.launching", {"name": instance.name, "target": launch_target}, "info")
        if inst.launch_instance_via_steam(instance):
            if self._active_id != instance.instance_id:
                self._active_id = instance.instance_id
                self._persist_active()
                self._model.refresh_active(instance.instance_id)
                self.activeInstanceChanged.emit()
            self._launch_in_progress = True
            self.launchInProgressChanged.emit()
            self.instanceLaunched.emit(instance.instance_id)
            # GameDetector odpytywany jest co kilka sekund. Guard zamyka
            # krótkie okno wyścigu między Steam a pierwszym wykryciem procesu.
            QTimer.singleShot(8000, self._clear_launch_guard)
        else:
            self._bus.toastKey("toast.instances.launchFailed", {}, "error")

    @Slot()
    def _clear_launch_guard(self) -> None:
        if not self._launch_in_progress:
            return
        self._launch_in_progress = False
        self.launchInProgressChanged.emit()

    @Slot()
    def launchActive(self) -> None:
        self.launchInstance(self._active_id)

    @Slot(str)
    def buildModsFor(self, profile_id: str) -> None:
        instance = self._instance(profile_id)
        if instance is None:
            return
        if instance.is_default:
            self._bus.toastKey("toast.instances.defaultBuild", {}, "info")
            return
        if library_ops.is_game_modifying_library_content():
            self._bus.toastKey("toast.instances.buildBlockedRunning", {}, "warning")
            return

        def worker(instance=instance):
            try:
                result = inst.build_mods_for_instance(
                    instance, library.load_library_entries(), library.load_activation_state())
                summary = f"linked={len(result.symlinked)};copied={len(result.copied)}"
                self.instanceBuilt.emit(instance.instance_id, summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("build_mods_for_instance failed")
                self.instanceBuilt.emit(instance.instance_id, f"error:{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_instance_built(self, instance_id: str, summary: str) -> None:
        instance = self._instance(instance_id)
        name = instance.name if instance else instance_id
        if summary.startswith("error:"):
            self._bus.toastKey("toast.instances.buildFailed", {"name": name, "summary": summary[6:].strip(" :")}, "error")
        else:
            linked = copied = 0
            for part in summary.split(";"):
                key, _, raw = part.partition("=")
                try:
                    value = max(0, int(raw))
                except (TypeError, ValueError):
                    value = 0
                if key == "linked":
                    linked = value
                elif key == "copied":
                    copied = value
            self._bus.toastKey("toast.instances.buildSuccessCounts", {"name": name, "linked": linked, "copied": copied}, "success")

    @Slot(str, str, str, str, bool, bool, bool, bool, str)
    def updateInstance(self, profile_id: str, name: str, data_dir: str,
                       description: str, noeos: bool, noeac: bool,
                       skip_news_screen: bool, skip_intro: bool,
                       game_branch: str = "") -> None:
        """Pełna edycja instancji (dialog edycji, Krok C): nazwa, opis,
        katalog danych i flagi - z walidacją jak przy tworzeniu."""
        if self._game.isRunning:
            self._bus.toastKey("toast.instances.cannotEditRunning", {}, "warning")
            return
        instance = self._instance(profile_id)
        if instance is None:
            return
        error = inst.validate_instance_name(name, self._instances, current_id=profile_id)
        if error:
            self._bus.toastKey("common.operationFailed", {"error": error}, "error")
            return
        if (data_dir or "").strip():
            error = inst.validate_instance_data_dir(data_dir, self._instances, current_id=profile_id)
            if error:
                self._bus.toastKey("common.operationFailed", {"error": error}, "error")
                return
        instance.name = name.strip() or instance.name
        instance.description = (description or "").strip()
        instance.data_dir = inst.normalize_data_dir(data_dir)
        instance.flag_noeos = noeos
        instance.flag_noeac = noeac
        instance.flag_skip_news_screen = skip_news_screen
        instance.flag_skip_intro = skip_intro
        instance.game_branch = (game_branch or "").strip()[:40]
        self._save_registry()
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self._bus.toastKey("toast.instances.saved", {"name": instance.name}, "success")

    # ------------------------------------------------------------------ #
    def reset_demo(self) -> None:
        """Demo = reset do samej instancji domyślnej (realny rejestr, D21)."""
        self._instances = [inst.make_default_instance()]
        self._active_id = inst.DEFAULT_INSTANCE_ID
        self._save_registry()
        self._model.set_profiles(
            [self._to_profile(i, idx) for idx, i in enumerate(self._instances)], self._active_id)
        self.instancesChanged.emit()
        self.activeInstanceChanged.emit()

    def _notify_counts(self) -> None:
        self.instancesChanged.emit()
        self._model.touch_all()
