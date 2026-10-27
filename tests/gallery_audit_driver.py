"""Exercise actual QML gallery for empty/single/multiple/error/large images."""
import os
from pathlib import Path
import sys
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from PIL import Image
from PySide6.QtCore import QUrl,QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow
from services.icon_service import IconService

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
large=out/'large.png';Image.new('RGB',(5000,5000),'#bf7942').save(large)
app=QGuiApplication([])
engine=QQmlEngine();icons=IconService(ROOT/'assets/icons')
engine.rootContext().setContextProperty('Icons',icons)
component=QQmlComponent(engine)
component.setData(f'''
import QtQuick
import "{(ROOT / 'qml/components').as_uri()}" as C
Item {{
    width: 800; height: 600
    property string imageUrl: ""
    property bool passed: false
    property int galleryStatus: gallery.children[0].status
    property int viewerStatus: viewer.children[1].children[0].status
    property bool boundedDecode: gallery.children[0].sourceSize.width <= 1280
        && viewer.children[1].children[0].sourceSize.width <= 3000
        && viewer.children[1].children[0].sourceSize.height <= 3000
    C.ScreenshotGallery {{ id: gallery; objectName: "gallery"; width: 600; height: 250 }}
    C.ImageViewer {{ id: viewer; objectName: "viewer" }}
    function exercise() {{
        gallery.images = []
        if (gallery.count !== 0 || gallery.visible) return
        gallery.images = [imageUrl]
        gallery.next(); gallery.prev()
        if (gallery.currentIndex !== 0 || gallery.multiple) return
        const many = Array(20).fill(imageUrl)
        gallery.images = many
        gallery.prev()
        if (gallery.currentIndex !== 19) return
        gallery.next()
        if (gallery.currentIndex !== 0) return
        viewer.openAt(many, 19); viewer.next()
        if (!viewer.opened || viewer.currentIndex !== 0) return
        viewer.prev()
        if (viewer.currentIndex !== 19) return
        viewer.close()
        viewer.openAt([], 0)
        if (viewer.opened) return
        gallery.images = ["file:///nonexistent-gallery-audit.png"]
        passed = true
    }}
    function loadLarge() {{ gallery.images = [imageUrl]; viewer.openAt([imageUrl], 0) }}
}}
'''.encode(),QUrl.fromLocalFile(str(out/'Harness.qml')))
assert not component.isError(),[e.toString() for e in component.errors()]
root=component.create();assert root is not None
window=QQuickWindow();window.resize(800,600);root.setParentItem(window.contentItem());window.show()
root.setProperty('imageUrl',QUrl.fromLocalFile(str(large)).toString())
QMetaObject.invokeMethod(root,'exercise'); assert root.property('passed')
QTest.qWait(100)

for _ in range(100):
    if root.property('galleryStatus') != 2:
        break
    QTest.qWait(10)
assert root.property('galleryStatus') == 3, 'broken image must enter Error state'
QMetaObject.invokeMethod(root,'loadLarge')
for _ in range(100):
    app.processEvents(); QTest.qWait(10)
    if root.property('galleryStatus') == 1 and root.property('viewerStatus') == 1:
        break
assert root.property('galleryStatus') == 1 and root.property('viewerStatus') == 1
assert root.property('boundedDecode')
print('PASS gallery: 0, 1, 20 images, broken URL, 5000px source, bounded decode',flush=True)
root.deleteLater();app.processEvents()
