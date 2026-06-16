# StudyApp

A local-first, subject-agnostic RAG + quiz web app. Point it at a folder of documents, chat with them, and generate quizzes — no cloud APIs, no subscriptions, runs entirely on your machine.

## Quick Start

```bash
git clone https://github.com/ViswaaTheMightyPickle/NoteLocalLM
cd NoteLocalLM
./start.sh
```

Open **http://localhost:8080** in your browser.

On first run `start.sh` will:
1. Ask you to choose a model tier (see below)
2. Pull the model automatically
3. Build and start all containers

---

## Model Tiers

Choose once on first run. The choice is saved to `.env` — delete it to change.

| Tier | Model | Size | Notes |
|------|-------|------|-------|
| **Fast** | Llama 3.1 8B | ~4.7 GB | Quick responses, lower VRAM |
| **Balanced** *(default)* | Mistral Nemo 12B Q4 | ~7.1 GB | 4-bit quantised, recommended |
| **Powerful** | Qwen 2.5 14B | ~8.7 GB | Best quality, needs more VRAM |

You can also choose the model tier **per subject** when creating a new subject in the UI.

---

## Platform Support

### Windows / Linux (NVIDIA GPU)
Docker Desktop + NVIDIA Container Toolkit required.

```bash
./start.sh   # auto-detects GPU
```

### macOS (Apple Silicon or Intel)
Ollama runs natively on Mac using Metal GPU acceleration. Docker is used only for the backend and vector DB.

```bash
brew install ollama
./start.sh   # auto-detects macOS, starts Ollama natively
```

### CPU-only (any platform)
`./start.sh` falls back to CPU automatically if no NVIDIA GPU is detected.

---

## Adding Subjects

### Via the UI (recommended)
1. Click **+** next to "Subjects" in the sidebar
2. Enter a name, choose source/answer language and model tier
3. Click **Create Subject** — the folder and config are created automatically
4. You land on the Documents tab — upload PDF, CSV, TXT, or MD files by clicking or dragging
5. Click **Re-index** to process the files
6. Switch to **Study Chat** to start asking questions

### Manually
Create a folder under `data/subjects/` with a `config.yaml`:

```yaml
subject_id: my_subject
display_name: My Subject
source_language: auto        # auto-detect per chunk, or specify e.g. "fr"
output_language: en
input_folder: data/subjects/my_subject/raw
vector_collection: subject_my_subject
chat_model: mistral-nemo:12b-instruct-2407-q4_K_M
quiz_model: mistral-nemo:12b-instruct-2407-q4_K_M
embedding_model: paraphrase-multilingual-mpnet-base-v2
```

Drop files into `data/subjects/my_subject/raw/` and click **Re-index** in the UI.

---

## Supported File Types

| Type | Notes |
|------|-------|
| PDF | Text extracted with PyMuPDF, page numbers and headings preserved |
| CSV | Auto-detects question/answer/explanation/topic columns |
| TXT / MD | Full text ingested as-is |

---

## Architecture

```
Browser → HTML/JS SPA (port 8080)
             ↓ REST API
         FastAPI backend (port 8000)
             ↓              ↓
         Qdrant          SQLite
      (vector search)  (sessions, quiz attempts, weak areas)
             ↓
         Ollama (models: chat, quiz)
         sentence-transformers (multilingual embeddings, CPU)
```

All services run via `docker compose`. Data persists in Docker volumes and `./data/`.

---

## Pages

| Page | What it does |
|------|-------------|
| **Study Chat** | Ask questions; answers grounded in your documents with source citations |
| **Quiz** | Generate multiple-choice, true/false, short-answer, fill-blank, flashcard, or mixed quizzes |
| **Weak Areas** | Tracks which concepts you get wrong most often across quiz attempts |
| **Documents** | Upload files, trigger re-indexing, see what's been ingested |

---

## Manual Docker Commands

The Compose stack is split so each platform loads only what it needs:

- `docker-compose.yml` — base (Qdrant, backend, frontend)
- `docker-compose.ollama.yml` — containerised Ollama + model pull (Linux/Windows)
- `docker-compose.nvidia.yml` — adds NVIDIA GPU to Ollama
- `docker-compose.mac.yml` — points the backend at native host Ollama (macOS)

```bash
# Windows/Linux with NVIDIA GPU
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.nvidia.yml up --build

# Linux/Windows CPU-only
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build

# macOS (after: brew install ollama && ollama serve)
docker compose -f docker-compose.yml -f docker-compose.mac.yml up --build
```

The model to pull/use is controlled by the `STUDYAPP_MODEL` variable (set once in
`.env` by `start.sh`, e.g. `STUDYAPP_MODEL=mistral-nemo:12b-instruct-2407-q4_K_M`).

---

## Development

Backend and frontend run independently. For local dev without Docker:

```bash
pip install -r requirements.txt
QDRANT_URL=http://localhost:6333 OLLAMA_URL=http://localhost:11434 DATA_DIR=./data SQLITE_PATH=./data/app.db \
  uvicorn backend.main:app --reload --port 8000

# Frontend: open frontend/index.html in a browser (no build step, no CDN — fully local)
```

Run the unit tests (no heavy deps required for these):

```bash
python -m pytest tests/
```
