import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "xvast_capture.swift"


@pytest.mark.skipif(shutil.which("swiftc") is None, reason="swiftc not installed")
def test_capture_tool_typechecks():
    proc = subprocess.run(["swiftc", "-typecheck", str(SOURCE)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
