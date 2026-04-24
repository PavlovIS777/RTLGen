#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATED_DIR="$ROOT/generated"

if ! command -v gtkwave >/dev/null 2>&1; then
  echo "gtkwave is not installed in WSL."
  echo "Install it with: sudo apt-get install -y gtkwave"
  exit 1
fi

if [[ ! -d "$GENERATED_DIR" ]]; then
  echo "No generated directory found."
  exit 1
fi

mapfile -t MODULES < <(find "$GENERATED_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [[ ${#MODULES[@]} -eq 0 ]]; then
  echo "No generated modules found."
  exit 1
fi

echo "Select module:"
for i in "${!MODULES[@]}"; do
  name="$(basename "${MODULES[$i]}")"
  printf "  %d) %s\n" "$((i + 1))" "$name"
done

read -rp "Enter number: " module_index
if ! [[ "$module_index" =~ ^[0-9]+$ ]]; then
  echo "Invalid input."
  exit 1
fi
if (( module_index < 1 || module_index > ${#MODULES[@]} )); then
  echo "Out of range."
  exit 1
fi

MODULE_DIR="${MODULES[$((module_index - 1))]}"
WAVES_DIR="$MODULE_DIR/waves"

if [[ ! -d "$WAVES_DIR" ]]; then
  echo "No waves directory found for module $(basename "$MODULE_DIR")."
  exit 1
fi

mapfile -t WAVES < <(find "$WAVES_DIR" -maxdepth 1 -type f -name "*.vcd" | sort)

if [[ ${#WAVES[@]} -eq 0 ]]; then
  echo "No waveform files found in $WAVES_DIR"
  exit 1
fi

echo
echo "Select waveform:"
for i in "${!WAVES[@]}"; do
  name="$(basename "${WAVES[$i]}")"
  printf "  %d) %s\n" "$((i + 1))" "$name"
done

read -rp "Enter number: " wave_index
if ! [[ "$wave_index" =~ ^[0-9]+$ ]]; then
  echo "Invalid input."
  exit 1
fi
if (( wave_index < 1 || wave_index > ${#WAVES[@]} )); then
  echo "Out of range."
  exit 1
fi

WAVE_FILE="${WAVES[$((wave_index - 1))]}"
echo "Opening: $WAVE_FILE"
nohup gtkwave "$WAVE_FILE" >/dev/null 2>&1 &