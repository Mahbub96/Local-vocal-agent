# Local Vocal Assistant

Local full-stack AI assistant with:

- FastAPI backend (`app/`)
- React + Vite frontend (`frontend/`)
- SQLite + Chroma memory layers
- Ollama LLM integration
- Voice pipeline (STT/TTS)
- Internet search support (default: Google News RSS, fallback: DuckDuckGo)

## Quick Start (recommended)

From project root:

```bash
./start.sh
```

This script:

- restarts backend on `127.0.0.1:8000`
- restarts frontend on `127.0.0.1:5173`
- handles Ctrl+C cleanup for started processes

## Manual Setup

1. Create and activate virtual environment.
2. Install backend dependencies:

```bash
pip install -r requirements.txt
```

3. Configure env:

```bash
cp .env.example .env
```

4. Install frontend dependencies:

```bash
cd frontend && npm install
```

## Manual Run

Backend:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## Core API Endpoints

Primary route prefix: `/api/v1`

- `POST /api/v1/chat`
- `POST /api/v1/voice-chat`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}/messages`
- `GET /api/v1/me`
- `PUT /api/v1/me`
- `GET /api/v1/system/metrics`
- `GET /api/v1/system/status`

## Search Provider

Configured in env:

- `SEARCH_PROVIDER=google` (default)
- `SEARCH_PROVIDER=duckduckgo`

Behavior:

- Google mode uses Google News RSS query results.
- Prothom Alo queries automatically use Prothom Alo RSS.
- If provider returns no results, backend falls back to alternative web source.

## CORS

Frontend-backend integration expects:

- `CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173`

Configured in `app/main.py` via FastAPI `CORSMiddleware`.

## Notes

- Storage directories are created automatically by settings bootstrap.
- `/health` is available for backend health check.
- Root `/` is not a required API endpoint (use `/api/v1/*` routes).
