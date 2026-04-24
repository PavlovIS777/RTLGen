from __future__ import annotations

import json
from pathlib import Path

from src.spec.schema import ModuleSpec


def build_report(
    spec: ModuleSpec,
    model_path: str | Path,
    trace_path: str | Path,
    tb_path: str | Path,
    rtl_path: str | Path,
    xrun_result: dict,
    out_dir: str | Path,
) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    report = {
        "module_name": spec.module_name,
        "description": spec.description,
        "inputs": spec.inputs,
        "outputs": spec.outputs,
        "artifacts": {
            "reference_model": str(model_path),
            "golden_trace": str(trace_path),
            "testbench": str(tb_path),
            "rtl": str(rtl_path),
        },
        "xrun": xrun_result,
    }

    report_file = out_path / f"{spec.module_name}_pipeline_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_file
