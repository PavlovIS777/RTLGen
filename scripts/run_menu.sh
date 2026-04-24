#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT/.rtlgen_profile" ]]; then
  echo "Profile is not configured."
  echo "Run: bash scripts/install_host.sh 12gb"
  exit 1
fi

PROFILE="$(cat "$ROOT/.rtlgen_profile")"
LLM_ENV="$ROOT/configs/llm/${PROFILE}.env"

if [[ ! -f "$ROOT/.env" ]]; then
  printf "UID=%s\nGID=%s\n" "$(id -u)" "$(id -g)" > "$ROOT/.env"
fi

docker compose \
  --env-file "$ROOT/.env" \
  --env-file "$LLM_ENV" \
  up -d

exec docker compose \
  --env-file "$ROOT/.env" \
  --env-file "$LLM_ENV" \
  exec app python scripts/menu.py