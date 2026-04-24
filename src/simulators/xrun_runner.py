from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_xrun(
    rtl_path: str | Path,
    tb_path: str | Path,
    enable: bool = False,
) -> dict:
    rtl_path = Path(rtl_path)
    tb_path = Path(tb_path)

    if not enable:
        return {
            "status": "skipped",
            "reason": "xrun is disabled. Pass --enable-xrun to try running it.",
            "rtl_path": str(rtl_path),
            "tb_path": str(tb_path),
        }

    if shutil.which("xrun") is None:
        return {
            "status": "skipped",
            "reason": "xrun was not found in PATH.",
            "rtl_path": str(rtl_path),
            "tb_path": str(tb_path),
        }

    cmd = ["xrun", "-sv", str(rtl_path), str(tb_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "command": " ".join(cmd),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "rtl_path": str(rtl_path),
        "tb_path": str(tb_path),
    }
