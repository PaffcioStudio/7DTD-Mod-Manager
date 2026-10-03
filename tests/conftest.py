"""Konfiguracja pytest: dodaje src/ do sys.path, żeby `from backend import ...`
działało bez ustawiania PYTHONPATH (uruchamianie: `python3 -m pytest tests`)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
