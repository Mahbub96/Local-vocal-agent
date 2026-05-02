"""Tests for DuckDuckGo row selection for weather snippets."""

from __future__ import annotations

import unittest

from app.agents.weather_web_pick import WEATHER_SCORE_KEYS, select_weather_web_result


class TestSelectWeatherWebResult(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        self.assertIsNone(select_weather_web_result([]))

    def test_prefers_higher_keyword_overlap(self) -> None:
        low = {"title": "Politics today", "body": "Election news.", "href": "http://a"}
        high = {
            "title": "Dhaka weather",
            "body": "Temperature and rain forecast with humidity.",
            "href": "http://b",
        }
        picked = select_weather_web_result([low, high])
        self.assertEqual(picked["href"], "http://b")

    def test_first_row_when_all_scores_zero(self) -> None:
        a = {"title": "A", "body": "alpha", "href": "http://first"}
        b = {"title": "B", "body": "beta", "href": "http://second"}
        picked = select_weather_web_result([a, b])
        self.assertEqual(picked["href"], "http://first")

    def test_score_keys_tuple_non_empty(self) -> None:
        self.assertGreater(len(WEATHER_SCORE_KEYS), 0)
        self.assertIn("weather", WEATHER_SCORE_KEYS)


if __name__ == "__main__":
    unittest.main()
