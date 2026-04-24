from __future__ import annotations

import json
from pathlib import Path

from src.spec.schema import ModuleSpec


def load_spec(path: str | Path) -> ModuleSpec:
    spec_path = Path(path)
    raw = json.loads(spec_path.read_text(encoding="utf-8"))

    required = ("module_name", "inputs", "outputs")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Spec {spec_path} is missing required fields: {missing}")

    known_keys = {"module_name", "description", "inputs", "outputs", "clock", "reset"}
    metadata = {k: v for k, v in raw.items() if k not in known_keys}

    return ModuleSpec(
        module_name=raw["module_name"],
        description=raw.get("description", ""),
        inputs=list(raw.get("inputs", [])),
        outputs=list(raw.get("outputs", [])),
        clock=raw.get("clock", "clk"),
        reset=raw.get("reset", "rst_n"),
        metadata=metadata,
    )
