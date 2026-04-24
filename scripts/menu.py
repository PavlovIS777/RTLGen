from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPECS_ROOT = PROJECT_ROOT / "specs"


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def color(text: str, *styles: str) -> str:
    return "".join(styles) + text + C.RESET


def line(char: str = "─", width: int = 88) -> str:
    return char * width


def wrap_block(text: str, indent: str = "", width: int = 88) -> str:
    return textwrap.fill(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def section(title: str) -> None:
    print()
    print(color(line("═"), C.CYAN))
    print(color(title, C.BOLD, C.CYAN))
    print(color(line("═"), C.CYAN))


def subsection(title: str) -> None:
    print()
    print(color(title, C.BOLD, C.YELLOW))
    print(color(line("─"), C.GRAY))


def run(cmd: list[str]) -> int:
    print(color("Command:", C.BOLD, C.BLUE), " ".join(cmd))
    print()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def list_spec_files() -> list[Path]:
    if not SPECS_ROOT.exists():
        return []

    files = sorted(SPECS_ROOT.rglob("*.json"))
    return [p for p in files if p.is_file()]


def load_spec_payload(spec_path: str | Path) -> dict:
    path = Path(spec_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_module_name_from_spec(spec_path: str | Path) -> str:
    return load_spec_payload(spec_path)["module_name"]


def get_module_description_from_spec(spec_path: str | Path) -> str:
    return load_spec_payload(spec_path).get("description", "")


def choose_spec_interactive() -> str | None:
    specs = list_spec_files()

    section("SELECT SPEC")

    if not specs:
        print(color("No spec files found in specs/", C.RED))
        return None

    for idx, path in enumerate(specs, start=1):
        rel = path.relative_to(PROJECT_ROOT)
        try:
            payload = load_spec_payload(path)
            module_name = payload.get("module_name", "<unknown>")
            description = payload.get("description", "")
        except Exception:
            module_name = "<invalid spec>"
            description = ""

        print(f"  {idx:>2}  {rel}")
        print(f"      module: {module_name}")
        if description:
            print(wrap_block(description, indent="      ", width=88))
        print(color(line("."), C.GRAY))

    choice = input(color("Select spec number (empty to cancel): ", C.BOLD)).strip()
    if not choice:
        return None

    if not choice.isdigit():
        print(color("Invalid selection.", C.RED))
        return None

    index = int(choice)
    if index < 1 or index > len(specs):
        print(color("Selection out of range.", C.RED))
        return None

    selected = specs[index - 1].relative_to(PROJECT_ROOT)
    print(color("Selected spec:", C.GREEN), selected)
    return str(selected)


def ensure_spec_selected(current_spec: str | None) -> str | None:
    if current_spec is not None:
        return current_spec

    print(color("No spec selected.", C.YELLOW))
    return choose_spec_interactive()


def generate_python_model(spec_path: str) -> int:
    return run([
        sys.executable,
        "scripts/generate_python_model.py",
        "--spec",
        spec_path,
    ])


def generate_tests(spec_path: str) -> int:
    module_name = get_module_name_from_spec(spec_path)
    model_path = f"generated/{module_name}/reference_model.py"

    return run([
        sys.executable,
        "scripts/generate_tests.py",
        "--spec",
        spec_path,
        "--model",
        model_path,
    ])


def run_reference_validation(spec_path: str) -> int:
    module_name = get_module_name_from_spec(spec_path)
    module_dir = f"generated/{module_name}"

    return run([
        sys.executable,
        "scripts/run_reference_tests.py",
        "--module-dir",
        module_dir,
    ])


def generate_rtl(spec_path: str) -> int:
    module_name = get_module_name_from_spec(spec_path)

    return run([
        sys.executable,
        "scripts/generate_rtl.py",
        "--spec",
        spec_path,
        "--model",
        f"generated/{module_name}/reference_model.py",
        "--trace",
        f"generated/{module_name}/tests/golden_trace.json",
    ])


def generate_testbench(spec_path: str) -> int:
    module_name = get_module_name_from_spec(spec_path)

    return run([
        sys.executable,
        "scripts/generate_testbench.py",
        "--spec",
        spec_path,
        "--trace",
        f"generated/{module_name}/tests/golden_trace.json",
    ])


def full_flow(spec_path: str) -> int:
    steps = [
        ("Generate Python reference model", lambda: generate_python_model(spec_path)),
        ("Generate input scenarios and golden trace", lambda: generate_tests(spec_path)),
        ("Validate reference model", lambda: run_reference_validation(spec_path)),
        ("Generate RTL module", lambda: generate_rtl(spec_path)),
        ("Generate SystemVerilog testbench", lambda: generate_testbench(spec_path)),
    ]

    section("RTLGEN · FULL FLOW")

    for idx, (name, fn) in enumerate(steps, start=1):
        subsection(f"[Step {idx}/{len(steps)}] {name}")
        code = fn()
        if code != 0:
            print()
            print(color("FLOW STOPPED", C.BOLD, C.RED))
            print(color(f"Failed step: {name}", C.RED))
            return code

    print()
    print(color("SUCCESS", C.BOLD, C.GREEN), "Full flow finished successfully.")
    return 0


def print_menu(spec_path: str | None) -> None:
    section("RTLGEN")

    if spec_path is None:
        print(color("Selected spec", C.BOLD), ": <none>")
    else:
        module_name = get_module_name_from_spec(spec_path)
        module_description = get_module_description_from_spec(spec_path)

        print(color("Selected spec", C.BOLD), f": {spec_path}")
        print(color("Module", C.BOLD), f": {module_name}")

        if module_description:
            print(color("Description", C.BOLD), ":")
            print(wrap_block(module_description, indent="  "))

    print(color(line("─"), C.GRAY))
    print("  1  Select spec from specs/")
    print("  2  Generate Python reference model")
    print("  3  Generate input scenarios and golden trace")
    print("  4  Validate reference model")
    print("  5  Generate RTL module")
    print("  6  Generate SystemVerilog testbench")
    print("  7  Run full flow")
    print("  0  Exit")
    print(color(line("─"), C.GRAY))


def main() -> None:
    spec_path: str | None = None

    while True:
        print_menu(spec_path)
        choice = input(color("Select option: ", C.BOLD)).strip()

        if choice == "1":
            selected = choose_spec_interactive()
            if selected is not None:
                spec_path = selected

        elif choice == "2":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                subsection("Generate Python reference model")
                generate_python_model(spec_path)

        elif choice == "3":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                subsection("Generate input scenarios and golden trace")
                generate_tests(spec_path)

        elif choice == "4":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                subsection("Validate reference model")
                run_reference_validation(spec_path)

        elif choice == "5":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                subsection("Generate RTL module")
                generate_rtl(spec_path)

        elif choice == "6":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                subsection("Generate SystemVerilog testbench")
                generate_testbench(spec_path)

        elif choice == "7":
            spec_path = ensure_spec_selected(spec_path)
            if spec_path:
                full_flow(spec_path)

        elif choice == "0":
            print(color("Bye.", C.DIM))
            break

        else:
            print(color("Unknown option.", C.RED))


if __name__ == "__main__":
    main()