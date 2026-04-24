# RTLGEN

RTLGEN is a local pipeline for generating and validating RTL modules from textual specifications.

The project uses a local LLM to build a full development chain:

**spec → Python reference model → test scenarios → golden trace → RTL → per-scenario testbenches → RTL simulation → waveforms**

---

## What RTLGEN does

RTLGEN automates the main steps of developing a digital module from a JSON specification:

- selects a module specification from `specs/`
- generates a **Python reference model**
- generates **input scenarios**
- computes a **golden trace** from the Python model
- generates an **RTL module** in SystemVerilog
- generates a **separate testbench for each scenario**
- compiles and runs RTL against those testbenches with **Icarus Verilog**
- saves a separate **waveform (`.vcd`)** for each scenario
- opens waveforms in **GTKWave**

This makes debugging much easier than using one giant testbench for all scenarios.

---

## Main idea

Instead of generating RTL and checking it directly, RTLGEN first builds an executable reference model in Python.

The pipeline is:

1. Generate a Python reference model from the specification.
2. Generate test scenarios for that model.
3. Run the model on those scenarios.
4. Save the resulting cycle-accurate outputs as a golden trace.
5. Generate RTL from the specification and reference artifacts.
6. Generate one SystemVerilog testbench per scenario.
7. Simulate the RTL and compare it against the golden trace.
8. Save one waveform per scenario.

This gives you both a functional oracle and a readable validation flow.

---

## Features

### Artifact generation

For each module, RTLGEN generates:

- `<module_name>_reference_model.py`
- `<module_name>.sv`
- `tb_<module_name>__<scenario>.sv` for each scenario
- `input_scenarios.json`
- `golden_trace.json`
- compile logs and simulation logs
- waveform files (`.vcd`)

### Reference-model validation

Before touching RTL, RTLGEN validates the generated Python reference model against the generated scenarios.

### RTL validation

RTLGEN validates the RTL using:

- one scenario per testbench
- one compile per scenario
- one simulation per scenario
- one waveform per scenario

This makes it easy to see which scenario passes or fails.

### Testbench repair loop

If a generated testbench fails to compile in `iverilog`, RTLGEN can:

- read the compiler log
- ask the LLM to regenerate the testbench with those errors in mind
- retry the compile

---

## Project structure

```text
RTLGen/
├── configs/
│   └── llm/
│       ├── 6gb.env
│       └── 12gb.env
├── docker/
├── generated/
│   └── <module_name>/
│       ├── <module_name>_reference_model.py
│       ├── <module_name>.sv
│       ├── <module_name>_pipeline_report.json
│       ├── tests/
│       │   ├── input_scenarios.json
│       │   ├── golden_trace.json
│       │   └── test_reference_model.py
│       ├── tb/
│       │   ├── tb_<module_name>__scenario_1.sv
│       │   └── tb_<module_name>__scenario_2.sv
│       ├── build/
│       │   └── <scenario_name>/
│       │       ├── compile.log
│       │       ├── sim.log
│       │       └── <module_name>.out
│       └── waves/
│           ├── scenario_1.vcd
│           └── scenario_2.vcd
├── scripts/
├── specs/
├── src/
├── docker-compose.yml
├── requirements.docker.txt
└── README.md
```

---

## Dependencies

### System dependencies on Linux

Install:

- Docker
- Docker Compose
- Icarus Verilog (`iverilog`, `vvp`)
- GTKWave
- Bash

For Ubuntu or Debian:

```bash
sudo apt update
sudo apt install -y git curl iverilog gtkwave
```

Check that the tools are available:

```bash
iverilog -V
vvp -V
gtkwave --version
docker --version
docker compose version
```

### Dependencies inside the `app` container

The application container uses Python 3.11 and installs:

- `requests`
- `PyYAML`
- `pytest`
- `rich`

### LLM backend

The `llm` container runs a local inference server based on `llama.cpp`.

Choose the profile that matches your GPU memory:

- `configs/llm/6gb.env`
- `configs/llm/12gb.env`

---

## Installation on Linux

### 1. Clone the repository

```bash
git clone <your-repo-url> RTLGen
cd RTLGen
```

### 2. Pick an LLM profile

Use one of the prepared profiles:

- `6gb.env` for smaller GPUs
- `12gb.env` for larger GPUs

### 3. Run the installer

For a 12 GB GPU:

```bash
bash scripts/install_host.sh 12gb
```

For a 6 GB GPU:

```bash
bash scripts/install_host.sh 6gb
```

The installer will:

- create `.env` with your local `UID` and `GID`
- save the selected profile
- build the Docker containers
- start the services
- prepare the workspace

---

## Running the program

### Start the menu

```bash
bash scripts/run_menu.sh
```

### Open waveforms

```bash
bash scripts/open_wave.sh
```

---

## Typical workflow

1. Select a spec from `specs/`.
2. Generate the Python reference model.
3. Generate input scenarios and the golden trace.
4. Validate the reference model.
5. Generate the RTL module.
6. Generate per-scenario testbenches.
7. Compile and run the RTL simulation suite.
8. Open the waveform of the scenario you want to inspect.

---

## Specification format

All specs are JSON files stored in `specs/`.

### Minimal example

```json
{
  "module_name": "counter",
  "description": "4-bit synchronous up-counter. When rst_n=0, counter resets to 0. On each cycle, if en=1 and rst_n=1, increment count by 1 modulo 16. If en=0, hold the current value.",
  "inputs": ["rst_n", "en"],
  "outputs": ["count"],
  "clock": "clk",
  "reset": "rst_n",
  "width": 4
}
```

### Fields

#### `module_name`
Module name. Used for:

- generated file names
- generated directory name
- RTL module name

#### `description`
Main behavioral description. This is the most important field for the LLM.

#### `inputs`
List of input signal names.

#### `outputs`
List of output signal names.

#### `clock`
Clock signal name.

#### `reset`
Reset signal name.

#### `width`
A module-specific parameter. Other modules may instead use fields such as:

- `data_width`
- `depth`
- `latency`
- `states`

### Extended test-generation configuration

Specs can include a `test_generation` block to control how scenarios are generated.

Example:

```json
{
  "test_generation": {
    "directed_scenarios": 8,
    "random_scenarios": 12,
    "min_cycles_per_scenario": 4,
    "max_cycles_per_scenario": 24,
    "include_reset_scenarios": true,
    "include_corner_cases": true,
    "include_long_run": true,
    "required_behaviors": [
      "reset clears the counter to zero",
      "counter increments only when en=1 and rst_n=1",
      "counter holds value when en=0",
      "counter wraps around from 15 to 0"
    ],
    "special_scenarios": [
      "multiple resets in one scenario",
      "enable toggles every cycle",
      "long increment sequence that crosses wraparound",
      "reset asserted immediately after wraparound"
    ],
    "notes": "Generate diverse scenarios, not just one scenario per behavior."
  }
}
```

---

## Golden trace

A **golden trace** is a cycle-accurate reference trace generated by the Python model.

For each cycle it stores:

- the cycle index
- the input values
- the expected output values

RTL is validated against this golden trace.

---

## Testbench model

RTLGEN generates **one testbench per scenario**.

That means:

- one scenario → one testbench
- one scenario → one compile
- one scenario → one simulation
- one scenario → one waveform

This makes logs and waveforms much easier to read and debug.

---

## Simulation backend

RTLGEN currently uses **Icarus Verilog** for RTL compilation and simulation.

Typical commands:

```bash
iverilog -g2012 -o <out> <rtl> <testbench>
vvp <out>
```

Each scenario gets:

- a dedicated compile log
- a dedicated simulation log
- a dedicated waveform file

---

## Waveform viewing

Waveforms are stored in:

```text
generated/<module_name>/waves/
```

Example:

```text
generated/counter/waves/reset_to_zero.vcd
generated/counter/waves/increment_when_en.vcd
generated/counter/waves/wraparound_check.vcd
```

To open a waveform manually:

```bash
gtkwave generated/counter/waves/reset_to_zero.vcd
```

Or use:

```bash
bash scripts/open_wave.sh
```

---

## Commands

### Install

```bash
bash scripts/install_host.sh 12gb
```

or

```bash
bash scripts/install_host.sh 6gb
```

### Start the menu

```bash
bash scripts/run_menu.sh
```

### Open a waveform

```bash
bash scripts/open_wave.sh
```

---

## Files that can likely be removed

Below is a **safe cleanup list based on the current pipeline design**.

### Likely removable if they still exist from older iterations

- `generated/logs/`
- `generated/python_models/`
- `generated/rtl/`
- `generated/tb/`
- `generated/traces/`
- `generated/reports/`

These are legacy layout folders if you have already migrated to the new per-module structure under `generated/<module>/...`.

### Remove if you are not using the old xrun flow

- `scripts/run_xrun_check.py`
- `src/simulators/xrun_runner.py`

### Remove if they are empty or obsolete in your current branch

- unused placeholder files in `generated/`
- outdated debug files from failed generations
- old single-testbench outputs that predate the per-scenario split

### Do **not** remove blindly

- `pyproject.toml` — keep it **if pytest still reads configuration from it**. If `pytest` output shows `configfile: pyproject.toml`, then it is being used.
- `requirements.docker.txt` — used for the `app` container
- `docker-compose.yml` — required
- `configs/llm/*.env` — required for profile selection
- `scripts/install_host.sh`, `scripts/run_menu.sh`, `scripts/open_wave.sh` — part of the current workflow

---

## Recommended final structure

```text
RTLGen/
├── configs/
├── docker/
├── generated/
├── scripts/
├── specs/
├── src/
├── docker-compose.yml
├── requirements.docker.txt
├── README.md
├── .env.example
└── .gitignore
```

If `pyproject.toml` is not used anymore, it can be removed too.

---

## Troubleshooting

### `iverilog not found in PATH`

Install Icarus Verilog:

```bash
sudo apt install -y iverilog
```

### `gtkwave not found in PATH`

Install GTKWave:

```bash
sudo apt install -y gtkwave
```

### No waveform files appear

Check that:

- testbenches were generated
- the RTL simulation suite was run
- `.vcd` files exist under `generated/<module>/waves/`

### LLM service does not start

Check:

- Docker is running
- the selected LLM profile matches your machine
- the `llm` container is healthy

---

## Future improvements

Possible next steps:

- additional simulator backends
- stricter spec schema
- structured validation reports
- improved waveform launch helpers
- stronger repair loops for RTL and testbenches
- coverage-oriented scenario generation
