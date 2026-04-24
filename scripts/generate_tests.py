from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.codegen import CodegenService
from src.paths import get_module_paths
from src.spec.parser import load_spec
from src.testgen.scenario_runner import build_pytest_file, run_scenarios, save_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate input scenarios and golden trace")
    parser.add_argument("--spec", required=True, help="Path to spec JSON")
    parser.add_argument("--model", default=None, help="Path to generated Python model")
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--num-scenarios", type=int, default=None)
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Return machine-readable JSON")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    model_path = Path(args.model) if args.model else paths.python_model_file
    model_code = model_path.read_text(encoding="utf-8")

    service = CodegenService()
    scenarios_payload = service.generate_input_scenarios(
        spec=spec,
        model_code=model_code,
        num_scenarios=args.num_scenarios,
        max_cycles=args.max_cycles,
        debug_dir=paths.tests_dir,
    )

    trace_payload = run_scenarios(spec, model_path, scenarios_payload)

    scenarios_path = save_json(scenarios_payload, paths.input_scenarios_file)
    trace_path = save_json(trace_payload, paths.golden_trace_file)
    pytest_path = build_pytest_file(
        spec=spec,
        model_path=model_path,
        scenario_results=trace_payload,
        out_path=paths.pytest_file,
    )

    payload = {
        "status": "ok",
        "module_name": spec.module_name,
        "artifact": "tests",
        "input_scenarios": str(scenarios_path),
        "golden_trace": str(trace_path),
        "pytest": str(pytest_path),
        "scenario_count": len(trace_payload.get("scenarios", [])),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"input_scenarios: {scenarios_path}")
        print(f"golden_trace: {trace_path}")
        print(f"pytest: {pytest_path}")


if __name__ == "__main__":
    main()