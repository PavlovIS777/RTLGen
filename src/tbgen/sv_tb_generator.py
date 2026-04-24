from __future__ import annotations

from pathlib import Path

from src.spec.schema import ModuleSpec


def _logic_decl(names: list[str], direction: str) -> str:
    if not names:
        return ""
    return "\n".join(f"  logic {name};" for name in names)


def _port_connections(spec: ModuleSpec) -> str:
    all_ports = spec.inputs + spec.outputs
    return ", ".join(f".{name}({name})" for name in all_ports)


def generate_testbench(
    spec: ModuleSpec,
    trace: list[dict],
    out_dir: str | Path,
) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    tb_file = out_path / f"{spec.module_name}_tb.sv"
    trace_comments = "\n".join(
        f"    // cycle={item['cycle']} inputs={item['inputs']} expected={item['outputs']}"
        for item in trace
    )

    tb_text = f"""`timescale 1ns/1ps

module {spec.module_name}_tb;
{_logic_decl(spec.inputs, "input")}
{_logic_decl(spec.outputs, "output")}

  {spec.module_name} dut ({_port_connections(spec)});

  initial begin
{trace_comments if trace_comments else "    // no trace data"}
    $display("Stub testbench generated. Real checks will be added later.");
    $finish;
  end
endmodule
"""
    tb_file.write_text(tb_text, encoding="utf-8")
    return tb_file
