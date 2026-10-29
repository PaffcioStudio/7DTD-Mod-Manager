"""Wybór mod/overhaul działa z kafelka, panelu i dla osobnego addonu."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
TEST_HOME = tempfile.TemporaryDirectory(prefix='mm-install-target-')
os.environ.update(HOME=TEST_HOME.name, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from backend import discover, download_manager as dm, web_mod_details as web
import main

SLUG = 'cooking-overhaul'
ITEM = {'slug': SLUG, 'title': '7D2D Cooking Overhaul', 'summary': '', 'author': 'Tester',
        'thumbnail': '', 'category': 'Food & Drink, Overhaul', 'versions': 'V3 Mods',
        'game_version': 'v3', 'version': '1.0', 'downloads': 0, 'url': 'https://example.test/mod'}
def catalog_data(*args, **kwargs):
    return {'items': [ITEM], 'total': 1, 'page': 1, 'pages': 1, 'offline': False, 'categories': [], 'versions': []}
discover.fetch_catalog = catalog_data
discover.fetch_local_catalog = catalog_data
dm.resolve_downloaded_branch = lambda _: 'public'
dm.DownloadManager._is_downloaded_game_version = staticmethod(lambda _: True)
dm.DownloadManager._start_mod_worker = Mock()
web.SevenDaysModsClient._fetch_mod = lambda self, slug: ({
    'id': SLUG, 'slug': SLUG, 'title': '7D2D Cooking Overhaul', 'current_version': '1.0',
    'categories': ['Food & Drink', 'Overhaul'], 'game_versions': ['V3 Mods'],
    'mod_files': [{'id': 'main', 'filename': 'Cooking-main.zip', 'file_type': 'main'},
                  {'id': 'addon', 'filename': 'Cooking-addon.zip', 'file_type': 'optional'}],
}, 'https://7daystodiemods.com/mods/' + SLUG)


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def js(item, expression):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, expression)
    expr.evaluate()
    assert not expr.hasError(), expr.error().toString()


def click(window, label, scope=None, index=0):
    buttons = [i for i in walk(scope or window.contentItem()) if 'Button' in i.metaObject().className()
               and i.isVisible() and i.isEnabled() and i.property('text') == label]
    buttons.sort(key=lambda i: i.mapToScene(QPointF()).y())
    assert len(buttons) > index, (label, len(buttons))
    button = buttons[index]
    point = button.mapToScene(QPointF(button.width()/2, button.height()/2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))
    QTest.qWait(550)


class TestEngine(QQmlApplicationEngine):
    def load(self, url):
        super().load(url)
        QTimer.singleShot(800, self.exercise)

    def exercise(self):
        try:
            window = self.rootObjects()[0]
            downloads = self.rootContext().contextProperty('Downloads')
            drawer = next(i for i in walk(window.contentItem()) if 'WebModDrawer' in i.metaObject().className())
            modal = next(i for i in walk(window.contentItem()) if i.property('fileLabel') is not None and i.property('modCount') is not None)
            def simulate_worker(item):
                addon = item.chosen_file_ref == 'hosted:addon'
                if not item.chosen_file_ref:
                    item.chosen_file_ref = 'hosted:main'
                downloads._multi_decisions[item.id] = {'event': threading.Event(), 'choice': ''}
                downloads.installTargetRequired.emit(item.id, ITEM['title'],
                    'Cooking-addon.zip' if addon else 'Cooking-main.zip', 'optional' if addon else 'main', 1)
            dm.DownloadManager._start_mod_worker.side_effect = simulate_worker
            for source, choice in [('tile', 'mods'), ('sidebar', 'mods'), ('sidebar', 'instance'), ('tile', 'cancel')]:
                downloads._model.clear()
                downloads._multi_decisions.clear()
                downloads._emit_counts()
                if source == 'tile':
                    js(drawer, 'close()')
                    QTest.qWait(450)
                    click(window, 'Pobierz')
                else:
                    js(drawer, 'openWith("cooking-overhaul", "public")')
                    QTest.qWait(300)
                    click(window, 'Pobierz', drawer, 1)
                entry, = downloads._model.items
                assert modal.property('opened') and entry.install_target == ''
                assert modal.property('fileLabel') == ('Cooking-addon.zip' if source == 'sidebar' else 'Cooking-main.zip')
                if source == 'sidebar':
                    assert modal.property('fileTypeLabel') == 'opcjonalny'
                    window.grabWindow().save('/tmp/mm-install-target-addon.png')
                label = {'mods': 'Zwykły mod', 'instance': 'Overhaul (instancja)', 'cancel': 'Anuluj'}[choice]
                click(window, label, modal)
                assert downloads._multi_decisions[entry.id]['choice'] == choice
                assert entry.install_target == ('' if choice == 'cancel' else choice)
                assert not modal.property('opened')
                if source == 'tile' and choice == 'mods':
                    downloads._emit_counts()
                    js(drawer, 'openWith("cooking-overhaul", "public")')
                    QTest.qWait(300)
                    click(window, 'Pobierz', drawer)
                    assert len(downloads._model.items) == 2
                    addon = downloads._model.items[-1]
                    assert addon.chosen_file_ref == 'hosted:addon' and modal.property('opened')
                    click(window, 'Zwykły mod', modal)
                    assert addon.install_target == 'mods'

            print('PASS: wybór mod/overhaul i anulowanie z kafelka oraz dla addonu w panelu', flush=True)
            QGuiApplication.instance().exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            QGuiApplication.instance().exit(1)


main.QQmlApplicationEngine = TestEngine
sys.exit(main.main(['--language', 'pl', '--page', 'discover', '--screenshot', '/tmp/mm-target-fallback.png', '--wait', '30000']))
