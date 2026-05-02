from __future__ import annotations

import asyncio
import contextlib
import difflib
import json
import re
from pathlib import Path
from typing import AsyncIterator, Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio_prepare import (
    AudioNormalizeError,
    FFmpegUnavailableError,
    prepare_for_whisper,
)
from app.core.settings import get_settings
from app.integrations.stt.whisper_stt import STTInputError, get_whisper_stt
from app.integrations.tts.coqui_tts import get_bangla_coqui_tts, get_default_coqui_tts
from app.integrations.tts.tts_cleanup import schedule_ephemeral_tts_delete
from app.integrations.tts.tts_locale import contains_bengali_script, prefers_bangla_tts
from app.schemas.chat import ChatResponse
from app.schemas.voice import VoiceChatResponse
from app.services.chat_service import ChatService
from app.services.voice_listen_intent import should_drop_voice_for_wake_gate
from app.services.voice_status_service import voice_status_service


settings = get_settings()

# Streaming voice TTS: speak partial replies before the LLM finishes (sentence / soft-max splits).
_TTS_STREAM_MIN_CHARS = 28
_TTS_STREAM_MAX_CHARS = 220

# One in-flight voice pipeline per user id so status + DB updates stay ordered (no overlapping replies).
_voice_chat_locks: dict[str, asyncio.Lock] = {}


def _voice_chat_lock_for(user_id: str | None) -> asyncio.Lock:
    key = (user_id or "").strip() or "__anon__"
    if key not in _voice_chat_locks:
        _voice_chat_locks[key] = asyncio.Lock()
    return _voice_chat_locks[key]


def _sse_token_delta(chunk: str) -> str | None:
    """Extract incremental text from ``event: token`` SSE chunk."""
    if not chunk.startswith("event: token"):
        return None
    for line in chunk.splitlines():
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
        t = obj.get("t")
        return t if isinstance(t, str) else None
    return None


def _take_spoken_chunk(buffer: str) -> tuple[str, str] | None:
    """Return ``(spoken_prefix, remainder)`` when buffer crosses a speak boundary."""
    if len(buffer) < _TTS_STREAM_MIN_CHARS:
        return None
    m = re.search(r"[.!?।॥]+\s*", buffer)
    if m is not None and m.end() >= _TTS_STREAM_MIN_CHARS:
        spoken = buffer[: m.end()].strip()
        rest = buffer[m.end() :].lstrip()
        if spoken:
            return spoken, rest
    nl = buffer.find("\n")
    if nl != -1 and nl >= _TTS_STREAM_MIN_CHARS:
        spoken = buffer[:nl].strip()
        rest = buffer[nl + 1 :].lstrip()
        if spoken:
            return spoken, rest
    if len(buffer) >= _TTS_STREAM_MAX_CHARS:
        cut = buffer[:_TTS_STREAM_MAX_CHARS]
        sp = cut.rfind(" ")
        if sp >= _TTS_STREAM_MIN_CHARS:
            spoken = buffer[:sp].strip()
            rest = buffer[sp:].lstrip()
            if spoken:
                return spoken, rest
    return None


def _voice_prefers_bangla(profile: dict[str, object]) -> bool:
    lang = profile.get("language")
    return isinstance(lang, str) and prefers_bangla_tts(lang)


def _contains_arabic_script(text: str) -> bool:
    return any(
        ("\u0600" <= ch <= "\u06ff")
        or ("\u0750" <= ch <= "\u077f")
        or ("\u08a0" <= ch <= "\u08ff")
        or ("\ufb50" <= ch <= "\ufdff")
        or ("\ufe70" <= ch <= "\ufeff")
        for ch in text
    )


def _contains_cjk_script(text: str) -> bool:
    return any(
        ("\u3040" <= ch <= "\u30ff")  # Hiragana + Katakana
        or ("\u31f0" <= ch <= "\u31ff")  # Katakana phonetic extensions
        or ("\u4e00" <= ch <= "\u9fff")  # CJK unified ideographs
        or ("\u3400" <= ch <= "\u4dbf")  # CJK extension A
        or ("\u1100" <= ch <= "\u11ff")  # Hangul Jamo
        or ("\u3130" <= ch <= "\u318f")  # Hangul compatibility Jamo
        or ("\ua960" <= ch <= "\ua97f")  # Hangul Jamo extended-A
        or ("\uac00" <= ch <= "\ud7af")  # Hangul syllables
        or ("\ud7b0" <= ch <= "\ud7ff")  # Hangul Jamo extended-B
        for ch in text
    )


def _is_low_clarity_transcript(text: str) -> bool:
    t = text.strip()
    if len(t) < 8:
        return False
    if re.search(r"(?i)\b([a-z]{2,})\b(?:\s+\1\b){8,}", t):
        return True
    words = re.findall(r"[A-Za-z\u0980-\u09ff]{2,}", t)
    if len(words) >= 10:
        uniq = {w.lower() for w in words}
        if len(uniq) <= max(2, len(words) // 8):
            return True
        freq: dict[str, int] = {}
        for w in words:
            k = w.lower()
            freq[k] = freq.get(k, 0) + 1
        top = max(freq.values()) if freq else 0
        if top >= 8 and top / max(1, len(words)) >= 0.35:
            return True
    letters = [ch.lower() for ch in t if ch.isalpha()]
    if len(letters) >= 50:
        unique_ratio = len(set(letters)) / max(1, len(letters))
        if unique_ratio < 0.18:
            return True
    return False


def _unclear_voice_reply(profile: dict[str, object]) -> str:
    if _voice_prefers_bangla(profile):
        return "আমি স্পষ্টভাবে বুঝতে পারিনি। অনুগ্রহ করে ধীরে, ছোট করে আবার বলুন।"
    return (
        "I could not understand that clearly. Please repeat slowly in one short sentence."
    )


def _is_transcript_language_mismatch(transcript: str, profile: dict[str, object]) -> bool:
    if not _voice_prefers_bangla(profile):
        return False
    return _contains_arabic_script(transcript) or _contains_cjk_script(transcript)


def _bangla_quality_score(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0
    letters = [ch for ch in t if ch.isalpha()]
    if not letters:
        return 0.0
    bn = sum(1 for ch in letters if "\u0980" <= ch <= "\u09ff")
    latin = sum(1 for ch in letters if "a" <= ch.lower() <= "z")
    total = max(1, len(letters))
    # Prefer real Bengali script and penalize heavy Latin-script fallback.
    return (bn / total) - (0.35 * latin / total)


def _normalize_transcript_hint(text: str | None) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    return re.sub(r"\s+", " ", t).strip()


class VoiceService:
    """Handles end-to-end voice chat orchestration."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.chat_service = ChatService(db_session)
        self.stt_service = get_whisper_stt()

    async def _synthesize_stream_chunk(self, text: str, prof: dict[str, object]) -> Path | None:
        """Coqui segment synth — serialized globally inside CoquiTTSService."""
        bn_name = (settings.tts_model_name_bn or "").strip()
        svc = get_default_coqui_tts()
        if bn_name:
            use_bn = contains_bengali_script(text)
            if not use_bn:
                lang = prof.get("language")
                if isinstance(lang, str) and prefers_bangla_tts(lang):
                    use_bn = True
            if use_bn:
                svc = get_bangla_coqui_tts(bn_name)
        pb: float | None = None
        v = prof.get("tts_playback_speed")
        if isinstance(v, (int, float)):
            pb = float(v)
        return await svc.synthesize_to_file(text, file_stem=uuid4().hex, playback_speed=pb)

    async def _transcribe_uploaded_audio(
        self,
        *,
        input_path: Path,
        user_id: str | None,
        transcript_hint: str | None = None,
    ) -> tuple[str, dict[str, object], list[Path]]:
        extra_paths: list[Path] = []
        prof: dict[str, object] = {}
        if user_id:
            prof = await self.chat_service.memory_service.get_user_profile(user_id)
        # Keep Whisper language auto-detection enabled.
        # Forcing BN from profile made English/mixed speech transcribe incorrectly.
        stt_lang: str | None = None
        try:
            path_for_stt, extra_paths = prepare_for_whisper(
                input_path,
                output_dir=settings.voice_staging_dir,
                timeout_seconds=float(settings.audio_ffmpeg_timeout_seconds),
            )
            transcript = await self.stt_service.transcribe(path_for_stt, language=stt_lang)
            if _voice_prefers_bangla(prof) and (
                _is_low_clarity_transcript(transcript) or _is_transcript_language_mismatch(transcript, prof)
            ):
                # Recovery pass: when user prefers Bangla and auto-detect looks noisy,
                # run a BN-forced pass and keep whichever looks more Bangla-coherent.
                try:
                    bn_transcript = await self.stt_service.transcribe(path_for_stt, language="bn")
                    if _bangla_quality_score(bn_transcript) > _bangla_quality_score(transcript):
                        transcript = bn_transcript
                except Exception:
                    pass
            hint = _normalize_transcript_hint(transcript_hint)
            if hint:
                # Browser live caption often has better short-phrase recognition than server STT.
                # Prefer it when server transcript looks degraded or clearly mismatched.
                if (
                    _is_low_clarity_transcript(transcript)
                    or _is_transcript_language_mismatch(transcript, prof)
                    or len(hint) >= len(transcript) + 4
                    or (
                        _voice_prefers_bangla(prof)
                        and contains_bengali_script(hint)
                        and not contains_bengali_script(transcript)
                    )
                    or (
                        len(hint) >= 8
                        and len(transcript) >= 8
                        and difflib.SequenceMatcher(
                            a=hint.lower(), b=transcript.lower()
                        ).ratio()
                        < 0.35
                    )
                ):
                    transcript = hint
            return transcript, prof, extra_paths
        except FFmpegUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AudioNormalizeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except STTInputError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc) or "Unable to read audio file.",
            ) from exc
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Speech recognition timed out. Try a shorter recording.",
            ) from None

    async def handle_voice_chat(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        session_id: str | None = None,
        user_id: str | None = None,
        transcript_hint: str | None = None,
    ) -> VoiceChatResponse:
        suffix = Path(filename).suffix or ".wav"
        input_path = settings.voice_staging_dir / f"{uuid4().hex}{suffix}"
        try:
            input_path.write_bytes(audio_bytes)
        except OSError as exc:
            raise HTTPException(
                status_code=507,
                detail="Could not save uploaded audio (disk full or permission issue).",
            ) from exc
        async with _voice_chat_lock_for(user_id):
            extra_paths: list[Path] = []
            try:
                await voice_status_service.set_state(
                    "transcribing",
                    detail="Speech → text (Whisper)",
                    audio_level=42.0,
                )
                transcript, prof, extra_paths = await self._transcribe_uploaded_audio(
                    input_path=input_path,
                    user_id=user_id,
                    transcript_hint=transcript_hint,
                )
                if not transcript:
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    await voice_status_service.set_state(
                        "idle",
                        detail="No speech detected",
                        audio_level=0.0,
                    )
                    return VoiceChatResponse(
                        session_id=session.id,
                        transcript="",
                        response="",
                        used_memory=False,
                        used_internet=False,
                        audio_path=None,
                        skipped=True,
                        skip_reason="no_speech",
                        voice_listen_paused=None,
                        voice_wake_session_active=None,
                    )

                profile_before = prof

                if user_id and should_drop_voice_for_wake_gate(profile_before, transcript):
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    return VoiceChatResponse(
                        session_id=session.id,
                        transcript=transcript,
                        response="",
                        used_memory=False,
                        used_internet=False,
                        audio_path=None,
                        skipped=True,
                        skip_reason="wake_gate",
                        voice_listen_paused=True,
                        voice_wake_session_active=bool(profile_before.get("voice_wake_session_active")),
                    )

                if _is_low_clarity_transcript(transcript) or _is_transcript_language_mismatch(
                    transcript, profile_before
                ):
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    reply = _unclear_voice_reply(profile_before)
                    tts_path = await self._synthesize_stream_chunk(reply, profile_before)
                    if tts_path:
                        schedule_ephemeral_tts_delete(tts_path)
                    await voice_status_service.set_state(
                        "idle",
                        detail="Need clearer speech",
                        audio_level=0.0,
                    )
                    return VoiceChatResponse(
                        session_id=session.id,
                        transcript=transcript,
                        response=reply,
                        used_memory=False,
                        used_internet=False,
                        audio_path=str(tts_path) if tts_path else None,
                        skipped=False,
                        skip_reason=None,
                        voice_listen_paused=bool(profile_before.get("voice_listen_paused"))
                        if user_id
                        else None,
                        voice_wake_session_active=bool(profile_before.get("voice_wake_session_active"))
                        if user_id
                        else None,
                    )

                await voice_status_service.set_state(
                    "thinking",
                    detail="Generating reply (LLM)",
                    audio_level=48.0,
                )
                chat_result = await self.chat_service.handle_chat(
                    message=transcript,
                    session_id=session_id,
                    user_id=user_id,
                    include_tts=True,
                    defer_tts=False,
                )
                prof_after: dict[str, object] = {}
                if user_id:
                    prof_after = await self.chat_service.memory_service.get_user_profile(user_id)
                await voice_status_service.set_state(
                    "speaking",
                    detail="Reply ready (TTS)",
                    audio_level=58.0,
                )
                return VoiceChatResponse(
                    session_id=chat_result.session_id,
                    transcript=transcript,
                    response=chat_result.response,
                    used_memory=chat_result.used_memory,
                    used_internet=chat_result.used_internet,
                    audio_path=chat_result.audio_path,
                    skipped=False,
                    skip_reason=None,
                    voice_listen_paused=bool(prof_after.get("voice_listen_paused")) if user_id else None,
                    voice_wake_session_active=bool(prof_after.get("voice_wake_session_active")) if user_id else None,
                )
            finally:
                await voice_status_service.set_state(
                    "idle",
                    detail="Ready",
                    audio_level=0.0,
                )
                with contextlib.suppress(OSError):
                    input_path.unlink()
                for p in extra_paths:
                    with contextlib.suppress(OSError):
                        p.unlink()

    async def handle_voice_chat_stream(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        session_id: str | None = None,
        user_id: str | None = None,
        transcript_hint: str | None = None,
    ) -> AsyncIterator[str]:
        """
        SSE lines for voice flow:
        - token: streamed assistant text chunks
        - tts_chunk: partial WAV URL + snippet (`audio_url`, `t`)
        - done: VoiceChatResponse JSON
        - error: {detail}
        """
        suffix = Path(filename).suffix or ".wav"
        input_path = settings.voice_staging_dir / f"{uuid4().hex}{suffix}"
        try:
            input_path.write_bytes(audio_bytes)
        except OSError as exc:
            raise HTTPException(
                status_code=507,
                detail="Could not save uploaded audio (disk full or permission issue).",
            ) from exc

        async with _voice_chat_lock_for(user_id):
            extra_paths: list[Path] = []
            try:
                await voice_status_service.set_state(
                    "transcribing",
                    detail="Speech → text (Whisper)",
                    audio_level=42.0,
                )
                transcript, prof, extra_paths = await self._transcribe_uploaded_audio(
                    input_path=input_path,
                    user_id=user_id,
                    transcript_hint=transcript_hint,
                )
                if not transcript:
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    payload = VoiceChatResponse(
                        session_id=session.id,
                        transcript="",
                        response="",
                        used_memory=False,
                        used_internet=False,
                        audio_path=None,
                        skipped=True,
                        skip_reason="no_speech",
                        voice_listen_paused=None,
                        voice_wake_session_active=None,
                    )
                    yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
                    return

                if user_id and should_drop_voice_for_wake_gate(prof, transcript):
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    payload = VoiceChatResponse(
                        session_id=session.id,
                        transcript=transcript,
                        response="",
                        used_memory=False,
                        used_internet=False,
                        audio_path=None,
                        skipped=True,
                        skip_reason="wake_gate",
                        voice_listen_paused=True,
                        voice_wake_session_active=bool(prof.get("voice_wake_session_active")),
                    )
                    yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
                    return

                if _is_low_clarity_transcript(transcript) or _is_transcript_language_mismatch(
                    transcript, prof
                ):
                    session = await self.chat_service.memory_service.get_or_create_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                    reply = _unclear_voice_reply(prof)
                    tts_path = await self._synthesize_stream_chunk(reply, prof)
                    if tts_path:
                        schedule_ephemeral_tts_delete(tts_path)
                        yield (
                            "event: tts_chunk\ndata: "
                            + json.dumps({"audio_url": f"tts/audio/{tts_path.name}", "t": reply})
                            + "\n\n"
                        )
                    payload = VoiceChatResponse(
                        session_id=session.id,
                        transcript=transcript,
                        response=reply,
                        used_memory=False,
                        used_internet=False,
                        audio_path=None,
                        skipped=False,
                        skip_reason=None,
                        voice_listen_paused=bool(prof.get("voice_listen_paused")) if user_id else None,
                        voice_wake_session_active=bool(prof.get("voice_wake_session_active"))
                        if user_id
                        else None,
                    )
                    yield f"event: token\ndata: {json.dumps({'t': reply})}\n\n"
                    yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
                    return

                await voice_status_service.set_state(
                    "thinking",
                    detail="Generating reply (LLM)",
                    audio_level=48.0,
                )
                final_chat_payload: ChatResponse | None = None
                tts_tail = ""
                streaming_speak_started = False
                async for chunk in self.chat_service.handle_chat_stream(
                    message=transcript,
                    session_id=session_id,
                    user_id=user_id,
                ):
                    if chunk.startswith("event: token"):
                        yield chunk
                        td = _sse_token_delta(chunk)
                        if td:
                            tts_tail += td
                            while True:
                                taken = _take_spoken_chunk(tts_tail)
                                if taken is None:
                                    break
                                speak_text, tts_tail = taken
                                path = await self._synthesize_stream_chunk(speak_text, prof)
                                if path:
                                    schedule_ephemeral_tts_delete(path)
                                    if not streaming_speak_started:
                                        await voice_status_service.set_state(
                                            "speaking",
                                            detail="Speaking (streaming)",
                                            audio_level=58.0,
                                        )
                                        streaming_speak_started = True
                                    au = f"tts/audio/{path.name}"
                                    yield (
                                        "event: tts_chunk\ndata: "
                                        + json.dumps({"audio_url": au, "t": speak_text})
                                        + "\n\n"
                                    )
                        continue
                    if chunk.startswith("event: error"):
                        yield chunk
                        return
                    if chunk.startswith("event: done"):
                        try:
                            data_line = next(
                                (ln for ln in chunk.splitlines() if ln.startswith("data:")),
                                "",
                            )
                            raw = data_line[5:].strip()
                            final_chat_payload = ChatResponse.model_validate_json(raw)
                        except Exception:
                            yield (
                                "event: error\ndata: "
                                + json.dumps(
                                    {"detail": "Voice stream failed to parse final assistant payload."}
                                )
                                + "\n\n"
                            )
                            return
                        break
                if final_chat_payload is None:
                    yield (
                        "event: error\ndata: "
                        + json.dumps({"detail": "Voice stream ended without final response."})
                        + "\n\n"
                    )
                    return
                if tts_tail.strip():
                    path = await self._synthesize_stream_chunk(tts_tail.strip(), prof)
                    if path:
                        schedule_ephemeral_tts_delete(path)
                        if not streaming_speak_started:
                            await voice_status_service.set_state(
                                "speaking",
                                detail="Speaking (streaming)",
                                audio_level=58.0,
                            )
                            streaming_speak_started = True
                        au = f"tts/audio/{path.name}"
                        yield (
                            "event: tts_chunk\ndata: "
                            + json.dumps({"audio_url": au, "t": tts_tail.strip()})
                            + "\n\n"
                        )
                prof_after: dict[str, Any] = {}
                if user_id:
                    prof_after = await self.chat_service.memory_service.get_user_profile(user_id)
                if not streaming_speak_started:
                    await voice_status_service.set_state(
                        "speaking",
                        detail="Reply ready",
                        audio_level=58.0,
                    )
                payload = VoiceChatResponse(
                    session_id=final_chat_payload.session_id,
                    transcript=transcript,
                    response=final_chat_payload.response,
                    used_memory=final_chat_payload.used_memory,
                    used_internet=final_chat_payload.used_internet,
                    audio_path=None,
                    skipped=False,
                    skip_reason=None,
                    voice_listen_paused=bool(prof_after.get("voice_listen_paused")) if user_id else None,
                    voice_wake_session_active=bool(prof_after.get("voice_wake_session_active"))
                    if user_id
                    else None,
                )
                yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
            finally:
                await voice_status_service.set_state(
                    "idle",
                    detail="Ready",
                    audio_level=0.0,
                )
                with contextlib.suppress(OSError):
                    input_path.unlink()
                for p in extra_paths:
                    with contextlib.suppress(OSError):
                        p.unlink()
