"""Klikanie panelu moda nie może zmieniać moda ani uruchamiać kart w tle."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
TEST_HOME = tempfile.TemporaryDirectory(prefix='mm-overlay-ui-')
os.environ.update(HOME=TEST_HOME.name, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
sys.path.insert(0, str(ROOT / 'src'))
from PIL import Image
from PySide6.QtCore import QCoreApplication, QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from backend import discover, download_manager as dm, web_mod_details as web
import main

image_path = Path(TEST_HOME.name) / 'cover.png'
Image.new('RGB', (800, 450), '#384754').save(image_path)
discover.DiscoverManager.refresh = lambda self: None
CATALOG_ITEMS = [{'slug': f'under-{index}', 'title': f'Mod under-{index}',
    'summary': '', 'author': 'Tester', 'thumbnail': '', 'category': 'Gameplay',
    'versions': 'V3 Mods', 'game_version': 'v3', 'version': '1', 'downloads': 0,
    'url': 'https://7daystodiemods.com/mods/test'} for index in range(8)]
def catalog_data(*args, **kwargs):
    return {'items': CATALOG_ITEMS, 'total': 8, 'pages': 1, 'page': 1, 'offline': False, 'categories': [], 'versions': []}
discover.fetch_catalog = catalog_data
discover.fetch_local_catalog = catalog_data

dm.resolve_downloaded_branch = lambda branch: 'public'
dm.DownloadManager._is_downloaded_game_version = staticmethod(lambda _: True)
dm.DownloadManager._start_mod_worker = Mock()
web.SevenDaysModsClient._fetch_mod = lambda self, slug: ({
    'id': slug, 'slug': slug, 'title': slug,
    'current_version': 'Latest', 'game_versions': ['V3 Mods', 'V2 Mods'],
    'mod_files': [{'id': 'chosen', 'filename': 'Mod.zip', 'mod_version': '3.2.9.4'}],
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


def center(item):
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2))
    return QPoint(int(point.x()), int(point.y()))


def text_button(window, text, scope=None):
    buttons = [i for i in walk(scope or window.contentItem()) if 'Button' in i.metaObject().className()
               and i.isVisible() and i.property('text') == text]
    assert len(buttons) == 1, (text, len(buttons))
    return buttons[0]


class TestEngine(QQmlApplicationEngine):
    def load(self, url):
        super().load(url)
        QTimer.singleShot(700, self.exercise)

    def exercise(self):
        try:
            window = self.rootObjects()[0]
            catalog = self.rootContext().contextProperty('Discover')
            catalog._items = CATALOG_ITEMS
            catalog.changed.emit()
            QTest.qWait(300)
            results = next(i for i in walk(window.contentItem())
                           if 'ListView' in i.metaObject().className() and i.property('count') == 8)
            results.setProperty('contentY', 100)
            drawer = next(i for i in walk(window.contentItem()) if 'WebModDrawer' in i.metaObject().className())
            downloads = self.rootContext().contextProperty('Downloads')
            js(drawer, 'openWith("selected-mod", "public")')
            QTest.qWait(400)
            js(drawer, 'var d = Object.assign({}, details); d.gallery = ["' + image_path.as_uri() + '"]; details = d')
            QTest.qWait(300)
            def wheel_at(point):
                event = QWheelEvent(QPointF(point), QPointF(window.mapToGlobal(point)),
                    QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
                QCoreApplication.sendEvent(window, event)
                QTest.qWait(50)
            before_wheel = results.property('contentY')
            wheel_at(QPoint(350, 300))
            assert results.property('contentY') == before_wheel, 'Kółko przeszło przez osłonę panelu'
            download = text_button(window, 'Pobierz', drawer)
            point = center(download)
            cards = [i for i in walk(window.contentItem()) if i.property('downloadKey')]
            window.grabWindow().save('/tmp/mm-overlay-position.png')
            # Punkt testowy musi leżeć nad klikalną częścią innego moda.
            assert any(0 <= c.mapFromScene(QPointF(point)).x() <= c.width()
                       and 0 <= c.mapFromScene(QPointF(point)).y() < c.height()-58 for c in cards)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(300)
            assert drawer.property('slug') == 'selected-mod' and drawer.property('opened')
            cancel = text_button(window, 'Anuluj')
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center(cancel))
            QTest.qWait(600)
            assert drawer.property('slug') == 'selected-mod' and drawer.property('opened')
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(300)
            accept = text_button(window, 'Pobierz mimo to')
            accept_point = center(accept)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, accept_point)
            QTest.qWait(20)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, accept_point)
            QTest.qWait(100)
            assert drawer.property('slug') == 'selected-mod' and drawer.property('opened')
            entry, = downloads._model.items
            assert entry.ref_id == 'selected-mod'
            QTest.qWait(600)
            outside = QPoint(350, 300)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, outside)
            QTest.qWait(20)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, outside)
            assert not drawer.property('opened') and drawer.property('slug') == 'selected-mod'
            QTest.qWait(450)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, outside)
            QTest.qWait(400)
            assert drawer.property('opened') and drawer.property('slug').startswith('under-')
            js(drawer, 'close()')
            QTest.qWait(500)
            results = next(i for i in walk(window.contentItem())
                           if 'ListView' in i.metaObject().className() and i.property('count') == 8)
            wheel_y = results.property('contentY')
            wheel_at(QPoint(600, 350))
            assert results.property('contentY') == wheel_y + 360
            old_y = results.property('contentY')
            start = QPoint(600, 350)
            QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
            for offset in range(20, 161, 20):
                QTest.mouseMove(window, QPoint(start.x(), start.y()-offset), 30)
            QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(start.x(), start.y()-160))
            QTest.qWait(300)
            assert results.property('contentY') == old_y, 'Lista przewija się po przeciągnięciu myszą'
            assert not drawer.property('opened'), 'Przeciągnięcie listy otworzyło moda'
            print('PASS: panel, potwierdzenie, szybki drugi klik, odblokowanie tła i brak przewijania LPM', flush=True)
            QGuiApplication.instance().exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            QGuiApplication.instance().exit(1)


main.QQmlApplicationEngine = TestEngine
sys.exit(main.main(['--language', 'pl', '--page', 'discover', '--screenshot', '/tmp/mm-overlay-fallback.png', '--wait', '30000']))
