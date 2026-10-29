import threading
import time
from PySide6.QtCore import QCoreApplication, QThread
from backend import web_mod_details as web


def test_details_and_pending_request_finish_on_gui_thread(monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    gate = threading.Event()
    started = threading.Event()
    def metadata(self, slug):
        started.set()
        assert gate.wait(2)
        return {'title': slug}
    monkeypatch.setattr(web.SevenDaysModsClient, 'get_metadata', metadata)
    web._cache.clear()
    writes = []
    class TrackedDetails(web.WebModDetails):
        def __setattr__(self, name, value):
            if name == '_busy':
                writes.append(QThread.currentThread())
            super().__setattr__(name, value)
    obj = TrackedDetails()
    threads = []
    results = []
    obj.busyChanged.connect(lambda: threads.append(QThread.currentThread()))
    obj.ready.connect(lambda slug, data: results.append((slug, QThread.currentThread())))
    obj.fetch('first')
    assert started.wait(2)
    obj.fetch('second')
    gate.set()
    deadline = time.monotonic() + 4
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert results == [('second', app.thread())]
    assert threads and all(t == app.thread() for t in threads)
    assert writes and all(t == app.thread() for t in writes)
    assert not obj.busy
