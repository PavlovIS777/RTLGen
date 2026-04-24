from __future__ import annotations

from pathlib import Path

from src.reference_model.builder import build_reference_model
from src.reports.report_builder import build_report
from src.rtl.generator import generate_rtl
from src.simulators.xrun_runner import run_xrun
from src.spec.parser import load_spec
from src.tbgen.sv_tb_generator import generate_testbench
from src.testgen.golden_trace import build_golden_trace, save_golden_trace
from src.testgen.stimulus import generate_stimulus


def run_pipeline(
    spec_path: str | Path,
    generated_dir: str | Path = "generated",
    enable_xrun: bool = False,
    num_cycles: int = 5,
) -> dict:
    generated_dir = Path(generated_dir)
    python_models_dir = generated_dir / "python_models"
    traces_dir = generated_dir / "traces"
    tb_dir = generated_dir / "tb"
    rtl_dir = generated_dir / "rtl"
    reports_dir = generated_dir / "reports"

    spec = load_spec(spec_path)

    model, model_path = build_reference_model(spec, python_models_dir)

    stimulus = generate_stimulus(spec, num_cycles=num_cycles)
    trace = build_golden_trace(model, stimulus)
    trace_path = save_golden_trace(trace, traces_dir / f"{spec.module_name}_golden_trace.json")

    tb_path = generate_testbench(spec, trace, tb_dir)
    rtl_path = generate_rtl(spec, rtl_dir)

    xrun_result = run_xrun(rtl_path, tb_path, enable=enable_xrun)

    report_path = build_report(
        spec=spec,
        model_path=model_path,
        trace_path=trace_path,
        tb_path=tb_path,
        rtl_path=rtl_path,
        xrun_result=xrun_result,
        out_dir=reports_dir,
    )

    return {
        "status": "ok",
        "spec": str(spec_path),
        "reference_model": str(model_path),
        "golden_trace": str(trace_path),
        "testbench": str(tb_path),
        "rtl": str(rtl_path),
        "report": str(report_path),
        "xrun_status": xrun_result.get("status", "unknown"),
    }
