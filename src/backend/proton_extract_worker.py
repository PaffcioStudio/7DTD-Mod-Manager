"""Extract a verified GE-Proton archive outside the Qt/Python GUI process.

This module is deliberately stdlib-only. It is invoked by the manager's bundled
Python interpreter as a separate process, preventing gzip/tar filesystem work
from contending for the GIL of the GUI process.
"""
from __future__ import annotations

import sys
import tarfile
from pathlib import Path


def extract(archive: Path, destination: Path) -> None:
    # Keep Python's strict extraction filter. Never replace this with an
    # unrestricted `tar -xf`: archives can contain hostile paths or links.
    with tarfile.open(archive, mode="r:gz") as source:
        for member in source:
            source.extract(member, destination, filter="data")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: proton_extract_worker.py ARCHIVE DESTINATION", file=sys.stderr)
        return 2
    try:
        extract(Path(args[0]), Path(args[1]))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
