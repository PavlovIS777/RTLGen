from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.spec.schema import ModuleSpec


@dataclass(slots=True)
class StepResult:
    cycle: int
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    state: dict[str, Any]


class CycleAccurateModel:
    def __init__(self, spec: ModuleSpec):
        self.spec = spec
        self.state: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        self.state = {"cycle": 0}

    def step(self, inputs: dict[str, Any]) -> StepResult:
        cycle = int(self.state.get("cycle", 0))

        outputs = {name: 0 for name in self.spec.outputs}

        self.state["cycle"] = cycle + 1

        return StepResult(
            cycle=cycle,
            inputs=dict(inputs),
            outputs=outputs,
            state=dict(self.state),
        )
