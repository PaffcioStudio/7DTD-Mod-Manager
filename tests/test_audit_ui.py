import os
import pytest
from pathlib import Path
import subprocess
import sys


@pytest.mark.parametrize("scale", ["0.85", "1", "1.25"])
def test_downloads_overflow_and_terminal_actions_offscreen(tmp_path, scale):
    driver=Path(__file__).with_name('downloads_audit_driver.py')
    result=subprocess.run([sys.executable,str(driver),str(tmp_path/'home')],
        env=dict(os.environ, AUDIT_SCALE=scale, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software'),
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0, result.stdout+result.stderr
    assert 'PASS scroll overflow' in result.stdout
    assert 'QML:' not in result.stderr


def test_gallery_edge_cases_in_real_qml(tmp_path):
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('gallery_audit_driver.py')),str(tmp_path)],
                          capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'PASS gallery' in result.stdout
