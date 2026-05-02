"""Tests for time placeholder stripping and internet-claim sanitization."""

from __future__ import annotations

import unittest

from app.agents.time_response_sanitize import (
    compact_date_response,
    compact_time_response,
    sanitize_live_data_claims,
    strip_llm_time_placeholders,
)


class TestStripLlmTimePlaceholders(unittest.TestCase):
    def test_substitutes_clock_from_live_time_line(self) -> None:
        line = "LIVE TIME for Asia/Dhaka: 2026-05-02 14:30:00 (UTC+6)"
        raw = "The time is [insert current time here]."
        out = strip_llm_time_placeholders(raw, line)
        self.assertIn("2026-05-02 14:30:00", out)
        self.assertNotIn("insert", out.lower())

    def test_fallback_when_no_time_line(self) -> None:
        raw = "[TBD]"
        out = strip_llm_time_placeholders(raw, None)
        self.assertIn("UTC+6", out)
        self.assertNotIn("TBD", out)


class TestCompactTimeAndDate(unittest.TestCase):
    _LINE = "LIVE TIME for Asia/Dhaka: 2026-05-02 14:30:00 (UTC+6)"

    def test_compact_time_includes_zone_and_clock(self) -> None:
        out = compact_time_response(self._LINE)
        self.assertIsNotNone(out)
        self.assertIn("Asia/Dhaka", out or "")
        self.assertIn("2026-05-02 14:30:00", out or "")

    def test_compact_date_iso(self) -> None:
        out = compact_date_response(self._LINE)
        self.assertEqual(out, "Today's date in Asia/Dhaka is 2026-05-02.")

    def test_compact_none(self) -> None:
        self.assertIsNone(compact_time_response(None))
        self.assertIsNone(compact_date_response(None))


class TestSanitizeLiveDataClaims(unittest.TestCase):
    def test_noop_without_internet(self) -> None:
        t = "I don't have internet access."
        self.assertEqual(sanitize_live_data_claims(t, used_internet=False), t)

    def test_replaces_no_internet_when_web_used(self) -> None:
        t = "I do not have real-time internet access."
        out = sanitize_live_data_claims(t, used_internet=True)
        self.assertNotIn("do not have", out.lower())
        self.assertIn("live internet access", out.lower())


if __name__ == "__main__":
    unittest.main()
