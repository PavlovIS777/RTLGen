from __future__ import annotations

from src.spec.schema import ModuleSpec


def generate_stimulus(spec: ModuleSpec, num_cycles: int = 5) -> list[dict[str, int]]:
    stimulus: list[dict[str, int]] = []

    for cycle in range(num_cycles):
        vector = {name: 0 for name in spec.inputs}

        if spec.clock in vector:
            vector[spec.clock] = cycle % 2

        if spec.reset in vector:
            vector[spec.reset] = 0 if cycle == 0 else 1

        stimulus.append(vector)

    return stimulus
