"""Sprawdza prawdziwe okno aplikacji na jednorazowym koncie testowym."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['HOME'] = sys.argv[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest
from backend import game_versions as gv
import main

language = sys.argv[2]
assert gv.save_steam_username('logout-test')
gv.GameVersionsManager.refreshAvailable = lambda self: None
gv.GameVersionsManager.startAuth = lambda self: None
original_exec = QGuiApplication.exec
labels = {
    'pl': ('Wylogować konto Steam?', 'Wyloguj', 'Anuluj'),
    'en': ('Log out of Steam?', 'Log out', 'Cancel'),
}


def walk(item):
    yield item
    for child in item.childItems():
        yield from walk(child)


def check():
    try:
        window = next(w for w in QGuiApplication.topLevelWindows() if hasattr(w, 'contentItem'))
        def named(name):
            return next(i for i in walk(window.contentItem()) if i.objectName() == name)
        def click(item):
            point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
            QTest.qWait(550)
        def button(label):
            return next(i for i in walk(dialog) if 'Button' in i.metaObject().className()
                        and i.property('text') == label and i.isVisible())
        def signed_in():
            assert gv.load_steam_username() == 'logout-test'
            assert manager.hasSavedSession
        page = named('steamReleasesPage')
        manager = QQmlEngine.contextForObject(page).contextProperty('GameVersions')
        dialog = named('steamLogoutConfirm')
        title, confirm, cancel = labels[language]
        click(named('steamReleasesLogout'))
        assert dialog.property('opened')
        assert dialog.property('title') == title
        signed_in()
        click(button(cancel))
        assert not dialog.property('opened')
        signed_in()
        click(named('accountButton'))
        click(named('steamAccountLogout'))
        assert dialog.property('opened')
        assert dialog.property('title') == title
        signed_in()
        QTest.keyClick(window, Qt.Key_Escape)
        QTest.qWait(550)
        assert not dialog.property('opened')
        signed_in()
        click(named('accountButton'))
        click(named('steamAccountLogout'))
        assert dialog.property('opened')
        click(button(confirm))
        assert not dialog.property('opened')
        assert gv.load_steam_username() == ''
        assert not manager.hasSavedSession
        print('PASS: page, header, cancel, Escape, confirm', flush=True)
        QGuiApplication.instance().exit(0)
    except Exception:
        import traceback
        traceback.print_exc()
        QGuiApplication.instance().exit(1)


def run(app):
    QTimer.singleShot(700, check)
    return original_exec()


QGuiApplication.exec = run
sys.exit(main.main(['--page', 'steam_releases', '--language', language,
                    '--screenshot', str(Path(sys.argv[1]) / 'timeout.png'), '--wait', '20000']))
