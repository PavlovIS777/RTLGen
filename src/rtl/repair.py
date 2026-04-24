from __future__ import annotations

import json
import re
from pathlib import Path

from src.llm.client import LlamaCppClient
from src.spec.schema import ModuleSpec


def _extract_sv_code(text: str) -> str:
    m = re.search(r"```(?:systemverilog|verilog)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        return "\n".join(lines).strip()

    return text


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


class RTLRepairService:
    def __init__(self, client: LlamaCppClient | None = None):
        self.client = client or LlamaCppClient()

    def repair_rtl(
        self,
        spec: ModuleSpec,
        rtl_code: str,
        compile_log: str = "",
        sim_log: str = "",
        failing_scenario: str = "",
        debug_dir: str | Path | None = None,
        attempt: int = 1,
    ) -> str:
        prompt = f"""
            You are fixing a SystemVerilog RTL module for Icarus Verilog.

            Specification:
            {_spec_to_prompt_json(spec)}

            Current RTL:
            ```systemverilog
            {rtl_code}
            Compile log:
            {compile_log}
            Simulation log:

            {sim_log}
            Failing scenario:
            {failing_scenario or "<none>"}

            Requirements:

            Return ONLY corrected SystemVerilog code in one code block.
            Keep the module name exactly: {spec.module_name}
            Keep the interface strictly consistent with the specification.
            Preserve required signal widths from the spec metadata.
            Target simulator is Icarus Verilog with -g2012.
            Prefer simple compatible constructs.
            Do not change testbench assumptions.
            Do not include explanations.
            """.strip()
        raw = self.client.chat(prompt, temperature=0.0, max_tokens=2600)

        if debug_dir is not None:
            debug_path = Path(debug_dir)
            debug_path.mkdir(parents=True, exist_ok=True)
            (debug_path / f"rtl_repair_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")

        return _extract_sv_code(raw).strip() + "\n"