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
from src.spec.parser import load_spec
from src.tbgen.repair import TestbenchRepairService


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_compile(rtl_file: Path, tb_file: Path, out_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = ["iverilog", "-g2012", "-o", str(out_file), str(rtl_file), str(tb_file)]
    return subprocess.run(cmd, capture_output=True, text=True)


def _run_sim(out_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = ["vvp", str(out_file)]
    return subprocess.run(cmd, capture_output=True, text=True)


def _is_testbench_error(log_text: str, tb_file: Path) -> bool:
    return tb_file.name in log_text or "testbench" in log_text.lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile and run RTL testbenches with Icarus Verilog")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--repair-attempts", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if shutil.which("iverilog") is None:
        raise SystemExit("iverilog not found in PATH")
    if shutil.which("vvp") is None:
        raise SystemExit("vvp not found in PATH")

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    rtl_file = paths.rtl_file
    golden_trace = json.loads(paths.golden_trace_file.read_text(encoding="utf-8"))

    if not rtl_file.exists():
        raise SystemExit(f"RTL file not found: {rtl_file}")

    scenario_results: list[dict] = []

    for scenario in golden_trace.get("scenarios", []):
        scenario_name = scenario.get("name", "unnamed_scenario")
        tb_file = paths.testbench_file_for(scenario_name)

        out_file = paths.compile_output_file_for(scenario_name)
        compile_log_file = paths.compile_log_file_for(scenario_name)
        sim_log_file = paths.sim_log_file_for(scenario_name)
        wave_file = paths.wave_file_for(scenario_name)

        repaired = False
        repair_count = 0

        compile_proc = _run_compile(rtl_file, tb_file, out_file)
        _write_text(compile_log_file, (compile_proc.stdout or "") + "\n" + (compile_proc.stderr or ""))

        if compile_proc.returncode != 0:
            repair_service = TestbenchRepairService()

            for _ in range(args.repair_attempts):
                compile_log = compile_log_file.read_text(encoding="utf-8")

                if not _is_testbench_error(compile_log, tb_file):
                    break

                repaired_tb = repair_service.repair_testbench(
                    spec=spec,
                    rtl_code=rtl_file.read_text(encoding="utf-8"),
                    tb_code=tb_file.read_text(encoding="utf-8"),
                    compile_log=compile_log,
                    debug_dir=paths.tests_dir,
                )
                tb_file.write_text(repaired_tb, encoding="utf-8")
                repaired = True
                repair_count += 1

                compile_proc = _run_compile(rtl_file, tb_file, out_file)
                _write_text(compile_log_file, (compile_proc.stdout or "") + "\n" + (compile_proc.stderr or ""))

                if compile_proc.returncode == 0:
                    break

        compile_ok = compile_proc.returncode == 0
        sim_ok = False

        if compile_ok:
            sim_proc = _run_sim(out_file)
            _write_text(sim_log_file, (sim_proc.stdout or "") + "\n" + (sim_proc.stderr or ""))
            sim_ok = sim_proc.returncode == 0
        else:
            _write_text(sim_log_file, "")

        scenario_results.append(
            {
                "scenario_name": scenario_name,
                "compile_ok": compile_ok,
                "simulation_ok": sim_ok,
                "passed": compile_ok and sim_ok,
                "repaired_testbench": repaired,
                "repair_count": repair_count,
                "tb_file": str(tb_file),
                "compile_output": str(out_file),
                "compile_log": str(compile_log_file),
                "sim_log": str(sim_log_file),
                "waveform": str(wave_file),
            }
        )

    passed_count = sum(1 for x in scenario_results if x["passed"])
    failed_count = len(scenario_results) - passed_count

    payload = {
        "status": "ok" if failed_count == 0 else "failed",
        "module_name": spec.module_name,
        "artifact": "simulation_suite",
        "scenario_count": len(scenario_results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "build_dir": str(paths.build_dir),
        "waves_dir": str(paths.waves_dir),
        "scenario_results": scenario_results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()