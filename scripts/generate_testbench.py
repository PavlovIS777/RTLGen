from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import get_module_paths
from src.spec.parser import load_spec
from src.tbgen.sv_tb_generator import generate_testbench


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SystemVerilog testbench from golden trace")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--trace", default=None)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    trace_path = Path(args.trace) if args.trace else paths.golden_trace_file
    golden_trace = json.loads(trace_path.read_text(encoding="utf-8"))

    tb_path = generate_testbench(
        spec=spec,
        golden_trace=golden_trace,
        out_path=paths.tb_file,
        wave_path=paths.wave_file,
    )

    payload = {
        "status": "ok",
        "module_name": spec.module_name,
        "artifact": "testbench",
        "path": str(tb_path),
        "waveform": str(paths.wave_file),
    }

    print(json.dumps(payload, ensure_ascii=False) if args.json else f"testbench: {tb_path}")


if __name__ == "__main__":
    main()