from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.llm.client import LlamaCppClient
from src.spec.schema import ModuleSpec


def _spec_to_prompt_json(spec: ModuleSpec) -> str:
    payload = {
        "module_name": spec.module_name,
        "description": spec.description,
        "inputs": spec.inputs,
        "outputs": spec.outputs,
        "clock": spec.clock,
        "reset": spec.reset,
        "metadata": spec.metadata,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _extract_fenced_block(text: str, language: str | None = None) -> str:
    if language:
        pattern = rf"```{re.escape(language)}\n(.*?)```"
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            return matches[0].strip()

    pattern = r"```(?:[a-zA-Z0-9_+\-]+)?\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    if matches:
        return matches[0].strip()

    return text.strip()


def _extract_likely_json_text(text: str) -> str:
    candidate = _extract_fenced_block(text, "json").strip()
    if candidate:
        return candidate

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    obj_candidate = text[obj_start:obj_end + 1] if obj_start != -1 and obj_end != -1 and obj_end > obj_start else ""
    arr_candidate = text[arr_start:arr_end + 1] if arr_start != -1 and arr_end != -1 and arr_end > arr_start else ""

    return obj_candidate if len(obj_candidate) >= len(arr_candidate) else arr_candidate


def _extract_json(text: str) -> Any:
    candidate = _extract_likely_json_text(text)
    if not candidate:
        raise ValueError("Could not extract JSON from LLM response.")
    return json.loads(candidate)


def _get_test_generation_config(spec: ModuleSpec) -> dict[str, Any]:
    cfg = spec.metadata.get("test_generation", {})
    if not isinstance(cfg, dict):
        return {}
    return cfg


class CodegenService:
    def __init__(self, client: LlamaCppClient | None = None):
        self.client = client or LlamaCppClient()

    def generate_python_reference_model(self, spec: ModuleSpec) -> str:
        prompt = f"""
You are generating a cycle-accurate Python reference model for an RTL module.

Specification:
{_spec_to_prompt_json(spec)}

Requirements:
- Return ONLY Python code in one code block.
- Use only Python standard library.
- Define exactly one public class named ReferenceModel.
- The class must implement:
    - __init__(self)
    - reset(self) -> None
    - step(self, inputs: dict) -> dict
- The model must be cycle-accurate and stateful.
- Internal state must be stored in self.state or self.<field>.
- step() must consume one cycle of inputs and return ONLY output signals as a dict.
- Missing inputs should default to 0.
- Reset signal is "{spec.reset}".
- Clock signal is "{spec.clock}", but the simulator is stepped manually once per cycle.
- Do not print anything.
- Do not include explanations.

If the specification is incomplete, implement the simplest behavior consistent with the description.
""".strip()

        raw = self.client.chat(
            prompt,
            temperature=0.1,
            max_tokens=1400,
        )
        return _extract_fenced_block(raw, "python")

    def _repair_json(self, broken_text: str) -> str:
        repair_prompt = f"""
Fix the following text so that it becomes valid JSON.

Rules:
- Return ONLY valid JSON.
- Do not add explanations.
- Preserve the original meaning as much as possible.

Broken text:
```text
{broken_text}""".strip()
        return self.client.chat(
            repair_prompt,
            temperature=0.0,
            max_tokens=1800,
        )

    def _chat_json_with_repair(
        self,
        prompt: str,
        debug_dir: Path | None,
        prefix: str,
        max_tokens: int,
        temperature: float = 0.1,
        attempts: int = 3,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            raw = self.client.chat(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if debug_dir is not None:
                (debug_dir / f"{prefix}_raw_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")

            try:
                return _extract_json(raw)
            except Exception as exc:
                last_error = exc

            repaired = self._repair_json(raw)

            if debug_dir is not None:
                (debug_dir / f"{prefix}_repaired_attempt_{attempt}.txt").write_text(repaired, encoding="utf-8")

            try:
                return _extract_json(repaired)
            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"Failed to generate valid JSON for {prefix}. Last error: {last_error}")

    def _generate_scenario_plan(
        self,
        spec: ModuleSpec,
        debug_dir: Path | None,
    ) -> list[dict[str, Any]]:
        test_cfg = _get_test_generation_config(spec)

        directed_scenarios = int(test_cfg.get("directed_scenarios", 4))
        random_scenarios = int(test_cfg.get("random_scenarios", 0))
        total_scenarios = directed_scenarios + random_scenarios

        include_reset_scenarios = bool(test_cfg.get("include_reset_scenarios", True))
        include_corner_cases = bool(test_cfg.get("include_corner_cases", True))
        include_long_run = bool(test_cfg.get("include_long_run", False))

        required_behaviors = test_cfg.get("required_behaviors", [])
        special_scenarios = test_cfg.get("special_scenarios", [])
        notes = test_cfg.get("notes", "")

        prompt = f"""You are generating a scenario plan for RTL test generation.
            Specification:
            {_spec_to_prompt_json(spec)}

            Test-generation configuration:
            {json.dumps(test_cfg, indent=2, ensure_ascii=False)}

            Return ONLY valid JSON with this schema:
            {{
            "scenarios": [
            {{
            "name": "short_snake_case_name",
            "description": "what this scenario checks",
            "kind": "directed|random|corner|long_run"
            }}
            ]
            }}

            Rules:

            Generate exactly {total_scenarios} scenarios.
            At least {directed_scenarios} scenarios must be directed.
            At least {random_scenarios} scenarios must be random if random_scenarios > 0.
            include_reset_scenarios = {include_reset_scenarios}
            include_corner_cases = {include_corner_cases}
            include_long_run = {include_long_run}
            Required behaviors: {json.dumps(required_behaviors, ensure_ascii=False)}
            Special scenarios: {json.dumps(special_scenarios, ensure_ascii=False)}
            Additional notes: {notes!r}
            Use short unique names.
            Return JSON only.
            """.strip()
        
        data = self._chat_json_with_repair(
            prompt=prompt,
            debug_dir=debug_dir,
            prefix="scenario_plan",
            max_tokens=1600,
            temperature=0.1,
        )

        if not isinstance(data, dict) or "scenarios" not in data or not isinstance(data["scenarios"], list):
            raise RuntimeError("Scenario plan has invalid structure.")

        return data["scenarios"]
    
    def _generate_scenario_cycles(
            self,
            spec: ModuleSpec,
            model_code: str,
            scenario: dict[str, Any],
            debug_dir: Path | None,
            index: int,
        ) -> dict[str, Any]:
        test_cfg = _get_test_generation_config(spec)
        min_cycles = int(test_cfg.get("min_cycles_per_scenario", 2))
        max_cycles = int(test_cfg.get("max_cycles_per_scenario", 8))

        prompt = f"""You are generating one input scenario for a Python RTL reference model.
            Specification:
            {_spec_to_prompt_json(spec)}

            Reference model code: {model_code}
            Scenario metadata:
            {json.dumps(scenario, indent=2, ensure_ascii=False)}

            Return ONLY valid JSON with this schema:
            {{
            "name": "same as provided",
            "description": "same as provided",
            "kind": "same as provided",
            "cycles": [
            {{
            "<input_name>": 0
            }}
            ]
            }}

            Rules:

            Keep the same name, description and kind.
            Generate between {min_cycles} and {max_cycles} cycles.
            Use only these input signals: {spec.inputs}.
            Do not include outputs.
            Missing inputs are not allowed: provide every input explicitly in every cycle.
            Make the cycle sequence match the scenario description.
            Return JSON only.
            """.strip()
            
        data = self._chat_json_with_repair(
            prompt=prompt,
            debug_dir=debug_dir,
            prefix=f"scenario_{index}_{scenario.get('name', 'unnamed')}",
            max_tokens=1400,
            temperature=0.1,
        )

        if not isinstance(data, dict):
            raise RuntimeError(f"Scenario {scenario.get('name', index)} is not a JSON object.")

        if "cycles" not in data or not isinstance(data["cycles"], list):
            raise RuntimeError(f"Scenario {scenario.get('name', index)} has no valid cycles field.")

        return {
            "name": data.get("name", scenario.get("name", f"scenario_{index}")),
            "description": data.get("description", scenario.get("description", "")),
            "kind": data.get("kind", scenario.get("kind", "directed")),
            "cycles": data["cycles"],
        }
        
    def generate_input_scenarios(
        self,
        spec: ModuleSpec,
        model_code: str,
        num_scenarios: int | None = None,
        max_cycles: int | None = None,
        debug_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        debug_path: Path | None = None
        if debug_dir is not None:
            debug_path = Path(debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)
        scenarios_plan = self._generate_scenario_plan(spec, debug_path)

        if num_scenarios is not None:
            scenarios_plan = scenarios_plan[:num_scenarios]

        scenarios: list[dict[str, Any]] = []
        for index, scenario in enumerate(scenarios_plan, start=1):
            scenario_payload = self._generate_scenario_cycles(
                spec=spec,
                model_code=model_code,
                scenario=scenario,
                debug_dir=debug_path,
                index=index,
            )

            if max_cycles is not None:
                scenario_payload["cycles"] = scenario_payload["cycles"][:max_cycles]

            scenarios.append(scenario_payload)

        return {"scenarios": scenarios}