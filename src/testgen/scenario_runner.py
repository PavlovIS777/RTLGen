from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.reference_model.loader import instantiate_reference_model
from src.spec.schema import ModuleSpec


def normalize_cycle_inputs(spec: ModuleSpec, raw_cycle: dict[str, Any]) -> dict[str, int]:
    cycle: dict[str, int] = {}
    for name in spec.inputs:
        cycle[name] = int(raw_cycle.get(name, 0))
    return cycle


def run_scenarios(
    spec: ModuleSpec,
    model_path: str | Path,
    scenarios_payload: dict[str, Any],
) -> dict[str, Any]:
    scenarios = scenarios_payload.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise ValueError("scenarios must be a list")

    all_results: list[dict[str, Any]] = []

    for scenario in scenarios:
        model = instantiate_reference_model(model_path)

        name = scenario.get("name", "unnamed_scenario")
        description = scenario.get("description", "")
        cycles = scenario.get("cycles", [])

        if not isinstance(cycles, list):
            raise ValueError(f"Scenario {name} has invalid cycles")

        scenario_trace: list[dict[str, Any]] = []

        for idx, raw_cycle in enumerate(cycles):
            norm_inputs = normalize_cycle_inputs(spec, raw_cycle)
            outputs = model.step(norm_inputs)

            scenario_trace.append(
                {
                    "cycle": idx,
                    "inputs": norm_inputs,
                    "outputs": outputs,
                }
            )

        all_results.append(
            {
                "name": name,
                "description": description,
                "num_cycles": len(scenario_trace),
                "trace": scenario_trace,
            }
        )

    return {
        "module_name": spec.module_name,
        "module_description": spec.description,
        "scenarios": all_results,
    }


def save_json(data: dict[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def build_pytest_file(
    spec: ModuleSpec,
    model_path: str | Path,
    scenario_results: dict[str, Any],
    out_path: str | Path,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    file_text = f"""from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_NAME = {spec.module_name!r}
MODULE_DESCRIPTION = {spec.description!r}
MODEL_PATH = Path(r"{Path(model_path).resolve()}")

SCENARIOS = {json.dumps(scenario_results["scenarios"], indent=2, ensure_ascii=False)}


def load_reference_model():
    spec = importlib.util.spec_from_file_location("generated_reference_model", MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.ReferenceModel()


def scenario_id(scenario):
    name = scenario.get("name", "unnamed")
    desc = scenario.get("description", "")
    num_cycles = scenario.get("num_cycles", len(scenario.get("trace", [])))
    if desc:
        return f"module={{MODULE_NAME}} | scenario={{name}} | cycles={{num_cycles}} | {{desc}}"
    return f"module={{MODULE_NAME}} | scenario={{name}} | cycles={{num_cycles}}"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=scenario_id)
def test_reference_model_scenario(scenario):
    model = load_reference_model()
    if hasattr(model, "reset"):
        model.reset()

    for item in scenario["trace"]:
        outputs = model.step(item["inputs"])
        assert outputs == item["outputs"], (
            f"module={{MODULE_NAME}}\\n"
            f"description={{MODULE_DESCRIPTION}}\\n"
            f"scenario={{scenario['name']}}\\n"
            f"scenario_description={{scenario.get('description', '')}}\\n"
            f"cycle={{item['cycle']}}\\n"
            f"inputs={{item['inputs']}}\\n"
            f"expected={{item['outputs']}}\\n"
            f"got={{outputs}}"
        )
"""
    out.write_text(file_text, encoding="utf-8")
    return out