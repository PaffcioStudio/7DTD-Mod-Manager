"""Sprawdza miniaturę i źródła modów w prawdziwym widoku biblioteki."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
TEST_HOME = tempfile.TemporaryDirectory(prefix='mm-library-ui-')
os.environ.update(HOME=TEST_HOME.name, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from backend import library, mod_thumbs, discover
from backend.library_ops import import_mod_to_library
from backend.scraper_client import SevenDaysModsClient
import main

for folder, title, source in [('Online', 'No Cheat Commands', 'web:no-cheat-commands'),
                               ('Manual', 'Mod importowany ręcznie', 'import')]:
    path = Path(TEST_HOME.name) / folder
    path.mkdir()
    (path / 'ModInfo.xml').write_text(
        f'<xml><ModInfo><Name value="{folder}"/><DisplayName value="{title}"/>'
        '<Version value="1.0.2.0"/><Author value="Paffcio"/></ModInfo></xml>')
    entry = import_mod_to_library(path, source=source, enable=False)
    if folder == 'Online':
        # Prawdziwa grafika z katalogu, zapisana tą samą ścieżką co po pobraniu moda.
        info = SevenDaysModsClient().get_mod('no-cheat-commands')
        mod_thumbs.cache_web_thumbnails('no-cheat-commands', [entry.library_id], info.thumbnail)
        assert mod_thumbs.has_thumb(entry.library_id)

# Nie uruchamiamy dodatkowych zapytań niezwiązanych z widokiem biblioteki.
discover.DiscoverManager.refresh = lambda self: None


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


class TestEngine(QQmlApplicationEngine):
    def load(self, url):
        super().load(url)
        QTimer.singleShot(1000, self.exercise)

    def exercise(self):
        try:
            window = self.rootObjects()[0]
            cards = [i for i in walk(window.contentItem()) if i.metaObject().className().startswith('ModCard_')]
            assert len(cards) == 2, len(cards)
            online = next(c for c in cards if c.property('source') == 'web:no-cheat-commands')
            manual = next(c for c in cards if c.property('source') == 'import')
            assert online.property('sourceLabel') == 'Źródło: Odkrywaj'
            assert manual.property('sourceLabel') == 'Źródło: import ręczny'
            thumb = online.property('thumbUrl')
            assert thumb.startswith('file:')
            images = [i for i in walk(online) if 'Image' in i.metaObject().className()
                      and str(i.property('source').toString()) == thumb]
            assert images
            expr = QQmlExpression(QQmlEngine.contextForObject(images[0]), images[0], 'status === Image.Ready')
            result = expr.evaluate()
            assert not expr.hasError() and result[0], result
            window.grabWindow().save('/tmp/mm-library-origin.png')
            mods = self.rootContext().contextProperty('Mods')
            dropdown = next(i for i in walk(window.contentItem()) if i.objectName() == 'modSourceFilter')
            def click(item):
                point = item.mapToScene(QPointF(item.width()/2, item.height()/2))
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))
                QTest.qWait(300)
            for label, expected, count in [('Pobrane z Odkrywaj', 'discover', 1),
                                           ('Importowane ręcznie', 'manual', 1),
                                           ('Wszystkie źródła', 'all', 2)]:
                click(dropdown)
                choice = next(i for i in walk(window.contentItem()) if i.isVisible() and i.property('text') == label)
                click(choice)
                assert mods.sourceFilter == expected
                assert mods.visibleMods == count
                assert mods.listModel.rowCount() == count
            window.grabWindow().save('/tmp/mm-library-source-filter.png')
            print('PASS: miniatura, źródła i wybór wszystkich trzech filtrów', flush=True)
            QGuiApplication.instance().exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            QGuiApplication.instance().exit(1)


main.QQmlApplicationEngine = TestEngine
sys.exit(main.main(['--language', 'pl', '--page', 'mods', '--screenshot', '/tmp/mm-library-fallback.png', '--wait', '20000', '--width', '1150', '--height', '700']))
