from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.jobs.export_case import export_case


class ExportCaseTest(unittest.TestCase):
    def test_export_case_writes_markdown_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "outputs" / "cn" / "2026-03-05"
            out.mkdir(parents=True, exist_ok=True)
            (out / "summary.md").write_text("# Summary\n\nline", encoding="utf-8")
            (out / "details.md").write_text("# Details\n\ncontent", encoding="utf-8")
            (out / "run_meta.json").write_text(
                json.dumps(
                    {
                        "run_id": "abc123",
                        "status": "success",
                        "model_version": "cn_20260305_test",
                        "llm_model": "openai:gpt-4o-mini",
                        "success_symbols": 3,
                        "total_symbols": 4,
                        "failed_symbols": 1,
                    }
                ),
                encoding="utf-8",
            )
            (out / "predictions.csv").write_text("x,y\n1,2\n", encoding="utf-8")

            case_path = export_case(project_root=root, market="cn", run_date="2026-03-05")
            self.assertTrue(case_path.exists())

            content = case_path.read_text(encoding="utf-8")
            self.assertIn("[CN] 2026-03-05 Daily Case", content)
            self.assertIn("## Summary", content)
            self.assertIn("## Details", content)

            index_path = root / "pages_data" / "cases_index.json"
            self.assertTrue(index_path.exists())
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(data))
            self.assertEqual("cn-2026-03-05", data[0]["id"])
            self.assertEqual("cases/cn/2026-03-05.md", data[0]["path"])


if __name__ == "__main__":
    unittest.main()
