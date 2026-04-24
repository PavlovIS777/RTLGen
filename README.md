# RTLGEN

RTLGEN — это локальный пайплайн для генерации и валидации RTL-модулей по текстовым спецификациям.

Проект использует локальную LLM и строит полную цепочку разработки:

**spec → Python reference model → test scenarios → golden trace → RTL → отдельные testbench-файлы по сценариям → RTL simulation → waveforms**

---

## Что делает RTLGEN

RTLGEN автоматизирует основные шаги разработки цифрового модуля на основе JSON-спецификации:

- выбирает спецификацию модуля из `specs/`
- генерирует **эталонную Python-модель**
- генерирует **входные сценарии**
- вычисляет **golden trace** по Python-модели
- генерирует **RTL-модуль** на SystemVerilog
- генерирует **отдельный testbench для каждого сценария**
- компилирует и запускает RTL через **Icarus Verilog**
- сохраняет отдельный **waveform (`.vcd`)** для каждого сценария
- открывает waveform-файлы в **GTKWave**

Такой подход делает отладку заметно проще, чем один большой testbench на все случаи сразу.

---

## Основная идея

RTLGEN сначала строит исполнимую эталонную модель на Python, а уже потом использует её как функциональный эталон для проверки RTL.

Общий пайплайн выглядит так:

1. По спецификации генерируется Python reference model.
2. Для этой модели генерируются тестовые сценарии.
3. Python-модель прогоняется по этим сценариям.
4. Результаты сохраняются как **golden trace**.
5. По спецификации и эталонным артефактам генерируется RTL.
6. Для каждого сценария создаётся отдельный SystemVerilog testbench.
7. RTL симулируется и сравнивается с golden trace.
8. Для каждого сценария сохраняется отдельный waveform.

В результате получается и функциональный эталон, и удобный, читаемый процесс валидации.

---

## Возможности

### Генерация артефактов

Для каждого модуля RTLGEN создаёт:

- `<module_name>_reference_model.py`
- `<module_name>.sv`
- `tb_<module_name>__<scenario>.sv` для каждого сценария
- `input_scenarios.json`
- `golden_trace.json`
- логи компиляции и симуляции
- waveform-файлы (`.vcd`)

### Проверка reference model

Перед генерацией RTL RTLGEN валидирует Python reference model на сгенерированных сценариях.

### Проверка RTL

RTLGEN валидирует RTL по схеме:

- один сценарий = один testbench
- один сценарий = одна компиляция
- один сценарий = одна симуляция
- один сценарий = один waveform

Это позволяет быстро понять, какой сценарий проходит, а какой — нет.

### Цикл восстановления testbench

Если сгенерированный testbench не компилируется в `iverilog`, RTLGEN может:

- прочитать лог компилятора
- попросить LLM перегенерировать testbench с учётом ошибки
- повторить попытку компиляции

---

## Структура проекта

```text
RTLGen/
├── configs/
│   ├── 6gb.env
│   └── 12gb.env
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

## Зависимости

### Системные зависимости на Linux

Нужно установить:

- Docker
- Docker Compose
- Icarus Verilog (`iverilog`, `vvp`)
- GTKWave
- Bash

Для Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y git curl iverilog gtkwave
```

Проверка установки:

```bash
iverilog -V
vvp -V
gtkwave --version
docker --version
docker compose version
```

### Зависимости внутри контейнера `app`

Контейнер приложения использует Python 3.11 и устанавливает:

- `requests`
- `PyYAML`
- `pytest`
- `rich`

### LLM backend

Контейнер `llm` поднимает локальный inference server на базе `llama.cpp`.

Нужно выбрать профиль, соответствующий объёму вашей GPU-памяти:

- `configs/6gb.env`
- `configs/12gb.env`

---

## Установка на Linux

### 1. Клонируйте репозиторий

```bash
git clone <your-repo-url> RTLGen
cd RTLGen
```

### 2. Выберите профиль LLM

Используйте один из подготовленных профилей:

- `6gb.env` — для меньшего объёма VRAM
- `12gb.env` — для большего объёма VRAM

### 3. Запустите установщик

Для GPU с 12 GB VRAM:

```bash
bash scripts/install_host.sh 12gb
```

Для GPU с 6 GB VRAM:

```bash
bash scripts/install_host.sh 6gb
```

Установщик:

- создаст `.env` с вашим `UID` и `GID`
- сохранит выбранный профиль
- соберёт Docker-контейнеры
- поднимет сервисы
- подготовит рабочее окружение

---

## Запуск

### Открыть главное меню

```bash
bash scripts/run_menu.sh
```

### Открыть waveforms

```bash
bash scripts/open_wave.sh
```

---

## Типичный рабочий процесс

1. Выбрать spec из `specs/`.
2. Сгенерировать Python reference model.
3. Сгенерировать входные сценарии и golden trace.
4. Проверить reference model.
5. Сгенерировать RTL-модуль.
6. Сгенерировать отдельные testbench-файлы по сценариям.
7. Скомпилировать и прогнать RTL simulation suite.
8. Открыть waveform интересующего сценария.

---

## Формат спецификации

Все спецификации — это JSON-файлы в папке `specs/`.

### Минимальный пример

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

### Что означают поля

#### `module_name`
Имя модуля. Используется:

- как имя RTL-модуля
- как имя папки в `generated/`

#### `description`
Главное текстовое описание поведения модуля. Это основной источник информации для LLM.

#### `inputs`
Список входных сигналов.

#### `outputs`
Список выходных сигналов.

#### `clock`
Имя тактового сигнала.

#### `reset`
Имя сигнала сброса.

#### `width`
Дополнительный параметр модуля. Для других модулей вместо `width` могут использоваться, например:

- `data_width`
- `depth`
- `latency`
- `states`

### Расширенная генерация тестов

В spec можно добавить блок `test_generation`, чтобы управлять качеством тестов:

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

## Что такое golden trace

`golden trace` — это эталонная потактовая трасса поведения модуля.

Она строится так:

- берутся входные сценарии
- они прогоняются через Python reference model
- на каждом такте сохраняются:
  - входы
  - выходы
  - номер такта

Затем RTL сравнивается именно с этим эталоном.

---

## Архитектура testbench-файлов

RTLGEN генерирует **отдельный testbench для каждого сценария**.

Это означает:

- один сценарий = один testbench
- один сценарий = одна компиляция
- один сценарий = одна симуляция
- один сценарий = один waveform

Плюсы такого подхода:

- легко увидеть, какой сценарий упал
- легко открыть нужный `.vcd`
- проще отлаживать и RTL, и testbench

---

## Компиляция и симуляция

Для RTL-проверки используется **Icarus Verilog**:

```bash
iverilog -g2012 -o <out> <rtl> <testbench>
vvp <out>
```

Для каждого сценария RTLGEN сохраняет:

- `compile.log`
- `sim.log`
- waveform `.vcd`

---

## Просмотр waveforms

Waveform-файлы лежат в:

```text
generated/<module>/waves/
```

Например:

```text
generated/counter/waves/reset_to_zero.vcd
generated/counter/waves/increment_when_en.vcd
generated/counter/waves/wraparound_check.vcd
```

### Открыть waveform вручную

```bash
gtkwave generated/counter/waves/reset_to_zero.vcd
```

### Или через helper script

```bash
bash scripts/open_wave.sh
```

Скрипт позволит:

- выбрать модуль
- выбрать нужный `.vcd`
- открыть его в GTKWave

---

## Основные команды

### Установка

```bash
bash scripts/install_host.sh 12gb
```

или

```bash
bash scripts/install_host.sh 6gb
```

### Запуск меню

```bash
bash scripts/run_menu.sh
```

### Открыть waveform

```bash
bash scripts/open_wave.sh
```

---

## Какие файлы можно убрать из проекта

Ниже перечислены только те файлы и каталоги, которые **обычно можно удалить**, если они реально не используются в вашей текущей версии проекта.

### Можно удалить, если они больше не задействованы

- `generated/` — целиком, если нужно очистить все сгенерированные артефакты
- старые тестбенчи и RTL-файлы со старыми именами, если они остались после смены формата
- временные debug-файлы в `generated/<module>/tests/`, если они больше не нужны

### Проверить перед удалением

#### `pyproject.toml`
Если у вас там нет настроек `pytest`, форматирования, линтеров или зависимостей, файл можно удалить. Но сначала проверьте, не использует ли его `pytest`.

#### `src/simulators/xrun_runner.py`
Если вы окончательно перешли на `iverilog` и `xrun` больше не поддерживается, этот файл можно удалить.

#### `scripts/run_xrun_check.py`
Если Cadence backend больше не используется, файл можно удалить.

#### `generated/rtl/`, `generated/tb/`, `generated/python_models/`
Если это старые каталоги от предыдущей структуры проекта, их можно удалить после миграции на новую структуру `generated/<module>/...`.

### Не удалять

Не удаляйте без необходимости:

- `docker-compose.yml`
- `docker/`
- `requirements.docker.txt`
- `scripts/`
- `src/`
- `specs/`
- `configs/`

---

## Troubleshooting

### `iverilog not found in PATH`
Установите Icarus Verilog:

```bash
sudo apt install -y iverilog
```

### `gtkwave not found in PATH`
Установите GTKWave:

```bash
sudo apt install -y gtkwave
```

### Не появляются waveforms

Проверьте, что:

- testbench-файлы были сгенерированы
- RTL suite действительно запускался
- в `generated/<module>/waves/` появились `.vcd`

### LLM не поднимается

Проверьте:

- выбранный профиль `6gb` или `12gb`
- доступность Docker
- что контейнер `llm` действительно стартовал