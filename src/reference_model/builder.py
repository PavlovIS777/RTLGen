from __future__ import annotations

from pathlib import Path

from src.reference_model.runtime import CycleAccurateModel
from src.spec.schema import ModuleSpec


def build_reference_model(spec: ModuleSpec, out_dir: str | Path) -> tuple[CycleAccurateModel, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    model_file = out_path / f"{spec.module_name}_reference_model.py"
    model_text = f'''"""Auto-generated stub reference model for {spec.module_name}."""

class ReferenceModel:
    def __init__(self):
        self.cycle = 0

    def reset(self):
        self.cycle = 0

    def step(self, inputs):
        outputs = {{name: 0 for name in {spec.outputs!r}}}
        self.cycle += 1
        return outputs
'''
    model_file.write_text(model_text, encoding="utf-8")
    return CycleAccurateModel(spec), model_file
