from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reference_model.loader import instantiate_reference_model
from src.ui.renderer import ConsoleUI


ui = ConsoleUI()


def short_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def run_module_reference_tests(module_dir: Path) -> int:
    tests_dir = module_dir / "tests"
    golden_trace_path = tests_dir / "golden_trace.json"

    if not golden_trace_path.exists():
        ui.error(f"Missing file: {golden_trace_path}")
        return 1

    payload = json.loads(golden_trace_path.read_text(encoding="utf-8"))
    module_name = payload.get("module_name", module_dir.name)
    module_description = payload.get("module_description", "")
    scenarios = payload.get("scenarios", [])

    model_path = module_dir / f"{module_name}_reference_model.py"

    if not model_path.exists():
        ui.error(f"Missing file: {model_path}")
        return 1

    ui.title("REFERENCE MODEL VALIDATION")
    ui.kv("Module", module_name, "bold bright_cyan")
    if module_description:
        ui.kv("Description", "")
        ui.paragraph(module_description, indent=2)
    ui.kv("Scenarios", str(len(scenarios)), "bold bright_cyan")
    ui.separator()

    ui.info("Scenario plan")
    for index, scenario in enumerate(scenarios, start=1):
        name = scenario.get("name", f"scenario_{index}")
        desc = scenario.get("description", "")
        num_cycles = scenario.get("num_cycles", len(scenario.get("trace", [])))
        ui.scenario_plan_item(index, len(scenarios), name, num_cycles, desc)

    ui.separator()
    ui.info("Execution")

    passed = 0
    failed = 0
    failure_details: list[str] = []

    for index, scenario in enumerate(scenarios, start=1):
        scenario_name = scenario.get("name", f"scenario_{index}")
        trace = scenario.get("trace", [])

        model = instantiate_reference_model(model_path)
        mismatch_found = False

        for item in trace:
            cycle = item["cycle"]
            inputs = item["inputs"]
            expected = item["outputs"]
            got = model.step(inputs)

            if got != expected:
                mismatch_found = True
                failed += 1
                ui.scenario_result(index, len(scenarios), scenario_name, passed=False)
                failure_details.append(
                    f"Scenario : {scenario_name}\n"
                    f"Cycle    : {cycle}\n"
                    f"Inputs   : {short_json(inputs)}\n"
                    f"Expected : {short_json(expected)}\n"
                    f"Got      : {short_json(got)}"
                )
                break

        if not mismatch_found:
            passed += 1
            ui.scenario_result(index, len(scenarios), scenario_name, passed=True)

    ui.separator()
    ui.info("Summary")
    ui.summary_row("Total", len(scenarios), "bright_white")
    ui.summary_row("Passed", passed, "bright_green")
    ui.summary_row("Failed", failed, "bright_red" if failed else "bright_green")

    if failure_details:
        ui.separator()
        ui.error("Failure details")
        for item in failure_details:
            ui.paragraph(item, indent=2)
            ui.separator()

    ui.hr("═", "bright_cyan")
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Readable validation for generated reference model")
    parser.add_argument("--module-dir", required=True, help="Example: generated/counter")
    args = parser.parse_args()

    module_dir = (PROJECT_ROOT / args.module_dir).resolve()
    raise SystemExit(run_module_reference_tests(module_dir))


if __name__ == "__main__":
    main()