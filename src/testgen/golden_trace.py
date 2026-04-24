from __future__ import annotations

import json
from pathlib import Path

from src.reference_model.runtime import CycleAccurateModel


def build_golden_trace(
    model: CycleAccurateModel,
    stimulus: list[dict[str, int]],
) -> list[dict]:
    model.reset()
    trace: list[dict] = []

    for vector in stimulus:
        step = model.step(vector)
        trace.append(
            {
                "cycle": step.cycle,
                "inputs": step.inputs,
                "outputs": step.outputs,
                "state": step.state,
            }
        )

    return trace


def save_golden_trace(trace: list[dict], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
