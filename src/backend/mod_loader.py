"""Load / save the persisted mod state (load order, enabled flags, versions).

The first run seeds the realistic demo data from mock_data.py; afterwards the
user's changes (toggle / reorder / uninstall / updates) are persisted to
config/state.json so the app behaves like a real manager across restarts.
"""

from __future__ import annotations

import logging
from pathlib import Path

from models.mod import Mod, make_date
from services import filesystem_service as fs
from services.i18n_message import message as i18n_message
from backend import mock_data

logger = logging.getLogger(__name__)


def _dict_to_mod(entry: dict) -> Mod:
    return Mod(
        id=entry["id"],
        name=entry.get("name", entry["id"]),
        author=entry.get("author") or i18n_message("common.unknown"),
        category=entry.get("category", "Gameplay"),
        version=entry.get("version", "1.0"),
        new_version=entry.get("new_version", ""),
        enabled=bool(entry.get("enabled", True)),
        description=entry.get("description", ""),
        size_bytes=int(entry.get("size_bytes", 0)),
        downloads=int(entry.get("downloads", 0)),
        rating=float(entry.get("rating", 0.0)),
        tags=list(entry.get("tags", [])),
        dependencies=list(entry.get("dependencies", [])),
        modified_files=list(entry.get("modified_files", [])),
        installed_at=make_date(entry.get("installed", "")),
        updated_at=make_date(entry.get("updated", "")),
        custom=bool(entry.get("custom", False)),
    )


class ModLoader:
    """Persistence for the mod list."""

    def __init__(self) -> None:
        self._file: Path = fs.mod_state_path()

    # ------------------------------------------------------------------ #
    def load_state(self) -> dict | None:
        data = fs.read_json_migrated(self._file, fs.legacy_mod_state_path(), None)
        return data if isinstance(data, dict) else None

    def save_state(self, mods: list[Mod]) -> None:
        payload = {
            "order": [m.id for m in mods],
            "enabled": {m.id: m.enabled for m in mods},
            "versions": {m.id: m.version for m in mods},
            "updates": {m.id: m.new_version for m in mods if m.new_version},
            "removed": self._removed_ids(mods),
            "custom": [m.to_record()["full"] for m in mods if m.custom],
        }
        if not fs.write_json(self._file, payload):
            logger.warning("Could not persist mod state to %s", self._file)

    def _removed_ids(self, mods: list[Mod]) -> list[str]:
        current = {m.id for m in mods}
        removed = []
        for entry in mock_data.MODS:
            if entry["id"] not in current:
                removed.append(entry["id"])
        return removed

    # ------------------------------------------------------------------ #
    def build_mods(self) -> list[Mod]:
        """Seed defaults, then apply persisted state on top."""
        mods = [_dict_to_mod(entry) for entry in mock_data.seed_mods()]
        state = self.load_state()
        if not state:
            return mods

        # drop uninstalled seed mods
        removed = set(state.get("removed") or [])
        mods = [m for m in mods if m.id not in removed]

        # add user-created mods
        for entry in state.get("custom") or []:
            try:
                mod = _dict_to_mod(entry)
                mod.custom = True
                mods.append(mod)
            except (KeyError, TypeError):
                continue

        by_id = {m.id: m for m in mods}

        # apply versions / updates / enabled
        for mod_id, version in (state.get("versions") or {}).items():
            if mod_id in by_id:
                by_id[mod_id].version = str(version)
        for mod_id, update in (state.get("updates") or {}).items():
            if mod_id in by_id:
                by_id[mod_id].new_version = str(update)
        for mod_id, enabled in (state.get("enabled") or {}).items():
            if mod_id in by_id:
                by_id[mod_id].enabled = bool(enabled)

        # apply load order
        order = [mid for mid in state.get("order") or [] if mid in by_id]
        ordered = [by_id[mid] for mid in order]
        ordered.extend(m for m in mods if m.id not in set(order))
        return ordered

    def reset_state(self) -> None:
        try:
            self._file.unlink(missing_ok=True)
        except OSError:
            pass
