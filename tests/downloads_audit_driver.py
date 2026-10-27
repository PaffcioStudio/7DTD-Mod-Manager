"""Offscreen integration: overflow queue, failed-row removal and history cleanup."""
import os
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
home = Path(sys.argv[1])
home.mkdir(parents=True, exist_ok=True)
os.environ.update(HOME=str(home), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
data=home/'.7dtd_modmanager'
data.mkdir(exist_ok=True)
(data/'settings.json').write_text(json.dumps({'uiScale':float(os.environ.get('AUDIT_SCALE','1'))}))
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtCore import QTimer, QMetaObject, Q_ARG, Qt
from PySide6.QtGui import QGuiApplication
import main
from backend.download_manager import DownloadItem

original = main.DownloadManager
results = []


def walk(obj):
    yield obj
    for child in obj.childItems():
        yield from walk(child)


def factory(*args):
    manager = original(*args)
    manager._timer.stop()
    for i in range(20):
        manager._model.append(DownloadItem('url',str(i),f'Queue test {i}', 'Details',100,
            status='failed' if i % 2 else 'completed', real=True, url='https://example.invalid/a.zip'))
    pending = DownloadItem('game','alpha19.6','Pending game','',100,status='paused',real=True)
    manager._model.append(pending)
    manager._emit_counts()

    def check_ui():
        try:
            window=QGuiApplication.topLevelWindows()[0]
            scrolls=[o for o in walk(window.contentItem())
                     if 'AppScrollView' in o.metaObject().className() and o.isVisible()]
            scroll=next(o for o in scrolls if o.property('contentHeight') > o.height()+500)
            scroll.setProperty('contentY', scroll.property('contentHeight') - scroll.height())
            assert scroll.property('contentY') > 500
            failed=next(i for i in manager._model.items if i.status=='failed')
            manager.removeCompletedAt(failed.id)
            assert failed not in manager._model.items
            manager.clearCompleted()
            assert manager._model.items == [pending]
            manager._ask_missing_game('alpha19.6', lambda: None)
            results.append(True)
            print('PASS scroll overflow, remove failed, clear history preserves paused game',flush=True)
        except Exception as exc:
            print('FAIL',repr(exc),flush=True)
            results.append(False)
    def check_confirmation():
        try:
            window=QGuiApplication.topLevelWindows()[0]
            dialogs=[o for o in walk(window.contentItem()) if 'ConfirmModal' in o.metaObject().className() and o.property('opened')]
            assert len(dialogs)==1
            assert 'alpha19.6' in dialogs[0].property('message')
            for token in list(manager._pending_requests):
                manager.resolveMissingGame(token,False)
            QMetaObject.invokeMethod(dialogs[0],'close')
            manager._bus.goTo('profiles')
            page=next(o for o in walk(window.contentItem()) if 'ProfilesPage' in o.metaObject().className())
            assert QMetaObject.invokeMethod(page,'openEditor',Qt.DirectConnection,Q_ARG('QVariant','main'))
            results.append(True)
            print('PASS missing-game confirmation and instance editor open',flush=True)
        except Exception as exc:
            results.append(False); print('FAIL confirmation/editor',repr(exc),flush=True)

    def check_editor():
        try:
            window=QGuiApplication.topLevelWindows()[0]
            texts=[o.property('text') for o in walk(window.contentItem()) if o.isVisible() and o.property('text')]
            assert 'Game executable' in texts
            results.append(True)
            print('PASS executable selector visible in editor',flush=True)
        except Exception as exc:
            results.append(False); print('FAIL editor',repr(exc),flush=True)
    QTimer.singleShot(700,check_ui)
    QTimer.singleShot(850,check_confirmation)
    QTimer.singleShot(1200,check_editor)
    return manager

main.DownloadManager=factory
code=main.main(['--page','downloads','--width','1150','--height','700',
                '--screenshot',str(home/'downloads.png'),'--wait','1600'])
raise SystemExit(0 if code==0 and results==[True,True,True] else 1)
