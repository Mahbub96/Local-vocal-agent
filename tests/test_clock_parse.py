"""Tests for LIVE TIME line clock extraction (stdlib only)."""

from __future__ import annotations

import unittest

from app.integrations.time.clock_parse import extract_iso_clock_from_time_line


class TestClockParse(unittest.TestCase):
    def test_extracts_iso_from_standard_line(self) -> None:
        line = "LIVE TIME for Asia/Dhaka: 2026-05-02 14:30:00 (UTC+6)"
        self.assertEqual(extract_iso_clock_from_time_line(line), "2026-05-02 14:30:00")

    def test_none_when_no_clock(self) -> None:
        self.assertIsNone(extract_iso_clock_from_time_line("no clock here"))


if __name__ == "__main__":
    unittest.main()
