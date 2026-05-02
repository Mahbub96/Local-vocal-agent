from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.assistant_agent import AssistantAgent, ModelUnavailableError
from app.memory.long_term.retriever import LongTermMemoryRetriever, SemanticMemoryMatch
from app.schemas.chat import ChatResponse
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.app_config_intent import process_app_configuration_message
from app.services.effective_assistant_prefs import EffectiveAssistantPrefs, resolve_effective_assistant_prefs
from app.services.memory_service import MemoryService
from app.services.speech_preferences import merge_speech_preferences_from_message
from app.services.voice_listen_intent import merge_voice_listen_profile, strip_wake_prefix
from app.integrations.tts.coqui_tts import CoquiTTSService, get_bangla_coqui_tts, get_default_coqui_tts
from app.integrations.tts.tts_cleanup import schedule_ephemeral_tts_delete
from app.integrations.tts.tts_locale import contains_bengali_script, prefers_bangla_tts
from app.core.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

# Widen vector recall for "who am I" / "my name" so prior self-intro messages still rank.
_IDENTITY_RETRIEVAL = re.compile(
    r"(?i)(my name|what(?:'s| is) my name|who am i\b|"
    r"do you know my name|remind me.*\bname\b|call me|i(?:'m| am)\b.*name)"
)


class ChatService:
    """Coordinates chat persistence, memory retrieval, and agent execution."""

    def __init__(
        self,
        db_session: AsyncSession,
        *,
        embedding_service: EmbeddingService | None = None,
        tts_service: CoquiTTSService | None = None,
    ) -> None:
        self.db_session = db_session
        self.memory_service = MemoryService(db_session)
        self.embedding_service = embedding_service or get_embedding_service()
        self.retriever = LongTermMemoryRetriever(
            embedding_service=self.embedding_service,
            memory_service=self.memory_service,
        )
        self.agent = AssistantAgent(retriever=self.retriever)
        self._tts_default = tts_service or get_default_coqui_tts()

    async def handle_chat(
        self,
        *,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        include_tts: bool = False,
        defer_tts: bool = False,
    ) -> ChatResponse:
        normalized_message = self._prepare_message(message)
        if not normalized_message:
            raise ValueError("Message cannot be empty.")

        session = await self.memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
        )
        effective_user_id = (user_id or session.user_id) or None
        profile_work: dict[str, Any] = {}
        if effective_user_id:
            profile_work = await self.memory_service.get_user_profile(effective_user_id)
            profile_work = await self._maybe_merge_voice_listen_profile(
                effective_user_id, normalized_message, profile_work
            )
            profile_work = await self._maybe_apply_speech_preferences(
                effective_user_id, normalized_message, profile_work
            )

        cfg = process_app_configuration_message(profile_work, normalized_message)
        if not effective_user_id and cfg.profile_changed and cfg.merged_profile is not None:
            if cfg.skip_llm and cfg.direct_reply:
                cfg = replace(
                    cfg,
                    merged_profile=None,
                    profile_changed=False,
                    direct_reply=(
                        "Assistant settings are saved per user id. "
                        "Set a user id in the client to enable configuration commands.\n\n"
                        + (cfg.direct_reply or "")
                    ),
                )
            else:
                cfg = replace(
                    cfg,
                    merged_profile=None,
                    profile_changed=False,
                    confirmation_note=(
                        "(Settings not saved — no user id.) " + (cfg.confirmation_note or "")
                    ),
                )
        if cfg.merged_profile is not None and cfg.profile_changed and effective_user_id:
            await self.memory_service.upsert_user_profile(effective_user_id, cfg.merged_profile)
            profile_work = await self.memory_service.get_user_profile(effective_user_id)

        prefs = resolve_effective_assistant_prefs(profile_work if effective_user_id else None)

        user_message = await self.memory_service.add_message(
            session.id,
            role="user",
            content=normalized_message,
        )

        if cfg.skip_llm and cfg.direct_reply is not None:
            assistant_message = await self.memory_service.add_message(
                session.id,
                role="assistant",
                content=cfg.direct_reply,
                parent_message_id=user_message.id,
                tool_name="app_configuration",
                tool_output="assistant_app_overrides",
            )
            self._schedule_background_task(
                self.embedding_service.index_message(
                    user_message, source="chat", user_id=effective_user_id
                )
            )
            self._schedule_background_task(
                self.embedding_service.index_message(
                    assistant_message, source="chat", user_id=effective_user_id
                )
            )
            return ChatResponse(
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response=cfg.direct_reply,
                used_memory=False,
                used_internet=False,
                audio_path=None,
            )

        retrieval_query = normalized_message
        if effective_user_id and _IDENTITY_RETRIEVAL.search(normalized_message):
            retrieval_query = (
                f"{normalized_message}\n"
                f"name identity self-introduction who I am user profile preferences"
            )
        semantic_matches, recent_msgs = await asyncio.gather(
            self._retrieve_long_term_matches(
                retrieval_query,
                session_id=session.id,
                effective_user_id=effective_user_id,
                prefs=prefs,
            ),
            self.memory_service.get_recent_messages(
                session.id,
                limit=prefs.short_term_message_limit,
            ),
        )
        memory_context = await self.memory_service.build_context(
            session.id,
            long_term_messages=[match.message for match in semantic_matches],
            user_id=effective_user_id,
            effective_prefs=prefs,
            cached_profile=profile_work if effective_user_id else None,
            recent_messages_cached=recent_msgs,
        )

        agent_base = cfg.stripped_query if cfg.stripped_query.strip() else normalized_message
        agent_query = self._agent_query_after_wake_strip(agent_base, memory_context.user_profile)
        agent_result = await self.agent.run(query=agent_query, memory_context=memory_context)
        final_reply = str(agent_result["response"])
        if cfg.confirmation_note:
            final_reply = f"{cfg.confirmation_note}\n\n{final_reply}"
        assistant_message = await self.memory_service.add_message(
            session.id,
            role="assistant",
            content=final_reply,
            parent_message_id=user_message.id,
            tool_name="internet_search_tool"
            if bool(agent_result.get("used_internet"))
            else "memory_context_tool",
            tool_output=str(agent_result.get("tool_result", "")),
        )

        self._schedule_background_task(
            self.embedding_service.index_message(
                user_message, source="chat", user_id=effective_user_id
            )
        )
        self._schedule_background_task(
            self.embedding_service.index_message(
                assistant_message, source="chat", user_id=effective_user_id
            )
        )

        audio_path: Path | None = None
        if include_tts:
            reply_text = final_reply
            tts_svc = await self._tts_service_for_response(
                effective_user_id,
                reply_text,
                user_profile=memory_context.user_profile,
            )
            pb = self._effective_playback_speed(memory_context.user_profile)
            if defer_tts:
                # Fire-and-forget: path may appear later; failures are logged only.
                self._schedule_background_task(
                    self._tts_deferred(reply_text, assistant_message.id, tts_svc, playback_speed=pb)
                )
                audio_path = tts_svc.build_output_path(file_stem=assistant_message.id)
            else:
                path = await tts_svc.synthesize_to_file(
                    reply_text,
                    file_stem=assistant_message.id,
                    playback_speed=pb,
                )
                audio_path = path
                schedule_ephemeral_tts_delete(path)

        return ChatResponse(
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            response=final_reply,
            used_memory=bool(agent_result["used_memory"]),
            used_internet=bool(agent_result["used_internet"]),
            audio_path=str(audio_path) if audio_path else None,
        )

    async def handle_chat_stream(
        self,
        *,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[str]:
        """SSE lines: `token` deltas, then `done` with ChatResponse JSON."""
        try:
            normalized_message = self._prepare_message(message)
            if not normalized_message:
                yield f"event: error\ndata: {json.dumps({'detail': 'Message cannot be empty.'})}\n\n"
                return

            session = await self.memory_service.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
            )
            effective_user_id = (user_id or session.user_id) or None
            profile_work: dict[str, Any] = {}
            if effective_user_id:
                profile_work = await self.memory_service.get_user_profile(effective_user_id)
                profile_work = await self._maybe_merge_voice_listen_profile(
                    effective_user_id, normalized_message, profile_work
                )
                profile_work = await self._maybe_apply_speech_preferences(
                    effective_user_id, normalized_message, profile_work
                )

            cfg = process_app_configuration_message(profile_work, normalized_message)
            if not effective_user_id and cfg.profile_changed and cfg.merged_profile is not None:
                if cfg.skip_llm and cfg.direct_reply:
                    cfg = replace(
                        cfg,
                        merged_profile=None,
                        profile_changed=False,
                        direct_reply=(
                            "Assistant settings are saved per user id. "
                            "Set a user id in the client to enable configuration commands.\n\n"
                            + (cfg.direct_reply or "")
                        ),
                    )
                else:
                    cfg = replace(
                        cfg,
                        merged_profile=None,
                        profile_changed=False,
                        confirmation_note=(
                            "(Settings not saved — no user id.) " + (cfg.confirmation_note or "")
                        ),
                    )
            if cfg.merged_profile is not None and cfg.profile_changed and effective_user_id:
                await self.memory_service.upsert_user_profile(effective_user_id, cfg.merged_profile)
                profile_work = await self.memory_service.get_user_profile(effective_user_id)

            prefs = resolve_effective_assistant_prefs(profile_work if effective_user_id else None)

            user_message = await self.memory_service.add_message(
                session.id,
                role="user",
                content=normalized_message,
            )

            if cfg.skip_llm and cfg.direct_reply is not None:
                yield f"event: token\ndata: {json.dumps({'t': cfg.direct_reply})}\n\n"
                assistant_message = await self.memory_service.add_message(
                    session.id,
                    role="assistant",
                    content=cfg.direct_reply,
                    parent_message_id=user_message.id,
                    tool_name="app_configuration",
                    tool_output="assistant_app_overrides",
                )
                self._schedule_background_task(
                    self.embedding_service.index_message(
                        user_message, source="chat", user_id=effective_user_id
                    )
                )
                self._schedule_background_task(
                    self.embedding_service.index_message(
                        assistant_message, source="chat", user_id=effective_user_id
                    )
                )
                payload = ChatResponse(
                    session_id=session.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    response=cfg.direct_reply,
                    used_memory=False,
                    used_internet=False,
                    audio_path=None,
                )
                yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
                return

            retrieval_query = normalized_message
            if effective_user_id and _IDENTITY_RETRIEVAL.search(normalized_message):
                retrieval_query = (
                    f"{normalized_message}\n"
                    f"name identity self-introduction who I am user profile preferences"
                )
            semantic_matches, recent_msgs = await asyncio.gather(
                self._retrieve_long_term_matches(
                    retrieval_query,
                    session_id=session.id,
                    effective_user_id=effective_user_id,
                    prefs=prefs,
                ),
                self.memory_service.get_recent_messages(
                    session.id,
                    limit=prefs.short_term_message_limit,
                ),
            )
            memory_context = await self.memory_service.build_context(
                session.id,
                long_term_messages=[match.message for match in semantic_matches],
                user_id=effective_user_id,
                effective_prefs=prefs,
                cached_profile=profile_work if effective_user_id else None,
                recent_messages_cached=recent_msgs,
            )

            agent_base = cfg.stripped_query if cfg.stripped_query.strip() else normalized_message
            agent_query = self._agent_query_after_wake_strip(agent_base, memory_context.user_profile)
            agent_result: dict[str, object] | None = None
            try:
                async for item in self.agent.stream_run(
                    query=agent_query,
                    memory_context=memory_context,
                ):
                    if isinstance(item, str):
                        yield f"event: token\ndata: {json.dumps({'t': item})}\n\n"
                    else:
                        agent_result = item
            except ModelUnavailableError as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
                return

            if agent_result is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'Stream ended without response.'})}\n\n"
                return

            final_reply = str(agent_result["response"])
            if cfg.confirmation_note:
                final_reply = f"{cfg.confirmation_note}\n\n{final_reply}"

            assistant_message = await self.memory_service.add_message(
                session.id,
                role="assistant",
                content=final_reply,
                parent_message_id=user_message.id,
                tool_name="internet_search_tool"
                if bool(agent_result.get("used_internet"))
                else "memory_context_tool",
                tool_output=str(agent_result.get("tool_result", "")),
            )

            self._schedule_background_task(
                self.embedding_service.index_message(
                    user_message, source="chat", user_id=effective_user_id
                )
            )
            self._schedule_background_task(
                self.embedding_service.index_message(
                    assistant_message, source="chat", user_id=effective_user_id
                )
            )

            payload = ChatResponse(
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response=final_reply,
                used_memory=bool(agent_result["used_memory"]),
                used_internet=bool(agent_result["used_internet"]),
                audio_path=None,
            )
            yield f"event: done\ndata: {json.dumps(payload.model_dump())}\n\n"
        except Exception as exc:
            logger.exception("chat stream failed: %s", exc)
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    async def _retrieve_long_term_matches(
        self,
        retrieval_query: str,
        *,
        session_id: str,
        effective_user_id: str | None,
        prefs: EffectiveAssistantPrefs,
    ) -> list[SemanticMemoryMatch]:
        """Vector search across the user’s indexed history + optional keyword matches on all sessions."""
        try:
            semantic_matches = await self.retriever.search(
                retrieval_query,
                session_id=session_id,
                user_id=effective_user_id,
                top_k=prefs.memory_top_k,
            )
        except Exception as exc:
            logger.exception("Semantic retrieval failed; continuing without long-term memory: %s", exc)
            semantic_matches = []
        semantic_matches.sort(key=lambda m: m.score)
        if (
            not effective_user_id
            or not prefs.memory_keyword_supplement
            or prefs.memory_keyword_match_limit <= 0
        ):
            return semantic_matches
        try:
            extra_msgs = await self.memory_service.search_user_messages_keyword(
                effective_user_id,
                retrieval_query,
                limit=prefs.memory_keyword_match_limit,
                min_word_len=settings.memory_keyword_min_word_len,
            )
        except Exception as exc:
            logger.warning("Keyword memory supplement failed: %s", exc)
            return semantic_matches
        seen = {m.message.id for m in semantic_matches}
        merged = list(semantic_matches)
        for msg in extra_msgs:
            if msg.id in seen:
                continue
            seen.add(msg.id)
            merged.append(
                SemanticMemoryMatch(
                    message=msg,
                    score=10.0,
                    metadata={"source": "keyword"},
                )
            )
        return merged

    async def _maybe_merge_voice_listen_profile(
        self,
        user_id: str | None,
        message: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not user_id or not message.strip():
            return profile
        merged, changed = merge_voice_listen_profile(profile, message)
        if changed:
            await self.memory_service.upsert_user_profile(user_id, merged)
            return merged
        return profile

    async def _maybe_apply_speech_preferences(
        self,
        user_id: str | None,
        message: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not user_id or not message.strip():
            return profile
        merged, changed = merge_speech_preferences_from_message(profile, message)
        if changed:
            await self.memory_service.upsert_user_profile(user_id, merged)
            return merged
        return profile

    @staticmethod
    def _agent_query_after_wake_strip(message: str, user_profile: dict[str, Any] | None) -> str:
        """Remove leading wake name for the LLM; user message in DB stays full text."""
        if not user_profile:
            return message
        w = user_profile.get("assistant_wake_name")
        if not isinstance(w, str) or not w.strip():
            return message
        stripped = strip_wake_prefix(message, w)
        return stripped.strip() if stripped.strip() else message

    @staticmethod
    def _effective_playback_speed(user_profile: dict[str, Any] | None) -> float | None:
        if not user_profile:
            return None
        v = user_profile.get("tts_playback_speed")
        if isinstance(v, (int, float)):
            return float(v)
        return None

    async def _tts_deferred(
        self,
        reply_text: str,
        file_stem: str,
        tts: CoquiTTSService,
        *,
        playback_speed: float | None = None,
    ) -> None:
        path = await tts.synthesize_to_file(
            reply_text,
            file_stem=file_stem,
            playback_speed=playback_speed,
        )
        if path is None:
            logger.warning("Deferred TTS produced no audio (stem=%s)", file_stem)
        else:
            schedule_ephemeral_tts_delete(path)

    async def _tts_service_for_response(
        self,
        effective_user_id: str | None,
        reply_text: str,
        *,
        user_profile: dict[str, Any] | None = None,
    ) -> CoquiTTSService:
        """Pick English vs Bangla Coqui from assistant *reply* script and/or profile (must match BN text)."""
        bn_name = (settings.tts_model_name_bn or "").strip()
        if not bn_name:
            return self._tts_default

        use_bn = False
        if contains_bengali_script(reply_text):
            use_bn = True
        elif effective_user_id:
            if user_profile is not None:
                lang = user_profile.get("language")
            else:
                profile = await self.memory_service.get_user_profile(effective_user_id)
                lang = profile.get("language") if profile else None
            if isinstance(lang, str) and prefers_bangla_tts(lang):
                use_bn = True

        if use_bn:
            return get_bangla_coqui_tts(bn_name)
        return self._tts_default

    def _prepare_message(self, message: str) -> str:
        text = message.strip()
        if not text:
            return ""

        if len(text) > settings.chat_max_input_chars:
            text = self._compact_large_input(text, settings.chat_max_input_chars)
        return " ".join(text.split())

    def _compact_large_input(self, text: str, limit: int) -> str:
        # LaTeX payloads can be very long and command-heavy; extract readable parts.
        if "\\documentclass" in text or text.count("\\") >= 20:
            extracted = re.findall(r"\{([^{}]+)\}", text)
            compact = " ".join(chunk.strip() for chunk in extracted if chunk.strip())
            if compact:
                text = compact
        return text[:limit]

    def _schedule_background_task(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        task.add_done_callback(self._log_background_task_error)

    def _log_background_task_error(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except Exception as exc:
            logger.exception("Background task failed: %s", exc)
