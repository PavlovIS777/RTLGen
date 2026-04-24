from __future__ import annotations

from pathlib import Path

from src.spec.schema import ModuleSpec


def generate_rtl(spec: ModuleSpec, out_dir: str | Path) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rtl_file = out_path / f"{spec.module_name}.sv"

    ports: list[str] = []
    ports.extend(f"    input logic {name}" for name in spec.inputs)
    ports.extend(f"    output logic {name}" for name in spec.outputs)

    port_block = ",\n".join(ports)
    assign_block = "\n".join(f"  assign {name} = 1'b0;" for name in spec.outputs)
    if not assign_block:
        assign_block = "  // no outputs defined"

    rtl_text = f"""module {spec.module_name}(
{port_block}
);
{assign_block}
endmodule
"""
    rtl_file.write_text(rtl_text, encoding="utf-8")
    return rtl_file
