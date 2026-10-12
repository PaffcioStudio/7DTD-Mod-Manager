"""Instance log inventory and bounded text previews, including Proton crashes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices

from backend import game_process
from backend.instances import find_instance, load_instances


def collect_logs(instance) -> list[dict]:
    manager = game_process._manager_data_root()
    data = instance.data_path or Path.home() / '.local' / 'share' / '7DaysToDie'
    roots = [(data / 'BacktraceLogs', 'game'), (data / 'logs', 'instance'), (manager / 'logs', 'manager')]
    prefixes = [manager / 'compatdata' / (instance.game_branch or 'steam') / 'pfx']
    if not instance.game_branch:
        prefixes.extend(root / 'steamapps' / 'compatdata' / game_process.STEAM_APP_ID / 'pfx'
                        for root in game_process._steam_library_roots())
    for prefix in prefixes:
        user = prefix / 'drive_c' / 'users' / 'steamuser' / 'AppData'
        roots.extend([(user / 'LocalLow' / 'The Fun Pimps' / '7 Days To Die', 'unity'),
                      (user / 'Local' / 'Temp' / 'The Fun Pimps' / '7 Days To Die' / 'Crashes', 'crash')])
    found = {}
    for root, kind in roots:
        if not root.is_dir():
            continue
        for file in root.rglob('*'):
            if file.suffix.casefold() not in {'.log', '.txt', '.dmp', '.mdmp'} or not file.is_file():
                continue
            try:
                stat = file.stat()
                path = str(file.resolve())
            except OSError:
                continue
            found[path] = {'name': file.name, 'path': path, 'kind': kind,
                           'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                           'size': stat.st_size, 'mtime': stat.st_mtime,
                           'text': file.suffix.casefold() not in {'.dmp', '.mdmp'}}
    return sorted(found.values(), key=lambda item: item['mtime'], reverse=True)[:200]


class InstanceLogs(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._preview = ''
        self._name = ''
        self._id = ''
        self._selected_path = ''

    @Property('QVariantList', notify=changed)
    def files(self): return self._files

    @Property(str, notify=changed)
    def previewText(self): return self._preview

    @Property(str, notify=changed)
    def instanceName(self): return self._name

    @Property(str, notify=changed)
    def selectedPath(self): return self._selected_path

    @Slot(str)
    def select(self, instance_id):
        self._id = instance_id
        instance = find_instance(load_instances(), instance_id)
        self._files = collect_logs(instance) if instance else []
        self._name = instance.name if instance else ''
        self._preview = ''
        self._selected_path = ''
        latest = next((item for item in self._files if item['text'] and item['kind'] != 'manager'), None)
        if latest:
            self.preview(latest['path'])
        self.changed.emit()

    @Slot()
    def refresh(self): self.select(self._id)

    def _file(self, path):
        return next((item for item in self._files if item['path'] == path), None)

    @Slot(str)
    def preview(self, path):
        item = self._file(path)
        if not item or not item['text']: return
        self._selected_path = path
        try:
            with Path(path).open('rb') as file:
                file.seek(0, 2)
                file.seek(max(0, file.tell() - 256 * 1024))
                self._preview = file.read(256 * 1024).decode('utf-8', errors='replace')
        except OSError as exc:
            self._preview = str(exc)
        self.changed.emit()

    @Slot(str)
    def openFile(self, path):
        if self._file(path): QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot(str)
    def openFolder(self, path):
        if self._file(path): QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))
