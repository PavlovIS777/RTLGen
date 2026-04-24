from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ModulePaths:
    module_dir: Path
    tests_dir: Path

    @property
    def python_model_file(self) -> Path:
        return self.module_dir / "reference_model.py"

    @property
    def input_scenarios_file(self) -> Path:
        return self.tests_dir / "input_scenarios.json"

    @property
    def golden_trace_file(self) -> Path:
        return self.tests_dir / "golden_trace.json"

    @property
    def pytest_file(self) -> Path:
        return self.tests_dir / "test_reference_model.py"

    @property
    def rtl_file(self) -> Path:
        return self.module_dir / "module.sv"

    @property
    def tb_file(self) -> Path:
        return self.module_dir / "testbench.sv"

    @property
    def report_file(self) -> Path:
        return self.module_dir / "pipeline_report.json"


def get_module_paths(base_generated_dir: str | Path, module_name: str) -> ModulePaths:
    base = Path(base_generated_dir)
    module_dir = base / module_name
    tests_dir = module_dir / "tests"

    module_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    return ModulePaths(
        module_dir=module_dir,
        tests_dir=tests_dir,
    )