import subprocess
import sys
from pathlib import Path


def test_platform_and_coordinator_with_observed_site_response():
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('smoke_entities.py'))],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
