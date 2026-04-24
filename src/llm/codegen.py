from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

from src.llm.client import LlamaCppClient
from src.spec.schema import ModuleSpec


def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _extract_python_code(text: str) -> str:
    text = _strip_thinking(text)

    m = re.search(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    m = re.search(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL)
    if m:
        return m.group(1).strip()

    if text.lstrip().startswith("```"):
        lines = text.splitlines()[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        return "\n".join(lines).strip()

    return text.strip()

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

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        return "\n".join(lines).strip()

    return text.strip()


def _extract_likely_json_text(text: str) -> str:
    candidate = _extract_fenced_block(text, "json").strip()
    if candidate:
        return candidate

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    obj_candidate = text[obj_start : obj_end + 1] if obj_start != -1 and obj_end != -1 and obj_end > obj_start else ""
    arr_candidate = text[arr_start : arr_end + 1] if arr_start != -1 and arr_end != -1 and arr_end > arr_start else ""

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


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "scenario"


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return 0
        try:
            return int(value, 0)
        except Exception:
            return 0
    return 0


def _extract_scenarios_list(data: Any) -> list[Any] | None:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return None

    if isinstance(data.get("scenarios"), list):
        return data["scenarios"]

    for key in ("scenario_plan", "plan", "tests", "cases", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    list_values = [v for v in data.values() if isinstance(v, list)]
    if len(list_values) == 1:
        return list_values[0]

    return None


def _normalize_scenario_plan_payload(data: Any) -> list[dict[str, Any]] | None:
    raw_items = _extract_scenarios_list(data)
    if not raw_items:
        return None

    normalized: list[dict[str, Any]] = []

    for idx, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            desc = item.strip()
            normalized.append(
                {
                    "name": _slugify(desc) or f"scenario_{idx}",
                    "description": desc,
                    "kind": "directed",
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        raw_name = (
            item.get("name")
            or item.get("scenario_name")
            or item.get("title")
            or item.get("id")
            or f"scenario_{idx}"
        )

        raw_desc = (
            item.get("description")
            or item.get("goal")
            or item.get("purpose")
            or item.get("what_it_checks")
            or item.get("summary")
            or ""
        )

        raw_kind = (
            item.get("kind")
            or item.get("type")
            or item.get("category")
            or "directed"
        )

        normalized.append(
            {
                "name": _slugify(str(raw_name)),
                "description": str(raw_desc).strip(),
                "kind": _slugify(str(raw_kind)),
            }
        )

    return normalized or None


def _build_fallback_scenario_plan(spec: ModuleSpec) -> list[dict[str, Any]]:
    test_cfg = _get_test_generation_config(spec)

    directed_scenarios = int(test_cfg.get("directed_scenarios", 4))
    random_scenarios = int(test_cfg.get("random_scenarios", 0))
    total_scenarios = directed_scenarios + random_scenarios

    include_corner_cases = bool(test_cfg.get("include_corner_cases", True))
    include_long_run = bool(test_cfg.get("include_long_run", False))

    required_behaviors = test_cfg.get("required_behaviors", [])
    special_scenarios = test_cfg.get("special_scenarios", [])

    scenarios: list[dict[str, Any]] = []
    used_names: set[str] = set()

    def add(description: str, kind: str) -> None:
        if len(scenarios) >= total_scenarios:
            return
        base = _slugify(description)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base}_{suffix}"
            suffix += 1
        used_names.add(name)
        scenarios.append(
            {
                "name": name,
                "description": description.strip(),
                "kind": kind,
            }
        )

    for desc in required_behaviors:
        if isinstance(desc, str) and desc.strip():
            add(desc, "directed")

    for desc in special_scenarios:
        if isinstance(desc, str) and desc.strip():
            kind = "corner" if "corner" in desc.lower() else "directed"
            add(desc, kind)

    if include_corner_cases:
        add("boundary and corner-case validation", "corner")

    if include_long_run:
        add("long run stability under repeated stimulus", "long_run")

    directed_count = len([s for s in scenarios if s["kind"] != "random"])
    while directed_count < directed_scenarios and len(scenarios) < total_scenarios:
        idx = directed_count + 1
        add(f"directed validation scenario {idx}", "directed")
        directed_count = len([s for s in scenarios if s["kind"] != "random"])

    random_count = len([s for s in scenarios if s["kind"] == "random"])
    while random_count < random_scenarios and len(scenarios) < total_scenarios:
        idx = random_count + 1
        add(f"randomized stimulus scenario {idx}", "random")
        random_count = len([s for s in scenarios if s["kind"] == "random"])

    while len(scenarios) < total_scenarios:
        add(f"extra validation scenario {len(scenarios) + 1}", "directed")

    return scenarios[:total_scenarios]


def _extract_cycles_list(data: Any) -> list[Any] | None:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return None

    for key in ("cycles", "steps", "sequence", "stimulus", "vectors", "timeline", "trace", "inputs"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    list_values = [v for v in data.values() if isinstance(v, list)]
    if len(list_values) == 1:
        return list_values[0]

    return None


def _normalize_cycle_item(item: Any, input_names: list[str]) -> dict[str, int] | None:
    if isinstance(item, dict):
        src = item.get("inputs") if isinstance(item.get("inputs"), dict) else item
        return {name: _coerce_int(src.get(name, 0)) for name in input_names}

    if isinstance(item, list):
        values = [_coerce_int(v) for v in item]
        return {
            name: values[idx] if idx < len(values) else 0
            for idx, name in enumerate(input_names)
        }

    if isinstance(item, (int, float, bool, str)) and len(input_names) == 1:
        return {input_names[0]: _coerce_int(item)}

    return None


def _normalize_scenario_cycles_payload(
    data: Any,
    scenario: dict[str, Any],
    input_names: list[str],
) -> dict[str, Any] | None:
    raw_cycles = _extract_cycles_list(data)
    if not raw_cycles:
        return None

    cycles: list[dict[str, int]] = []
    for item in raw_cycles:
        normalized = _normalize_cycle_item(item, input_names)
        if normalized is not None:
            cycles.append(normalized)

    if not cycles:
        return None

    if isinstance(data, dict):
        name = data.get("name", scenario.get("name", "scenario"))
        description = data.get("description", scenario.get("description", ""))
        kind = data.get("kind", scenario.get("kind", "directed"))
    else:
        name = scenario.get("name", "scenario")
        description = scenario.get("description", "")
        kind = scenario.get("kind", "directed")

    return {
        "name": _slugify(str(name)),
        "description": str(description).strip(),
        "kind": _slugify(str(kind)),
        "cycles": cycles,
    }


def _build_fallback_cycles(
    spec: ModuleSpec,
    scenario: dict[str, Any],
    min_cycles: int,
    max_cycles: int,
) -> list[dict[str, int]]:
    seed_src = scenario.get("name", "scenario")
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    name = str(scenario.get("name", "")).lower()
    description = str(scenario.get("description", "")).lower()
    text = f"{name} {description}"

    num_cycles = min(max(min_cycles, 8), max_cycles)
    input_names = list(spec.inputs)
    cycles: list[dict[str, int]] = []

    reset_name = spec.reset if spec.reset in input_names else None
    reset_active = 0 if reset_name and reset_name.endswith("_n") else 1
    reset_inactive = 1 - reset_active if reset_name else 0

    def blank_cycle() -> dict[str, int]:
        return {signal: 0 for signal in input_names}

    for i in range(num_cycles):
        c = blank_cycle()

        if reset_name:
            c[reset_name] = reset_inactive

        for signal in input_names:
            if signal == reset_name:
                continue

            s = signal.lower()

            if "enable" in s or s == "en":
                if "toggle" in text:
                    c[signal] = i % 2
                elif "hold" in text:
                    c[signal] = 0
                elif "increment" in text or "long" in text or "wrap" in text:
                    c[signal] = 1
                else:
                    c[signal] = rng.randint(0, 1)
            else:
                c[signal] = rng.randint(0, 1)

        if reset_name and "reset" in text:
            if i < 2:
                c[reset_name] = reset_active
            elif "multiple" in text and i in (4, 5):
                c[reset_name] = reset_active
            elif "after_wrap" in text or "after wrap" in text:
                if i >= num_cycles - 2:
                    c[reset_name] = reset_active

        cycles.append(c)

    return cycles


class CodegenService:
    def __init__(self, client: LlamaCppClient | None = None):
        self.client = client or LlamaCppClient()

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

    def generate_python_reference_model(self, spec: ModuleSpec) -> str:
        prompt = f"""You are generating a cycle-accurate Python reference model for an RTL module.
            Specification:
            {_spec_to_prompt_json(spec)}

            Requirements:

            Return only the contents of a single .py file.
            Do not use markdown fences.
            Do not include explanations.
            Use only Python standard library.
            Define exactly one public class named ReferenceModel.
            The class must implement:
            init(self)
            reset(self) -> None
            step(self, inputs: dict) -> dict
            The model must be cycle-accurate and stateful.
            step() must consume one cycle of inputs and return ONLY output signals as a dict.
            Missing inputs should default to 0.
            Reset signal is "{spec.reset}".
            Clock signal is "{spec.clock}", but the simulator is stepped manually once per cycle.
            """.strip()
            
        raw = self.client.chat(
            prompt,
            temperature=0.1,
            max_tokens=1800,
        )
        return _extract_fenced_block(raw, "python")
    
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

        normalized = _normalize_scenario_plan_payload(data)

        if normalized is None:
            normalized = _build_fallback_scenario_plan(spec)

        if len(normalized) < total_scenarios:
            fallback = _build_fallback_scenario_plan(spec)
            existing_names = {item["name"] for item in normalized}
            for item in fallback:
                if item["name"] not in existing_names:
                    normalized.append(item)
                    existing_names.add(item["name"])
                if len(normalized) >= total_scenarios:
                    break

        normalized = normalized[:total_scenarios]

        if debug_dir is not None:
            (debug_dir / "scenario_plan_normalized.json").write_text(
                json.dumps({"scenarios": normalized}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return normalized
    
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
        input_names = list(spec.inputs)

        prompt = f"""You are generating one input scenario for a Python RTL reference model.
            Specification:
            {_spec_to_prompt_json(spec)}

            Reference model code:{model_code}
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

        normalized = _normalize_scenario_cycles_payload(
            data=data,
            scenario=scenario,
            input_names=input_names,
        )

        if normalized is None:
            normalized = {
                "name": scenario.get("name", f"scenario_{index}"),
                "description": scenario.get("description", ""),
                "kind": scenario.get("kind", "directed"),
                "cycles": _build_fallback_cycles(spec, scenario, min_cycles, max_cycles),
            }

        cycles = normalized["cycles"]

        if len(cycles) < min_cycles:
            filler = _build_fallback_cycles(spec, scenario, min_cycles, max_cycles)
            for item in filler:
                if len(cycles) >= min_cycles:
                    break
                cycles.append(item)

        if len(cycles) > max_cycles:
            cycles = cycles[:max_cycles]

        normalized["cycles"] = cycles

        if debug_dir is not None:
            safe_name = _slugify(str(scenario.get("name", f"scenario_{index}")))
            (debug_dir / f"scenario_{index}_{safe_name}_normalized.json").write_text(
                json.dumps(normalized, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return normalized
    
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