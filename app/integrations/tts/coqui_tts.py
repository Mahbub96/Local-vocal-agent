from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import threading
from pathlib import Path
from uuid import uuid4

from TTS.api import TTS
from TTS.utils.generic_utils import get_user_data_dir

from app.core.settings import BASE_DIR, get_settings
from app.integrations.tts.tts_text import prepare_tts_text

logger = logging.getLogger(__name__)
settings = get_settings()

# Serialize Coqui GPU/CPU work — concurrent calls can OOM or corrupt output.
_tts_model_lock = threading.Lock()


def _language_name_for_coqui_synth(synthesizer: object) -> str:
    """Pick a language code when the checkpoint has multiple languages (bypasses broken TTS API checks)."""
    tts_model = getattr(synthesizer, "tts_model", None)
    if tts_model is None:
        return ""
    lm = getattr(tts_model, "language_manager", None)
    if lm is None or not getattr(lm, "name_to_id", None):
        return ""
    name_to_id = lm.name_to_id
    if len(name_to_id) <= 1:
        return ""
    if "en" in name_to_id:
        return "en"
    return next(iter(name_to_id.keys()))


def _coqui_model_cache_dir(model_name: str) -> Path:
    """Coqui stores under get_user_data_dir('tts') with `/` replaced by ``--``."""
    return Path(get_user_data_dir("tts")) / model_name.replace("/", "--")


def resolve_local_coqui_paths(model_spec: str) -> tuple[Path, Path] | None:
    """
    If ``model_spec`` is a directory under the project (or absolute) containing
    ``config.json`` and a checkpoint ``*.pth``, return ``(checkpoint, config)`` for
    ``TTS(model_path=..., config_path=...)``.

    Custom bundles like ``tts_models/bn/custom/vits-male`` are not Coqui Hub names;
    loading via ``model_name=`` triggers a broken download. This path fixes that.
    """
    spec = (model_spec or "").strip()
    if not spec:
        return None
    candidates: list[Path] = []
    p = Path(spec)
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(BASE_DIR / spec)
        candidates.append(Path.cwd() / spec)
        candidates.append(_coqui_model_cache_dir(spec))
    for root in candidates:
        if not root.is_dir():
            continue
        cfg = root / "config.json"
        if not cfg.is_file():
            continue
        ckpt: Path | None = None
        for name in ("model_file.pth", "model_file.pth.tar", "model.pth", "best_model.pth"):
            cand = root / name
            if cand.is_file():
                ckpt = cand
                break
        if ckpt is None:
            for f in sorted(root.glob("*.pth")):
                ckpt = f
                break
        if ckpt is not None:
            return (ckpt, cfg)
        logger.warning(
            "Local TTS directory %s has config.json but no .pth checkpoint; skipping",
            root,
        )
    return None


def _clear_coqui_model_cache(model_name: str) -> None:
    path = _coqui_model_cache_dir(model_name)
    if path.is_dir():
        logger.warning("Removing incomplete Coqui TTS cache: %s", path)
        shutil.rmtree(path, ignore_errors=True)


# Same filenames Coqui ModelManager._find_files expects (non-XTTS/tortoise/bark).
_COQUI_CHECKPOINT_FILES = frozenset({"model_file.pth", "model_file.pth.tar", "model.pth"})


def _apply_playback_speed_wav(path: Path, speed: float) -> bool:
    """Rewrite WAV in place with faster/slower playback using ffmpeg atempo. No-op if speed≈1 or ffmpeg missing."""
    if abs(speed - 1.0) < 0.02:
        return True
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not on PATH; TTS playback speed left at 1.0")
        return True
    tempo = max(0.5, min(2.0, float(speed)))
    tmp = path.with_name(f"{path.stem}.speed{path.suffix}")
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-filter:a",
        f"atempo={tempo}",
        "-c:a",
        "pcm_s16le",
        str(tmp),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=min(120.0, float(settings.tts_timeout_seconds)),
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as exc:
        logger.warning("ffmpeg atempo failed for %s (%s); keeping original wav", path.name, exc)
        tmp.unlink(missing_ok=True)
        return True
    try:
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Could not replace TTS wav after atempo: %s", exc)
        tmp.unlink(missing_ok=True)
        return False
    return True


def _coqui_cache_loadable(model_name: str) -> bool:
    """True if no cache dir, or dir already has a checkpoint + config.json (ready to load)."""
    root = _coqui_model_cache_dir(model_name)
    if not root.is_dir():
        return True
    try:
        names = {p.name for p in root.iterdir() if p.is_file()}
    except OSError:
        return False
    has_ckpt = bool(names & _COQUI_CHECKPOINT_FILES)
    has_cfg = "config.json" in names
    return has_ckpt and has_cfg


class CoquiTTSService:
    """Async wrapper for local Coqui TTS synthesis (defensive: timeout, sanitize, lock)."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.tts_model_name
        self._tts: TTS | None = None

    def _get_model(self) -> TTS:
        if self._tts is None:
            local = resolve_local_coqui_paths(self.model_name)
            if local is not None:
                ckpt, cfg = local
                try:
                    self._tts = TTS(
                        model_path=str(ckpt),
                        config_path=str(cfg),
                        progress_bar=False,
                    )
                    return self._tts
                except Exception:
                    logger.exception(
                        "Coqui TTS failed to load local checkpoint %s (config %s)",
                        ckpt,
                        cfg,
                    )
                    raise
            if not _coqui_cache_loadable(self.model_name):
                logger.warning(
                    "Coqui TTS cache exists but has no checkpoint/config for %s; clearing before download.",
                    self.model_name,
                )
                _clear_coqui_model_cache(self.model_name)
            try:
                self._tts = TTS(model_name=self.model_name, progress_bar=False)
            except ValueError as exc:
                # Common after interrupted download: folder exists but no model_file.pth/config.json.
                msg = str(exc)
                if "Model file not found" in msg or "Config file not found" in msg:
                    logger.warning(
                        "Coqui TTS cache incomplete for %s (%s). Clearing cache and re-downloading.",
                        self.model_name,
                        msg,
                    )
                    _clear_coqui_model_cache(self.model_name)
                    try:
                        self._tts = TTS(model_name=self.model_name, progress_bar=False)
                    except Exception as exc2:
                        logger.exception(
                            "Coqui TTS failed to load after cache clear for %s",
                            self.model_name,
                        )
                        raise exc2 from exc
                else:
                    raise
        return self._tts

    def build_output_path(self, *, file_stem: str | None = None) -> Path:
        return settings.tts_staging_dir / f"{file_stem or uuid4().hex}.wav"

    @staticmethod
    def _unlink_quiet(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    async def synthesize_to_file(
        self,
        text: str,
        *,
        file_stem: str | None = None,
        playback_speed: float | None = None,
    ) -> Path | None:
        """
        Write assistant speech to WAV under ``tts_staging_dir`` (temp or persistent).
        Returns ``None`` on empty input, timeout, or synthesis failure (chat still succeeds).
        """
        prepared = prepare_tts_text(text, settings.tts_max_chars)
        if not prepared:
            logger.warning("TTS skipped: empty or invalid text after preparation")
            return None

        output_path = self.build_output_path(file_stem=file_stem)
        self._unlink_quiet(output_path)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, prepared, output_path),
                timeout=settings.tts_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("TTS timed out after %s s (output=%s)", settings.tts_timeout_seconds, output_path.name)
            self._unlink_quiet(output_path)
            return None
        except RuntimeError as exc:
            err = str(exc).lower()
            if "kernel size" in err or "input size" in err:
                logger.warning(
                    "TTS input sequence too short for model (output=%s): %s",
                    output_path.name,
                    exc,
                )
            else:
                logger.exception("TTS synthesis RuntimeError (output=%s)", output_path.name)
            self._unlink_quiet(output_path)
            return None
        except Exception:
            logger.exception("TTS synthesis raised (output=%s)", output_path.name)
            self._unlink_quiet(output_path)
            return None

        try:
            if not output_path.is_file():
                logger.error("TTS missing output file: %s", output_path)
                return None
            speed = float(playback_speed) if playback_speed is not None else float(settings.tts_playback_speed)
            _apply_playback_speed_wav(output_path, speed)
            size = output_path.stat().st_size
            if size < settings.tts_min_output_bytes:
                logger.error("TTS output too small (%s bytes), removing: %s", size, output_path)
                self._unlink_quiet(output_path)
                return None
        except OSError as exc:
            logger.error("TTS cannot stat output: %s — %s", output_path, exc)
            self._unlink_quiet(output_path)
            return None

        return output_path

    def warm_load(self) -> None:
        """Load checkpoint into RAM (startup); serialised with synthesis via ``_tts_model_lock``."""
        with _tts_model_lock:
            self._get_model()

    def _synthesize_sync(self, text: str, output_path: Path) -> None:
        with _tts_model_lock:
            model = self._get_model()
            syn = model.synthesizer
            if syn is None:
                raise RuntimeError("Coqui TTS synthesizer is not initialized")
            # Avoid TTS.tts_to_file → _check_arguments → is_multi_lingual: some PyTorch/nn.Module
            # stacks fail to resolve that property and raise AttributeError (voice would be silent).
            lang = _language_name_for_coqui_synth(syn)
            wav = syn.tts(
                text=text,
                speaker_name="",
                language_name=lang,
                split_sentences=True,
            )
            syn.save_wav(wav=wav, path=str(output_path), pipe_out=None)


_default_coqui: CoquiTTSService | None = None
_bn_coqui: CoquiTTSService | None = None
_bn_coqui_model_name: str | None = None
_coqui_default_lock = threading.Lock()
_bn_coqui_lock = threading.Lock()


def get_default_coqui_tts() -> CoquiTTSService:
    """One English (default) Coqui stack per process — avoids full reload every request."""
    global _default_coqui
    if _default_coqui is None:
        with _coqui_default_lock:
            if _default_coqui is None:
                _default_coqui = CoquiTTSService()
    return _default_coqui


def get_bangla_coqui_tts(model_name: str) -> CoquiTTSService:
    """Shared Bangla TTS instance for the configured checkpoint name."""
    global _bn_coqui, _bn_coqui_model_name
    name = model_name.strip()
    if not name:
        return get_default_coqui_tts()
    with _bn_coqui_lock:
        if _bn_coqui is None or _bn_coqui_model_name != name:
            _bn_coqui = CoquiTTSService(model_name=name)
            _bn_coqui_model_name = name
        return _bn_coqui
