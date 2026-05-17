from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPECS_ROOT = PROJECT_ROOT / "specs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.client import create_model_client
from src.pipeline.logger import PipelineLogger
from src.pipeline.orchestrator import PipelineOrchestrator
from src.spec.parser import load_spec
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
    return json.loads(path.read_text(encoding="utf-8"))


def choose_spec_interactive() -> str | None:
    specs = list_spec_files()
    ui.title("RTLGEN · SELECT SPEC")
    if not specs:
        ui.error("No spec files found in specs/")
        return None

    for idx, path in enumerate(specs, start=1):
        payload = load_spec_payload(path)
        ui.bullet(f"[{idx}] {path.relative_to(PROJECT_ROOT)}", detail=f"module: {payload.get('module_name', '<unknown>')}")
        if payload.get("description"):
            ui.paragraph(payload["description"], indent=6)
        ui.separator()

    choice = input("Select spec number (empty to cancel): ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        ui.error("Invalid selection.")
        return None

    idx = int(choice)
    if idx < 1 or idx > len(specs):
        ui.error("Selection out of range.")
        return None

    selected = str(specs[idx - 1].relative_to(PROJECT_ROOT))
    ui.success(f"Selected spec: {selected}")
    return selected


def print_stage_report(report: dict) -> None:
    ui.success("Stage finished")
    for key in ("artifact", "module_name"):
        if key in report:
            ui.kv(key, str(report[key]))
    for key in ("strategy_file", "plan_file", "scenarios_file", "path", "results_file", "golden_trace_file", "coverage_file", "tb_dir", "waves_dir", "plots_dir"):
        if key in report:
            ui.artifact(key, str(report[key]))
    for key in ("scenario_count", "passed_count", "failed_count", "iterations", "count", "waveform_count"):
        if key in report:
            style = "summary_total"
            if key == "passed_count":
                style = "summary_passed"
            elif key == "failed_count":
                style = "summary_failed_bad" if int(report[key]) else "summary_failed_ok"
            ui.summary_row(key, report[key], style)


def print_menu(spec_path: str | None) -> None:
    ui.title("RTLGEN")
    if spec_path is None:
        ui.kv("Selected spec", "<none>")
    else:
        payload = load_spec_payload(spec_path)
        ui.kv("Selected spec", spec_path, "artifact")
        ui.kv("Module", payload["module_name"], "label")
        if payload.get("description"):
            ui.kv("Description", "")
            ui.paragraph(payload["description"], indent=2)

    ui.separator()
    ui.bullet("1  Select spec from specs/")
    ui.bullet("2  Generate tests")
    ui.bullet("3  Generate and validate Python module")
    ui.bullet("4  Generate testbenches")
    ui.bullet("5  Generate and validate RTL")
    ui.bullet("6  Generate post artifacts")
    ui.bullet("7  Run full pipeline")
    ui.bullet("0  Exit")
    ui.separator()


def main() -> None:
    spec_path: str | None = None
    client = create_model_client()
    client.wait_until_ready()
    orch = PipelineOrchestrator(client, logger=PipelineLogger())

    while True:
        print_menu(spec_path)
        choice = input("Select option: ").strip()

        try:
            if choice == "1":
                selected = choose_spec_interactive()
                if selected:
                    spec_path = selected
            elif choice in {"2", "3", "4", "5", "6", "7"}:
                if spec_path is None:
                    ui.warning("No spec selected.")
                    spec_path = choose_spec_interactive()
                    if not spec_path:
                        continue
                spec = load_spec(spec_path)

                if choice == "2":
                    report = orch.generate_tests(spec)
                    print_stage_report(report)
                elif choice == "3":
                    report = orch.validate_python(spec)
                    print_stage_report(report)
                elif choice == "4":
                    report = orch.generate_testbenches(spec)
                    print_stage_report(report)
                elif choice == "5":
                    report = orch.validate_rtl(spec)
                    print_stage_report(report)
                    if "results" in report:
                        ui.separator()
                        ui.info("Scenario results")
                        results = report["results"]["scenario_results"]
                        total = max(1, len(results))
                        for i, item in enumerate(results, start=1):
                            ui.scenario_result(i, total, item["scenario_name"], item["passed"])
                elif choice == "6":
                    report = orch.postprocess_artifacts(spec)
                    print_stage_report(report)
                elif choice == "7":
                    report = orch.run(spec)
                    ui.success("Full pipeline finished")
                    ui.artifact("Generated dir", report["generated_dir"])
                    ui.artifact("Plots dir", report["plots_dir"])
                    rtl = report["rtl"]
                    ui.summary_row("Scenarios", rtl["scenario_count"], "summary_total")
                    ui.summary_row("Passed", rtl["passed_count"], "summary_passed")
                    ui.summary_row("Failed", rtl["failed_count"], "summary_failed_bad" if rtl["failed_count"] else "summary_failed_ok")
            elif choice == "0":
                ui.note("Bye.")
                break
            else:
                ui.error("Unknown option.")
        except Exception as exc:
            ui.error("Flow failed")
            ui.paragraph(str(exc), indent=2)


if __name__ == "__main__":
    main()
