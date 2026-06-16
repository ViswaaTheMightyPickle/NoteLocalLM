# StudyApp

StudyApp is a document-based study assistant. It indexes subject materials, stores searchable chunks in Qdrant, uses Ollama-hosted language models for answers and quiz generation, and exposes the experience through a FastAPI backend and Streamlit frontend.

## Features

- Subject-based document ingestion from PDF, CSV, TXT, and Markdown files.
- Retrieval-augmented study chat with source previews.
- Quiz generation with multiple question types and answer tracking.
- Weak-area reporting based on quiz attempts.
- Docker Compose setup for the backend, frontend, Qdrant, and Ollama.

## Repository Layout

```text
backend/                  FastAPI application and backend modules
  api/                    HTTP route handlers
  core/                   configuration, database, and models
  ingestion/              document parsing, chunking, and indexing
  llm/                    Ollama client and prompts
  quiz/                   quiz generation and attempt tracking
  retrieval/              embeddings and Qdrant retrieval
frontend/                 Streamlit app
config/app_config.yaml    default application configuration
data/subjects/            subject configuration and source documents
docker-compose.yml        full local service stack
requirements.txt          backend Python dependencies
requirements.frontend.txt frontend Python dependencies
```

## Prerequisites

- Docker and Docker Compose for the recommended setup.
- Python 3.12 if running services directly.
- Enough disk space for Ollama and Hugging Face model caches.
- Optional NVIDIA GPU support for the Ollama service as configured in `docker-compose.yml`.

## Quick Start With Docker

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Add source files for the example subject:

   ```bash
   mkdir -p data/subjects/example_subject/raw
   ```

   Put PDF, CSV, TXT, or Markdown files in `data/subjects/example_subject/raw/`.

3. Start the stack:

   ```bash
   docker compose up --build
   ```

   The first run pulls the configured Ollama model, `mistral-nemo:12b`, and downloads the embedding model cache. This can take a while.

4. Open the app:

   - Frontend: <http://localhost:8501>
   - Backend health check: <http://localhost:8000/health>
   - Backend OpenAPI docs: <http://localhost:8000/docs>

5. In the Streamlit app, open the Documents page and click **Re-index Subject** to ingest files.

## Subject Configuration

Each subject lives under `data/subjects/<subject_id>/` and needs a `config.yaml`.

Example:

```yaml
subject_id: example_subject
display_name: Example Subject
source_language: auto
output_language: en
input_folder: data/subjects/example_subject/raw
vector_collection: subject_example_subject
chat_model: mistral-nemo:12b
quiz_model: mistral-nemo:12b
embedding_model: paraphrase-multilingual-mpnet-base-v2
```

When running in Docker, `DATA_DIR` is `/data`, and the local `data/` directory is mounted there. Relative `input_folder` values are resolved under the configured data directory.

## Local Development

Docker Compose is the simplest way to run dependencies. If you run the backend or frontend outside Docker, set local URLs in your environment:

```bash
export QDRANT_URL=http://localhost:6333
export OLLAMA_URL=http://localhost:11434
export SQLITE_PATH=data/app.db
export DATA_DIR=data
export BACKEND_URL=http://localhost:8000
```

Install backend dependencies and start FastAPI:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Install frontend dependencies and start Streamlit:

```bash
pip install -r requirements.frontend.txt
streamlit run frontend/app.py
```

## API Overview

- `GET /health` returns backend health status.
- `GET /subjects` lists configured subjects.
- `POST /subjects/{subject_id}/ingest` starts background ingestion.
- `GET /subjects/{subject_id}/ingest/status` returns ingestion status.
- `POST /chat` answers a question using indexed subject materials.
- `POST /quiz/generate` generates quiz items.
- `POST /quiz/attempt` records and checks a quiz answer.
- `GET /weak-areas/{subject_id}` returns weak concepts from quiz history.
- `GET /sources/{chunk_id}` returns a stored source chunk.

## Data And Generated Files

Runtime data is written under `data/`, including the SQLite database when using the default Docker configuration. Qdrant, Ollama, and Hugging Face caches are persisted in Docker volumes.

Do not commit private study materials, secrets, model caches, or generated databases unless they are intentionally shared fixtures.

## Testing

No automated test suite is currently included. When adding reusable logic, add tests under `tests/` and run them from the repository root, for example:

```bash
python -m pytest
```
