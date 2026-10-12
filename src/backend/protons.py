"""Installed Proton discovery and cancellable GE-Proton downloads."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import tarfile
import tempfile
import threading
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Property, Signal, Slot

from backend import game_process
from services.i18n_message import message

logger = logging.getLogger(__name__)
RELEASES_URL = 'https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases'


def managed_root() -> Path:
    return game_process._manager_data_root() / 'protons'


def installed_protons() -> list[dict]:
    entries = []
    seen = set()
    for root in game_process._steam_library_roots():
        for directory, custom in ((root / 'steamapps' / 'common', False), (root / 'compatibilitytools.d', True)):
            if not directory.is_dir():
                continue
            for child in sorted(directory.iterdir()):
                if not custom and not child.name.casefold().startswith('proton'):
                    continue
                entries.append((child, root, False))
    root = managed_root()
    if root.is_dir():
        entries.extend((child, None, True) for child in sorted(root.iterdir()) if not child.name.startswith('.'))
    result = []
    for child, library, managed in entries:
        proton = child / 'proton'
        if not proton.is_file() or not os.access(proton, os.X_OK):
            continue
        path = str(proton.resolve())
        if path in seen:
            continue
        seen.add(path)
        result.append({'name': child.name, 'path': path, 'library': str(library) if library else '', 'managed': managed})
    return sorted(result, key=lambda item: item['name'].casefold())


def resolve_proton(selection: str = '') -> tuple[Path | None, Path | None]:
    if not selection:
        return game_process.find_proton()
    for item in installed_protons():
        if item['path'] == str(Path(selection).expanduser().resolve()):
            library = Path(item['library']) if item['library'] else game_process._find_steam_client_root()
            return Path(item['path']), library
    return None, None  # explicit selection must never silently fall back


def release_catalog(payload: list) -> list[dict]:
    result = []
    for release in payload:
        if release.get('draft'):
            continue
        assets = release.get('assets', [])
        archive = next((a for a in assets if a['name'].endswith('.tar.gz') and 'aarch64' not in a['name'] and 'arm64' not in a['name']), None)
        if not archive:
            continue
        checksum = next((a for a in assets if a['name'] == archive['name'].removesuffix('.tar.gz') + '.sha512sum'), None)
        if not checksum:
            continue
        result.append({'name': release['tag_name'], 'filename': archive['name'], 'url': archive['browser_download_url'],
                       'checksum': checksum['browser_download_url'], 'size': archive.get('size', 0), 'published': release.get('published_at', '')})
    return result


class Cancelled(Exception):
    pass


def install_release(release: dict, cancel: threading.Event, progress, phase, session=None) -> Path:
    """Verify SHA-512, extract into staging with data filter, publish atomically."""
    session = session or requests.Session()
    root = managed_root()
    root.mkdir(parents=True, exist_ok=True)
    name = release['filename'].removesuffix('.tar.gz')
    if not re.fullmatch(r'GE-Proton[a-zA-Z0-9._-]+', name):
        raise ValueError('Invalid release name')
    destination = root / name
    if destination.exists():
        raise FileExistsError(str(destination))
    def check():
        if cancel.is_set():
            raise Cancelled()
    with tempfile.TemporaryDirectory(prefix='.download-', dir=root) as temporary:
        staging = Path(temporary)
        archive = staging / 'download.tar.gz'
        phase('protons.downloading')
        digest = hashlib.sha512()
        received = 0
        with session.get(release['url'], stream=True, timeout=(15, 30)) as response:
            response.raise_for_status()
            total = int(response.headers.get('Content-Length', release['size']) or 0)
            with archive.open('wb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    check()
                    if chunk:
                        output.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        progress(min(100, received * 100 / total) if total else 0)
        check()
        phase('protons.verifying')
        with session.get(release['checksum'], timeout=(15, 30)) as response:
            response.raise_for_status()
            expected = response.text.split()[0].lower()
        if not re.fullmatch('[0-9a-f]{128}', expected) or digest.hexdigest() != expected:
            raise ValueError('SHA-512 checksum mismatch')
        check()
        phase('protons.extracting')
        extracted = staging / 'unpacked'
        extracted.mkdir()
        with tarfile.open(archive) as source:
            for member in source:
                check()
                source.extract(member, extracted, filter='data')
        children = list(extracted.iterdir())
        if len(children) != 1 or not children[0].is_dir() or children[0].is_symlink():
            raise ValueError('Invalid Proton archive layout')
        candidate = children[0]
        executable = candidate / 'proton'
        if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError('Missing executable Proton launcher')
        check()
        if destination.exists():
            raise FileExistsError(str(destination))
        candidate.rename(destination)
    return destination


class ProtonManager(QObject):
    changed = Signal()
    _event = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed = installed_protons()
        self._available = []
        self._busy = False
        self._progress = 0.0
        self._status = ''
        self._active_name = ''
        self._cancel = threading.Event()
        self._worker = None
        self._event.connect(self._receive)

    @Property('QVariantList', notify=changed)
    def installed(self): return self._installed

    @Property('QVariantList', notify=changed)
    def available(self): return self._available

    @Property(bool, notify=changed)
    def busy(self): return self._busy

    @Property(float, notify=changed)
    def progress(self): return self._progress

    @Property(str, notify=changed)
    def status(self): return self._status

    @Property(str, notify=changed)
    def activeName(self): return self._active_name

    @Slot(str, object)
    def _receive(self, kind, value):
        if kind == 'catalog': self._available = value
        elif kind == 'progress': self._progress = value
        elif kind == 'status': self._status = message(value)
        elif kind == 'error': self._status = message('protons.error', {'error': str(value)})
        elif kind == 'done':
            self._busy = False
            self._active_name = ''
            self._installed = installed_protons()
        self.changed.emit()

    def _start(self, operation, name=""):
        if self._busy:
            return
        self._cancel.clear()
        self._busy = True
        self._active_name = name
        self._progress = 0
        self._status = ''
        self.changed.emit()
        def work():
            try:
                operation()
            except Cancelled:
                self._event.emit('status', 'protons.cancelled')
            except Exception as exc:
                logger.exception('Proton operation failed')
                self._event.emit('error', str(exc))
            finally:
                self._event.emit('done', None)
        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    @Slot()
    def refreshInstalled(self):
        self._installed = installed_protons()
        self.changed.emit()

    @Slot()
    def refreshAvailable(self):
        def fetch():
            self._event.emit('status', 'protons.loading')
            with requests.get(RELEASES_URL, params={'per_page': 100}, timeout=(15, 30)) as response:
                response.raise_for_status()
                catalog = release_catalog(response.json())
            if self._cancel.is_set(): raise Cancelled()
            self._event.emit('catalog', catalog)
            self._event.emit('status', 'protons.ready')
        self._start(fetch)

    @Slot(str)
    def download(self, name):
        release = next((item for item in self._available if item['name'] == name), None)
        if release:
            def install():
                install_release(release, self._cancel, lambda p: self._event.emit('progress', p),
                                lambda key: self._event.emit('status', key))
                self._event.emit('status', 'protons.installedSuccess')
            self._start(install, name)

    @Slot()
    def cancel(self): self._cancel.set()

    @Slot(str)
    def remove(self, path):
        if self._busy or game_process.is_game_running():
            self._status = message('protons.removeBlocked')
            self.changed.emit()
            return
        item = next((p for p in self._installed if p['path'] == path and p['managed']), None)
        if not item: return
        from backend.instances import load_instances
        if any(i.proton_path == path for i in load_instances()):
            self._status = message('protons.inUse')
            self.changed.emit()
            return
        target = Path(path).parent
        if target.parent.resolve() != managed_root().resolve() or target.is_symlink(): return
        try:
            shutil.rmtree(target)
            self.refreshInstalled()
        except OSError as exc:
            self._receive('error', str(exc))

    def shutdown(self):
        self._cancel.set()
        if self._worker:
            self._worker.join(timeout=35)
