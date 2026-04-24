from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModuleSpec:
    module_name: str
    description: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    clock: str = "clk"
    reset: str = "rst_n"
    metadata: dict[str, Any] = field(default_factory=dict)
