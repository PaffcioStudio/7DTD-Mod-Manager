"""E2E driver for tests/test_backups_ui_e2e.py (not collected by pytest itself).

Runs the REAL app offscreen with a throw-away HOME, then:
  startup migration modpacks/ -> backups/, click trash -> confirmation modal ->
  confirm -> check disk, corrupt instance data, click Restore -> modal -> confirm
  -> check disk. Prints PASS/FAIL lines; exit code 0 only if everything passed.
Usage: python tests/e2e_backups_driver.py <throw-away-home-dir>
"""
import json, os, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(sys.argv[1]); shutil.rmtree(HOME, ignore_errors=True); HOME.mkdir(parents=True)
os.environ.update(HOME=str(HOME), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
sys.path.insert(0, str(ROOT / "src"))
D = HOME / ".7dtd_modmanager"; D.mkdir()

def mk(iid, name):
    p = HOME / "data" / iid
    (p / "Mods" / "M").mkdir(parents=True); (p / "Mods" / "M" / "ModInfo.xml").write_text("<x/>")
    (p / "Saves").mkdir(); (p / "Saves" / "w.sav").write_text("orig-" + iid)
    return p
p1, p2 = mk("inst1", "Alpha"), mk("inst2", "Beta")
(D / "instances.json").write_text(json.dumps({"instances": [
    {"instance_id": "inst1", "name": "Alpha", "data_dir": str(p1), "flags": {"noeos": True}, "created_at": "2026-09-20T10:00:00"},
    {"instance_id": "inst2", "name": "Beta", "data_dir": str(p2), "flags": {"noeos": True}, "created_at": "2026-09-20T10:00:00"}]}))
(D / "settings.json").write_text(json.dumps({"language": "en"}))

from backend import instances as inst_mod, modpacks
from services import filesystem_service as fs
# inst2: backup in the NEW layout; inst1: backup in the LEGACY layout (must be migrated at startup)
r2 = modpacks.create_backup_from_instance(inst_mod.find_instance(inst_mod.load_instances(), "inst2"))
leg = fs.legacy_modpacks_root() / "inst1"; shutil.copytree(p1, leg)
rec1 = modpacks.BackupRecord("inst1", "Alpha", str(p1), {}, str(leg), created_at="2026-09-20T10:00:00", updated_at="2026-09-20T10:00:00", item_count=5)
modpacks.save_backups(modpacks.load_backups() + [rec1])
print("seeded; legacy exists:", leg.is_dir(), "| backups/inst2:", (fs.backups_root() / "inst2").is_dir(), flush=True)

from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import main as appmain

# Test ma byc deterministyczny: gdy na maszynie dev dziala 7DTD, blokady gry
# wylaczaja restore w trzech miejscach (guard w ModpackManager, przycisk
# "Restore backup" w QML przez Game.isRunning z GameDetector, guard w
# instances). Udajemy, ze zadna gra nie dziala - w kazdym z nich.
from backend import game_process as _game_process
from backend import modpack_manager as _modpack_manager
_game_process.find_game_processes = lambda *a, **k: []
_game_process.find_game_pids = lambda *a, **k: []
_game_process.is_game_running = lambda: False
_modpack_manager.is_game_running = lambda: False
inst_mod.find_game_processes = lambda *a, **k: []

results = []
def check(name, ok):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name, flush=True)

def walk(item):
    yield item
    for c in item.childItems():
        yield from walk(c)

def find(win, pred):
    return [it for it in walk(win.contentItem()) if pred(it)]

def cls(it): return it.metaObject().className()
def prop(it, n):
    try: return it.property(n)
    except Exception: return None

def center(it):
    pt = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)); return QPoint(int(pt.x()), int(pt.y()))

def click(win, it):
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, center(it))

def shot(win, name):
    out = os.environ.get("E2E_SHOTS")
    if not out:
        return
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    win.requestUpdate(); QCoreApplication.processEvents()
    win.grabWindow().save(f"{out}/{name}.png")

def visible_buttons(win, text):
    return [it for it in find(win, lambda i: "Button" in cls(i) and prop(i, "text") == text and i.isVisible() and i.width() > 0)]

def modal_open(win, cname):
    return any(prop(i, "opened") is True for i in find(win, lambda i: cname in cls(i)))

steps = []
def step(delay, fn): steps.append((delay, fn))

def run_steps():
    if not steps:
        ok = all(r[1] for r in results)
        print("ALL PASS" if ok else "SOME FAILED", flush=True)
        # os._exit() skips interpreter shutdown, so flush explicitly: with a piped
        # stdout (pytest, CI) the buffered report would otherwise be lost
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(0 if ok else 1)
    delay, fn = steps.pop(0)
    QTimer.singleShot(delay, lambda: (fn(), run_steps()))

win = None
def driver():
    global win
    win = QGuiApplication.topLevelWindows()[0]
    import builtins
    # navigate to the backups page
    from PySide6.QtQuick import QQuickItem
    root = win.contentItem().childItems()[0]
    QTest.keyClick(win, Qt.Key_6, Qt.ControlModifier)
    run_steps()

def s_after_migration():
    check("legacy folder migrated at startup", (fs.backups_root() / "inst1").is_dir() and not (fs.legacy_modpacks_root()).exists())
    recs = {r.instance_id: r.path for r in modpacks.load_backups()}
    check("record path rewritten to backups/", recs.get("inst1") == str(fs.backups_root() / "inst1"))
    shot(win, "01_page")

state = {}
def s_click_trash():
    order = [r.instance_id for r in modpacks.load_backups()]
    state["first"], state["second"] = order[0], order[1]
    print("row order:", order, flush=True)
    trash = find(win, lambda i: "IconButton" in cls(i) and prop(i, "tooltip") == "Delete backup" and i.isVisible() and i.width() > 0)
    check("two trash buttons visible", len(trash) == 2)
    trash.sort(key=lambda i: center(i).y())
    click(win, trash[0])

def s_modal_shown():
    check("delete confirmation modal opened", modal_open(win, "ConfirmModal"))
    shot(win, "02_delete_modal")

def s_confirm_delete():
    btns = visible_buttons(win, "Delete backup")
    check("confirm button present", len(btns) >= 1)
    if btns: click(win, btns[0])

def s_after_delete():
    ids = [r.instance_id for r in modpacks.load_backups()]
    a, b = state["first"], state["second"]
    check("clicked backup deleted (record)", ids == [b])
    check("clicked backup deleted (folder)", not (fs.backups_root() / a).exists())
    check("other backup untouched", (fs.backups_root() / b / "Saves" / "w.sav").exists())
    check("instance data of deleted backup untouched", (HOME / "data" / a / "Saves" / "w.sav").exists())
    shot(win, "03_after_delete")

def s_corrupt_and_restore_click():
    global pr
    pr = HOME / "data" / state["second"]
    (pr / "Saves" / "w.sav").write_text("CORRUPTED"); (pr / "junk.txt").write_text("x")
    shutil.rmtree(pr / "Mods")
    btns = visible_buttons(win, "Restore")
    check("restore button visible", len(btns) == 1)
    if btns: click(win, btns[0])

def s_restore_modal():
    check("restore modal opened", modal_open(win, "Modal") and len(visible_buttons(win, "Restore backup")) >= 1)
    shot(win, "04_restore_modal")

def s_confirm_restore():
    btns = visible_buttons(win, "Restore backup")
    if btns: click(win, btns[0])

def s_after_restore():
    check("restored save content", (pr / "Saves" / "w.sav").read_text() == "orig-" + state["second"])
    check("restored deleted Mods folder", (pr / "Mods" / "M" / "ModInfo.xml").exists())
    check("junk removed (1:1 restore)", not (pr / "junk.txt").exists())
    shot(win, "05_after_restore")

step(1200, s_after_migration); step(100, s_click_trash); step(1500, s_modal_shown); step(100, s_confirm_delete)
step(1500, s_after_delete); step(100, s_corrupt_and_restore_click); step(1500, s_restore_modal)
step(100, s_confirm_restore); step(2500, s_after_restore)

_orig_exec = QGuiApplication.exec
def _patched_exec(*a):
    QTimer.singleShot(1500, driver)
    return _orig_exec()
QGuiApplication.exec = staticmethod(_patched_exec)
sys.exit(appmain.main(["--page", "modpacks"]))
