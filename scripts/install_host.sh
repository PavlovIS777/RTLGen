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

print_progress() {
  local cache_human="0B"
  local last_log=""

  cache_human="$(compose_cmd exec -T llm sh -lc 'du -sh /models/cache 2>/dev/null | cut -f1' 2>/dev/null || echo 0B)"
  last_log="$(compose_cmd logs --no-color --tail=1 llm 2>/dev/null | tail -n 1 || true)"

  printf "\rDownloading model... cache=%-8s" "$cache_human"
  if [[ -n "$last_log" ]]; then
    printf " | %s" "$last_log"
  fi
}

echo
echo "Waiting for LLM server and model: $MODEL_ALIAS"
echo "This can take a while if the model is not cached yet."
echo

READY=0
for _ in $(seq 1 360); do
  print_progress

  if curl -fsS http://localhost:8080/v1/models >/tmp/rtlgen_models.json 2>/dev/null; then
    if grep -q "\"$MODEL_ALIAS\"" /tmp/rtlgen_models.json; then
      READY=1
      break
    fi
  fi

  sleep 5
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