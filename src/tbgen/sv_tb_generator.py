from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.paths import slugify_name
from src.spec.schema import ModuleSpec


def _infer_reset_active_level(reset_name: str) -> int:
    return 0 if reset_name.endswith("_n") else 1


def _collect_signal_max_values(golden_trace: dict[str, Any]) -> dict[str, int]:
    max_values: dict[str, int] = {}

    for scenario in golden_trace.get("scenarios", []):
        for item in scenario.get("trace", []):
            for domain in ("inputs", "outputs"):
                for name, value in item.get(domain, {}).items():
                    try:
                        v = int(value)
                    except Exception:
                        v = 0
                    max_values[name] = max(max_values.get(name, 0), v)

    return max_values


def _infer_signal_widths(spec: ModuleSpec, golden_trace: dict[str, Any]) -> dict[str, int]:
    widths: dict[str, int] = {}
    signal_widths = spec.metadata.get("signal_widths", {})

    if isinstance(signal_widths, dict):
        for name, width in signal_widths.items():
            try:
                widths[name] = max(1, int(width))
            except Exception:
                pass

    max_values = _collect_signal_max_values(golden_trace)

    for name in set(spec.inputs + spec.outputs + [spec.clock]):
        if not name:
            continue
        if name in widths:
            continue

        if name == spec.clock or name == spec.reset:
            widths[name] = 1
            continue

        if "width" in spec.metadata and len(spec.outputs) == 1 and name == spec.outputs[0]:
            try:
                widths[name] = max(1, int(spec.metadata["width"]))
                continue
            except Exception:
                pass

        max_val = int(max_values.get(name, 0))
        widths[name] = max(1, max_val.bit_length())

    return widths


def _sv_decl(name: str, width: int) -> str:
    if width <= 1:
        return f"logic {name};"
    return f"logic [{width - 1}:0] {name};"


def _sv_literal(value: int, width: int) -> str:
    value = int(value)
    if width <= 1:
        return f"1'b{value & 1}"
    return f"{width}'d{value}"


def _port_list(spec: ModuleSpec) -> list[str]:
    ports: list[str] = []
    if spec.clock and spec.clock not in ports:
        ports.append(spec.clock)

    for name in spec.inputs:
        if name not in ports:
            ports.append(name)

    for name in spec.outputs:
        if name not in ports:
            ports.append(name)

    return ports


def _connection_block(spec: ModuleSpec) -> str:
    ports = _port_list(spec)
    return ",\n".join(f"    .{name}({name})" for name in ports)


def _build_reset_task(spec: ModuleSpec, widths: dict[str, int]) -> str:
    if not spec.reset:
        return ""

    active_level = _infer_reset_active_level(spec.reset)
    inactive_level = 0 if active_level == 1 else 1

    assignments = []
    for name in spec.inputs:
        width = widths.get(name, 1)
        if name == spec.reset:
            assignments.append(f"    {name} = {_sv_literal(active_level, width)};")
        else:
            assignments.append(f"    {name} = {_sv_literal(0, width)};")

    assignments_text = "\n".join(assignments)
    deassert_text = f"    {spec.reset} = {_sv_literal(inactive_level, widths.get(spec.reset, 1))};"

    return f"""
task automatic reset_dut();
begin
{assignments_text}
    repeat (2) @(posedge {spec.clock});
    #1;
{deassert_text}
    @(negedge {spec.clock});
end
endtask
""".strip()


def _tb_module_name(spec: ModuleSpec, scenario_name: str) -> str:
    slug = slugify_name(scenario_name)
    return f"tb_{spec.module_name}__{slug}"


def generate_testbench_for_scenario(
    spec: ModuleSpec,
    golden_trace: dict[str, Any],
    scenario: dict[str, Any],
    out_path: str | Path,
    wave_path: str | Path,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    scenario_name = scenario.get("name", "unnamed_scenario")
    scenario_description = scenario.get("description", "")
    tb_module_name = _tb_module_name(spec, scenario_name)
    wave_path = str(Path(wave_path))

    widths = _infer_signal_widths(spec, golden_trace)
    trace = scenario.get("trace", [])

    declarations: list[str] = []
    for name in _port_list(spec):
        declarations.append(_sv_decl(name, widths.get(name, 1)))

    reset_task = _build_reset_task(spec, widths)

    lines: list[str] = []
    lines.append(f'    $display("SCENARIO: {scenario_name}");')
    if scenario_description:
        escaped_desc = scenario_description.replace('"', '\\"')
        lines.append(f'    $display("DESCRIPTION: {escaped_desc}");')

    if spec.reset:
        lines.append("    reset_dut();")

    lines.append("    scenario_failed = 0;")

    for item in trace:
        cycle = int(item["cycle"])
        inputs = item.get("inputs", {})
        outputs = item.get("outputs", {})

        lines.append(f"    // cycle {cycle}")

        for name in spec.inputs:
            value = int(inputs.get(name, 0))
            lines.append(f"    {name} = {_sv_literal(value, widths.get(name, 1))};")

        if spec.clock:
            lines.append(f"    @(posedge {spec.clock});")
            lines.append("    #1;")
        else:
            lines.append("    #1;")

        for name in spec.outputs:
            expected = int(outputs.get(name, 0))
            expected_lit = _sv_literal(expected, widths.get(name, 1))
            lines.append(
                f"""    total_checks = total_checks + 1;
    if ({name} !== {expected_lit}) begin
      total_failures = total_failures + 1;
      scenario_failed = 1;
      $display("FAIL scenario={scenario_name} cycle={cycle} signal={name} expected=%0d got=%0d", {expected_lit}, {name});
    end"""
            )

    lines.append(
        f"""    if (scenario_failed == 0) begin
      $display("PASS scenario={scenario_name}");
    end else begin
      $display("FAIL scenario={scenario_name}");
    end
    $display("==============================================");
    $display("RTL TESTBENCH SUMMARY");
    $display("scenario       = {scenario_name}");
    $display("total_checks   = %0d", total_checks);
    $display("total_failures = %0d", total_failures);
    $display("==============================================");

    if (total_failures == 0) begin
      $finish;
    end else begin
      $fatal(1, "RTL testbench detected failures.");
    end
"""
    )

    scenario_body = "\n".join(lines)

    tb_text = f"""`timescale 1ns/1ps

module {tb_module_name};

{chr(10).join("  " + d for d in declarations)}

  integer total_checks = 0;
  integer total_failures = 0;
  integer scenario_failed = 0;

  {spec.module_name} dut (
{_connection_block(spec)}
  );

{"  initial begin " + spec.clock + " = 0; end" if spec.clock else ""}
{"  always #5 " + spec.clock + " = ~" + spec.clock + ";" if spec.clock else ""}

  initial begin
    $dumpfile("{wave_path}");
    $dumpvars(0, {tb_module_name});
  end

{"" if not reset_task else "  " + reset_task.replace(chr(10), chr(10) + "  ")}

  initial begin
    $display("==============================================");
    $display("RTL TESTBENCH START");
    $display("Module: {spec.module_name}");
    $display("Testbench: {tb_module_name}");
    $display("==============================================");
    $display("");

{scenario_body}
  end

endmodule
"""
    out.write_text(tb_text, encoding="utf-8")
    return out