from __future__ import annotations

import unittest

from app.report.splitter import (
    escape_telegram_markdown,
    render_telegram_html,
    split_markdown_for_telegram_html,
    split_text,
)


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

    def test_render_telegram_html_converts_common_markdown(self) -> None:
        text = "\n".join(
            [
                "# 标题",
                "> 摘要",
                "- [新闻](https://example.com)",
                "*仅供研究参考*",
            ]
        )
        rendered = render_telegram_html(text)
        self.assertIn("<b>标题</b>", rendered)
        self.assertIn("▎ 摘要", rendered)
        self.assertIn('• <a href="https://example.com">新闻</a>', rendered)
        self.assertIn("<i>仅供研究参考</i>", rendered)

    def test_split_markdown_for_telegram_html_keeps_chunk_limit(self) -> None:
        text = "\n\n".join([f"## 段落{i}\n- 内容 {'A' * 80}" for i in range(12)])
        chunks = split_markdown_for_telegram_html(text, limit=220)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 220)


if __name__ == "__main__":
    unittest.main()
