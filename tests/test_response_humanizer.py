"""Tests for leading-phrase stripping in response_humanizer."""

from __future__ import annotations

import unittest

from app.agents.language_detection import ResponseLanguageTarget
from app.agents.response_humanizer import (
    humanize_response,
    remove_generic_ai_openers,
    remove_patronizing_bangla_tail,
)


class TestHumanizeResponse(unittest.TestCase):
    def test_strips_certainly_english(self) -> None:
        t = humanize_response(
            "Certainly! Here is the answer.",
            target=ResponseLanguageTarget.ENGLISH,
        )
        self.assertNotIn("Certainly", t)
        self.assertIn("answer", t)

    def test_strips_bn_lead_banglish(self) -> None:
        t = humanize_response(
            "নিঃসন্দেহে, এটা ঠিক আছে।",
            target=ResponseLanguageTarget.BANGLISH,
        )
        self.assertNotIn("নিঃসন্দেহে", t)
        self.assertIn("ঠিক", t)

    def test_empty_passthrough(self) -> None:
        self.assertEqual(humanize_response("", target=ResponseLanguageTarget.ENGLISH), "")

    def test_collapses_double_spaces(self) -> None:
        t = humanize_response("Hello  world", target=ResponseLanguageTarget.ENGLISH)
        self.assertNotIn("  ", t)

    def test_removes_generic_ai_opener(self) -> None:
        raw = "As an AI assistant, I can help you with that. Here is the answer."
        t = remove_generic_ai_openers(raw)
        self.assertNotIn("AI assistant", t)
        self.assertIn("answer", t)

    def test_removes_patronizing_bangla_tail(self) -> None:
        raw = "কী হচ্ছে? আমার খুব ভালো করে বলতে পারেন না তো?"
        t = remove_patronizing_bangla_tail(raw)
        self.assertNotIn("ভালো করে বলতে", t)
        self.assertIn("কী হচ্ছে", t)

    def test_humanize_bengali_script_strips_patronizing_tail(self) -> None:
        raw = "হ্যাঁ, বুঝেছি। ভালো করে বলতে পারেন না তো।"
        t = humanize_response(raw, target=ResponseLanguageTarget.BENGALI_SCRIPT)
        self.assertNotIn("বলতে পারেন", t)
        self.assertIn("বুঝেছি", t)


if __name__ == "__main__":
    unittest.main()
