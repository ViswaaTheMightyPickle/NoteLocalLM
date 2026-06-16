#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s)"
COMPOSE_FILES="-f docker-compose.yml"

if [[ "$OS" == "Darwin" ]]; then
  echo "==> macOS detected — using native Ollama on host"
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.mac.yml"

  if ! command -v ollama &>/dev/null; then
    echo ""
    echo "ERROR: Ollama is not installed."
    echo "  Install it with:  brew install ollama"
    echo "  Or download from: https://ollama.com"
    exit 1
  fi

  if ! ollama list &>/dev/null; then
    echo "==> Starting Ollama in the background…"
    ollama serve &>/tmp/ollama.log &
    sleep 3
  fi

  if ! ollama list | grep -q "mistral-nemo"; then
    echo "==> Pulling mistral-nemo:12b (this takes a while on first run)…"
    ollama pull mistral-nemo:12b
  fi

else
  if command -v nvidia-smi &>/dev/null 2>&1; then
    echo "==> NVIDIA GPU detected — enabling GPU passthrough"
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.nvidia.yml"
  else
    echo "==> No NVIDIA GPU detected — running Ollama on CPU"
  fi
fi

echo "==> Starting StudyApp…"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up --build "$@"
