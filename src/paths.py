from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def slugify_name(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scenario"


@dataclass(slots=True)
class ModulePaths:
    module_name: str
    module_dir: Path
    tests_dir: Path
    tb_dir: Path
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
    def report_file(self) -> Path:
        return self.module_dir / f"{self.module_name}_pipeline_report.json"

    def scenario_slug(self, scenario_name: str) -> str:
        return slugify_name(scenario_name)

    def testbench_file_for(self, scenario_name: str) -> Path:
        slug = self.scenario_slug(scenario_name)
        return self.tb_dir / f"tb_{self.module_name}__{slug}.sv"

    def build_dir_for(self, scenario_name: str) -> Path:
        slug = self.scenario_slug(scenario_name)
        path = self.build_dir / slug
        path.mkdir(parents=True, exist_ok=True)
        return path

    def compile_output_file_for(self, scenario_name: str) -> Path:
        return self.build_dir_for(scenario_name) / f"{self.module_name}.out"

    def compile_log_file_for(self, scenario_name: str) -> Path:
        return self.build_dir_for(scenario_name) / "compile.log"

    def sim_log_file_for(self, scenario_name: str) -> Path:
        return self.build_dir_for(scenario_name) / "sim.log"

    def wave_file_for(self, scenario_name: str) -> Path:
        slug = self.scenario_slug(scenario_name)
        return self.waves_dir / f"{slug}.vcd"


def get_module_paths(base_generated_dir: str | Path, module_name: str) -> ModulePaths:
    base = Path(base_generated_dir)
    module_dir = base / module_name
    tests_dir = module_dir / "tests"
    tb_dir = module_dir / "tb"
    build_dir = module_dir / "build"
    waves_dir = module_dir / "waves"

    for d in (module_dir, tests_dir, tb_dir, build_dir, waves_dir):
        d.mkdir(parents=True, exist_ok=True)

    return ModulePaths(
        module_name=module_name,
        module_dir=module_dir,
        tests_dir=tests_dir,
        tb_dir=tb_dir,
        build_dir=build_dir,
        waves_dir=waves_dir,
    )