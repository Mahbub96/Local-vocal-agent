from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


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
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_request_timeout: int = 180
    ollama_retry_attempts: int = 3
    ollama_retry_base_delay: float = 0.5
    ollama_temperature: float = 0.2
    ollama_num_ctx: int = 4096

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
    stt_beam_size: int = 5
    stt_temperature: float = 0.0
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 500
    tts_model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    tts_output_dir: Path = BASE_DIR / "storage" / "audio"

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

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: object) -> list[str]:
        """Allow both CSV string and list input for CORS origins."""
        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("CORS_ALLOWED_ORIGINS must be a comma-separated string or list")

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
