from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.spec.schema import ModuleSpec


@dataclass
class PortInfo:
    direction: str
    name: str
    width: int


@dataclass
class SanityResult:
    ok: bool
    errors: list[str]


def _infer_expected_widths(spec: ModuleSpec) -> dict[str, int]:
    widths: dict[str, int] = {}

    signal_widths = spec.metadata.get("signal_widths", {})
    if isinstance(signal_widths, dict):
        for name, width in signal_widths.items():
            try:
                widths[str(name)] = max(1, int(width))
            except Exception:
                pass

    if spec.clock:
        widths.setdefault(spec.clock, 1)
    if spec.reset:
        widths.setdefault(spec.reset, 1)

    for name in spec.inputs:
        widths.setdefault(name, 1)

    for name in spec.outputs:
        widths.setdefault(name, 1)

    if "width" in spec.metadata and len(spec.outputs) == 1:
        try:
            widths[spec.outputs[0]] = max(1, int(spec.metadata["width"]))
        except Exception:
            pass

    return widths


def _parse_width(token: str) -> int:
    token = token.strip()
    if not token:
        return 1

    m = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", token)
    if not m:
        return 1

    msb = int(m.group(1))
    lsb = int(m.group(2))
    return abs(msb - lsb) + 1


def _extract_module_name(rtl_code: str) -> str | None:
    m = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", rtl_code)
    return m.group(1) if m else None


def _extract_ports_from_header(rtl_code: str) -> list[PortInfo]:
    m = re.search(r"\bmodule\s+[A-Za-z_][A-Za-z0-9_]*\s*\((.*?)\)\s*;", rtl_code, flags=re.DOTALL)
    if not m:
        return []

    header = m.group(1)
    parts = [p.strip() for p in header.split(",") if p.strip()]

    ports: list[PortInfo] = []
    for part in parts:
        part = re.sub(r"\s+", " ", part.strip())

        m_port = re.match(
            r"^(input|output|inout)\s+(?:wire|reg|logic\s+)?(?:\s*(\[[^\]]+\]))?\s*([A-Za-z_][A-Za-z0-9_]*)$",
            part,
            flags=re.IGNORECASE,
        )
        if not m_port:
            continue

        direction = m_port.group(1)
        width_token = m_port.group(2) or ""
        name = m_port.group(3)
        ports.append(PortInfo(direction=direction.lower(), name=name, width=_parse_width(width_token)))

    return ports


def check_rtl_interface(spec: ModuleSpec, rtl_code: str) -> SanityResult:
    errors: list[str] = []

    module_name = _extract_module_name(rtl_code)
    if module_name != spec.module_name:
        errors.append(
            f"Module name mismatch: expected {spec.module_name!r}, got {module_name!r}."
        )

    ports = _extract_ports_from_header(rtl_code)
    if not ports:
        errors.append("Could not parse module header ports.")
        return SanityResult(ok=False, errors=errors)

    expected_widths = _infer_expected_widths(spec)
    port_map = {p.name: p for p in ports}

    expected_inputs = []
    if spec.clock:
        expected_inputs.append(spec.clock)
    expected_inputs.extend(spec.inputs)

    for name in expected_inputs:
        if name not in port_map:
            errors.append(f"Missing input port: {name}.")
            continue
        if port_map[name].direction != "input":
            errors.append(f"Port {name} must be declared as input.")
        expected_width = expected_widths.get(name, 1)
        if port_map[name].width != expected_width:
            errors.append(
                f"Width mismatch for input {name}: expected {expected_width}, got {port_map[name].width}."
            )

    for name in spec.outputs:
        if name not in port_map:
            errors.append(f"Missing output port: {name}.")
            continue
        if port_map[name].direction != "output":
            errors.append(f"Port {name} must be declared as output.")
        expected_width = expected_widths.get(name, 1)
        if port_map[name].width != expected_width:
            errors.append(
                f"Width mismatch for output {name}: expected {expected_width}, got {port_map[name].width}."
            )

    return SanityResult(ok=len(errors) == 0, errors=errors)