from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import get_module_paths
from src.spec.parser import load_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Open waveform in GTKWave")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--generated-dir", default="generated")
    args = parser.parse_args()

    if shutil.which("gtkwave") is None:
        raise SystemExit("gtkwave not found in PATH")

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    if not paths.wave_file.exists():
        raise SystemExit(f"Waveform not found: {paths.wave_file}")

    subprocess.Popen(["gtkwave", str(paths.wave_file)], cwd=PROJECT_ROOT)


if __name__ == "__main__":
    main()