#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s)"
COMPOSE_FILES="-f docker-compose.yml"
ENV_FILE=".env"

# ── Model selection ───────────────────────────────────────────────────────────
# Skip if already set in .env
if grep -qs "^STUDYAPP_MODEL=" "$ENV_FILE" 2>/dev/null; then
  STUDYAPP_MODEL="$(grep "^STUDYAPP_MODEL=" "$ENV_FILE" | cut -d= -f2-)"
  echo "==> Using saved model: $STUDYAPP_MODEL"
  echo "    (delete $ENV_FILE to change)"
else
  echo ""
  echo "┌─────────────────────────────────────────────────────────┐"
  echo "│               StudyApp — First-time Setup               │"
  echo "├─────────────────────────────────────────────────────────┤"
  echo "│  Choose a model tier:                                   │"
  echo "│                                                         │"
  echo "│  1) Fast      · Llama 3.1 8B         (~4.7 GB)         │"
  echo "│               Lower VRAM, snappier responses            │"
  echo "│                                                         │"
  echo "│  2) Balanced  · Mistral Nemo 12B Q4  (~7.1 GB)  [rec] │"
  echo "│               4-bit quant, good quality & speed         │"
  echo "│                                                         │"
  echo "│  3) Powerful  · Qwen 2.5 14B         (~8.7 GB)         │"
  echo "│               Best quality, needs more VRAM             │"
  echo "└─────────────────────────────────────────────────────────┘"
  echo ""
  read -rp "  Enter choice [1/2/3] (default 2): " CHOICE
  CHOICE="${CHOICE:-2}"

  case "$CHOICE" in
    1) STUDYAPP_MODEL="llama3.1:8b" ;;
    3) STUDYAPP_MODEL="qwen2.5:14b" ;;
    *) STUDYAPP_MODEL="mistral-nemo:12b-instruct-q4_K_M" ;;
  esac

  echo "STUDYAPP_MODEL=$STUDYAPP_MODEL" >> "$ENV_FILE"
  echo ""
  echo "==> Model selected: $STUDYAPP_MODEL (saved to $ENV_FILE)"
fi

export STUDYAPP_MODEL

# ── Platform detection ────────────────────────────────────────────────────────
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

  # Start ollama serve if not already running
  if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "==> Starting Ollama in the background…"
    ollama serve >/tmp/ollama.log 2>&1 &
    for i in $(seq 1 10); do
      sleep 2
      curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
      echo "   waiting for Ollama… ($i/10)"
    done
  fi

  if ! ollama list 2>/dev/null | grep -qF "${STUDYAPP_MODEL%%:*}"; then
    echo "==> Pulling $STUDYAPP_MODEL (this may take a while)…"
    OLLAMA_HOST=http://localhost:11434 ollama pull "$STUDYAPP_MODEL"
  fi

else
  if command -v nvidia-smi &>/dev/null 2>&1; then
    echo "==> NVIDIA GPU detected — enabling GPU passthrough"
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.nvidia.yml"
  else
    echo "==> No NVIDIA GPU detected — Ollama will run on CPU"
  fi
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo "==> Starting StudyApp…"
echo "    Open http://localhost:8080 in your browser"
echo ""
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up --build "$@"
