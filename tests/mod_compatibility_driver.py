"""Sprawdza potwierdzenie niepewnej zgodności i ponawianie pobierania."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
TEST_HOME = tempfile.TemporaryDirectory(prefix='mm-compat-ui-')
os.environ.update(HOME=TEST_HOME.name, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from backend import discover, download_manager as dm, web_mod_details as web
import main

discover.DiscoverManager.refresh = lambda self: None
dm.resolve_downloaded_branch = lambda branch: 'public'
dm.DownloadManager._is_downloaded_game_version = staticmethod(lambda _: True)
dm.DownloadManager._start_mod_worker = Mock()
web.SevenDaysModsClient._fetch_mod = lambda self, slug: ({
    'id': 'mod', 'slug': slug, 'title': 'Airdrop Spawn Zeds - V3.2 b9',
    'current_version': 'Latest', 'game_versions': ['V3 Mods', 'V2 Mods'],
    'mod_files': [{'id': 'chosen', 'filename': 'WMMZAirdropSpawnZeds.zip', 'mod_version': '3.2.9.4'}],
}, 'https://7daystodiemods.com/mods/' + slug)


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def js(item, expression):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, expression)
    result = expr.evaluate()
    assert not expr.hasError(), expr.error().toString()
    return result


def click(window, label, scope=None):
    buttons = [i for i in walk(scope or window.contentItem())
               if 'Button' in i.metaObject().className() and i.isVisible() and i.property('text') == label]
    assert len(buttons) == 1, (label, len(buttons))
    point = buttons[0].mapToScene(QPointF(buttons[0].width()/2, buttons[0].height()/2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))
    QTest.qWait(550)


class TestEngine(QQmlApplicationEngine):
    def load(self, url):
        super().load(url)
        QTimer.singleShot(700, self.exercise)

    def exercise(self):
        try:
            window = self.rootObjects()[0]
            drawer = next(i for i in walk(window.contentItem()) if 'WebModDrawer' in i.metaObject().className())
            downloads = self.rootContext().contextProperty('Downloads')
            js(drawer, 'openWith("airdrop-spawn-zeds-v32-b9", "public")')
            QTest.qWait(400)
            click(window, 'Pobierz', drawer)
            assert not downloads._model.items
            click(window, 'Anuluj')
            assert not downloads._model.items
            click(window, 'Pobierz', drawer)
            window.grabWindow().save('/tmp/mm-compatibility-warning.png')
            click(window, 'Pobierz mimo to')
            entry, = downloads._model.items
            assert entry.allow_incompatible_file and entry.status == 'downloading'
            assert entry.chosen_file_ref == 'hosted:chosen'
            assert entry.game_version == 'public'
            js(drawer, 'close()')
            QTest.qWait(400)
            entry.status = 'failed'
            entry.allow_incompatible_file = False
            entry.subtitle = '__I18N__:download.mod.incompatibleFile|{"version":"public"}'
            downloads.retryAt(entry.id)
            QTest.qWait(400)
            click(window, 'Anuluj')
            assert entry.status == 'failed' and not entry.allow_incompatible_file
            downloads.retryAt(entry.id)
            QTest.qWait(400)
            window.grabWindow().save('/tmp/mm-compatibility-retry.png')
            click(window, 'Pobierz mimo to')
            assert entry.status == 'downloading' and entry.allow_incompatible_file
            assert not downloads._pending_requests
            downloads._model.clear()
            downloads._emit_counts()
            catalog = self.rootContext().contextProperty('Discover')
            page = next(i for i in walk(window.contentItem()) if 'DiscoverPage' in i.metaObject().className())
            page.setProperty('version', 'public')
            catalog._items = [{
                'slug': 'workstation-material-timer-v32-b9', 'title': 'Workstation Material Timer - V3.2 b9',
                'summary': '', 'author': 'WMM', 'thumbnail': '', 'category': 'Gameplay',
                'versions': 'V3 Mods, V2 Mods', 'game_version': 'v3', 'version': 'Latest',
                'downloads': 0, 'url': 'https://7daystodiemods.com/mods/workstation-material-timer-v32-b9',
            }]
            catalog.changed.emit()
            def simulate_worker(item):
                if not item.allow_incompatible_file:
                    downloads.urlState.emit(item.id, 'confirm_compatibility:__I18N__:download.mod.noCompatibleFile|{"version":"public"}')
            dm.DownloadManager._start_mod_worker.side_effect = simulate_worker
            QTest.qWait(400)
            click(window, 'Pobierz', page)
            entry, = downloads._model.items
            assert not entry.allow_incompatible_file
            window.grabWindow().save('/tmp/mm-tile-compatibility.png')
            click(window, 'Pobierz mimo to')
            assert entry.allow_incompatible_file and entry.status == 'downloading'
            assert not downloads._pending_requests
            downloads._model.clear()
            entries = [dm.DownloadItem('mod', slug, slug, '', 0, status='downloading',
                       real=True, url='https://example.test/mod.zip', flavor='mod', game_version='public')
                       for slug in ['first', 'second']]
            for pending in entries:
                downloads._model.append(pending)
                downloads._on_url_state(pending.id, 'confirm_compatibility:__I18N__:download.mod.noCompatibleFile|{"version":"public"}')
            QTest.qWait(400)
            click(window, 'Anuluj')
            assert not entries[0].allow_incompatible_file
            click(window, 'Pobierz mimo to')
            assert entries[1].allow_incompatible_file and entries[1].status == 'downloading'
            assert not downloads._pending_requests
            print('PASS: sidebar, ponowienie, Pobierz na kafelku i kolejka dwóch pytań', flush=True)
            QGuiApplication.instance().exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            QGuiApplication.instance().exit(1)


main.QQmlApplicationEngine = TestEngine
sys.exit(main.main(['--language', 'pl', '--page', 'discover', '--screenshot', '/tmp/mm-compat-fallback.png', '--wait', '30000']))
