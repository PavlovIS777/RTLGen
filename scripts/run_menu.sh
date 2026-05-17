#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$ROOT/configs"
HOST_VENV="$ROOT/.venv"

if [[ $# -ge 1 ]]; then
  if [[ ! -f "$CONFIG_DIR/$1.env" ]]; then
    echo "Unknown profile: $1"
    echo "Expected file: $CONFIG_DIR/$1.env"
    exit 1
  fi
  echo "$1" > "$ROOT/.rtlgen_profile"
fi

if [[ ! -f "$ROOT/.rtlgen_profile" ]]; then
  echo "No RTLGEN profile selected."
  echo "Run: ./scripts/install_host.sh <profile>"
  echo
  echo "Available profiles:"
  find "$CONFIG_DIR" -maxdepth 1 -type f -name '*.env' \
    ! -name 'requirements.docker.txt' \
    -printf '  %f\n' | sed 's/\.env$//' | sort
  exit 1
fi

PROFILE="$(cat "$ROOT/.rtlgen_profile")"
MODEL_ENV="$CONFIG_DIR/${PROFILE}.env"

if [[ ! -f "$MODEL_ENV" ]]; then
  echo "Selected profile does not exist: $PROFILE"
  echo "Expected file: $MODEL_ENV"
  exit 1
fi

set -a
# shellcheck source=/dev/null
. "$MODEL_ENV"
set +a

BACKEND="${RTLGEN_BACKEND:-local}"

if [[ "$BACKEND" == "api" ]]; then
  if [[ ! -x "$HOST_VENV/bin/python" ]]; then
    echo "Host API environment is not installed."
    echo "Run first:"
    echo "  ./scripts/install_host.sh $PROFILE"
    exit 1
  fi
  if [[ -z "${MODEL_API_KEY:-}" ]]; then
    echo "MODEL_API_KEY is required for API profile: $PROFILE"
    echo "Set it in your shell before running:"
    echo "  export MODEL_API_KEY=..."
    exit 1
  fi
  export PYTHONPATH="$ROOT"
  exec "$HOST_VENV/bin/python" "$ROOT/scripts/menu.py"
fi

if [[ "$BACKEND" != "local" ]]; then
  echo "Unsupported RTLGEN_BACKEND=$BACKEND in $MODEL_ENV"
  echo "Supported values: local, api"
  exit 1
fi

printf "UID=%s\nGID=%s\n" "$(id -u)" "$(id -g)" > "$ROOT/.env"

docker compose --env-file "$ROOT/.env" --env-file "$MODEL_ENV" up -d >/dev/null
exec docker compose --env-file "$ROOT/.env" --env-file "$MODEL_ENV" exec app python scripts/menu.py
