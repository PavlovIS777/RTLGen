from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.paths import get_module_paths
from src.rtl.generator import RTLCodegenService
from src.spec.parser import load_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate RTL module from spec and reference artifacts")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--trace", default=None)
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    paths = get_module_paths(args.generated_dir, spec.module_name)

    model_path = Path(args.model) if args.model else paths.python_model_file
    trace_path = Path(args.trace) if args.trace else paths.golden_trace_file

    reference_model_code = model_path.read_text(encoding="utf-8")
    golden_trace = json.loads(trace_path.read_text(encoding="utf-8"))

    service = RTLCodegenService()
    rtl_code = service.generate_rtl_module(
        spec=spec,
        reference_model_code=reference_model_code,
        golden_trace=golden_trace,
        debug_dir=paths.tests_dir,
    )

    paths.rtl_file.write_text(rtl_code, encoding="utf-8")

    payload = {
        "status": "ok",
        "module_name": spec.module_name,
        "artifact": "rtl",
        "path": str(paths.rtl_file),
    }

    print(json.dumps(payload, ensure_ascii=False) if args.json else f"rtl: {paths.rtl_file}")


if __name__ == "__main__":
    main()