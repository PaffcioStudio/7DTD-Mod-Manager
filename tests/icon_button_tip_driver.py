"""Driver testu tooltipu IconButton: przycisk jest PRZESUWANY po utworzeniu,
a tooltip ma wyladowac nad nim (a nie w miejscu z chwili tworzenia)."""
import os, sys
from pathlib import Path
os.environ["QT_QPA_PLATFORM"]="offscreen"; os.environ["QT_QUICK_BACKEND"]="software"
from PySide6.QtCore import QUrl, QPoint, QTimer, QObject, Slot, QMetaObject, Q_RETURN_ARG, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
app=QGuiApplication([])
class _Icons(QObject):
    @Slot(str,str,result=str)
    def url(self,n,c): return ""
ic=_Icons()
eng=QQmlApplicationEngine()
eng.rootContext().setContextProperty("Icons",ic)
eng.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / 'qml' / 'IconButtonTipHarness.qml')))
win=eng.rootObjects()[0]
def step1(): QTest.mouseMove(win, QPoint(517,317))
def step2():
    info=QMetaObject.invokeMethod(win,"tipInfo",Qt.DirectConnection,Q_RETURN_ARG("QVariant"))
    i=info.toVariant() if hasattr(info,'toVariant') else info
    if not i: print("NO TIP"); app.quit(); return
    exp_x=i['bx']+(i['bw']-i['tw'])/2; exp_y=i['by']-i['th']-8
    print("button", round(i['bx']),round(i['by']),"tip", round(i['tx']),round(i['ty']),"expected", round(exp_x),round(exp_y),"opacity",round(i['op'],2))
    ok = abs(i['tx']-exp_x)<3 and abs(i['ty']-exp_y)<3
    print("TIP OK" if ok else "TIP WRONG")
    sys.stdout.flush(); os._exit(0 if ok else 1)
QTimer.singleShot(500, step1)
QTimer.singleShot(1800, step2)
app.exec()
