# Local Vocal Assistant Backend

Production-oriented local AI assistant backend built with FastAPI, Ollama, ChromaDB, SQLite, LangChain, Whisper, and Coqui TTS.

## Features

- Persistent conversation history in SQLite
- Semantic memory retrieval with ChromaDB
- Hybrid short-term and long-term memory
- Local Qwen chat generation through Ollama
- Internet search via DuckDuckGo for real-time questions
- Voice input using local Whisper
- Voice output using Coqui TTS

## Endpoints

- `POST /chat`
- `POST /voice-chat`
- `POST /memory/search`

The same routes are also exposed under `POST /api/v1/...`.

## Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file:

```bash
cp .env.example .env
```

4. Make sure local services and models are available:

- Ollama running locally on `http://127.0.0.1:11434`
- Qwen model pulled in Ollama
- Embedding model pulled in Ollama
- Whisper runtime dependencies installed
- Coqui TTS runtime dependencies installed

## Run

```bash
uvicorn app.main:app --reload
```

## Notes

- SQLite and Chroma storage directories are created automatically on startup.
- Voice responses are synthesized asynchronously and returned as an audio file path.
