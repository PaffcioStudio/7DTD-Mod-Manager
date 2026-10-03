"""Profile/instance data model (migration stage 6).

Profile IS a game instance now: a data dir (empty = the default instance
running the game without -UserDataFolder) plus the launch flags. The
registry itself lives in backend/instances.py (instances.json); this
class is the UI-facing snapshot built via from_instance().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.mod import human_date
from services.i18n_message import message as i18n_message


@dataclass
class Profile:
    """One game instance as shown on the Profile cards."""

    id: str
    name: str
    description: str = ""
    data_dir: str = ""                   # "" = default instance (no -UserDataFolder)
    flag_noeos: bool = True
    flag_noeac: bool = False
    flag_skip_news_screen: bool = True
    flag_skip_intro: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    color_tag: str = "#FF7A38"
    # przypisana wersja gry (branch Steam z pobranych przez DepotDownloader);
    # "" = bez przypisania (globalna instalacja Steam)
    game_branch: str = ""
    favorite: bool = False

    # ------------------------------------------------------------------ #
    @property
    def is_default(self) -> bool:
        return not self.data_dir.strip()

    @property
    def created_text(self) -> str:
        return human_date(self.created_at)

    @property
    def data_dir_display(self) -> str:
        if self.is_default:
            return i18n_message("common.defaultGameLocation")
        return self.data_dir

    # ------------------------------------------------------------------ #
    # serialization (registry payload; description is this app's addition)
    # ------------------------------------------------------------------ #
    def to_record(self) -> dict:
        return {
            "instance_id": self.id,
            "name": self.name,
            "description": self.description,
            "data_dir": self.data_dir,
            "flags": {
                "noeos": self.flag_noeos,
                "noeac": self.flag_noeac,
                "skip_news_screen": self.flag_skip_news_screen,
                "skip_intro": self.flag_skip_intro,
            },
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "color_tag": self.color_tag,
        }
