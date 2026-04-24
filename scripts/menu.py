from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPECS_ROOT = PROJECT_ROOT / "specs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import get_module_paths
from src.ui.renderer import ConsoleUI


ui = ConsoleUI()


def list_spec_files() -> list[Path]:
    if not SPECS_ROOT.exists():
        return []
    return [p for p in sorted(SPECS_ROOT.rglob("*.json")) if p.is_file()]


def load_spec_payload(spec_path: str | Path) -> dict:
    path = Path(spec_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_module_name_from_spec(spec_path: str | Path) -> str:
    return load_spec_payload(spec_path)["module_name"]


def get_module_description_from_spec(spec_path: str | Path) -> str:
    return load_spec_payload(spec_path).get("description", "")


def choose_spec_interactive() -> str | None:
    specs = list_spec_files()
    ui.title("RTLGEN · SELECT SPEC")

    if not specs:
        ui.error("No spec files found in specs/")
        return None

    for idx, path in enumerate(specs, start=1):
        rel = path.relative_to(PROJECT_ROOT)
        payload = load_spec_payload(path)
        ui.bullet(f"[{idx}] {rel}", detail=f"module: {payload.get('module_name', '<unknown>')}")
        if payload.get("description"):
            ui.paragraph(payload["description"], indent=6)
        ui.separator()

    choice = input("Select spec number (empty to cancel): ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        ui.error("Invalid selection.")
        return None

    index = int(choice)
    if index < 1 or index > len(specs):
        ui.error("Selection out of range.")
        return None

    selected = specs[index - 1].relative_to(PROJECT_ROOT)
    ui.success(f"Selected spec: {selected}")
    return str(selected)


def ensure_spec_selected(current_spec: str | None) -> str | None:
    if current_spec is not None:
        return current_spec
    ui.warning("No spec selected.")
    return choose_spec_interactive()


def run_json_command(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return json.loads(result.stdout.strip()) if result.stdout.strip() else {}


def print_artifact_result(payload: dict) -> None:
    artifact = payload.get("artifact")

    if artifact == "python_model":
        ui.success("Python reference model generated")
        ui.artifact("File", payload["path"])

    elif artifact == "tests":
        ui.success("Input scenarios and golden trace generated")
        ui.summary_row("Scenarios", payload.get("scenario_count", "?"), "bright_cyan")
        ui.artifact("Input scenarios", payload["input_scenarios"])
        ui.artifact("Golden trace", payload["golden_trace"])
        ui.artifact("Pytest file", payload["pytest"])

    elif artifact == "rtl":
        ui.success("RTL module generated")
        ui.artifact("RTL file", payload["path"])

    elif artifact == "testbenches":
        ui.success("SystemVerilog testbenches generated")
        ui.summary_row("Count", payload["count"], "bright_cyan")
        ui.artifact("Testbench dir", payload["tb_dir"])
        ui.artifact("Waveforms dir", payload["waves_dir"])

    elif artifact == "simulation_suite":
        if payload.get("failed_count", 0) == 0:
            ui.success("RTL module passed all generated testbenches")
        else:
            ui.error("RTL simulation suite detected failures")

        ui.summary_row("Scenarios", payload["scenario_count"], "bright_cyan")
        ui.summary_row("Passed", payload["passed_count"], "bright_green")
        ui.summary_row("Failed", payload["failed_count"], "bright_red" if payload["failed_count"] else "bright_green")

        ui.separator()
        ui.info("Scenario results")
        for idx, item in enumerate(payload.get("scenario_results", []), start=1):
            ui.scenario_result(
                idx,
                payload["scenario_count"],
                item["scenario_name"],
                item["passed"],
            )
            if item.get("repaired_testbench"):
                ui.warning(f"Testbench repaired {item.get('repair_count', 0)} time(s): {item['scenario_name']}")

        ui.separator()
        ui.artifact("Build dir", payload["build_dir"])
        ui.artifact("Waveforms dir", payload["waves_dir"])

    ui.separator()


def generate_python_model(spec_path: str) -> int:
    payload = run_json_command([sys.executable, "scripts/generate_python_model.py", "--spec", spec_path, "--json"])
    print_artifact_result(payload)
    return 0


def generate_tests(spec_path: str) -> int:
    paths = get_module_paths("generated", get_module_name_from_spec(spec_path))
    payload = run_json_command([
        sys.executable,
        "scripts/generate_tests.py",
        "--spec",
        spec_path,
        "--model",
        str(paths.python_model_file),
        "--json",
    ])
    print_artifact_result(payload)
    return 0


def run_reference_validation(spec_path: str) -> int:
    module_name = get_module_name_from_spec(spec_path)
    result = subprocess.run(
        [sys.executable, "scripts/run_reference_tests.py", "--module-dir", f"generated/{module_name}"],
        cwd=PROJECT_ROOT,
    )
    return result.returncode


def generate_rtl(spec_path: str) -> int:
    paths = get_module_paths("generated", get_module_name_from_spec(spec_path))
    payload = run_json_command([
        sys.executable,
        "scripts/generate_rtl.py",
        "--spec",
        spec_path,
        "--model",
        str(paths.python_model_file),
        "--trace",
        str(paths.golden_trace_file),
        "--json",
    ])
    print_artifact_result(payload)
    return 0


def generate_testbenches(spec_path: str) -> int:
    paths = get_module_paths("generated", get_module_name_from_spec(spec_path))
    payload = run_json_command([
        sys.executable,
        "scripts/generate_testbench.py",
        "--spec",
        spec_path,
        "--trace",
        str(paths.golden_trace_file),
        "--json",
    ])
    print_artifact_result(payload)
    return 0


def run_iverilog_suite(spec_path: str) -> int:
    payload = run_json_command([
        sys.executable,
        "scripts/run_iverilog.py",
        "--spec",
        spec_path,
        "--json",
    ])
    print_artifact_result(payload)
    return 0 if payload.get("failed_count", 1) == 0 else 1


def full_flow(spec_path: str) -> int:
    steps = [
        ("Generate Python reference model", lambda: generate_python_model(spec_path)),
        ("Generate input scenarios and golden trace", lambda: generate_tests(spec_path)),
        ("Validate reference model", lambda: run_reference_validation(spec_path)),
        ("Generate RTL module", lambda: generate_rtl(spec_path)),
        ("Generate SystemVerilog testbenches", lambda: generate_testbenches(spec_path)),
        ("Compile and run RTL simulation suite", lambda: run_iverilog_suite(spec_path)),
    ]

    ui.title("RTLGEN · FULL FLOW")

    for idx, (name, fn) in enumerate(steps, start=1):
        ui.step(idx, len(steps), name)
        try:
            code = fn()
        except Exception as exc:
            ui.error("Flow failed")
            ui.paragraph(str(exc), indent=2)
            ui.error(f"Stopped on step {idx}: {name}")
            return 1

        if code != 0:
            ui.error(f"Stopped on step {idx}: {name}")
            return code

    ui.success("RTL MODULE IS READY AND PASSED TESTBENCH VALIDATION")
    return 0


def print_menu(spec_path: str | None) -> None:
    ui.title("RTLGEN")

    if spec_path is None:
        ui.kv("Selected spec", "<none>")
    else:
        module_name = get_module_name_from_spec(spec_path)
        module_description = get_module_description_from_spec(spec_path)
        ui.kv("Selected spec", spec_path, "bold bright_magenta")
        ui.kv("Module", module_name, "bold bright_cyan")
        if module_description:
            ui.kv("Description", "")
            ui.paragraph(module_description, indent=2)

    ui.separator()
    ui.bullet("1  Select spec from specs/")
    ui.bullet("2  Generate Python reference model")
    ui.bullet("3  Generate input scenarios and golden trace")
    ui.bullet("4  Validate reference model")
    ui.bullet("5  Generate RTL module")
    ui.bullet("6  Generate SystemVerilog testbenches")
    ui.bullet("7  Compile and run RTL simulation suite")
    ui.bullet("8  Run full flow")
    ui.bullet("0  Exit")
    ui.separator()


def main() -> None:
    spec_path: str | None = None

    while True:
        print_menu(spec_path)
        choice = input("Select option: ").strip()

        try:
            if choice == "1":
                selected = choose_spec_interactive()
                if selected is not None:
                    spec_path = selected
            elif choice == "2":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Generate Python reference model")
                    generate_python_model(spec_path)
            elif choice == "3":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Generate input scenarios and golden trace")
                    generate_tests(spec_path)
            elif choice == "4":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Validate reference model")
                    run_reference_validation(spec_path)
            elif choice == "5":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Generate RTL module")
                    generate_rtl(spec_path)
            elif choice == "6":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Generate SystemVerilog testbenches")
                    generate_testbenches(spec_path)
            elif choice == "7":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    ui.section("Compile and run RTL simulation suite")
                    run_iverilog_suite(spec_path)
            elif choice == "8":
                spec_path = ensure_spec_selected(spec_path)
                if spec_path:
                    full_flow(spec_path)
            elif choice == "0":
                ui.note("Bye.")
                break
            else:
                ui.error("Unknown option.")
        except Exception as exc:
            ui.error("ERROR")
            ui.paragraph(str(exc), indent=2)


if __name__ == "__main__":
    main()