from __future__ import annotations

import unittest

from app.report.splitter import escape_telegram_markdown, split_text


class SplitterTest(unittest.TestCase):
    def test_escape_markdown_v2(self) -> None:
        text = "[US] AAPL (test) + score=1.0!"
        escaped = escape_telegram_markdown(text)
        self.assertIn("\\[US\\]", escaped)
        self.assertIn("\\(test\\)", escaped)
        self.assertIn("\\+", escaped)
        self.assertIn("\\!", escaped)

    def test_split_text_keeps_chunk_limit(self) -> None:
        text = "\n\n".join([f"段落{i}: " + ("A" * 50) for i in range(20)])
        chunks = split_text(text, limit=180)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 180)


if __name__ == "__main__":
    unittest.main()
