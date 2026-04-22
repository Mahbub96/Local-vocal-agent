from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:8b"
    ollama_request_timeout: int = 180

    sqlite_path: Path = BASE_DIR / "storage" / "sqlite" / "assistant.db"
    chroma_path: Path = BASE_DIR / "storage" / "chroma"
    chroma_collection_name: str = "conversation_memory"

    embedding_model: str = "nomic-embed-text"
    memory_top_k: int = 5
    short_term_message_limit: int = 10
    llm_max_context_messages: int = 12

    whisper_model_size: str = "base"
    stt_device: str = "cpu"
    tts_model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    tts_output_dir: Path = BASE_DIR / "storage" / "audio"

    duckduckgo_region: str = "wt-wt"
    duckduckgo_safesearch: str = "moderate"
    duckduckgo_time_limit: str = "m"
    duckduckgo_max_results: int = 5

    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    temp_dir: Path = BASE_DIR / "storage" / "tmp"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    def ensure_directories(self) -> None:
        """Create runtime directories needed by the application."""
        required_paths = (
            self.sqlite_path.parent,
            self.chroma_path,
            self.tts_output_dir,
            self.upload_dir,
            self.temp_dir,
        )
        for path in required_paths:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
