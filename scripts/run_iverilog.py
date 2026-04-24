from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import get_module_paths
from src.rtl.repair import RTLRepairService
from src.rtl.sanity import check_rtl_interface
from src.spec.parser import load_spec


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_compile(files: list[Path], out_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = ["iverilog", "-g2012", "-o", str(out_file), *[str(f) for f in files]]
    return subprocess.run(cmd, capture_output=True, text=True)


def _run_sim(out_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["vvp", str(out_file)], capture_output=True, text=True)


def _compile_rtl_only(rtl_file: Path, build_dir: Path, module_name: str) -> tuple[bool, Path, str]:
    out_file = build_dir / f"{module_name}_rtl_only.out"
    log_file = build_dir / "rtl_compile.log"

    proc = _run_compile([rtl_file], out_file)
    log_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    _write_text(log_file, log_text)

    return proc.returncode == 0, log_file, log_text


def _run_suite(spec, paths) -> tuple[list[dict], int, int]:
    golden_trace = json.loads(paths.golden_trace_file.read_text(encoding="utf-8"))
    rtl_file = paths.rtl_file

    results: list[dict] = []

    for scenario in golden_trace.get("scenarios", []):
        scenario_name = scenario.get("name", "unnamed_scenario")
        tb_file = paths.testbench_file_for(scenario_name)

        out_file = paths.compile_output_file_for(scenario_name)
        compile_log_file = paths.compile_log_file_for(scenario_name)
        sim_log_file = paths.sim_log_file_for(scenario_name)
        wave_file = paths.wave_file_for(scenario_name)

        compile_proc = _run_compile([rtl_file, tb_file], out_file)
        compile_log = (compile_proc.stdout or "") + "\n" + (compile_proc.stderr or "")
        _write_text(compile_log_file, compile_log)

        compile_ok = compile_proc.returncode == 0
        sim_ok = False
        sim_log = ""

        if compile_ok:
            sim_proc = _run_sim(out_file)
            sim_log = (sim_proc.stdout or "") + "\n" + (sim_proc.stderr or "")
            _write_text(sim_log_file, sim_log)
            sim_ok = sim_proc.returncode == 0
        else:
            _write_text(sim_log_file, "")

        results.append(
            {
                "scenario_name": scenario_name,
                "compile_ok": compile_ok,
                "simulation_ok": sim_ok,
                "passed": compile_ok and sim_ok,
                "tb_file": str(tb_file),
                "compile_output": str(out_file),
                "compile_log": str(compile_log_file),
                "sim_log": str(sim_log_file),
                "waveform": str(wave_file),
            }
        )

    passed_count = sum(1 for x in results if x["passed"])
    failed_count = len(results) - passed_count
    return results, passed_count, failed_count


def _first_failure_context(results: list[dict]) -> tuple[str, str]:
    for item in results:
        if not item["passed"]:
            compile_log = Path(item["compile_log"]).read_text(encoding="utf-8") if Path(item["compile_log"]).exists() else ""
            sim_log = Path(item["sim_log"]).read_text(encoding="utf-8") if Path(item["sim_log"]).exists() else ""
            return item["scenario_name"], (compile_log + "\n" + sim_log).strip()
    return "", ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile and run RTL suite with RTL-only repair loop")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--rtl-repair-attempts", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if shutil.which("iverilog") is None:
        raise SystemExit("iverilog not found in PATH")
    if shutil.which("vvp") is None:
        raise SystemExit("vvp not found in PATH")

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)
    rtl_file = paths.rtl_file

    if not rtl_file.exists():
        raise SystemExit(f"RTL file not found: {rtl_file}")

    repair_service = RTLRepairService()
    rtl_repair_count = 0

    # Step A: syntax + interface sanity repair loop
    rtl_ok = False
    rtl_compile_log_file = paths.build_dir / "rtl_compile.log"
    last_compile_log = ""

    for attempt in range(1, args.rtl_repair_attempts + 1):
        rtl_code = rtl_file.read_text(encoding="utf-8")

        sanity = check_rtl_interface(spec, rtl_code)
        if not sanity.ok:
            compile_log = "\n".join(sanity.errors)
            _write_text(rtl_compile_log_file, compile_log)
            repaired = repair_service.repair_rtl(
                spec=spec,
                rtl_code=rtl_code,
                compile_log=compile_log,
                debug_dir=paths.build_dir,
                attempt=attempt,
            )
            rtl_file.write_text(repaired, encoding="utf-8")
            rtl_repair_count += 1
            last_compile_log = compile_log
            continue

        compile_ok, log_file, compile_log = _compile_rtl_only(rtl_file, paths.build_dir, spec.module_name)
        rtl_compile_log_file = log_file
        last_compile_log = compile_log

        if compile_ok:
            rtl_ok = True
            break

        repaired = repair_service.repair_rtl(
            spec=spec,
            rtl_code=rtl_code,
            compile_log=compile_log,
            debug_dir=paths.build_dir,
            attempt=attempt,
        )
        rtl_file.write_text(repaired, encoding="utf-8")
        rtl_repair_count += 1

    if not rtl_ok:
        payload = {
            "status": "failed",
            "module_name": spec.module_name,
            "artifact": "simulation_suite",
            "rtl_compile_ok": False,
            "rtl_repair_count": rtl_repair_count,
            "rtl_compile_log": str(rtl_compile_log_file),
            "scenario_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "build_dir": str(paths.build_dir),
            "waves_dir": str(paths.waves_dir),
            "scenario_results": [],
        }
        print(json.dumps(payload, ensure_ascii=False) if args.json else json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # Step B: frozen testbenches + RTL functional repair loop
    final_results: list[dict] = []
    passed_count = 0
    failed_count = 0

    for attempt in range(1, args.rtl_repair_attempts + 1):
        results, passed_count, failed_count = _run_suite(spec, paths)
        final_results = results

        if failed_count == 0:
            break

        failing_scenario, failing_log = _first_failure_context(results)
        repaired = repair_service.repair_rtl(
            spec=spec,
            rtl_code=rtl_file.read_text(encoding="utf-8"),
            sim_log=failing_log,
            failing_scenario=failing_scenario,
            debug_dir=paths.build_dir,
            attempt=attempt + rtl_repair_count,
        )
        rtl_file.write_text(repaired, encoding="utf-8")
        rtl_repair_count += 1

        # repair result must still pass sanity + rtl-only compile
        rtl_code = rtl_file.read_text(encoding="utf-8")
        sanity = check_rtl_interface(spec, rtl_code)
        if not sanity.ok:
            _write_text(rtl_compile_log_file, "\n".join(sanity.errors))
            break

        compile_ok, log_file, compile_log = _compile_rtl_only(rtl_file, paths.build_dir, spec.module_name)
        rtl_compile_log_file = log_file
        if not compile_ok:
            break

    payload = {
        "status": "ok" if failed_count == 0 else "failed",
        "module_name": spec.module_name,
        "artifact": "simulation_suite",
        "rtl_compile_ok": True,
        "rtl_repair_count": rtl_repair_count,
        "rtl_compile_log": str(rtl_compile_log_file),
        "scenario_count": len(final_results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "build_dir": str(paths.build_dir),
        "waves_dir": str(paths.waves_dir),
        "scenario_results": final_results,
    }

    print(json.dumps(payload, ensure_ascii=False) if args.json else json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()