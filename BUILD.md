# Build guide

## Docker Compose (recommended)

**Default: on-prem AI** via Ollama on the host (no `OPENAI_API_KEY` required). Pre-built `data/faiss/` uses `nomic-embed-text` embeddings.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [Ollama](https://ollama.com/) on the host with:
  - `ollama pull qwen3.6:27b` (or similar 26B-class model)
  - `ollama pull nomic-embed-text`

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000/oil/

`docker/config/config.yaml` points Ollama at `http://host.docker.internal:11434` (Docker Desktop on Windows/macOS). On Linux, configure host gateway access for the `oil` container.

Services:

| Service | Role |
|---------|------|
| `tsurugi` | Tsurugi DB (`ghcr.io/project-tsurugi/tsurugidb:1.11.0`) |
| `db-init` | Loads `data/20260624T221136/setup.sql`, creates admin user |
| `oil` | Web UI + API on port 8000 |

### Environment variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Optional | Only if switching `ai.provider` / `ai.llm_provider` to `openai` for faster cloud LLM |
| `OIL_BOOTSTRAP_PASSWORD` | No | Initial admin password (default: `admin`) |
| `OIL_SESSION_SECRET` | Recommended | Session cookie signing secret |
| `VITE_API_BASE_URL` | Docker only | Leave as `/oil` when using compose |

Tsurugi connection in Docker is configured via `OIL_TSURUGI_*` in `docker-compose.yaml` and `docker/config/config.yaml`.

### RAG index (`data/faiss/`)

The published repository includes a pre-built FAISS index (`nomic-embed-text`, 768 dimensions). To rebuild locally:

```bash
# config/config.yaml: ai.provider: ollama, Ollama running with nomic-embed-text
python tools/build_faiss_index.py
```

Requires `data/20260624T221136/corpus.jsonl` and a running Tsurugi (or `--allow-db-fallback` for summary counts only).

### Cloud LLM (optional)

For evaluation with lower latency, set `OPENAI_API_KEY` and change `docker/config/config.yaml`:

```yaml
ai:
  provider: openai
  llm_provider: openai
```

Rebuild FAISS if you change the embedding provider (`python tools/build_faiss_index.py`).

## Manual build (without Docker)

### Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend)
- Running Tsurugi with `setup.sql` loaded
- Ollama with `qwen3.6:27b` and `nomic-embed-text` (default), or `OPENAI_API_KEY` for cloud mode

### Steps

```bash
cp config/config.yaml.example config/config.yaml
cp .env.example .env
# edit config.yaml (Tsurugi endpoint) if needed

python -m venv wenv && source wenv/bin/activate
pip install ./backend
python tools/build_faiss_index.py

cd frontend && npm ci && npm run build
cd ../backend && python -m app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/oil/

## Configuration

Application settings: `config/config.yaml` (see `config/config.yaml.example`).

Tsurugi endpoint can be overridden with:

- `OIL_TSURUGI_ENDPOINT` (e.g. `tcp://127.0.0.1:12345`)
- `OIL_TSURUGI_USER`
- `OIL_TSURUGI_PASSWORD`

## Tsurugi

oil uses [Tsurugi](https://github.com/project-tsurugi/tsurugidb), an open-source relational database. Docker Compose pulls the official image automatically. For manual setup, see the Tsurugi documentation.

## Database initialization

```bash
python tools/load_setup_sql.py
```

Or load `data/20260624T221136/setup.sql` with your Tsurugi SQL client.
