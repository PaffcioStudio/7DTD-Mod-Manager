"""Kopie zapasowe instancji (etap 19) - NOWA SEMANTYKA wg decyzji
użytkownika, zastępuje stary model "modpacków" (przenoszenie danych
+ whitelista):

- Utwórz kopię: PEŁNA KOPIA katalogu danych instancji. Nic nie jest
  przenoszone ani zmieniane w instancji.
- JEDNA kopia na instancję: próba utworzenia drugiej = blokada
  (do odświeżenia kopii służy Aktualizuj, do odtworzenia Przywróć).
- Przywróć: usuwa WSZYSTKO z katalogu danych instancji (1:1, bez żadnej
  whitelist) i przywraca kopię; usunięta instancja jest odtwarzana
  1:1 z zapisanych metadanych (nazwa, katalog, flagi).
- Usunięcie instancji NIE dotyka kopii zapasowej.

Folder kopii = backups/<instance_id> (identyfikator instancji jest
kluczem - naturalnie wymusza "jedna kopia na instancję"). Starsze wersje
trzymały kopie w modpacks/<instance_id> - migrate_legacy_layout()
przenosi je przy starcie (zob. niżej).
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.fileops import (
    ProgressCallback,
    copy_tree_with_progress,
    count_files,
    remove_tree_with_progress,
)
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BackupRecord:
    instance_id: str
    instance_name: str
    data_dir: str                 # zapisany katalog danych instancji
    flags: dict                   # {noeos, noeac, skip_news_screen, skip_intro}
    path: str = ""                # folder kopii
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    item_count: int = 0
    size_bytes: int = 0


def _read_payload() -> dict:
    data = fs.read_json(fs.modpacks_path(), None)
    return data if isinstance(data, dict) else {"backups": []}


def load_backups() -> list[BackupRecord]:
    items = _read_payload().get("backups", [])
    records: list[BackupRecord] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict) or not item.get("instance_id"):
                continue
            records.append(BackupRecord(
                instance_id=str(item.get("instance_id", "")),
                instance_name=str(item.get("instance_name", "")),
                data_dir=str(item.get("data_dir", "")),
                flags=item.get("flags") if isinstance(item.get("flags"), dict) else {},
                path=str(item.get("path", "")),
                description=str(item.get("description", "")),
                created_at=str(item.get("created_at", "")),
                updated_at=str(item.get("updated_at", "")),
                item_count=int(item.get("item_count", 0)),
                size_bytes=int(item.get("size_bytes", 0)),
            ))
    return records


def save_backups(records: list[BackupRecord]) -> None:
    fs.write_json(fs.modpacks_path(), {
        "backups": [
            {
                "instance_id": r.instance_id,
                "instance_name": r.instance_name,
                "data_dir": r.data_dir,
                "flags": dict(r.flags),
                "path": r.path,
                "description": r.description,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "item_count": r.item_count,
                "size_bytes": r.size_bytes,
            }
            for r in records
        ]
    })


def find_backup_for_instance(records: list[BackupRecord],
                             instance_id: str) -> BackupRecord | None:
    return next((r for r in records if r.instance_id == instance_id), None)


def backup_dir_for(instance_id: str) -> Path:
    return fs.backups_root() / instance_id


def dir_size_bytes(path: str | Path) -> int:
    total = 0
    for item in Path(path).rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def count_items(path: str | Path) -> int:
    return sum(1 for _ in Path(path).rglob("*"))


def format_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def format_when(iso_value: Optional[str]) -> str:
    if not iso_value:
        return "-"
    value = iso_value.replace("T", " ")
    return value[:16] if len(value) >= 16 else value


def _validate_data_path(path: Path) -> None:
    """Bezpiecznik ścieżki danych instancji (jak w starym projekcie)."""
    home = Path.home().resolve(strict=False)
    if path in {Path("/").resolve(strict=False), home} or len(path.parts) < 3:
        raise ValueError(i18n_message("backups.error.unsafePath", {"path": str(path)}))


def _own_root() -> Path:
    return fs.backups_root().resolve(strict=False)


def _allowed_roots() -> list[Path]:
    """Folders under which a backup may be deleted: the current root and the
    legacy one (a backup that could not be migrated stays deletable)."""
    return [_own_root(), fs.legacy_modpacks_root().resolve(strict=False)]


def create_backup_from_instance(
    instance,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> BackupRecord:
    """Pełna KOPIA katalogu danych instancji do backups/<instance_id>.
    Instancja pozostaje nietknięta. Blokada: ta instancja ma już kopię."""
    data_path = instance.data_path
    if data_path is None:
        raise ValueError(i18n_message("backups.error.defaultInstance"))
    data_path = data_path.expanduser().resolve(strict=False)
    _validate_data_path(data_path)

    records = load_backups()
    if find_backup_for_instance(records, instance.instance_id):
        raise FileExistsError(i18n_message("backups.error.alreadyExists", {
            "name": instance.name
        }))

    dest = backup_dir_for(instance.instance_id)
    dest.mkdir(parents=True, exist_ok=False)

    copy_tree_with_progress(data_path, dest, progress_cb=progress_cb,
                            cancel_event=cancel_event)

    record = BackupRecord(
        instance_id=instance.instance_id,
        instance_name=instance.name,
        data_dir=instance.data_dir,
        flags={
            "noeos": instance.flag_noeos,
            "noeac": instance.flag_noeac,
            "skip_news_screen": instance.flag_skip_news_screen,
            "skip_intro": instance.flag_skip_intro,
        },
        path=str(dest),
        created_at=datetime.now().isoformat(timespec="seconds"),
        updated_at=datetime.now().isoformat(timespec="seconds"),
        item_count=count_items(dest),
        size_bytes=dir_size_bytes(dest),
    )
    records.append(record)
    save_backups(records)
    return record


def update_backup_from_instance(
    record: BackupRecord,
    instance,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> BackupRecord:
    """Odświeża kopię bieżącym stanem instancji: usuwa starą zawartość
    kopii i kopiuje pełny stan katalogu danych (1:1)."""
    data_path = instance.data_path
    if data_path is None:
        raise ValueError(i18n_message("backups.error.noDataDirectory"))
    data_path = data_path.expanduser().resolve(strict=False)
    _validate_data_path(data_path)

    dest = Path(record.path)
    if dest.exists():
        remove_tree_with_progress(dest, progress_cb=progress_cb,
                                  cancel_event=cancel_event)
    dest.mkdir(parents=True, exist_ok=True)
    copy_tree_with_progress(data_path, dest, progress_cb=progress_cb,
                            cancel_event=cancel_event)

    records = load_backups()
    record.item_count = count_items(dest)
    record.size_bytes = dir_size_bytes(dest)
    record.updated_at = datetime.now().isoformat(timespec="seconds")
    records = [r for r in records if r.instance_id != record.instance_id]
    records.append(record)
    save_backups(records)
    return record


def restore_backup(record: BackupRecord, *,
                   progress_cb: Optional[ProgressCallback] = None,
                   cancel_event: Optional[threading.Event] = None):
    """Przywraca kopię 1:1: usuwa WSZYSTKO z katalogu danych instancji
    (bez whitelist!) i kopiuje zawartość kopii. Jeśli instancja została
    usunięta - jest ODTWARZANA 1:1 z zapisanych metadanych
    (ten sam instance_id, nazwa, katalog danych i flagi).
    Zwraca instancję docelową."""
    from backend import instances as inst_mod
    from backend.instances import Instance

    source = Path(record.path).expanduser().resolve(strict=False)
    if not source.is_dir():
        raise FileNotFoundError(i18n_message("backups.error.folderMissing", {"path": str(source)}))

    instances = inst_mod.load_instances()
    target = inst_mod.find_instance(instances, record.instance_id)

    if target is None:
        # instancja usunięta - odtworzenie 1:1 z metadanych kopii
        flags = record.flags or {}
        target = Instance(
            instance_id=record.instance_id,
            name=record.instance_name,
            data_dir=record.data_dir,
            flag_noeos=bool(flags.get("noeos", True)),
            flag_skip_news_screen=bool(flags.get("skip_news_screen", True)),
            flag_skip_intro=bool(flags.get("skip_intro", True)),
            flag_noeac=bool(flags.get("noeac", False)),
            created_at=record.created_at,
            description=record.description,
        )
        instances.append(target)
        inst_mod.save_instances(instances)

    data_path = target.data_path
    if data_path is None:
        raise ValueError(i18n_message("backups.error.restoreNoDataDirectory"))
    data_path = data_path.expanduser().resolve(strict=False)
    _validate_data_path(data_path)
    data_path.mkdir(parents=True, exist_ok=True)

    grand_total = max(1, count_files(data_path) + count_files(source))

    def remove_cb(done: int, _t: int, label: str) -> None:
        if progress_cb:
            progress_cb(done, grand_total, i18n_message("backups.progress.cleaning", {"name": label}))

    def copy_cb(done: int, _t: int, label: str) -> None:
        if progress_cb:
            progress_cb(remove_total + done, grand_total, i18n_message("backups.progress.restoring", {"name": label}))

    remove_total = count_files(data_path)
    grand_total = max(1, remove_total + count_files(source))

    for child in sorted(data_path.iterdir(), key=lambda p: p.name.lower()):
        remove_tree_with_progress(child, progress_cb=remove_cb,
                                  cancel_event=cancel_event)

    copy_tree_with_progress(source, data_path, progress_cb=copy_cb,
                            cancel_event=cancel_event)
    if progress_cb:
        progress_cb(grand_total, grand_total, i18n_message("fileops.done"))
    return target


def delete_backup(record: BackupRecord, *,
                  progress_cb: Optional[ProgressCallback] = None,
                  cancel_event: Optional[threading.Event] = None) -> None:
    path = Path(record.path).expanduser().resolve(strict=False)
    if path.exists():
        if any(path == root for root in _allowed_roots()) or not any(
                root in path.parents for root in _allowed_roots()):
            raise ValueError(i18n_message("backups.error.outsideRoot", {"path": str(path)}))
        remove_tree_with_progress(path, progress_cb=progress_cb,
                                  cancel_event=cancel_event)
    records = [r for r in load_backups() if r.instance_id != record.instance_id]
    save_backups(records)


def migrate_legacy_layout() -> int:
    """One-time move of backup folders from modpacks/<id> to backups/<id>.

    * every record whose folder lives in the legacy root is moved (a plain
      rename on the same filesystem - instant, no copying) and its ``path``
      is rewritten; the records file is saved after each move, so an
      interrupted run simply continues next time;
    * a folder that was already moved (record still points to the old path)
      is repointed;
    * nothing is overwritten: if backups/<id> already exists the record is
      left untouched and a warning is logged;
    * the legacy folder is removed only if it ends up empty - anything that
      is not a known backup stays where it is.

    Returns the number of folders moved. Never raises.
    """
    try:
        legacy = fs.legacy_modpacks_root()
        new_root = fs.backups_root()
        legacy_res = legacy.resolve(strict=False)
        records = load_backups()
        moved = 0
        for record in records:
            target = new_root / record.instance_id
            current = Path(record.path).expanduser() if record.path else legacy / record.instance_id
            current_res = current.resolve(strict=False)
            if current_res == target.resolve(strict=False):
                continue                                   # already migrated
            if current_res.parent != legacy_res:
                continue                                   # custom location: leave alone
            if current.is_dir():
                if target.exists():
                    logger.warning("Backup migration skipped for %s: %s already exists",
                                   record.instance_id, target)
                    continue
                new_root.mkdir(parents=True, exist_ok=True)
                try:
                    os.rename(current, target)
                except OSError as exc:
                    logger.warning("Backup migration skipped for %s: cannot move %s -> %s (%s)",
                                   record.instance_id, current, target, exc)
                    continue
                moved += 1
                logger.info("Moved backup %s -> %s", current, target)
            elif not target.is_dir():
                continue                                   # folder missing everywhere
            record.path = str(target)                      # moved now or in an earlier run
            save_backups(records)
        try:
            legacy.rmdir()                                 # succeeds only when empty
            logger.info("Removed empty legacy backup folder %s", legacy)
        except OSError:
            pass
        return moved
    except Exception:  # noqa: BLE001 - startup migration must never break the app
        logger.exception("Backup folder migration failed")
        return 0
