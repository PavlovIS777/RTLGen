from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ModulePaths:
    module_name: str
    module_dir: Path
    tests_dir: Path
    build_dir: Path
    waves_dir: Path

    @property
    def python_model_file(self) -> Path:
        return self.module_dir / f"{self.module_name}_reference_model.py"

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
        return self.module_dir / f"{self.module_name}.sv"

    @property
    def tb_file(self) -> Path:
        return self.module_dir / f"tb_{self.module_name}.sv"

    @property
    def report_file(self) -> Path:
        return self.module_dir / f"{self.module_name}_pipeline_report.json"

    @property
    def compile_output_file(self) -> Path:
        return self.build_dir / f"{self.module_name}.out"

    @property
    def compile_log_file(self) -> Path:
        return self.build_dir / f"{self.module_name}_compile.log"

    @property
    def sim_log_file(self) -> Path:
        return self.build_dir / f"{self.module_name}_sim.log"

    @property
    def wave_file(self) -> Path:
        return self.waves_dir / f"{self.module_name}.vcd"


def get_module_paths(base_generated_dir: str | Path, module_name: str) -> ModulePaths:
    base = Path(base_generated_dir)
    module_dir = base / module_name
    tests_dir = module_dir / "tests"
    build_dir = module_dir / "build"
    waves_dir = module_dir / "waves"

    for d in (module_dir, tests_dir, build_dir, waves_dir):
        d.mkdir(parents=True, exist_ok=True)

    return ModulePaths(
        module_name=module_name,
        module_dir=module_dir,
        tests_dir=tests_dir,
        build_dir=build_dir,
        waves_dir=waves_dir,
    )