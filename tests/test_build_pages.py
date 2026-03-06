from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_pages import build_site


class BuildPagesTest(unittest.TestCase):
    def test_build_site_generates_zh_en_pages_and_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "pages_data" / "cases" / "cn").mkdir(parents=True, exist_ok=True)

            (root / "docs" / "full-guide.md").write_text("# 中文指南", encoding="utf-8")
            (root / "docs" / "github-actions-setup.md").write_text("# 中文 Actions", encoding="utf-8")
            (root / "docs" / "full-guide_EN.md").write_text("# English Guide", encoding="utf-8")
            (root / "docs" / "github-actions-setup_EN.md").write_text("# English Actions", encoding="utf-8")

            for day in ("2026-03-05", "2026-03-04", "2026-03-03", "2026-03-02"):
                case_md = root / "pages_data" / "cases" / "cn" / f"{day}.md"
                case_md.write_text(f"# Case {day}\n\nexample", encoding="utf-8")
            (root / "pages_data" / "cases_index.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "cn-2026-03-05",
                            "market": "cn",
                            "date": "2026-03-05",
                            "title": "[CN] 2026-03-05 Daily Case",
                            "path": "cases/cn/2026-03-05.md",
                            "summary_line": "example",
                            "status": "success",
                            "success_symbols": 3,
                            "total_symbols": 3,
                        },
                        {
                            "id": "cn-2026-03-04",
                            "market": "cn",
                            "date": "2026-03-04",
                            "title": "[CN] 2026-03-04 Daily Case",
                            "path": "cases/cn/2026-03-04.md",
                            "summary_line": "example",
                            "status": "success",
                            "success_symbols": 3,
                            "total_symbols": 3,
                        },
                        {
                            "id": "cn-2026-03-03",
                            "market": "cn",
                            "date": "2026-03-03",
                            "title": "[CN] 2026-03-03 Daily Case",
                            "path": "cases/cn/2026-03-03.md",
                            "summary_line": "example",
                            "status": "success",
                            "success_symbols": 3,
                            "total_symbols": 3,
                        },
                        {
                            "id": "cn-2026-03-02",
                            "market": "cn",
                            "date": "2026-03-02",
                            "title": "[CN] 2026-03-02 Daily Case",
                            "path": "cases/cn/2026-03-02.md",
                            "summary_line": "example",
                            "status": "success",
                            "success_symbols": 3,
                            "total_symbols": 3,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            out = root / "site_dist"
            build_site(project_root=root, output_dir=out, default_language="en")

            root_index = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("url=en/index.html", root_index)

            zh_docs = (out / "zh" / "docs.html").read_text(encoding="utf-8")
            en_docs = (out / "en" / "docs.html").read_text(encoding="utf-8")
            self.assertIn("中文完整指南", zh_docs)
            self.assertIn("GitHub Actions 配置（中文）", zh_docs)
            self.assertIn("参数速查", zh_docs)
            self.assertIn("English Full Guide", en_docs)
            self.assertIn("GitHub Actions Setup (EN)", en_docs)
            self.assertIn("Parameter Quick Reference", en_docs)

            self.assertTrue((out / "zh" / "cases" / "cn-2026-03-05.html").exists())
            self.assertTrue((out / "en" / "cases" / "cn-2026-03-05.html").exists())
            # Keep only latest 3 days by default.
            self.assertTrue((out / "zh" / "cases" / "cn-2026-03-03.html").exists())
            self.assertFalse((out / "zh" / "cases" / "cn-2026-03-02.html").exists())


if __name__ == "__main__":
    unittest.main()
