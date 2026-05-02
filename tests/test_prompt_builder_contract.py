"""Prompt contract ordering and enforcement (stdlib unittest)."""

from __future__ import annotations

import unittest

from app.agents.language_detection import InputLanguageKind, ResponseLanguageTarget
from app.agents.prompt_builder import (
    CONVERSATION_INTERACTION_CONTRACT,
    VOICE_INPUT_CONTRACT_SUPPLEMENT,
    build_llm_prompt,
)
from app.agents.task_policy import TaskType


def _minimal_prompt(
    *,
    query: str,
    task_type: TaskType,
    voice_turn: bool = False,
) -> str:
    return build_llm_prompt(
        query=query,
        profile_text="",
        short_term_context="(none)",
        long_term_context="(none)",
        web_context="(none)",
        response_format_pref="plain",
        target=ResponseLanguageTarget.BENGALI_SCRIPT,
        detected=InputLanguageKind.MIXED,
        profile=None,
        task_type=task_type,
        voice_turn=voice_turn,
    )


class TestPromptContract(unittest.TestCase):
    def test_contract_constant_nonempty(self) -> None:
        self.assertIn("Grounding first", CONVERSATION_INTERACTION_CONTRACT)
        self.assertIn("শুনতে পাচ্ছি", CONVERSATION_INTERACTION_CONTRACT)
        self.assertIn("phonetic", VOICE_INPUT_CONTRACT_SUPPLEMENT.lower())

    def test_enforced_constraints_after_user_query(self) -> None:
        p = _minimal_prompt(query="marker_q", task_type=TaskType.SMALL_TALK)
        self.assertIn("ENFORCED CONSTRAINTS", p)
        self.assertGreater(p.index("ENFORCED CONSTRAINTS"), p.index("User query:"))

    def test_section_order_personality_before_contract(self) -> None:
        p = _minimal_prompt(query="hi", task_type=TaskType.SMALL_TALK)
        i_personality = p.index("Personality:")
        i_contract = p.index("Conversation interaction contract")
        self.assertLess(i_personality, i_contract)

    def test_section_order_contract_before_task_policy(self) -> None:
        p = _minimal_prompt(query="hi", task_type=TaskType.SMALL_TALK)
        i_contract = p.index("Conversation interaction contract")
        i_task = p.index("Task policy")
        self.assertLess(i_contract, i_task)

    def test_section_order_task_policy_before_response_length(self) -> None:
        p = _minimal_prompt(query="hello there friend how are you today", task_type=TaskType.CASUAL_CHAT)
        i_task = p.index("Task policy")
        i_len = p.index("Response length:")
        self.assertLess(i_task, i_len)

    def test_section_order_language_before_memory(self) -> None:
        p = _minimal_prompt(query="test", task_type=TaskType.GENERAL_QNA)
        i_lang = p.index("Output language:")
        i_mem = p.index("Recent conversation:")
        self.assertLess(i_lang, i_mem)

    def test_section_order_memory_before_web(self) -> None:
        p = _minimal_prompt(query="test", task_type=TaskType.GENERAL_QNA)
        i_mem = p.index("Retrieved long-term memory")
        i_web = p.index("Internet / live data")
        self.assertLess(i_mem, i_web)

    def test_section_order_web_before_user_query(self) -> None:
        p = _minimal_prompt(query="unique_query_marker_xyz", task_type=TaskType.GENERAL_QNA)
        i_web = p.index("Internet / live data")
        i_uq = p.index("User query:")
        self.assertLess(i_web, i_uq)
        self.assertIn("unique_query_marker_xyz", p)

    def test_voice_turn_appends_voice_supplement(self) -> None:
        p_voice = _minimal_prompt(
            query="tumi ki amake sunte pachcho",
            task_type=TaskType.CASUAL_CHAT,
            voice_turn=True,
        )
        p_text = _minimal_prompt(
            query="tumi ki amake sunte pachcho",
            task_type=TaskType.CASUAL_CHAT,
            voice_turn=False,
        )
        self.assertIn("Voice input", p_voice)
        self.assertIn("romanized Bangla", p_voice)
        self.assertNotIn("Voice input (this message is from speech", p_text)

    def test_critical_task_strict_policy(self) -> None:
        p = _minimal_prompt(query="Bitcoin price today", task_type=TaskType.FINANCE_MARKET)
        self.assertIn("Task policy (critical", p)
        self.assertIn("Script handling (this task): precision", p)

    def test_small_talk_trivial_ok(self) -> None:
        p = _minimal_prompt(query="ok", task_type=TaskType.SMALL_TALK)
        self.assertIn("Task policy (casual / voice-friendly", p)
        self.assertIn("ঠিক আছে", p)


if __name__ == "__main__":
    unittest.main()
