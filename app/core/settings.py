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
    # Lower = faster local inference (smaller KV cache). Use 8192+ for huge memory prompts.
    ollama_num_ctx: int = 4096
    # Cap generated tokens — lower = faster first token completion; set -1 for no cap (slower).
    ollama_num_predict: int = Field(default=320, ge=-1, le=32_768)

    app_storage_path: Path | None = None
    sqlite_path: Path = BASE_DIR / "storage" / "sqlite" / "assistant.db"
    chroma_path: Path = BASE_DIR / "storage" / "chroma"
    chroma_collection_name: str = "conversation_memory"

    embedding_model: str = "nomic-embed-text"
    # Semantic Chroma hits (fewer = faster retrieval + shorter prompts).
    memory_top_k: int = Field(default=12, ge=1, le=100)
    short_term_message_limit: int = Field(default=6, ge=4, le=80)
    # Extra SQLite substring matches across *all* sessions for this user (exact phrase / keyword catch).
    memory_keyword_supplement: bool = True
    memory_keyword_match_limit: int = Field(default=10, ge=0, le=100)
    # Ignore very short tokens in keyword search (reduces noise).
    memory_keyword_min_word_len: int = Field(default=4, ge=3, le=12)
    # Trim each retrieved memory line in the LLM prompt so huge chats do not blow the context window.
    memory_injected_chars_per_message: int = Field(default=1400, ge=200, le=16_000)
    llm_max_context_messages: int = 6

    whisper_model_size: str = "base"
    stt_device: str = "cpu"
    # False = faster decoding (recommended for interactive voice); True can improve multi-segment coherence.
    stt_condition_on_previous_text: bool = False
    # 1 = greedy decoding (fast); raise to 3–5 for slightly better quality at higher latency.
    stt_beam_size: int = 1
    # faster-whisper: int8 is fastest on CPU; use float16 with STT_DEVICE=cuda when on GPU.
    stt_compute_type: str = "int8"
    stt_temperature: float = 0.0
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 500
    # Second Whisper pass (language=bn) when Bangla profile + noisy auto-detect — improves quality, adds latency.
    stt_bn_recovery_pass: bool = Field(default=True)
    # VITS (end-to-end) tends to sound less “flat” than tacotron2+DDC for English.
    tts_model_name: str = "tts_models/en/ljspeech/vits"
    # >1.0 speeds up playback (ffmpeg atempo). Coqui’s API `speed` does not apply to local VITS/Tacotron.
    tts_playback_speed: float = Field(default=1.25, ge=0.85, le=2.0)
    # When user profile language is Bangla; lazy-loaded on first Bangla TTS. Large download on first use.
    tts_model_name_bn: str = "tts_models/bn/custom/vits-male"
    tts_output_dir: Path = BASE_DIR / "storage" / "audio"
    # False (default): TTS WAVs are written only under temp_dir and deleted after playback grace (no storage/audio growth).
    persist_tts_files: bool = False
    # False (default): voice upload + ffmpeg normalization use temp_dir only (no storage/uploads accumulation).
    persist_voice_uploads: bool = False
    # TTS safety: cap input size, wall-clock bound, reject tiny outputs; delete files older than this.
    tts_max_chars: int = 6000
    tts_timeout_seconds: float = 180.0
    tts_min_output_bytes: int = 256
    # Remove generated WAVs after playback window (conversation text stays in SQLite + Chroma).
    tts_ephemeral: bool = True
    tts_ephemeral_grace_seconds: float = Field(default=120.0, ge=5.0, le=7200.0)
    # Fallback: delete any leftover *.wav older than this (covers crashes / missed schedules).
    tts_retention_hours: int = Field(default=6, ge=1, le=8760)
    # If True, download English + Bangla Coqui weights to cache after startup (background; large download).
    tts_preload_on_startup: bool = True
    # If True, load Whisper + Coqui into RAM after download (cuts first-request latency; uses more memory).
    warm_speech_models_on_startup: bool = True
    # If False, skip loading the Bangla checkpoint at startup (one less Coqui “Using model: vits” block + less RAM;
    # first Bangla reply loads weights on demand). English default TTS still warms when warm_speech_models_on_startup is true.
    warm_bangla_tts_on_startup: bool = True
    # STT wall-clock bound (Whisper can hang on corrupt audio).
    stt_transcribe_timeout_seconds: float = 120.0
    # ffmpeg WebM→WAV normalization (voice uploads); separate from STT inference timeout.
    audio_ffmpeg_timeout_seconds: float = 120.0

    duckduckgo_region: str = "wt-wt"
    duckduckgo_safesearch: str = "moderate"
    duckduckgo_time_limit: str = "m"
    duckduckgo_max_results: int = Field(default=3, ge=1, le=20)
    duckduckgo_request_timeout: float = Field(default=5.0, ge=1.0, le=60.0)
    duckduckgo_retry_attempts: int = 2

    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    temp_dir: Path = BASE_DIR / "storage" / "tmp"
    files_root: Path = BASE_DIR

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tts_staging_dir(self) -> Path:
        """Where Coqui writes WAVs: ``tts_output_dir`` if persisting, else ``temp_dir``."""
        return self.tts_output_dir if self.persist_tts_files else self.temp_dir

    @computed_field  # type: ignore[prop-decorator]
    @property
    def voice_staging_dir(self) -> Path:
        """Scratch dir for voice capture + ffmpeg: ``upload_dir`` if persisting, else ``temp_dir``."""
        return self.upload_dir if self.persist_voice_uploads else self.temp_dir

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
            self.temp_dir,
            self.tts_staging_dir,
            self.voice_staging_dir,
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
