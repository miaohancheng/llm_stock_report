from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path

try:
    import markdown  # type: ignore
except Exception:  # pragma: no cover
    markdown = None


SUPPORTED_LANGS = ("zh", "en")


def _normalize_lang(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw if raw in SUPPORTED_LANGS else "zh"


def _i18n(lang: str) -> dict[str, str]:
    if lang == "en":
        return {
            "html_lang": "en",
            "site_heading": "LLM Stock Report · GitHub Pages",
            "site_subtitle": "Detailed docs + daily case updates",
            "nav_home": "Home",
            "nav_docs": "Docs",
            "nav_cases": "Daily Cases",
            "switch_label": "中文",
            "docs_title": "Detailed Usage Docs",
            "docs_desc": "Rendered from repository markdown files and updated with code changes.",
            "cases_title": "Daily Case Updates",
            "cases_desc": "Newest first. Data is generated from daily report outputs.",
            "cases_col_date": "Date",
            "cases_col_market": "Market",
            "cases_col_status": "Status",
            "cases_col_sample": "Sample",
            "cases_col_summary": "Summary",
            "cases_col_detail": "Detail",
            "open": "Open",
            "no_cases": "No case data yet. Run any daily workflow first.",
            "home_title": "Site Content",
            "home_intro": "This Pages site includes two sections:",
            "home_item_docs": "Detailed usage docs: setup, variables, actions, troubleshooting.",
            "home_item_cases": "Daily case updates: auto-published report summary + details.",
            "home_latest": "Latest Cases",
            "home_no_cases": "No case data yet.",
            "missing_doc": "Document not found.",
            "missing_case": "Case markdown file not found.",
        }
    return {
        "html_lang": "zh-CN",
        "site_heading": "LLM Stock Report · GitHub Pages",
        "site_subtitle": "详细使用文档 + 每日案例更新",
        "nav_home": "首页",
        "nav_docs": "使用文档",
        "nav_cases": "每日案例",
        "switch_label": "English",
        "docs_title": "详细使用文档",
        "docs_desc": "以下文档由仓库内 Markdown 自动渲染，随代码更新。",
        "cases_title": "每日案例更新",
        "cases_desc": "最新案例在最上方。数据来源于日报任务输出并自动汇总。",
        "cases_col_date": "日期",
        "cases_col_market": "市场",
        "cases_col_status": "状态",
        "cases_col_sample": "样本",
        "cases_col_summary": "摘要",
        "cases_col_detail": "详情",
        "open": "打开",
        "no_cases": "暂无案例数据，先运行日报 workflow 生成输出。",
        "home_title": "站点内容",
        "home_intro": "本 Pages 站点包含两块内容：",
        "home_item_docs": "详细使用文档：安装、变量、Actions、排障。",
        "home_item_cases": "每日案例更新：自动展示日报输出（摘要 + 详细）。",
        "home_latest": "最新案例",
        "home_no_cases": "暂无案例数据。",
        "missing_doc": "文档不存在。",
        "missing_case": "案例文件不存在。",
    }


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


def _filter_cases_recent_days(cases: list[dict], keep_days: int) -> list[dict]:
    if keep_days <= 0:
        return list(cases)
    unique_dates: list[str] = []
    seen: set[str] = set()
    for item in cases:
        day = str(item.get("date", "")).strip()
        if not day or day in seen:
            continue
        seen.add(day)
        unique_dates.append(day)
    keep = set(unique_dates[:keep_days])
    return [item for item in cases if str(item.get("date", "")).strip() in keep]


def _page_template(
    *,
    title: str,
    body: str,
    active: str,
    lang: str,
    root_prefix: str,
    switch_rel: str,
) -> str:
    strings = _i18n(lang)
    nav_docs = "active" if active == "docs" else ""
    nav_cases = "active" if active == "cases" else ""
    nav_home = "active" if active == "home" else ""
    other = "en" if lang == "zh" else "zh"
    switch_href = f"{root_prefix}{other}/{switch_rel}"

    return f"""<!doctype html>
<html lang="{strings['html_lang']}">
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
    .nav {{ margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .nav a {{
      color: #d9e7ff; border: 1px solid rgba(255,255,255,0.26);
      border-radius: 999px; padding: 6px 12px; font-size: 13px;
    }}
    .nav a.active {{ background: #fff; color: #0b3fae; border-color: #fff; }}
    .nav .lang-switch {{ margin-left: auto; }}
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
      <h1>{strings['site_heading']}</h1>
      <p>{strings['site_subtitle']}</p>
      <nav class="nav">
        <a class="{nav_home}" href="{root_prefix}{lang}/index.html">{strings['nav_home']}</a>
        <a class="{nav_docs}" href="{root_prefix}{lang}/docs.html">{strings['nav_docs']}</a>
        <a class="{nav_cases}" href="{root_prefix}{lang}/cases.html">{strings['nav_cases']}</a>
        <a class="lang-switch" href="{switch_href}">{strings['switch_label']}</a>
      </nav>
    </section>
    <main class="content">
      {body}
    </main>
  </div>
</body>
</html>
"""


def _write_page(
    *,
    path: Path,
    title: str,
    body: str,
    active: str,
    lang: str,
    root_prefix: str,
    switch_rel: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _page_template(
            title=title,
            body=body,
            active=active,
            lang=lang,
            root_prefix=root_prefix,
            switch_rel=switch_rel,
        ),
        encoding="utf-8",
    )


def _write_redirect(path: Path, target: str, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="0; url={html.escape(target)}"/>
  <title>{html.escape(title)}</title>
</head>
<body>
  <p>Redirecting to <a href="{html.escape(target)}">{html.escape(target)}</a> ...</p>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def _render_docs_index(lang: str) -> str:
    s = _i18n(lang)
    if lang == "en":
        rows = [
            ("English Full Guide", "docs/guide.html"),
            ("GitHub Actions Setup (EN)", "docs/actions.html"),
        ]
        nav_rows = [
            ("How to Configure", "docs/actions.html", "Secrets, Variables, workflow schedule, rerun."),
            ("Parameter Guide", "docs/guide.html", "Training/data window, retries, model settings."),
            ("Daily Case Examples", "cases.html", "Open latest 3-day auto-generated case samples."),
        ]
        param_rows = [
            ("DAILY_ANALYSIS_LOOKBACK_DAYS", "30", "Lookback window used in daily LLM reasoning."),
            ("TRAINING_WINDOW_DAYS", "730", "Two-year training window for model retraining."),
            ("MAX_STOCKS_PER_RUN", "30", "Hard cap of analyzed symbols per run."),
            ("LLM_MAX_RETRIES", "6", "Retry count for LLM API HTTP failures."),
            ("LLM_MAX_OUTPUT_TOKENS", "800", "Output length cap to reduce truncation."),
            ("PAGES_CASE_RETENTION_DAYS", "3", "Only show latest N calendar days in Pages cases."),
        ]
        nav_title = "Usage Navigation"
        nav_desc = "Start here for setup, parameters, and daily examples."
        param_title = "Parameter Quick Reference"
    else:
        rows = [
            ("中文完整指南", "docs/guide.html"),
            ("GitHub Actions 配置（中文）", "docs/actions.html"),
        ]
        nav_rows = [
            ("怎么配置", "docs/actions.html", "Secrets、Variables、工作流定时与回跑。"),
            ("参数说明", "docs/guide.html", "训练窗口、重试策略、模型参数。"),
            ("每日用例示例", "cases.html", "查看最近3天自动生成案例。"),
        ]
        param_rows = [
            ("DAILY_ANALYSIS_LOOKBACK_DAYS", "30", "日度LLM推理使用的回看窗口。"),
            ("TRAINING_WINDOW_DAYS", "730", "模型重训默认两年窗口。"),
            ("MAX_STOCKS_PER_RUN", "30", "单次分析股票上限。"),
            ("LLM_MAX_RETRIES", "6", "LLM接口失败重试次数。"),
            ("LLM_MAX_OUTPUT_TOKENS", "800", "限制输出长度，降低截断概率。"),
            ("PAGES_CASE_RETENTION_DAYS", "3", "Pages只展示最近N天案例。"),
        ]
        nav_title = "使用导航"
        nav_desc = "建议从这里进入：先配置，再看参数，再看每日示例。"
        param_title = "参数速查"

    lines = [
        f"<h2>{s['docs_title']}</h2>",
        f"<p class='muted'>{s['docs_desc']}</p>",
        f"<h3>{nav_title}</h3>",
        f"<p class='muted'>{nav_desc}</p>",
        "<table>",
        "<thead><tr><th>Topic</th><th>Description</th><th>Link</th></tr></thead>",
        "<tbody>",
    ]
    for name, link, desc in nav_rows:
        lines.append(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(desc)}</td><td><a href='{link}'>{s['open']}</a></td></tr>"
        )
    lines.extend(
        [
            "</tbody>",
            "</table>",
            "<br/>",
            "<table>",
            "<thead><tr><th>Document</th><th>Link</th></tr></thead>",
            "<tbody>",
        ]
    )
    for name, link in rows:
        lines.append(f"<tr><td>{html.escape(name)}</td><td><a href='{link}'>{s['open']}</a></td></tr>")
    lines.extend(
        [
            "</tbody>",
            "</table>",
            f"<h3>{param_title}</h3>",
            "<table>",
            "<thead><tr><th>Key</th><th>Default</th><th>Description</th></tr></thead>",
            "<tbody>",
        ]
    )
    for key, default, desc in param_rows:
        lines.append(
            f"<tr><td><code>{html.escape(key)}</code></td><td>{html.escape(default)}</td><td>{html.escape(desc)}</td></tr>"
        )
    lines.extend(["</tbody>", "</table>"])
    return "\n".join(lines)


def _render_cases_index(lang: str, cases: list[dict], retention_days: int) -> str:
    s = _i18n(lang)
    lines = [
        f"<h2>{s['cases_title']}</h2>",
        f"<p class='muted'>{s['cases_desc']}</p>",
        (
            f"<p class='muted'>{'Only latest ' if lang == 'en' else '仅展示最近'}"
            f"{retention_days}{' days of case data.' if lang == 'en' else '天案例数据。'}</p>"
        ),
        "<table>",
        (
            "<thead><tr>"
            f"<th>{s['cases_col_date']}</th>"
            f"<th>{s['cases_col_market']}</th>"
            f"<th>{s['cases_col_status']}</th>"
            f"<th>{s['cases_col_sample']}</th>"
            f"<th>{s['cases_col_summary']}</th>"
            f"<th>{s['cases_col_detail']}</th>"
            "</tr></thead>"
        ),
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
            f"<td><a href='cases/{case_id}.html'>{s['open']}</a></td></tr>"
        )
    lines.extend(["</tbody>", "</table>"])
    if not cases:
        lines.append(f"<p class='muted'>{s['no_cases']}</p>")
    return "\n".join(lines)


def _render_home(lang: str, cases: list[dict], retention_days: int) -> str:
    s = _i18n(lang)
    latest = cases[:10]
    items = []
    for item in latest:
        case_id = html.escape(str(item.get("id", "")))
        title = html.escape(str(item.get("title", case_id)))
        items.append(f"<li><a href='cases/{case_id}.html'>{title}</a></li>")
    latest_block = "<ul>" + "".join(items) + "</ul>" if items else f"<p class='muted'>{s['home_no_cases']}</p>"
    return "\n".join(
        [
            f"<h2>{s['home_title']}</h2>",
            f"<p>{s['home_intro']}</p>",
            (
                f"<p class='muted'>{'Cases page keeps only latest ' if lang == 'en' else '案例页仅保留最近'}"
                f"{retention_days}{' days of examples.' if lang == 'en' else '天示例。'}</p>"
            ),
            "<ol>",
            f"<li><strong>{s['nav_docs']}</strong>: {s['home_item_docs']}</li>",
            f"<li><strong>{s['nav_cases']}</strong>: {s['home_item_cases']}</li>",
            "</ol>",
            f"<h3>{s['home_latest']}</h3>",
            latest_block,
        ]
    )


def build_site(
    project_root: Path,
    output_dir: Path,
    default_language: str = "zh",
    case_retention_days: int = 3,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    default_lang = _normalize_lang(default_language)
    keep_days = max(1, int(case_retention_days))
    cases_all = _load_cases_index(project_root / "pages_data" / "cases_index.json")
    cases_index = _filter_cases_recent_days(cases_all, keep_days)

    _write_redirect(output_dir / "index.html", f"{default_lang}/index.html", "LLM Stock Report Pages")
    _write_redirect(output_dir / "docs.html", f"{default_lang}/docs.html", "LLM Stock Report Docs")
    _write_redirect(output_dir / "cases.html", f"{default_lang}/cases.html", "LLM Stock Report Cases")

    docs_source_map = {
        "zh": [
            ("docs/full-guide.md", "docs/guide.html", "中文完整指南"),
            ("docs/github-actions-setup.md", "docs/actions.html", "GitHub Actions 配置（中文）"),
        ],
        "en": [
            ("docs/full-guide_EN.md", "docs/guide.html", "English Full Guide"),
            ("docs/github-actions-setup_EN.md", "docs/actions.html", "GitHub Actions Setup (EN)"),
        ],
    }

    for lang in SUPPORTED_LANGS:
        lang_root = output_dir / lang

        _write_page(
            path=lang_root / "index.html",
            title="LLM Stock Report Pages",
            body=_render_home(lang, cases_index, keep_days),
            active="home",
            lang=lang,
            root_prefix="../",
            switch_rel="index.html",
        )
        _write_page(
            path=lang_root / "docs.html",
            title="Detailed Docs",
            body=_render_docs_index(lang),
            active="docs",
            lang=lang,
            root_prefix="../",
            switch_rel="docs.html",
        )
        _write_page(
            path=lang_root / "cases.html",
            title="Daily Cases",
            body=_render_cases_index(lang, cases_index, keep_days),
            active="cases",
            lang=lang,
            root_prefix="../",
            switch_rel="cases.html",
        )

        for src_rel, dst_rel, page_title in docs_source_map[lang]:
            md = _read_text(project_root / src_rel)
            body = _md_to_html(md) if md else f"<p class='muted'>{_i18n(lang)['missing_doc']}</p>"
            _write_page(
                path=lang_root / dst_rel,
                title=page_title,
                body=body,
                active="docs",
                lang=lang,
                root_prefix="../../",
                switch_rel=dst_rel,
            )

        for item in cases_index:
            case_id = str(item.get("id", "")).strip()
            case_path = str(item.get("path", "")).strip()
            if not case_id or not case_path:
                continue
            md = _read_text(project_root / "pages_data" / case_path)
            body = _md_to_html(md) if md else f"<p class='muted'>{_i18n(lang)['missing_case']}</p>"
            _write_page(
                path=lang_root / "cases" / f"{case_id}.html",
                title=str(item.get("title", case_id)),
                body=body,
                active="cases",
                lang=lang,
                root_prefix="../../",
                switch_rel=f"cases/{case_id}.html",
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages site")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--output", default="site_dist")
    parser.add_argument("--default-language", default=None, help="zh or en")
    parser.add_argument("--case-retention-days", default=None, help="Keep latest N days of case pages")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    output_dir = (project_root / args.output).resolve()
    default_language = _normalize_lang(args.default_language or os.getenv("PAGES_DEFAULT_LANGUAGE", "zh"))
    case_retention_days = int(args.case_retention_days or os.getenv("PAGES_CASE_RETENTION_DAYS", "3"))
    build_site(
        project_root=project_root,
        output_dir=output_dir,
        default_language=default_language,
        case_retention_days=case_retention_days,
    )
    print(f"Built site at: {output_dir}")
    print(f"Default language: {default_language}")
    print(f"Case retention days: {max(1, case_retention_days)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
