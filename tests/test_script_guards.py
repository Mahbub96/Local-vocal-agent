"""Tests for script detection and apply_script_policy."""

from __future__ import annotations

import unittest

from app.agents.language_detection import ResponseLanguageTarget
from app.agents.script_guards import (
    apply_script_policy,
    contains_arabic_script,
    contains_cjk_script,
    strip_forbidden_scripts,
)
from app.agents.task_policy import TaskType


class TestScriptDetection(unittest.TestCase):
    def test_arabic_detected(self) -> None:
        self.assertTrue(contains_arabic_script("مرحبا"))

    def test_bengali_not_arabic(self) -> None:
        self.assertFalse(contains_arabic_script("আমি বাংলায় লিখি"))

    def test_cjk_detected(self) -> None:
        self.assertTrue(contains_cjk_script("你好"))

    def test_strip_removes_arabic_keeps_bangla(self) -> None:
        raw = "হ্যালো السلام"  # Bangla + Arabic
        out = strip_forbidden_scripts(raw)
        self.assertNotIn("\u0627", out)
        self.assertIn("হ্যালো", out)


class TestApplyScriptPolicy(unittest.TestCase):
    def test_bengali_strict_replaces_when_forbidden(self) -> None:
        t = ResponseLanguageTarget.BENGALI_SCRIPT
        bad = "আমি লিখছি 中"
        out = apply_script_policy(bad, t, task_type=TaskType.FINANCE_MARKET)
        self.assertTrue(out.startswith("আমি দুঃখিত"))

    def test_bengali_relaxed_strips_when_long_enough(self) -> None:
        t = ResponseLanguageTarget.BENGALI_SCRIPT
        # Voice-relaxed task + enough Bangla after stripping one CJK char
        mixed = "এটি একটি পরীক্ষা 中"
        out = apply_script_policy(mixed, t, task_type=TaskType.CASUAL_CHAT)
        self.assertNotIn("中", out)
        self.assertGreater(len(out), 8)

    def test_english_strips_cjk(self) -> None:
        t = ResponseLanguageTarget.ENGLISH
        out = apply_script_policy("Price is 你好 high", t, task_type=None)
        self.assertNotIn("\u4f60", out)
        self.assertIn("Price", out)
        self.assertIn("high", out)

    def test_voice_never_script_fallback(self) -> None:
        t = ResponseLanguageTarget.BENGALI_SCRIPT
        bad = "আমি লিখছি 中"
        out = apply_script_policy(bad, t, task_type=TaskType.FINANCE_MARKET, input_source="voice")
        self.assertFalse(out.startswith("আমি দুঃখিত"))
        self.assertNotIn("中", out)


if __name__ == "__main__":
    unittest.main()
