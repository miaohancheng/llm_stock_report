from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def _first_content_line(markdown_text: str) -> str:
    for raw in markdown_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("*") and line.endswith("*"):
            continue
        return line[:240]
    return ""


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_index(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def export_case(project_root: Path, market: str, run_date: str) -> Path:
    market = market.strip().lower()
    if market not in {"cn", "us", "hk"}:
        raise ValueError(f"Unsupported market: {market}")

    output_dir = project_root / "outputs" / market / run_date
    summary_path = output_dir / "summary.md"
    details_path = output_dir / "details.md"
    run_meta_path = output_dir / "run_meta.json"
    predictions_path = output_dir / "predictions.csv"

    if not summary_path.exists():
        raise FileNotFoundError(f"Missing summary output: {summary_path}")
    if not details_path.exists():
        raise FileNotFoundError(f"Missing details output: {details_path}")

    summary_md = summary_path.read_text(encoding="utf-8")
    details_md = details_path.read_text(encoding="utf-8")
    run_meta = _read_json(run_meta_path)

    case_root = project_root / "pages_data" / "cases" / market
    case_root.mkdir(parents=True, exist_ok=True)
    case_id = f"{market}-{run_date}"
    case_rel_path = Path("cases") / market / f"{run_date}.md"
    case_abs_path = case_root / f"{run_date}.md"

    meta_lines = [
        f"- run_id: `{run_meta.get('run_id', '')}`",
        f"- status: `{run_meta.get('status', '')}`",
        f"- model_version: `{run_meta.get('model_version', '')}`",
        f"- llm_model: `{run_meta.get('llm_model', '')}`",
        f"- symbols: {run_meta.get('success_symbols', 0)}/{run_meta.get('total_symbols', 0)} (success/total)",
        f"- failed_symbols: {run_meta.get('failed_symbols', 0)}",
    ]
    if predictions_path.exists():
        meta_lines.append(f"- predictions_file: `{predictions_path.name}`")

    case_doc = "\n".join(
        [
            f"# [{market.upper()}] {run_date} Daily Case",
            "",
            "## Run Metadata",
            *meta_lines,
            "",
            "## Summary",
            summary_md.strip(),
            "",
            "## Details",
            details_md.strip(),
            "",
        ]
    )
    case_abs_path.write_text(case_doc, encoding="utf-8")

    index_path = project_root / "pages_data" / "cases_index.json"
    index = _read_index(index_path)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    new_item = {
        "id": case_id,
        "market": market,
        "date": run_date,
        "title": f"[{market.upper()}] {run_date} Daily Case",
        "path": str(case_rel_path).replace("\\", "/"),
        "summary_line": _first_content_line(summary_md),
        "status": str(run_meta.get("status", "")),
        "success_symbols": int(run_meta.get("success_symbols", 0) or 0),
        "total_symbols": int(run_meta.get("total_symbols", 0) or 0),
        "updated_at": now_iso,
    }

    filtered = [item for item in index if item.get("id") != case_id]
    filtered.append(new_item)
    filtered.sort(key=lambda x: (str(x.get("date", "")), str(x.get("market", ""))), reverse=True)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    return case_abs_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export daily output to pages_data cases")
    parser.add_argument("--market", choices=["cn", "us", "hk"], required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--project-root", default=None)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[2]
    target = export_case(project_root=project_root, market=args.market, run_date=args.date)
    print(f"Exported case to: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
