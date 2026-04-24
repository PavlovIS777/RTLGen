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
from src.tbgen.sv_tb_generator import generate_testbench_for_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SystemVerilog testbenches from golden trace")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--trace", default=None)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    trace_path = Path(args.trace) if args.trace else paths.golden_trace_file
    golden_trace = json.loads(trace_path.read_text(encoding="utf-8"))

    tb_files: list[str] = []
    wave_files: list[str] = []

    for scenario in golden_trace.get("scenarios", []):
        scenario_name = scenario.get("name", "unnamed_scenario")
        tb_path = generate_testbench_for_scenario(
            spec=spec,
            golden_trace=golden_trace,
            scenario=scenario,
            out_path=paths.testbench_file_for(scenario_name),
            wave_path=paths.wave_file_for(scenario_name),
        )
        tb_files.append(str(tb_path))
        wave_files.append(str(paths.wave_file_for(scenario_name)))

    payload = {
        "status": "ok",
        "module_name": spec.module_name,
        "artifact": "testbenches",
        "count": len(tb_files),
        "tb_dir": str(paths.tb_dir),
        "waves_dir": str(paths.waves_dir),
        "files": tb_files,
        "waveforms": wave_files,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()