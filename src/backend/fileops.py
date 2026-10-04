"""Operacje na plikach z raportowaniem postępu i możliwością przerwania.

Port 1:1 ze starego projektu (7dtd-mod-manager/fileops.py, etap 3 migracji).

Te funkcje są świadomie "płaskie" (plik po pliku, katalog po katalogu) zamiast
korzystać z shutil.copytree/rmtree/move w jednym strzale - dzięki temu można
wołać callback po każdym pliku i sprawdzać flagę anulowania w trakcie.
Używane przez warstwę biblioteki (library_ops.py) i workerów, żeby długie
operacje (kopiowanie modów, usuwanie) nie blokowały głównego wątku UI.
"""
from __future__ import annotations

import errno
import os
import shutil
import threading
from pathlib import Path
from services.i18n_message import message as i18n_message
from typing import Callable, Iterable, Optional

ProgressCallback = Callable[[int, int, str], None]


class OperationCancelled(Exception):
    """Podniesione, gdy użytkownik przerwał operację plikową."""


class InsufficientDiskSpace(Exception):
    """Za mało wolnego miejsca na dysku. ``str(exc)`` to gotowa koperta
    i18n (``__I18N__:...``), więc UI pokazuje przetłumaczony komunikat
    z ilością potrzebnego i dostępnego miejsca zamiast surowego Errno 28."""


# zapas na metadane systemu plików, logi, pliki tymczasowe gry itp.
FREE_SPACE_MARGIN = 256 * 1024 * 1024


def format_size(num_bytes: int) -> str:
    """Rozmiar czytelny dla człowieka (binarnie, np. ``7.5 GB``)."""
    size = float(max(0, int(num_bytes)))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover


def _existing_ancestor(path: Path) -> Path:
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def free_space(path: Path | str) -> int:
    """Wolne bajty na systemie plików, na którym leży (lub powstanie) path."""
    return shutil.disk_usage(_existing_ancestor(Path(path))).free


def ensure_free_space(path: Path | str, required: int, *, margin: int = FREE_SPACE_MARGIN) -> None:
    """Rzuca InsufficientDiskSpace, jeśli na dysku z ``path`` jest mniej niż
    ``required`` + ``margin`` bajtów. ``required <= 0`` nic nie sprawdza."""
    if required is None or required <= 0:
        return
    free = free_space(path)
    needed = int(required) + max(0, int(margin))
    if free < needed:
        raise InsufficientDiskSpace(i18n_message("download.error.noSpace", {
            "path": str(_existing_ancestor(Path(path))),
            "need": format_size(needed),
            "free": format_size(free),
        }))


def raise_if_no_space(exc: OSError, path: Path | str) -> None:
    """Zamienia surowe OSError(ENOSPC) na InsufficientDiskSpace (wołać w
    ``except OSError`` wokół zapisu). Inne błędy OSError zostają bez zmian."""
    if getattr(exc, "errno", None) != errno.ENOSPC:
        return
    try:
        free = free_space(path)
    except OSError:
        free = 0
    raise InsufficientDiskSpace(i18n_message("download.error.noSpaceDuringWrite", {
        "path": str(_existing_ancestor(Path(path))),
        "free": format_size(free),
    })) from exc


def same_device(a: Path | str, b: Path | str) -> bool:
    """Czy dwie ścieżki leżą na tym samym systemie plików (rename = O(1))."""
    try:
        return os.stat(_existing_ancestor(Path(a))).st_dev == os.stat(_existing_ancestor(Path(b))).st_dev
    except OSError:
        return False


def tree_size(path: Path | str) -> int:
    """Suma rozmiarów plików w drzewie (symlinki nie są śledzone)."""
    path = Path(path)
    if path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            fp = os.path.join(root, name)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def check_cancel(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled(i18n_message("common.operationCancelled"))


def count_files(path: Path | str) -> int:
    """Liczy pliki (nie katalogi) w drzewie - używane do wyznaczenia 100% postępu.

    Symlinki do katalogów liczą się jak pliki (jeden "krok" do usunięcia/
    przetworzenia, nigdy nie wchodzimy rekursywnie w ich zawartość - zob.
    remove_tree_with_progress) - os.walk() klasyfikuje je do dirnames, nie
    filenames, nawet z domyślnym followlinks=False, więc trzeba je doliczyć
    ręcznie, inaczej drzewo z samymi symlinkami (typowy folder Mods/
    instancji - zob. mod_activation.py) liczy 0 plików."""
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        return 1
    total = 0
    for root, dirs, files in os.walk(path):
        total += len(files)
        total += sum(1 for d in dirs if (Path(root) / d).is_symlink())
    return total


def _report(progress_cb: Optional[ProgressCallback], done: int, total: int, label: str) -> None:
    if progress_cb is not None:
        progress_cb(done, max(total, 1), label)


def copy_tree_with_progress(
    src: Path | str,
    dst: Path | str,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Kopiuje plik lub całe drzewo katalogów, zgłaszając postęp po każdym pliku."""
    src = Path(src)
    dst = Path(dst)
    total = count_files(src)

    if src.is_file() or src.is_symlink():
        dst.parent.mkdir(parents=True, exist_ok=True)
        check_cancel(cancel_event)
        if src.is_symlink():
            linkto = os.readlink(src)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(linkto, dst)
        else:
            shutil.copy2(src, dst)
        _report(progress_cb, 1, total, src.name)
        return

    done = 0
    _report(progress_cb, 0, total, i18n_message("fileops.preparing", {"name": src.name}))
    for dirpath, _dirnames, filenames in os.walk(src, followlinks=False):
        check_cancel(cancel_event)
        rel = Path(dirpath).relative_to(src)
        target_dir = dst if str(rel) == "." else dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for fname in filenames:
            check_cancel(cancel_event)
            sp = Path(dirpath) / fname
            tp = target_dir / fname
            if sp.is_symlink():
                linkto = os.readlink(sp)
                if tp.exists() or tp.is_symlink():
                    tp.unlink()
                os.symlink(linkto, tp)
            else:
                shutil.copy2(sp, tp)
            done += 1
            label = fname if str(rel) == "." else str(rel / fname)
            _report(progress_cb, done, total, label)
    _report(progress_cb, total, total, i18n_message("fileops.done"))


def remove_tree_with_progress(
    path: Path | str,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Usuwa plik lub całe drzewo katalogów, zgłaszając postęp po każdym pliku.

    NAPRAWIONE 28.08.2026 w starym projekcie (zgłoszenie użytkownika:
    usunięcie instancji zostawiało folder Mods/ pełen martwych symlinków):
    os.walk() klasyfikuje symlinki do katalogów do dirnames, NIGDY do
    filenames - nawet z domyślnym followlinks=False. Poprzednia wersja
    iterowała wyłącznie po filenames, więc symlinki-katalogi (dokładnie to,
    czym są wpisy w Mods/ instancji - zob. mod_activation.py) nigdy nie
    trafiały do unlink() i zostawały na dysku. Naprawa: przy każdym katalogu
    w drzewie sprawdzamy jego bezpośrednie dzieci - te, które same są
    symlinkami, kasujemy przez unlink() (jeden krok, NIGDY nie wchodzimy
    w ich zawartość, więc plik docelowy poza drzewem - np. w bibliotece -
    jest zawsze bezpieczny), zanim os.rmdir() zostanie wywołane na katalogu.
    """
    path = Path(path)
    if not path.exists():
        _report(progress_cb, 1, 1, i18n_message("fileops.done"))
        return
    if path.is_file() or path.is_symlink():
        check_cancel(cancel_event)
        path.unlink()
        _report(progress_cb, 1, 1, path.name)
        return

    total = count_files(path)
    done = 0
    _report(progress_cb, 0, total, i18n_message("fileops.preparing", {"name": path.name}))
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        check_cancel(cancel_event)
        for fname in filenames:
            check_cancel(cancel_event)
            fp = Path(dirpath) / fname
            try:
                fp.unlink()
            except FileNotFoundError:
                pass
            done += 1
            _report(progress_cb, done, total, fname)
        for dname in dirnames:
            check_cancel(cancel_event)
            dp = Path(dirpath) / dname
            if not dp.is_symlink():
                continue  # prawdziwy podkatalog - już opróżniony (topdown=False), zniknie przez rmdir niżej
            try:
                dp.unlink()
            except FileNotFoundError:
                pass
            done += 1
            _report(progress_cb, done, total, dname)
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
    _report(progress_cb, total, total, i18n_message("fileops.done"))


def move_tree_with_progress(
    src: Path | str,
    dst: Path | str,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Przenosi plik/katalog. Na tym samym systemie plików to zwykły rename
    (błyskawiczny), w przeciwnym razie kopiuje plik po pliku, a potem kasuje źródło."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel_event)

    same_device = False
    try:
        same_device = src.stat().st_dev == dst.parent.stat().st_dev
    except OSError:
        same_device = False

    if same_device:
        total = count_files(src)
        _report(progress_cb, 0, total, f"Przenoszenie: {src.name}")
        shutil.move(str(src), str(dst))
        _report(progress_cb, total, total, f"Przeniesiono: {src.name}")
        return

    copy_tree_with_progress(src, dst, progress_cb=progress_cb, cancel_event=cancel_event)
    remove_tree_with_progress(src, cancel_event=cancel_event)


def move_many_with_progress(
    pairs: Iterable[tuple[Path, Path]],
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    label_prefix: Optional[Callable[[int, int], str]] = None,
) -> None:
    """Przenosi wiele drzew plików, raportując jeden wspólny pasek postępu."""
    pairs = list(pairs)
    totals = [count_files(s) for s, _ in pairs]
    grand_total = sum(totals) or 1
    done_before = 0
    for i, ((src, dst), total) in enumerate(zip(pairs, totals)):
        check_cancel(cancel_event)
        prefix = label_prefix(i, len(pairs)) if label_prefix else ""

        def cb(done: int, _t: int, label: str, base: int = done_before, pre: str = prefix) -> None:
            full_label = f"{pre}{label}" if pre else label
            _report(progress_cb, base + done, grand_total, full_label)

        move_tree_with_progress(src, dst, progress_cb=cb, cancel_event=cancel_event)
        done_before += total
    _report(progress_cb, grand_total, grand_total, i18n_message("fileops.done"))


def copy_many_with_progress(
    pairs: Iterable[tuple[Path, Path]],
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    label_prefix: Optional[Callable[[int, int], str]] = None,
) -> None:
    """Kopiuje wiele drzew plików, raportując jeden wspólny pasek postępu."""
    pairs = list(pairs)
    totals = [count_files(s) for s, _ in pairs]
    grand_total = sum(totals) or 1
    done_before = 0
    for i, ((src, dst), total) in enumerate(zip(pairs, totals)):
        check_cancel(cancel_event)
        prefix = label_prefix(i, len(pairs)) if label_prefix else ""

        def cb(done: int, _t: int, label: str, base: int = done_before, pre: str = prefix) -> None:
            full_label = f"{pre}{label}" if pre else label
            _report(progress_cb, base + done, grand_total, full_label)

        copy_tree_with_progress(src, dst, progress_cb=cb, cancel_event=cancel_event)
        done_before += total
    _report(progress_cb, grand_total, grand_total, i18n_message("fileops.done"))


def remove_many_with_progress(
    paths: Iterable[Path],
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    label_prefix: Optional[Callable[[int, int], str]] = None,
) -> None:
    """Usuwa wiele drzew plików, raportując jeden wspólny pasek postępu."""
    paths = list(paths)
    totals = [count_files(p) for p in paths]
    grand_total = sum(totals) or 1
    done_before = 0
    for i, (p, total) in enumerate(zip(paths, totals)):
        check_cancel(cancel_event)
        prefix = label_prefix(i, len(paths)) if label_prefix else ""

        def cb(done: int, _t: int, label: str, base: int = done_before, pre: str = prefix) -> None:
            full_label = f"{pre}{label}" if pre else label
            _report(progress_cb, base + done, grand_total, full_label)

        remove_tree_with_progress(p, progress_cb=cb, cancel_event=cancel_event)
        done_before += total
    _report(progress_cb, grand_total, grand_total, i18n_message("fileops.done"))
