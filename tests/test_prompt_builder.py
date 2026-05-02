"""Smoke tests for build_llm_prompt structure (no LLM call)."""

from __future__ import annotations

import unittest

from app.agents.language_detection import InputLanguageKind, ResponseLanguageTarget
from app.agents.prompt_builder import build_llm_prompt, enforce_conversation_contract
from app.agents.task_policy import TaskType


def _minimal_prompt(
    *,
    query: str = "What is 2+2?",
    voice_turn: bool = False,
    response_format_pref: str = "auto",
) -> str:
    return build_llm_prompt(
        query=query,
        profile_text="",
        short_term_context="(empty)",
        long_term_context="(empty)",
        web_context="(empty)",
        response_format_pref=response_format_pref,
        target=ResponseLanguageTarget.ENGLISH,
        detected=InputLanguageKind.ENGLISH_DOMINANT,
        profile=None,
        task_type=TaskType.GENERAL_QNA,
        voice_turn=voice_turn,
    )


class TestBuildLlmPrompt(unittest.TestCase):
    def test_contains_user_query_section(self) -> None:
        p = _minimal_prompt(query="Hello there")
        self.assertIn("User query:", p)
        self.assertIn("Hello there", p)

    def test_contains_core_sections(self) -> None:
        p = _minimal_prompt()
        self.assertIn("Recent conversation:", p)
        self.assertIn("Retrieved long-term memory", p)
        self.assertIn("Internet / live data", p)

    def test_includes_interaction_contract(self) -> None:
        p = _minimal_prompt()
        self.assertIn("Grounding first", p)

    def test_includes_live_data_rules(self) -> None:
        p = _minimal_prompt()
        self.assertIn("LIVE TIME", p)
        self.assertIn("DO NOT fabricate", p)

    def test_voice_supplement_when_voice_turn(self) -> None:
        p = _minimal_prompt(voice_turn=True)
        self.assertIn("Voice input", p)
        self.assertIn("ENFORCED CONSTRAINTS", p)

    def test_includes_foreign_script_guidance(self) -> None:
        p = _minimal_prompt()
        self.assertIn("Cyrillic", p)

    def test_audio_check_voice_does_not_deny_mic_or_passage_lecture(self) -> None:
        p = _minimal_prompt(query="তুমি কি আমাকে শুনতে পাচ্ছো?", voice_turn=True)
        self.assertNotIn("you do not hear a microphone", p)
        self.assertIn("transcribed from speech", p)
        self.assertIn("Do not contrast", p)

    def test_audio_check_text_is_brief_receipt(self) -> None:
        p = _minimal_prompt(query="Can you hear me?", voice_turn=False)
        self.assertNotIn("you do not hear a microphone", p)
        self.assertIn("confirm their message was received", p)

    def test_response_format_markdown_instruction(self) -> None:
        p = _minimal_prompt(response_format_pref="markdown")
        self.assertIn("Format responses in clean markdown", p)

    def test_response_format_table_instruction(self) -> None:
        p = _minimal_prompt(response_format_pref="table")
        self.assertIn("markdown tables", p)


_BASE = "STUB_PROMPT\n"


class TestEnforceConversationContract(unittest.TestCase):
    def test_voice_adds_grounding_and_voice_output_rules(self) -> None:
        out = enforce_conversation_contract(
            TaskType.GENERAL_QNA, input_source="voice", prompt=_BASE
        )
        self.assertIn("GROUNDING FIRST", out)
        self.assertIn("Voice output", out)

    def test_text_general_qna_adds_conversational_line(self) -> None:
        out = enforce_conversation_contract(
            TaskType.GENERAL_QNA, input_source="text", prompt=_BASE
        )
        self.assertIn("Conversational task: intent first", out)

    def test_finance_adds_critical_task_line(self) -> None:
        out = enforce_conversation_contract(
            TaskType.FINANCE_MARKET, input_source="text", prompt=_BASE
        )
        self.assertIn("CRITICAL TASK", out)
        self.assertNotIn("Conversational task: intent first", out)

    def test_casual_chat_voice_adds_short_reply_line(self) -> None:
        out = enforce_conversation_contract(
            TaskType.CASUAL_CHAT, input_source="voice", prompt=_BASE
        )
        self.assertIn("SHORT and spoken-like", out)

    def test_accepts_string_task_type(self) -> None:
        out = enforce_conversation_contract(
            "general_qna", input_source="text", prompt=_BASE
        )
        self.assertIn("Conversational task: intent first", out)


if __name__ == "__main__":
    unittest.main()
