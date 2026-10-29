"""Sprawdza anulowanie i pobieranie mimo braku gry w prawdziwym QML."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
TEST_HOME = tempfile.TemporaryDirectory(prefix='mm-discover-ui-')
os.environ.update(HOME=TEST_HOME.name, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtGui import QGuiApplication
from backend import discover, download_manager as dm, web_mod_details as web
import main

# Dane sieciowe są stałe, ale przyciski, modal i panel działają naprawdę.
discover.DiscoverManager.refresh = lambda self: None
dm.resolve_downloaded_branch = lambda branch: ''
dm.DownloadManager._start_mod_worker = Mock()
web.SevenDaysModsClient._fetch_mod = lambda self, slug: ({
    'id': 'test-mod', 'slug': slug, 'title': 'No Cheat Commands',
    'current_version': '1.0.2.0', 'game_versions': ['V3 Mods'],
    'description': 'Test anulowania pobierania.',
    'mod_files': [{'id': '1', 'filename': 'NoCheatCommands-v1.0.2.zip'}],
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


def click_text(window, label, scope=None):
    buttons = [i for i in walk(scope or window.contentItem()) if 'Button' in i.metaObject().className()
               and i.isVisible() and i.property('text') == label]
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
            modal = next(i for i in walk(window.contentItem())
                         if 'ConfirmModal' in i.metaObject().className() and i.property('alternativeLabel'))
            for attempt in range(5):
                js(drawer, 'openWith("example-mod", "v3")')
                QTest.qWait(400)
                click_text(window, 'Pobierz', drawer)
                assert modal.property('opened')
                if attempt == 4:
                    window.grabWindow().save('/tmp/mm-missing-game-dialog.png')
                    click_text(window, 'Pobierz mimo to')
                    entry, = downloads._model.items
                    assert entry.ignore_missing_game and entry.status == 'downloading'
                    assert not entry.install_game
                else:
                    click_text(window, 'Anuluj')
                    assert not downloads._model.items
                    assert not downloads._pending_requests
                assert not modal.property('opened')
                assert drawer.property('opened')
                # Klik w tło zamyka panel tak jak w zgłoszeniu.
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(350, 350))
                QTest.qWait(400)
                assert not drawer.property('opened')
            print('PASS: 4x Pobierz > Anuluj > zamknij panel; Pobierz mimo to', flush=True)
            QGuiApplication.instance().exit(0)
        except Exception:
            import traceback
            traceback.print_exc()
            QGuiApplication.instance().exit(1)


main.QQmlApplicationEngine = TestEngine
sys.exit(main.main(['--language', 'pl', '--page', 'discover', '--screenshot', '/tmp/mm-discover-fallback.png', '--wait', '30000']))
