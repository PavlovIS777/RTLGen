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
    parser.add_argument("--spec", required=True, help="Path to spec JSON")
    parser.add_argument("--trace", default=None, help="Path to generated golden trace JSON")
    parser.add_argument("--generated-dir", default="generated")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    trace_path = Path(args.trace) if args.trace else paths.golden_trace_file
    golden_trace = json.loads(trace_path.read_text(encoding="utf-8"))

    tb_path = generate_testbench(
        spec=spec,
        golden_trace=golden_trace,
        out_path=paths.tb_file,
    )

    print(f"module: {spec.module_name}")
    print(f"testbench: {tb_path}")


if __name__ == "__main__":
    main()