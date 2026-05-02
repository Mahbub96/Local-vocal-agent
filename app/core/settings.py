from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import json

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]

_log = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Centralized application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Local Vocal Assistant"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    log_level: str = "INFO"

    api_prefix: str = "/api/v1"
    search_provider: str = "google"
    chat_max_input_chars: int = 4000
    # When the semantic memory retriever returns no long-term hits, run DuckDuckGo for the user message.
    assistant_search_if_no_memory: bool = True
    # CSV or JSON array in .env (CORS_ALLOWED_ORIGINS). Stored as str so pydantic-settings
    # does not JSON-decode list fields before validators (which breaks CSV / empty values).
    cors_allowed_origins_raw: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        validation_alias="CORS_ALLOWED_ORIGINS",
        exclude=True,
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_request_timeout: int = 180
    ollama_retry_attempts: int = 3
    ollama_retry_base_delay: float = 0.5
    ollama_temperature: float = 0.2
    ollama_num_ctx: int = 4096
    # Cap generated tokens for snappier local replies; set -1 in .env for no cap (slower).
    ollama_num_predict: int = 512

    app_storage_path: Path | None = None
    sqlite_path: Path = BASE_DIR / "storage" / "sqlite" / "assistant.db"
    chroma_path: Path = BASE_DIR / "storage" / "chroma"
    chroma_collection_name: str = "conversation_memory"

    embedding_model: str = "nomic-embed-text"
    memory_top_k: int = 5
    short_term_message_limit: int = 10
    llm_max_context_messages: int = 12

    whisper_model_size: str = "base"
    stt_device: str = "cpu"
    # 1 = greedy decoding (fast); raise to 3–5 for slightly better quality at higher latency.
    stt_beam_size: int = 1
    # faster-whisper: int8 is fastest on CPU; use float16 with STT_DEVICE=cuda when on GPU.
    stt_compute_type: str = "int8"
    stt_temperature: float = 0.0
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 500
    tts_model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    # When user profile language is Bangla; lazy-loaded on first Bangla TTS. Large download on first use.
    tts_model_name_bn: str = "tts_models/bn/custom/vits-male"
    tts_output_dir: Path = BASE_DIR / "storage" / "audio"
    # TTS safety: cap input size, wall-clock bound, reject tiny outputs; delete files older than this.
    tts_max_chars: int = 6000
    tts_timeout_seconds: float = 180.0
    tts_min_output_bytes: int = 256
    tts_retention_hours: int = 168
    # STT wall-clock bound (Whisper can hang on corrupt audio).
    stt_transcribe_timeout_seconds: float = 120.0

    duckduckgo_region: str = "wt-wt"
    duckduckgo_safesearch: str = "moderate"
    duckduckgo_time_limit: str = "m"
    duckduckgo_max_results: int = 5
    duckduckgo_request_timeout: float = 8.0
    duckduckgo_retry_attempts: int = 2

    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    temp_dir: Path = BASE_DIR / "storage" / "tmp"
    files_root: Path = BASE_DIR

    @property
    def sqlite_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    def _resolve_storage_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        if self.app_storage_path is None:
            return path
        return self.app_storage_path / path

    def ensure_directories(self) -> None:
        """Create runtime directories needed by the application."""
        if self.app_storage_path is not None and not self.app_storage_path.exists():
            env = (self.app_env or "").strip().lower()
            if env in {"development", "dev", "local", "test"}:
                miss = self.app_storage_path
                self.app_storage_path = BASE_DIR / "storage"
                _log.warning(
                    "APP_STORAGE_PATH %s does not exist (e.g. volume not mounted). "
                    "Using %s for relative DB/chroma paths.",
                    miss,
                    self.app_storage_path,
                )
            else:
                raise RuntimeError(
                    f"Configured APP_STORAGE_PATH is not mounted or missing: {self.app_storage_path}"
                )

        self.sqlite_path = self._resolve_storage_path(self.sqlite_path)
        self.chroma_path = self._resolve_storage_path(self.chroma_path)
        self.tts_output_dir = self._resolve_storage_path(self.tts_output_dir)
        self.upload_dir = self._resolve_storage_path(self.upload_dir)
        self.temp_dir = self._resolve_storage_path(self.temp_dir)

        required_paths = (
            self.sqlite_path.parent,
            self.chroma_path,
            self.tts_output_dir,
            self.upload_dir,
            self.temp_dir,
        )
        for path in required_paths:
            path.mkdir(parents=True, exist_ok=True)

    @computed_field
    @property
    def cors_allowed_origins(self) -> list[str]:
        """Origins for CORSMiddleware: CSV, JSON array string, or empty (defaults to local Vite)."""
        raw = (self.cors_allowed_origins_raw or "").strip()
        defaults = ["http://127.0.0.1:5173", "http://localhost:5173"]
        if not raw:
            return defaults
        if raw.startswith("["):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return defaults
            if isinstance(data, list):
                out = [str(x).strip() for x in data if str(x).strip()]
                return out if out else defaults
            return defaults
        return [p.strip() for p in raw.split(",") if p.strip()] or defaults

    @field_validator("search_provider", mode="before")
    @classmethod
    def normalize_search_provider(cls, value: object) -> str:
        provider = str(value or "google").strip().lower()
        if provider not in {"google", "duckduckgo"}:
            raise ValueError("SEARCH_PROVIDER must be either 'google' or 'duckduckgo'")
        return provider


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
