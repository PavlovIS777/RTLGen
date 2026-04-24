from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reference_model.loader import instantiate_reference_model


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def color(text: str, *styles: str) -> str:
    return "".join(styles) + text + C.RESET


def line(char: str = "─", width: int = 88) -> str:
    return char * width


def wrap_block(text: str, indent: str = "", width: int = 88) -> str:
    return textwrap.fill(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def short_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def print_header(module_name: str, module_description: str, model_path: Path, trace_path: Path, scenario_count: int) -> None:
    print(color(line("═"), C.CYAN))
    print(color("REFERENCE MODEL VALIDATION", C.BOLD, C.CYAN))
    print(color(line("═"), C.CYAN))
    print(color("Module", C.BOLD), f": {module_name}")
    if module_description:
        print(color("Description", C.BOLD), ":")
        print(wrap_block(module_description, indent="  "))
    print(color("Model", C.BOLD), f": {model_path}")
    print(color("Trace", C.BOLD), f": {trace_path}")
    print(color("Scenarios", C.BOLD), f": {scenario_count}")
    print(color(line("─"), C.GRAY))


def print_scenario_plan(scenarios: list[dict]) -> None:
    print(color("Scenario plan", C.BOLD, C.BLUE))
    for index, scenario in enumerate(scenarios, start=1):
        name = scenario.get("name", f"scenario_{index}")
        desc = scenario.get("description", "")
        num_cycles = scenario.get("num_cycles", len(scenario.get("trace", [])))

        print(f"  [{index}] {name}  {color(f'({num_cycles} cycles)', C.DIM)}")
        if desc:
            print(wrap_block(desc, indent="      ", width=88))
    print(color(line("─"), C.GRAY))


def run_module_reference_tests(module_dir: Path) -> int:
    model_path = module_dir / "reference_model.py"
    tests_dir = module_dir / "tests"
    golden_trace_path = tests_dir / "golden_trace.json"

    if not model_path.exists():
        print(color(f"ERROR: reference model not found: {model_path}", C.RED))
        return 1

    if not golden_trace_path.exists():
        print(color(f"ERROR: golden trace not found: {golden_trace_path}", C.RED))
        return 1

    payload = json.loads(golden_trace_path.read_text(encoding="utf-8"))
    module_name = payload.get("module_name", module_dir.name)
    module_description = payload.get("module_description", "")
    scenarios = payload.get("scenarios", [])

    print_header(
        module_name=module_name,
        module_description=module_description,
        model_path=model_path,
        trace_path=golden_trace_path,
        scenario_count=len(scenarios),
    )
    print_scenario_plan(scenarios)

    passed = 0
    failed = 0
    failure_details: list[str] = []

    print(color("Execution", C.BOLD, C.BLUE))

    for index, scenario in enumerate(scenarios, start=1):
        scenario_name = scenario.get("name", f"scenario_{index}")
        trace = scenario.get("trace", [])

        model = instantiate_reference_model(model_path)

        mismatch_found = False
        mismatch_message = ""

        for item in trace:
            cycle = item["cycle"]
            inputs = item["inputs"]
            expected = item["outputs"]

            got = model.step(inputs)

            if got != expected:
                mismatch_found = True
                mismatch_message = (
                    f"Scenario : {scenario_name}\n"
                    f"Cycle    : {cycle}\n"
                    f"Inputs   : {short_json(inputs)}\n"
                    f"Expected : {short_json(expected)}\n"
                    f"Got      : {short_json(got)}"
                )
                failure_details.append(mismatch_message)
                failed += 1
                print(color(f"  FAIL  [{index}/{len(scenarios)}] {scenario_name}", C.BOLD, C.RED))
                break

        if not mismatch_found:
            passed += 1
            print(color(f"  PASS  [{index}/{len(scenarios)}] {scenario_name}", C.BOLD, C.GREEN))

    print(color(line("─"), C.GRAY))
    print(color("Summary", C.BOLD, C.BLUE))
    print(f"  Total   : {len(scenarios)}")
    print(color(f"  Passed  : {passed}", C.GREEN if passed else C.DIM))
    print(color(f"  Failed  : {failed}", C.RED if failed else C.DIM))

    if failure_details:
        print(color(line("─"), C.GRAY))
        print(color("Failure details", C.BOLD, C.RED))
        for item in failure_details:
            print(wrap_block(item, indent="  ", width=88))
            print(color(line("."), C.GRAY))

    print(color(line("═"), C.CYAN))
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Readable validation for generated reference model")
    parser.add_argument("--module-dir", required=True, help="Example: generated/counter")
    args = parser.parse_args()

    module_dir = (PROJECT_ROOT / args.module_dir).resolve()
    raise SystemExit(run_module_reference_tests(module_dir))


if __name__ == "__main__":
    main()