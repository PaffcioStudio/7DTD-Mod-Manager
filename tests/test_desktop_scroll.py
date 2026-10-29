import subprocess
import sys
from pathlib import Path


def test_desktop_scroll_interactions():
    driver = Path(__file__).with_name('desktop_scroll_driver.py')
    result = subprocess.run([sys.executable, str(driver)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout
