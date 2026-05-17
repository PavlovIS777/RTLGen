# RTLGEN

RTLGEN — tests-first пайплайн генерации и верификации RTL-модулей с помощью LLM.

Он строит артефакты по шагам:

**spec → strategy → scenario plan → compact scenarios (segments) → Python reference model → Python validation → coverage refinement (if needed) → golden trace → deterministic testbenches → RTL → RTL validation / repair → post artifacts**

Ключевая идея:
- сначала строится эталонная Python-модель и валидируется на сгенерированных сценариях;
- golden trace строится только из валидированной Python-модели;
- testbench'и детерминированно генерируются из golden trace;
- только после этого генерируется RTL;
- если RTL не проходит тесты, регенерируется **только RTL**, а тесты и testbench'и считаются фиксированными.
- plots / waveform summaries генерируются отдельным post-generation stage.

Пайплайн вдохновлён статьёй **AutoVeriFix: Automatically Correcting Errors and Enhancing Functional Correctness in LLM-Generated Verilog Code** (Yan Tan, Xiangchen Meng, Zijun Jiang, Yangdi Lyu, arXiv:2509.08416).

## Обновлённая структура проекта

```text
rtlgen/
  configs/
    Qwen2.5-Coder-7B.env
    Qwen2.5-Coder-14B.env
  specs/
    counter.json
  generated/
    <module>/
      <module>_reference_model.py
      <module>.sv
      tests/
        strategy.json
        scenarios.json
        golden_trace.json
      tb/
        tb_<module>__<scenario>.sv
      build/
        python_validation/
        <scenario>/
      waves/
        <scenario>.vcd
      stats/
        metrics.json
        events.jsonl
        duration_by_stage.png
        failures_by_iteration.png
        pass_rate_by_iteration.png
  src/
    artifacts/
    llm/
    modules/
    pipeline/
    sim/
    spec/
    stats/
    tb/
    testing/
    ui/
  scripts/
    menu.py
    install_host.sh
    run_menu.sh
    render_stats.py
```

## Что изменено в этой версии

- генерация тестов сделана в **два шага**:
  1. LLM генерирует **strategy / corner cases**;
  2. затем сценарии строятся **по одному**, чтобы снизить вероятность поломки JSON;
- Python model и RTL **не знают о testbench'ах**;
- testbench'и детерминированно создаются только из `golden_trace.json`;
- если не проходит Python validation, регенерируется только Python model;
- если не проходит RTL validation, регенерируется только RTL;
- добавлен сбор статистики и построение графиков.

## Профили моделей

Все модели запускаются через профили в `configs/`. Один и тот же интерфейс используется для локальных GGUF-моделей и удалённых API:

- `RTLGEN_BACKEND=local` — поднять локальный `llm` контейнер через Docker Compose;
- `RTLGEN_BACKEND=api` — использовать OpenAI-compatible API напрямую с host Python.

Для API-профилей используются:

- `MODEL_PROVIDER` (`openai_compatible` по умолчанию)
- `MODEL_API_KEY`
- `MODEL_BASE_URL`
- `MODEL_NAME`
- `MODEL_TOKEN_PARAM` (`auto`, `max_tokens`, `max_completion_tokens`)
- `MODEL_TIMEOUT_SEC`
- `MODEL_MAX_RETRIES`

Выходные token budget'ы настраиваются отдельно по стадиям:
- `MODEL_MAX_TOKENS_STRATEGY`
- `MODEL_MAX_TOKENS_PLAN`
- `MODEL_MAX_TOKENS_SCENARIO`
- `MODEL_MAX_TOKENS_JSON_REPAIR`
- `MODEL_MAX_TOKENS_COVERAGE`
- `MODEL_MAX_TOKENS_PYTHON`
- `MODEL_MAX_TOKENS_RTL`
- `MODEL_MAX_TOKENS_RTL_REPAIR`

Если провайдер вернул `finish_reason=length`, RTLGEN пометит запрос как обрезанный в `stats/llm_requests.csv`; это не считается валидным JSON/code artifact.

Готовые API-профили:
- `Gemini`
- `Gemini-Lite`
- `OpenAI`
- `Qwen-DashScope`

Секреты не хранятся в репозитории. Перед запуском API-профиля задайте ключ через shell:

```bash
export MODEL_API_KEY=...
```

## Как пользоваться

Выбрать профиль:

```bash
./scripts/install_host.sh Gemini
```

Запустить меню:

```bash
./scripts/run_menu.sh
```

Локальный профиль запускается теми же командами:

```bash
./scripts/install_host.sh Qwen2.5-7B
./scripts/run_menu.sh
```

## Спецификация

Минимальный пример:

```json
{
  "module_name": "counter",
  "description": "4-bit synchronous up-counter. When rst_n=0, counter resets to 0. On each cycle, if en=1 and rst_n=1, increment count by 1 modulo 16. If en=0, hold the current value.",
  "inputs": ["rst_n", "en"],
  "outputs": ["count"],
  "clock": "clk",
  "reset": "rst_n",
  "signal_widths": {
    "clk": 1,
    "rst_n": 1,
    "en": 1,
    "count": 4
  },
  "test_generation": {
    "directed_scenarios": 6,
    "random_scenarios": 2,
    "min_cycles_per_scenario": 4,
    "max_cycles_per_scenario": 20,
    "required_behaviors": [
      "reset clears the counter to zero",
      "counter increments only when en=1 and rst_n=1",
      "counter holds value when en=0",
      "counter wraps around from 15 to 0"
    ],
    "special_scenarios": [
      "multiple resets in one scenario",
      "enable toggles every cycle",
      "long increment sequence crossing wraparound",
      "reset immediately after wraparound"
    ]
  }
}
```

## Что делает статистика

RTLGEN сохраняет:
- длительности этапов;
- число итераций repair loop;
- число упавших сценариев по итерациям;
- pass rate по итерациям;
- итоговый JSON-отчёт по пайплайну.

Графики рендерятся единым стилем через `matplotlib`.

## Зависимости

- Python 3.11+
- `requests`
- `PyYAML`
- `rich`
- `matplotlib`
- `iverilog`
- `vvp`
- `gtkwave`

## Важно

В этой архитектуре:
- тесты и testbench'и считаются эталонными;
- repair loop меняет только **модуль**, а не тесты.
- RTLGEN не содержит module-specific behavioral oracles; generated scenario checks are advisory by default.
- Python validation hard-gates generic properties: execution, output interface, width ranges, determinism, coverage.
