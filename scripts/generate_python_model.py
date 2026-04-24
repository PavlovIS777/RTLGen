from __future__ import annotations

import argparse
import json
import py_compile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.codegen import CodegenService, _extract_python_code
from src.paths import get_module_paths
from src.spec.parser import load_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Python reference model from spec")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    service = CodegenService()
    code = service.generate_python_reference_model(spec)

    model_path = paths.python_model_file
    model_path.write_text(code + "\n", encoding="utf-8")
    try:
        py_compile.compile(str(model_path), doraise=True)
    except py_compile.PyCompileError as exc:
        broken_code = model_path.read_text(encoding="utf-8")
        repair_prompt = f"""
            Fix this Python file so that it becomes valid Python.

            Return only the corrected .py file.
            Do not use markdown fences.
            Do not include explanations.

            Broken file:
            ```python
            {broken_code}
            Compiler error:
            {exc}
            """.strip()
            
        repaired_raw = service.client.chat(repair_prompt, temperature=0.0, max_tokens=1800)
        repaired_code = _extract_python_code(repaired_raw)
        model_path.write_text(repaired_code + "\\n", encoding="utf-8")
        py_compile.compile(str(model_path), doraise=True)

    payload = {
        "status": "ok",
        "module_name": spec.module_name,
        "artifact": "python_model",
        "path": str(model_path),
    }

    print(json.dumps(payload, ensure_ascii=False) if args.json else f"python_model: {model_path}")


if __name__ == "__main__":
    main()