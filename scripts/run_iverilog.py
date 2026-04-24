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
    parser = argparse.ArgumentParser(description="Compile and run RTL testbench with Icarus Verilog")
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
    tb_file = paths.tb_file
    out_file = paths.compile_output_file
    compile_log_file = paths.compile_log_file
    sim_log_file = paths.sim_log_file

    repaired = False
    compile_ok = False
    sim_ok = False
    repair_count = 0

    compile_proc = _run_compile(rtl_file, tb_file, out_file)
    _write_text(
        compile_log_file,
        (compile_proc.stdout or "") + "\n" + (compile_proc.stderr or ""),
    )

    if compile_proc.returncode != 0:
        repair_service = TestbenchRepairService()

        for attempt in range(1, args.repair_attempts + 1):
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
            _write_text(
                compile_log_file,
                (compile_proc.stdout or "") + "\n" + (compile_proc.stderr or ""),
            )

            if compile_proc.returncode == 0:
                break

    compile_ok = compile_proc.returncode == 0

    if compile_ok:
        sim_proc = _run_sim(out_file)
        _write_text(
            sim_log_file,
            (sim_proc.stdout or "") + "\n" + (sim_proc.stderr or ""),
        )
        sim_ok = sim_proc.returncode == 0

    payload = {
        "status": "ok" if compile_ok and sim_ok else "failed",
        "module_name": spec.module_name,
        "artifact": "simulation",
        "compile_ok": compile_ok,
        "simulation_ok": sim_ok,
        "repaired_testbench": repaired,
        "repair_count": repair_count,
        "rtl_file": str(rtl_file),
        "testbench_file": str(tb_file),
        "compile_output": str(out_file),
        "compile_log": str(compile_log_file),
        "sim_log": str(sim_log_file),
        "waveform": str(paths.wave_file),
    }

    print(json.dumps(payload, ensure_ascii=False) if args.json else json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()