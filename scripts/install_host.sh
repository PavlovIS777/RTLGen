#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$ROOT/configs"

print_profiles() {
  echo "Available profiles:"
  find "$CONFIG_DIR" -maxdepth 1 -type f -name '*.env' \
    ! -name 'requirements.docker.txt' \
    -printf '  %f\n' | sed 's/\.env$//' | sort
}

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/install_host.sh <profile>"
  echo
  print_profiles
  exit 1
fi

PROFILE="$1"
MODEL_ENV="$CONFIG_DIR/${PROFILE}.env"

if [[ ! -f "$MODEL_ENV" ]]; then
  echo "Unknown profile: $PROFILE"
  echo "Expected file: $MODEL_ENV"
  echo
  print_profiles
  exit 1
fi

set -a
# shellcheck source=/dev/null
. "$MODEL_ENV"
set +a

BACKEND="${RTLGEN_BACKEND:-local}"
MODEL_NAME="${MODEL_NAME:-${MODEL_ALIAS:-local}}"

printf "UID=%s\nGID=%s\n" "$(id -u)" "$(id -g)" > "$ROOT/.env"
echo "$PROFILE" > "$ROOT/.rtlgen_profile"
mkdir -p "$ROOT/generated"

if [[ "$BACKEND" == "api" ]]; then
  echo "Selected API profile: $PROFILE"
  echo "Provider: ${MODEL_PROVIDER:-openai_compatible}"
  echo "Base URL: ${MODEL_BASE_URL:-<not set>}"
  echo "Model: $MODEL_NAME"
  if [[ -z "${MODEL_API_KEY:-}" ]]; then
    echo
    echo "MODEL_API_KEY is not set."
    echo "Set it before running the menu, for example:"
    echo "  export MODEL_API_KEY=..."
  fi
  echo
  echo "Run menu:"
  echo "  ./scripts/run_menu.sh"
  exit 0
fi

if [[ "$BACKEND" != "local" ]]; then
  echo "Unsupported RTLGEN_BACKEND=$BACKEND in $MODEL_ENV"
  echo "Supported values: local, api"
  exit 1
fi

mkdir -p "$ROOT/models/cache"

compose_cmd() {
  docker compose --env-file "$ROOT/.env" --env-file "$MODEL_ENV" "$@"
}

if [[ "${RTLGEN_REBUILD:-0}" == "1" ]]; then
  echo "Building containers..."
  compose_cmd build app llm
else
  echo "Skipping rebuild. Set RTLGEN_REBUILD=1 to force rebuild."
fi

echo "Starting local model services..."
compose_cmd up -d --force-recreate llm app

MODEL_ALIAS="${MODEL_ALIAS:-$MODEL_NAME}"

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
width = 24
filled = int(round(width * percent / 100.0))
bar = "#" * filled + "." * (width - filled)
print(bar)
PY
}

progress_from_logs() {
  local logs
  logs="$(compose_cmd logs --no-color --tail=200 llm 2>/dev/null || true)"
  PYLOGS="$logs" python3 - <<'PY'
import json, os, re, sys
text = os.environ.get("PYLOGS", "")
for line in reversed(text.splitlines()):
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

  percent="$(JSON_DATA="$progress_json" python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("JSON_DATA", "{}"))
v = obj.get("percent")
print("" if v is None else v)
PY
)"
  downloaded="$(JSON_DATA="$progress_json" python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("JSON_DATA", "{}"))
v = obj.get("downloaded")
print("" if v is None else v)
PY
)"
  total="$(JSON_DATA="$progress_json" python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("JSON_DATA", "{}"))
v = obj.get("total")
print("" if v is None else v)
PY
)"

  if [[ -n "$downloaded" && -n "$total" ]]; then
    d_h="$(human_bytes "$downloaded")"
    t_h="$(human_bytes "$total")"
    bar="$(draw_bar "$percent")"
    printf "\r[%s] %6.2f%%  %8s / %-8s  cache=%-8s" "$bar" "$percent" "$d_h" "$t_h" "$cache_human"
  else
    printf "\r[........................]   waiting for LLM / model  cache=%-8s" "$cache_human"
  fi
}

echo "Waiting for model download / server readiness..."
READY=0
for _ in $(seq 1 360); do
  print_progress || true
  if curl -fsS http://localhost:8080/v1/models >/tmp/rtlgen_models.json 2>/dev/null; then
    if grep -q "\"$MODEL_ALIAS\"" /tmp/rtlgen_models.json; then
      READY=1
      break
    fi
  fi
  sleep 30
done
echo

if [[ "$READY" -ne 1 ]]; then
  echo "Local LLM server did not become ready in time."
  echo "Check logs with:"
  echo "  docker compose --env-file \"$ROOT/.env\" --env-file \"$MODEL_ENV\" logs -f llm"
  exit 1
fi

echo
echo "RTLGEN installation finished."
echo "Selected profile: $PROFILE"
echo "Backend: local"
echo "Menu launcher: ./scripts/run_menu.sh"
