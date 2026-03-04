from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

try:
    import markdown  # type: ignore
except Exception:  # pragma: no cover
    markdown = None


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _md_to_html(md_text: str) -> str:
    if markdown is None:
        return f"<pre>{html.escape(md_text)}</pre>"
    return markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code", "toc", "sane_lists", "nl2br"],
    )


def _load_cases_index(path: Path) -> list[dict]:
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
    out.sort(key=lambda x: (str(x.get("date", "")), str(x.get("market", ""))), reverse=True)
    return out


def _page_template(title: str, body: str, active: str, base_prefix: str = "") -> str:
    nav_docs = "active" if active == "docs" else ""
    nav_cases = "active" if active == "cases" else ""
    nav_home = "active" if active == "home" else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f4f8ff;
      --text: #1e2a3a;
      --muted: #5b6b7f;
      --card: #ffffff;
      --line: #dfe7f5;
      --accent: #175fe6;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; color: var(--text); background: var(--bg); }}
    a {{ color: var(--accent); text-decoration: none; }}
    .wrap {{ max-width: 1120px; margin: 0 auto; padding: 20px 16px 40px; }}
    .top {{
      background: linear-gradient(135deg, #0b3fae 0%, #1f7cff 100%);
      color: #fff; border-radius: 14px; padding: 20px;
      box-shadow: 0 10px 24px rgba(10, 44, 117, 0.28);
    }}
    .top h1 {{ margin: 0; font-size: 22px; }}
    .top p {{ margin: 8px 0 0; opacity: 0.92; }}
    .nav {{ margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }}
    .nav a {{
      color: #d9e7ff; border: 1px solid rgba(255,255,255,0.26);
      border-radius: 999px; padding: 6px 12px; font-size: 13px;
    }}
    .nav a.active {{ background: #fff; color: #0b3fae; border-color: #fff; }}
    .content {{ margin-top: 18px; background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px; }}
    .muted {{ color: var(--muted); }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; font-size: 14px; text-align: left; }}
    th {{ background: #f6f9ff; }}
    code {{ background: #eef3ff; border-radius: 4px; padding: 1px 4px; }}
    pre code {{ display: block; overflow-x: auto; padding: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="top">
      <h1>LLM Stock Report · GitHub Pages</h1>
      <p>详细使用文档 + 每日案例更新</p>
      <nav class="nav">
        <a class="{nav_home}" href="{base_prefix}index.html">首页</a>
        <a class="{nav_docs}" href="{base_prefix}docs.html">使用文档</a>
        <a class="{nav_cases}" href="{base_prefix}cases.html">每日案例</a>
      </nav>
    </section>
    <main class="content">
      {body}
    </main>
  </div>
</body>
</html>
"""


def _write_page(path: Path, title: str, body: str, active: str, base_prefix: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _page_template(title=title, body=body, active=active, base_prefix=base_prefix),
        encoding="utf-8",
    )


def _render_docs_index() -> str:
    rows = [
        ("中文完整指南", "docs/guide-zh.html"),
        ("English Full Guide", "docs/guide-en.html"),
        ("GitHub Actions 配置（中文）", "docs/actions-zh.html"),
        ("GitHub Actions Setup (EN)", "docs/actions-en.html"),
    ]
    lines = [
        "<h2>详细使用文档</h2>",
        "<p class='muted'>以下文档由仓库内 Markdown 自动渲染，随代码更新。</p>",
        "<table>",
        "<thead><tr><th>文档</th><th>链接</th></tr></thead>",
        "<tbody>",
    ]
    for name, link in rows:
        lines.append(f"<tr><td>{html.escape(name)}</td><td><a href='{link}'>打开</a></td></tr>")
    lines.extend(["</tbody>", "</table>"])
    return "\n".join(lines)


def _render_cases_index(cases: list[dict]) -> str:
    lines = [
        "<h2>每日案例更新</h2>",
        "<p class='muted'>最新案例在最上方。数据来源于日报任务输出并自动汇总。</p>",
        "<table>",
        "<thead><tr><th>日期</th><th>市场</th><th>状态</th><th>样本</th><th>摘要</th><th>详情</th></tr></thead>",
        "<tbody>",
    ]
    for item in cases:
        date = html.escape(str(item.get("date", "")))
        market = html.escape(str(item.get("market", "")).upper())
        status = html.escape(str(item.get("status", "")))
        success = int(item.get("success_symbols", 0) or 0)
        total = int(item.get("total_symbols", 0) or 0)
        summary = html.escape(str(item.get("summary_line", ""))[:140])
        case_id = html.escape(str(item.get("id", "")))
        lines.append(
            f"<tr><td>{date}</td><td>{market}</td><td>{status}</td>"
            f"<td>{success}/{total}</td><td>{summary}</td>"
            f"<td><a href='cases/{case_id}.html'>打开</a></td></tr>"
        )
    lines.extend(["</tbody>", "</table>"])
    if not cases:
        lines.append("<p class='muted'>暂无案例数据，先运行日报 workflow 生成输出。</p>")
    return "\n".join(lines)


def _render_home(cases: list[dict]) -> str:
    latest = cases[:10]
    list_items = []
    for item in latest:
        case_id = html.escape(str(item.get("id", "")))
        title = html.escape(str(item.get("title", case_id)))
        list_items.append(f"<li><a href='cases/{case_id}.html'>{title}</a></li>")
    latest_block = "<ul>" + "".join(list_items) + "</ul>" if list_items else "<p class='muted'>暂无案例数据。</p>"
    return "\n".join(
        [
            "<h2>站点内容</h2>",
            "<p>本 Pages 站点包含两块内容：</p>",
            "<ol>",
            "<li><strong>详细使用文档</strong>：安装、变量、Actions、排障。</li>",
            "<li><strong>每日案例更新</strong>：自动展示日报输出（摘要 + 详细）。</li>",
            "</ol>",
            "<h3>最新案例</h3>",
            latest_block,
        ]
    )


def build_site(project_root: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_index = _load_cases_index(project_root / "pages_data" / "cases_index.json")

    _write_page(
        output_dir / "index.html",
        "LLM Stock Report Pages",
        _render_home(cases_index),
        active="home",
        base_prefix="",
    )
    _write_page(
        output_dir / "docs.html",
        "Detailed Docs",
        _render_docs_index(),
        active="docs",
        base_prefix="",
    )
    _write_page(
        output_dir / "cases.html",
        "Daily Cases",
        _render_cases_index(cases_index),
        active="cases",
        base_prefix="",
    )

    docs_map = [
        ("docs/full-guide.md", "docs/guide-zh.html", "中文完整指南"),
        ("docs/full-guide_EN.md", "docs/guide-en.html", "English Full Guide"),
        ("docs/github-actions-setup.md", "docs/actions-zh.html", "GitHub Actions 配置（中文）"),
        ("docs/github-actions-setup_EN.md", "docs/actions-en.html", "GitHub Actions Setup (EN)"),
    ]
    for src_rel, dst_rel, title in docs_map:
        md = _read_text(project_root / src_rel)
        body = _md_to_html(md) if md else "<p class='muted'>文档不存在。</p>"
        _write_page(output_dir / dst_rel, title, body, active="docs", base_prefix="../")

    for item in cases_index:
        case_id = str(item.get("id", "")).strip()
        case_path = str(item.get("path", "")).strip()
        if not case_id or not case_path:
            continue
        md = _read_text(project_root / "pages_data" / case_path)
        body = _md_to_html(md) if md else "<p class='muted'>案例文件不存在。</p>"
        _write_page(
            output_dir / "cases" / f"{case_id}.html",
            item.get("title", case_id),
            body,
            active="cases",
            base_prefix="../",
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages site")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--output", default="site_dist")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    output_dir = (project_root / args.output).resolve()
    build_site(project_root=project_root, output_dir=output_dir)
    print(f"Built site at: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
