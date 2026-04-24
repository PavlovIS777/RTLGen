#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-12gb}"
LLM_ENV="$ROOT/configs/llm/${PROFILE}.env"

if [[ ! -f "$LLM_ENV" ]]; then
  echo "Unknown profile: $PROFILE"
  echo "Expected file: $LLM_ENV"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH."
  echo "Install Docker Desktop with WSL integration first."
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
    echo "Installing GTKWave in WSL..."
    sudo apt-get update
    sudo apt-get install -y gtkwave
  else
    echo "GTKWave is not installed and sudo is unavailable."
    echo "Install it manually if you want waveform viewing."
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
  up -d

echo
echo "RTLGEN installation finished."
echo "Selected profile: $PROFILE"
echo "Menu launcher: bash scripts/run_menu.sh"
echo "Waveform launcher: bash scripts/open_wave.sh"