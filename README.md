# RTLGEN

RTLGEN — инструмент для локальной генерации и проверки RTL-модулей по текстовой спецификации.

Основной поток выглядит так:

**spec → reference model → сценарии → golden trace → RTL → testbench’и → simulation → waveforms**

Где:
- **reference model** — эталонная Python-модель поведения;
- **golden trace** — эталонные потактовые выходы этой модели;
- **testbench’и** — отдельные SystemVerilog testbench-файлы, по одному на сценарий;
- **waveforms** — `.vcd`-файлы для просмотра сигналов.

---

## Что умеет RTLGEN

RTLGEN позволяет:

- выбрать спецификацию из папки `specs/`;
- сгенерировать эталонную Python-модель;
- сгенерировать набор сценариев проверки;
- рассчитать golden trace;
- сгенерировать RTL на SystemVerilog;
- сгенерировать отдельный testbench для каждого сценария;
- прогнать RTL через `iverilog`;
- сохранить `.vcd` waveforms по каждому сценарию;
- открыть нужную waveform в GTKWave.

---

## Зависимости

### На Linux / WSL

Нужны:

- Docker
- Docker Compose
- Icarus Verilog (`iverilog`, `vvp`)
- GTKWave
- Bash

### Внутри контейнера

Контейнер `app` использует Python 3.11 и основные пакеты:

- `requests`
- `PyYAML`
- `pytest`
- `rich`

Контейнер `llm` поднимает локальный inference server на основе `llama.cpp`.

---

## Установка

### 1. Установите системные зависимости

Для Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y git curl iverilog gtkwave
```

Проверьте:

```bash
iverilog -V
vvp -V
gtkwave --version
docker --version
docker compose version
```

### 2. Клонируйте проект

```bash
git clone <your-repo-url> RTLGen
cd RTLGen
```

### 3. Выберите профиль модели

В проекте есть готовые пресеты:

- `configs/6gb.env`
- `configs/12gb.env`

Можно добавить и свои собственные `.env`-профили в папку `configs/`, если нужен другой размер модели, другой контекст или другая конфигурация inference.

### 4. Установите и соберите проект

Для 12 GB VRAM:

```bash
bash scripts/install_host.sh 12gb
```

Для 6 GB VRAM:

```bash
bash scripts/install_host.sh 6gb
```

---

## Быстрый старт

### Запуск меню

```bash
bash scripts/run_menu.sh
```

### Просмотр waveforms

```bash
bash scripts/open_wave.sh
```

---

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

### Поля спецификации

| Поле | Назначение |
|---|---|
| `module_name` | имя модуля и имя папки в `generated/` |
| `description` | описание поведения модуля |
| `inputs` | список входных сигналов |
| `outputs` | список выходных сигналов |
| `clock` | имя тактового сигнала |
| `reset` | имя сигнала сброса |
| `width` / другие параметры | дополнительные параметры модуля |

### Настройка генерации тестов

Можно добавить блок `test_generation`:

```json
{
  "test_generation": {
    "directed_scenarios": 8,
    "random_scenarios": 12,
    "min_cycles_per_scenario": 4,
    "max_cycles_per_scenario": 24,
    "include_reset_scenarios": true,
    "include_corner_cases": true,
    "include_long_run": true
  }
}
```

---

## Что создаёт RTLGEN

Для модуля `counter` структура будет примерно такой:

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

---

## Как проходит проверка

1. По spec строится reference model.
2. По модели строятся сценарии.
3. По сценариям считается golden trace.
4. На основе golden trace генерируются testbench’и.
5. Каждый сценарий компилируется и запускается отдельно.
6. Для каждого сценария создаётся свой `.vcd`.

Это позволяет быстро понять:
- какой сценарий прошёл;
- какой сценарий упал;
- какую waveform нужно открыть.

---

## Основные команды

Установка:

```bash
bash scripts/install_host.sh 12gb
```

Запуск меню:

```bash
bash scripts/run_menu.sh
```

Открыть waveforms:

```bash
bash scripts/open_wave.sh
```

---

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
- testbench’и сгенерированы;
- simulation suite был запущен;
- в `generated/<module>/waves/` появились файлы.

### LLM не поднимается

Проверьте:
- выбранный профиль в `configs/`;
- доступность Docker;
- что контейнер `llm` успешно стартовал.