from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.llm.client import LlamaCppClient
from src.spec.schema import ModuleSpec


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


def _build_trace_summary(golden_trace: dict[str, Any], max_scenarios: int = 4, max_cycles: int = 4) -> str:
    scenarios = golden_trace.get("scenarios", [])
    short = []

    for scenario in scenarios[:max_scenarios]:
        trace = scenario.get("trace", [])
        short.append(
            {
                "name": scenario.get("name", "unnamed"),
                "description": scenario.get("description", ""),
                "num_cycles": len(trace),
                "sample_cycles": trace[:max_cycles],
            }
        )

    payload = {
        "module_name": golden_trace.get("module_name", ""),
        "module_description": golden_trace.get("module_description", ""),
        "scenario_summary": short,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


class RTLCodegenService:
    def __init__(self, client: LlamaCppClient | None = None):
        self.client = client or LlamaCppClient()

    def generate_rtl_module(
        self,
        spec: ModuleSpec,
        reference_model_code: str,
        golden_trace: dict[str, Any],
        debug_dir: str | Path | None = None,
    ) -> str:
        prompt = f"""
            You are generating a SystemVerilog RTL module from a specification, a Python reference model, and a sample of golden traces.

            Specification:
            {_spec_to_prompt_json(spec)}

            Python reference model:
            ```python
            {reference_model_code}
            Golden trace summary:
            {_build_trace_summary(golden_trace)}

            Requirements:

            Return ONLY SystemVerilog code in one code block.
            Generate exactly one module named {spec.module_name}.
            Do NOT generate a testbench.
            The module must include ports for:
            clock signal: {spec.clock}
            input signals: {spec.inputs}
            output signals: {spec.outputs}
            Use synthesizable RTL only.
            Prefer always_ff for sequential logic and always_comb for combinational logic when appropriate.
            Implement behavior consistent with the specification and golden traces.
            If metadata contains width-like information, use it.
            Do not include explanations.

            Important:

            The design must match the Python reference model semantics.
            Treat the design as cycle-accurate.
            Reset signal name is "{spec.reset}".
            If reset name ends with "_n", assume active-low reset unless the description clearly says otherwise.
            """.strip()
        raw = self.client.chat(
            prompt,
            temperature=0.1,
            max_tokens=2200,
        )

        if debug_dir is not None:
            debug_path = Path(debug_dir)
            debug_path.mkdir(parents=True, exist_ok=True)
            (debug_path / "rtl_raw_response.txt").write_text(raw, encoding="utf-8")

        code = _extract_fenced_block(raw, "systemverilog")
        if code == raw.strip():
            code = _extract_fenced_block(raw, "verilog")

        return code.strip() + "\n"