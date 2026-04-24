from __future__ import annotations

import json
import re
from pathlib import Path

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


class TestbenchRepairService:
    def __init__(self, client: LlamaCppClient | None = None):
        self.client = client or LlamaCppClient()

    def repair_testbench(
        self,
        spec: ModuleSpec,
        rtl_code: str,
        tb_code: str,
        compile_log: str,
        debug_dir: str | Path | None = None,
    ) -> str:
        prompt = f"""
            You are fixing a SystemVerilog testbench for Icarus Verilog.

            Specification:
            {_spec_to_prompt_json(spec)}

            Current RTL:
            ```systemverilog
            {rtl_code}
            Current testbench:
            {tb_code}
            Compiler error log:
            {compile_log}
            Requirements:
            Return ONLY corrected SystemVerilog code in one code block.
            Keep one scenario per testbench.
            Keep waveform dumping enabled.
            Keep the behavioral checks against expected outputs.
            Target simulator is Icarus Verilog with -g2012.
            Use simple, compatible SystemVerilog only.

            Do not include explanations.
            """.strip()
        raw = self.client.chat(prompt, temperature=0.0, max_tokens=2600)

        if debug_dir is not None:
            debug_path = Path(debug_dir)
            debug_path.mkdir(parents=True, exist_ok=True)
            (debug_path / "tb_repair_raw_response.txt").write_text(raw, encoding="utf-8")

        code = _extract_fenced_block(raw, "systemverilog")
        if code == raw.strip():
            code = _extract_fenced_block(raw, "verilog")

        return code.strip() + "\n"