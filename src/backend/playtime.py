"""Durable, per-instance game playtime from actual 7 Days to Die processes.

Each observed (pid, process-start) session is checkpointed to playtime.json.
Reloading the manager while a game is still running resumes the same session
without adding already-accounted seconds a second time. Steam launch requests
alone never count as playtime. Missing/unknown processes are not attributed to
an instance, and multiple Wine processes for one instance count only once.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

from services import filesystem_service as fs


class PlaytimeStore:
    def __init__(self, path: Path | None = None):
        self.path = path if path is not None else fs.data_dir() / "playtime.json"
        raw = fs.read_json(self.path, {})
        entries = raw.get("instances", {}) if isinstance(raw, dict) else {}
        self.records: dict[str, dict] = entries if isinstance(entries, dict) else {}

    def seconds(self, instance_id: str) -> int:
        value = self.records.get(instance_id, {}).get("totalSeconds", 0)
        try:
            return max(0, int(value))
        except (ValueError, TypeError, OverflowError):
            return 0

    def last_played(self, instance_id: str) -> float:
        try:
            return max(0.0, float(self.records.get(instance_id, {}).get("lastPlayed", 0)))
        except (ValueError, TypeError, OverflowError):
            return 0.0

    def total_seconds(self, valid_ids: set[str] | None = None) -> int:
        # Deleted instances do not count toward the current library summary.
        ids = valid_ids if valid_ids is not None else self.records.keys()
        return sum(self.seconds(i) for i in ids)

    def update(self, observed: dict[str, tuple[int, float]], now: float | None = None) -> bool:
        """Checkpoint processes: instance id -> (PID, epoch process start).

        Updating only recognized instances prevents guessing from the last
        selected instance when an external/modded game cannot be matched.
        """
        now = float(time.time() if now is None else now)
        changed = False
        for instance_id in set(self.records) | set(observed):
            old = self.records.get(instance_id)
            running = observed.get(instance_id)
            if not running and (not old or not old.get("sessionPid")):
                continue
            if not old:
                old = {"totalSeconds": 0, "lastPlayed": 0}
                self.records[instance_id] = old
            if running:
                pid, started = running
                if not (pid > 0 and math.isfinite(started) and 0 < started <= now):
                    continue
                same = (old.get("sessionPid") == pid and
                        abs(float(old.get("sessionStarted", 0)) - started) < 2)
                if same:
                    accounted = max(started, min(now, float(old.get("accountedUntil", started))))
                else:
                    # A Wine/Proton launcher and the actual game can have
                    # different PIDs. If the watched PID disappears and the
                    # other PID takes over without a gap in our observations,
                    # continue the same instance interval instead of counting
                    # the second process's entire lifetime once again.
                    accounted = max(started, min(now, float(old.get("accountedUntil", started))))
                delta = max(0, now - accounted)
                old["totalSeconds"] = max(0.0, float(old.get("totalSeconds", 0))) + delta
                old["lastPlayed"] = now
                old["sessionPid"] = pid
                old["sessionStarted"] = started
                old["accountedUntil"] = now
                changed = True
            elif old.get("sessionPid"):
                old["sessionPid"] = 0
                old["sessionStarted"] = 0
                old["accountedUntil"] = 0
                # lastPlayed reflects the last confirmed running heartbeat.
                changed = True
        if changed:
            fs.write_json(self.path, {"schema": 1, "instances": self.records})
        return changed
