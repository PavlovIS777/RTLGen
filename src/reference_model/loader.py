
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_python_module_from_path(path: str | Path) -> ModuleType:
    file_path = Path(path)
    module_name = f"generated_model_{file_path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reference_model_class(path: str | Path):
    module = load_python_module_from_path(path)

    if not hasattr(module, "ReferenceModel"):
        raise AttributeError(f"{path} does not define ReferenceModel")

    return module.ReferenceModel


def instantiate_reference_model(path: str | Path):
    cls = load_reference_model_class(path)
    instance = cls()
    if hasattr(instance, "reset"):
        instance.reset()
    return instance