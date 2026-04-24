# RTLGEN

RTLGEN — инструмент для генерации и верификации RTL-модулей с помощью LLM.  
Проект использует многошаговый пайплайн, в котором модель не просто пишет Verilog, а последовательно строит эталонную модель, сценарии проверки, golden trace, RTL и testbench'и, а затем прогоняет симуляцию и сохраняет waveforms.

**Пайплайн:**  
**spec → Python reference model → test scenarios → golden trace → RTL → per-scenario testbenches → simulation → waveforms**

## Основа пайплайна

Архитектура RTLGEN основана на идеях статьи **AutoVeriFix: Automatically Correcting Errors and Enhancing Functional Correctness in LLM-Generated Verilog Code**  
**Yan Tan, Xiangchen Meng, Zijun Jiang, Yangdi Lyu**  
arXiv:2509.08416, 2025  
DOI: `10.48550/arXiv.2509.08416`

В духе AutoVeriFix пайплайн строится вокруг двух ключевых шагов:
- сначала LLM генерирует **Python reference model**;
- затем эта модель используется для генерации **тестов и golden trace**, по которым проверяется RTL.

## Что делает RTLGEN

RTLGEN позволяет:

- выбрать спецификацию модуля из `specs/`;
- сгенерировать **Python reference model**;
- сгенерировать **сценарии тестирования**;
- построить **golden trace**;
- сгенерировать **RTL на SystemVerilog**;
- сгенерировать **отдельный testbench на каждый сценарий**;
- прогнать RTL через **Icarus Verilog**;
- сохранить **`.vcd` waveforms**;
- открыть нужную waveform в **GTKWave**.

## Зависимости

Для запуска на Linux / WSL нужны:

- Docker
- Docker Compose
- Icarus Verilog (`iverilog`, `vvp`)
- GTKWave
- Bash

## Установка

### 1. Установить системные зависимости

Для Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y git curl iverilog gtkwave
```

Проверка:

```bash
iverilog -V
vvp -V
gtkwave --version
docker --version
docker compose version
```

### 2. Клонировать репозиторий

```bash
git clone <your-repo-url> RTLGen
cd RTLGen
```

### 3. Выбрать конфигурацию модели

Папка `configs/` содержит готовые `.env`-профили, названные по моделям.  
Например:

- `configs/Qwen2.5-7B.env`
- `configs/Qwen2.5-14B.env`
- `configs/DeepSeekV2_Lite.env`
- `configs/StarCoder-16B.env`

Можно добавлять и свои собственные `.env`-файлы в `configs/`.

### 4. Установить проект

Пример для профиля `Qwen2.5-14B`:

```bash
bash scripts/install_host.sh Qwen2.5-14B
```

Пример для профиля `Qwen2.5-7B`:

```bash
bash scripts/install_host.sh Qwen2.5-7B
```

## Быстрый старт

### Запуск меню

```bash
bash scripts/run_menu.sh
```

### Просмотр waveforms

```bash
bash scripts/open_wave.sh
```

## Структура спецификации

Минимальный пример:

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

### Основные поля

| Поле | Назначение |
|---|---|
| `module_name` | имя RTL-модуля и имя каталога в `generated/` |
| `description` | описание поведения модуля |
| `inputs` | входные сигналы |
| `outputs` | выходные сигналы |
| `clock` | имя тактового сигнала |
| `reset` | имя сигнала сброса |
| `width` / другие параметры | дополнительные параметры модуля |

## Что создаёт RTLGEN

Для модуля `counter` структура результатов выглядит так:

```text
generated/
  counter/
    counter_reference_model.py
    counter.sv
    tests/
      input_scenarios.json
      golden_trace.json
      test_reference_model.py
    tb/
      tb_counter__reset_to_zero.sv
      tb_counter__increment_when_en.sv
    build/
      reset_to_zero/
        compile.log
        sim.log
        counter.out
    waves/
      reset_to_zero.vcd
      increment_when_en.vcd
```

## Как проходит проверка

1. По spec генерируется Python reference model.
2. По модели строятся сценарии.
3. По сценариям рассчитывается golden trace.
4. По golden trace генерируются testbench'и.
5. Каждый сценарий компилируется и симулируется отдельно.
6. Для каждого сценария создаётся свой `.vcd`.

Такой подход делает ошибки локализуемыми: видно, какой сценарий упал, какой testbench был использован и какую waveform нужно открыть.

## Основные команды

Установка с выбранной моделью:

```bash
bash scripts/install_host.sh Qwen2.5-14B
```

Запуск меню:

```bash
bash scripts/run_menu.sh
```

Открыть waveform:

```bash
bash scripts/open_wave.sh
```

## Troubleshooting

### `iverilog not found in PATH`

```bash
sudo apt install -y iverilog
```

### `gtkwave not found in PATH`

```bash
sudo apt install -y gtkwave
```

### Не появляются `.vcd`

Проверьте, что:
- testbench'и были сгенерированы;
- simulation suite был запущен;
- в `generated/<module>/waves/` появились `.vcd`.

### LLM не поднимается

Проверьте:
- какой профиль выбран в `configs/`;
- что Docker доступен;
- что контейнер `llm` стартовал без ошибок.
