from __future__ import annotations

import unittest

from app.llm.base import parse_json_text


class LLMJsonParseTest(unittest.TestCase):
    def test_parse_truncated_array_tail(self) -> None:
        raw = (
            '{"summary":"s","details":"d","decision":"观望","trend":"震荡",'
            '"urgency":"低","risk_points":["r1"],"catalysts":['
        )
        parsed = parse_json_text(raw, provider_name="OpenAI")
        self.assertEqual("s", parsed.get("summary"))
        self.assertEqual(["r1"], parsed.get("risk_points"))
        self.assertEqual([], parsed.get("catalysts"))

    def test_parse_truncated_in_string(self) -> None:
        raw = '{"summary":"s","details":"技术面偏弱，短期需谨慎'
        parsed = parse_json_text(raw, provider_name="OpenAI")
        self.assertEqual("s", parsed.get("summary"))
        self.assertTrue(str(parsed.get("details", "")).startswith("技术面偏弱"))


if __name__ == "__main__":
    unittest.main()
