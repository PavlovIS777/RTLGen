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

echo "Building containers..."
docker compose \
  --env-file "$ROOT/.env" \
  --env-file "$LLM_ENV" \
  build app llm

echo "Starting services..."
docker compose \
  --env-file "$ROOT/.env" \
  --env-file "$LLM_ENV" \
  up -d --force-recreate llm app

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

echo
echo "Waiting for LLM server and model: $MODEL_ALIAS"
echo "This can take a while if the model is not cached yet."

READY=0
for _ in $(seq 1 360); do
  if curl -fsS http://localhost:8080/v1/models >/tmp/rtlgen_models.json 2>/dev/null; then
    if grep -q "\"$MODEL_ALIAS\"" /tmp/rtlgen_models.json; then
      READY=1
      break
    fi
  fi
  sleep 5
done

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