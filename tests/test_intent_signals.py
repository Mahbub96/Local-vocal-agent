"""Regression tests for web-search routing (stdlib unittest — no pytest)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.agents.intent_signals import (
    REALTIME_PATTERN,
    classify_intent_label,
    is_time_query,
    should_use_internet_search,
)


def _ctx(*, search_if_no_memory: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        user_profile={},
        long_term_messages=[],
        effective_prefs=SimpleNamespace(
            assistant_search_if_no_memory=search_if_no_memory,
            always_web_search=False,
        ),
    )


class TestIntentSearchRouting(unittest.TestCase):
    def test_realtime_pattern_does_not_match_bare_time_word(self) -> None:
        self.assertIsNone(REALTIME_PATTERN.search("take your time please"))

    def test_take_your_time_no_web(self) -> None:
        q = "Take your time and do what you need to do"
        self.assertFalse(should_use_internet_search(q, _ctx(search_if_no_memory=False), zone=None))

    def test_take_your_time_no_web_even_with_search_if_no_memory(self) -> None:
        q = "please take your time"
        self.assertFalse(should_use_internet_search(q, _ctx(search_if_no_memory=True), zone=None))

    def test_explicit_time_still_searches(self) -> None:
        q = "What's the time in Asia/Dhaka?"
        self.assertTrue(is_time_query(q))
        self.assertTrue(should_use_internet_search(q, _ctx(search_if_no_memory=False), zone=None))

    def test_audio_check_no_web_when_search_if_no_memory(self) -> None:
        q = "Can you hear me?"
        self.assertFalse(should_use_internet_search(q, _ctx(search_if_no_memory=True), zone=None))

    def test_okay_plus_news_still_searches_with_fallback_on(self) -> None:
        """Reassurance substring must not block when the user also asks for live data."""
        q = "that's okay — latest news in Dhaka"
        self.assertTrue(should_use_internet_search(q, _ctx(search_if_no_memory=True), zone=None))

    def test_search_if_no_memory_still_true_for_news(self) -> None:
        q = "latest news Bangladesh"
        self.assertTrue(should_use_internet_search(q, _ctx(search_if_no_memory=True), zone=None))

    def test_search_if_no_memory_off_when_memory_hits(self) -> None:
        mc = SimpleNamespace(
            user_profile={},
            long_term_messages=[object()],
            effective_prefs=SimpleNamespace(
                assistant_search_if_no_memory=True,
                always_web_search=False,
            ),
        )
        self.assertFalse(
            should_use_internet_search("random small talk hello", mc, zone=None),
        )

    def test_classify_take_your_time_general(self) -> None:
        self.assertEqual(classify_intent_label("take your time"), "general")


if __name__ == "__main__":
    unittest.main()
