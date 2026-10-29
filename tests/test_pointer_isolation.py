import subprocess
import sys
from pathlib import Path


def test_controls_and_modal_do_not_click_background():
    driver = Path(__file__).with_name('pointer_isolation_driver.py')
    result = subprocess.run([sys.executable, str(driver)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout
