"""Mod data model used by the backend and exposed to QML through roles."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from services.i18n_message import message as i18n_message


def _now() -> datetime:
    return datetime.now()


@dataclass
class Mod:
    """A single installed mod."""

    id: str
    name: str
    author: str
    category: str = "Gameplay"
    version: str = "1.0"
    new_version: str = ""            # non-empty => update available
    enabled: bool = True
    description: str = ""
    size_bytes: int = 0
    downloads: int = 0
    rating: float = 0.0
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)   # mod ids
    modified_files: list[str] = field(default_factory=list)
    installed_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    custom: bool = False             # added manually by the user
    game_version: str = ""           # wersja gry modu wg katalogu (slug; "" = nieznana)

    # ------------------------------------------------------------------ #
    # convenience
    # ------------------------------------------------------------------ #
    @property
    def has_update(self) -> bool:
        return bool(self.new_version)

    @property
    def size_text(self) -> str:
        return human_size(self.size_bytes)

    @property
    def downloads_text(self) -> str:
        return human_count(self.downloads)

    @property
    def installed_stamp(self) -> float:
        return self.installed_at.timestamp()

    @property
    def updated_stamp(self) -> float:
        return self.updated_at.timestamp()

    @property
    def installed_text(self) -> str:
        return human_date(self.installed_at)

    @property
    def updated_text(self) -> str:
        return human_date(self.updated_at)

    @property
    def updated_ago(self) -> str:
        return human_ago(self.updated_at)

    def to_record(self) -> dict:
        """Serializable subset persisted in the state file."""
        return {
            "id": self.id,
            "enabled": self.enabled,
            "version": self.version,
            "new_version": self.new_version,
            "custom": self.custom,
            "full": {
                "id": self.id,
                "name": self.name,
                "author": self.author,
                "category": self.category,
                "version": self.version,
                "new_version": self.new_version,
                "enabled": self.enabled,
                "description": self.description,
                "size_bytes": self.size_bytes,
                "downloads": self.downloads,
                "rating": self.rating,
                "tags": list(self.tags),
                "dependencies": list(self.dependencies),
                "modified_files": list(self.modified_files),
                "custom": self.custom,
            },
        }


# ---------------------------------------------------------------------- #
# formatting helpers (shared with the download manager etc.)
# ---------------------------------------------------------------------- #
def human_size(num_bytes: float) -> str:
    # Rozmiar pliku jest wielkością bezwzględną. Ujemna wartość może pojawić
    # się tylko przez uszkodzony/wyścigowy callback postępu i nie powinna nigdy
    # trafić do UI jako "-123 B".
    try:
        value = max(0.0, float(num_bytes or 0))
    except (TypeError, ValueError):
        value = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit in ("B", "KB"):
                return f"{value:,.0f} {unit}"
            return f"{value:,.1f} {unit}"
        value /= 1024.0
    return f"{value:,.1f} TB"


def human_count(num: int) -> str:
    value = float(num or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{int(value)}"


def human_date(dt: datetime) -> str:
    try:
        return i18n_message("date.absolute", {"day": dt.day, "month": dt.month, "year": dt.year})
    except Exception:
        return i18n_message("date.relative.unknown")


def human_ago(dt: datetime) -> str:
    try:
        delta = time.time() - dt.timestamp()
    except Exception:
        return i18n_message("date.relative.unknown")
    if delta < 0:
        return i18n_message("date.relative.now")
    minutes = int(delta // 60)
    if minutes < 1:
        return i18n_message("date.relative.now")
    if minutes < 60:
        return i18n_message("date.relative", {"kind": "minutes", "count": minutes})
    hours = int(delta // 3600)
    if hours < 24:
        return i18n_message("date.relative", {"kind": "hours", "count": hours})
    days = int(delta // 86400)
    if days < 30:
        return i18n_message("date.relative", {"kind": "days", "count": days})
    months = int(days // 30)
    if months < 12:
        return i18n_message("date.relative", {"kind": "months", "count": months})
    years = int(days // 365)
    return i18n_message("date.relative", {"kind": "years", "count": years})


def make_date(text: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM' (used by mock data)."""
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return _now()
