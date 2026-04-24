from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.orchestrator import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run minimal RTL generation pipeline.")
    parser.add_argument("--spec", default="specs/examples/counter.json")
    parser.add_argument("--generated-dir", default="generated")
    parser.add_argument("--num-cycles", type=int, default=5)
    parser.add_argument("--enable-xrun", action="store_true")
    args = parser.parse_args()

    result = run_pipeline(
        spec_path=args.spec,
        generated_dir=args.generated_dir,
        enable_xrun=args.enable_xrun,
        num_cycles=args.num_cycles,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
