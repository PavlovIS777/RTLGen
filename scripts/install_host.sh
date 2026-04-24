#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-12gb}"
LLM_ENV="$ROOT/configs/${PROFILE}.env"

if [[ ! -f "$LLM_ENV" ]]; then
  echo "Unknown profile: $PROFILE"
  echo "Expected file: $LLM_ENV"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is not available."
  exit 1
fi

echo "Preparing RTLGEN environment..."
printf "UID=%s\nGID=%s\n" "$(id -u)" "$(id -g)" > "$ROOT/.env"
echo "$PROFILE" > "$ROOT/.rtlgen_profile"

mkdir -p "$ROOT/generated"

if ! command -v gtkwave >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    echo "Installing GTKWave in WSL/Linux..."
    sudo apt-get update
    sudo apt-get install -y gtkwave
  fi
fi

compose_cmd() {
  docker compose \
    --env-file "$ROOT/.env" \
    --env-file "$LLM_ENV" \
    "$@"
}

echo "Building containers..."
compose_cmd build app llm

echo "Starting services..."
compose_cmd up -d --force-recreate llm app

MODEL_ALIAS="$(
python3 - <<PY
from pathlib import Path
p = Path(r"$LLM_ENV")
alias = ""
for line in p.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("MODEL_ALIAS="):
        alias = line.split("=", 1)[1].strip()
        break
print(alias)
PY
)"

if [[ -z "$MODEL_ALIAS" ]]; then
  echo "MODEL_ALIAS not found in $LLM_ENV"
  exit 1
fi

human_bytes() {
  python3 - "$1" <<'PY'
import sys
n = float(sys.argv[1])
units = ["B", "KB", "MB", "GB", "TB"]
i = 0
while n >= 1024 and i < len(units) - 1:
    n /= 1024.0
    i += 1
print(f"{n:.1f}{units[i]}")
PY
}

draw_bar() {
  python3 - "$1" <<'PY'
import sys
try:
    percent = float(sys.argv[1])
except Exception:
    percent = 0.0
percent = max(0.0, min(100.0, percent))
width = 30
filled = int(round(width * percent / 100.0))
bar = "█" * filled + "░" * (width - filled)
print(bar)
PY
}

progress_from_logs() {
  local logs
  logs="$(compose_cmd logs --no-color --tail=200 llm 2>/dev/null || true)"

  python3 - <<PY
import json
import re
import sys

text = """$logs"""
lines = text.splitlines()

for line in reversed(lines):
    m = re.search(r'(\{.*\})', line)
    if not m:
        continue
    try:
        obj = json.loads(m.group(1))
    except Exception:
        continue

    stage = obj.get("stage")
    if stage == "model_download_progress":
        print(json.dumps({
            "downloaded": obj.get("downloaded_bytes"),
            "total": obj.get("total_bytes"),
            "percent": obj.get("percent"),
        }))
        sys.exit(0)

    if stage == "model_download_complete":
        size = obj.get("size_bytes")
        print(json.dumps({
            "downloaded": size,
            "total": size,
            "percent": 100.0,
        }))
        sys.exit(0)

print("{}")
PY
}

print_progress() {
  local cache_human progress_json percent downloaded total d_h t_h bar

  cache_human="$(compose_cmd exec -T llm sh -lc 'du -sh /models/cache 2>/dev/null | cut -f1' 2>/dev/null || echo 0B)"
  progress_json="$(progress_from_logs || echo '{}')"

  percent="$(python3 - <<PY
import json
obj = json.loads('''$progress_json''')
v = obj.get("percent")
print("" if v is None else v)
PY
)"
  downloaded="$(python3 - <<PY
import json
obj = json.loads('''$progress_json''')
v = obj.get("downloaded")
print("" if v is None else v)
PY
)"
  total="$(python3 - <<PY
import json
obj = json.loads('''$progress_json''')
v = obj.get("total")
print("" if v is None else v)
PY
)"

  if [[ -n "$downloaded" && -n "$total" ]]; then
    d_h="$(human_bytes "$downloaded")"
    t_h="$(human_bytes "$total")"
    bar="$(draw_bar "$percent")"
    printf "\r[%s] %6.2f%%  %8s / %-8s  cache=%-8s" \
      "$bar" "$percent" "$d_h" "$t_h" "$cache_human"
  else
    printf "\r[░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   0.00%%  waiting for progress...  cache=%-8s" \
      "$cache_human"
  fi
}

echo
echo "Waiting for LLM server and model: $MODEL_ALIAS"
echo "This can take a while if the model is not cached yet."
echo

READY=0
for _ in $(seq 1 360); do
  print_progress || true

  if curl -fsS http://localhost:8080/v1/models >/tmp/rtlgen_models.json 2>/dev/null; then
    if grep -q "\"$MODEL_ALIAS\"" /tmp/rtlgen_models.json; then
      READY=1
      break
    fi
  fi

  sleep 3
done

echo

if [[ "$READY" -ne 1 ]]; then
  echo
  echo "LLM server did not become ready in time."
  echo "Check logs with:"
  echo "  docker compose --env-file \"$ROOT/.env\" --env-file \"$LLM_ENV\" logs -f llm"
  exit 1
fi

echo
echo "RTLGEN installation finished."
echo "Selected profile: $PROFILE"
echo "Loaded model alias: $MODEL_ALIAS"
echo "Menu launcher: bash scripts/run_menu.sh"
echo "Waveform launcher: bash scripts/open_wave.sh"