from __future__ import annotations

import json
from pathlib import Path

from src.spec.schema import ModuleSpec


KNOWN_KEYS = {"module_name", "description", "inputs", "outputs", "clock", "reset"}


def load_spec(path: str | Path) -> ModuleSpec:
    spec_path = Path(path)
    data = json.loads(spec_path.read_text(encoding="utf-8"))

    missing = [k for k in ("module_name", "inputs", "outputs") if k not in data]
    if missing:
        raise ValueError(f"Spec is missing required fields: {missing}")

    metadata = {k: v for k, v in data.items() if k not in KNOWN_KEYS}

    return ModuleSpec(
        module_name=data["module_name"],
        description=data.get("description", ""),
        inputs=list(data.get("inputs", [])),
        outputs=list(data.get("outputs", [])),
        clock=data.get("clock", "clk"),
        reset=data.get("reset", "rst_n"),
        metadata=metadata,
    )
