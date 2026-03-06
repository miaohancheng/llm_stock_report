from __future__ import annotations

from html import escape
import re

TELEGRAM_MARKDOWN_V2_SPECIALS = "_ * [ ] ( ) ~ ` > # + - = | { } . !".split()
_INLINE_TOKEN_RE = re.compile(
    r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)|`([^`\n]+)`|(?<!\*)\*([^*\n]+)\*(?!\*)"
)


def escape_telegram_markdown(text: str) -> str:
    escaped = text
    for ch in TELEGRAM_MARKDOWN_V2_SPECIALS:
        escaped = escaped.replace(ch, f"\\{ch}")
    return escaped


def split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    buffer = ""
    sections = text.split("\n\n")

    for section in sections:
        section = section.strip()
        if not section:
            continue
        candidate = f"{buffer}\n\n{section}".strip() if buffer else section
        if len(candidate) <= limit:
            buffer = candidate
            continue

        if buffer:
            parts.append(buffer)
            buffer = ""

        if len(section) <= limit:
            buffer = section
            continue

        # Force split too-long section.
        start = 0
        while start < len(section):
            end = min(start + limit, len(section))
            parts.append(section[start:end])
            start = end

    if buffer:
        parts.append(buffer)

    return parts


def render_telegram_html(text: str) -> str:
    rendered_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if rendered_lines and rendered_lines[-1] != "":
                rendered_lines.append("")
            continue
        rendered_lines.append(_render_telegram_html_line(line))
    return "\n".join(rendered_lines).strip()


def split_markdown_for_telegram_html(text: str, limit: int) -> list[str]:
    rendered = render_telegram_html(text)
    if len(rendered) <= limit:
        return [rendered]

    parts: list[str] = []
    buffer = ""
    sections = text.split("\n\n")

    for section in sections:
        section = section.strip()
        if not section:
            continue
        section_html = render_telegram_html(section)
        candidate = f"{buffer}\n\n{section_html}".strip() if buffer else section_html
        if len(candidate) <= limit:
            buffer = candidate
            continue

        if buffer:
            parts.append(buffer)
            buffer = ""

        if len(section_html) <= limit:
            buffer = section_html
            continue

        line_buffer = ""
        for raw_line in section.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            line_html = render_telegram_html(stripped)
            candidate_line = f"{line_buffer}\n{line_html}".strip() if line_buffer else line_html
            if len(candidate_line) <= limit:
                line_buffer = candidate_line
                continue

            if line_buffer:
                parts.append(line_buffer)
                line_buffer = ""

            if len(line_html) <= limit:
                line_buffer = line_html
                continue

            for piece in _split_long_markdown_line(stripped, limit):
                piece_html = render_telegram_html(piece)
                if len(piece_html) <= limit:
                    parts.append(piece_html)
                    continue

                start = 0
                while start < len(piece_html):
                    end = min(start + limit, len(piece_html))
                    parts.append(piece_html[start:end])
                    start = end

        if line_buffer:
            buffer = line_buffer

    if buffer:
        parts.append(buffer)

    return parts


def _render_telegram_html_line(line: str) -> str:
    if line == "---":
        return "────────"
    if line.startswith("### "):
        return f"<b>{_render_inline_telegram_html(line[4:])}</b>"
    if line.startswith("## "):
        return f"<b>{_render_inline_telegram_html(line[3:])}</b>"
    if line.startswith("# "):
        return f"<b>{_render_inline_telegram_html(line[2:])}</b>"
    if line.startswith("> "):
        return f"▎ {_render_inline_telegram_html(line[2:])}"
    if line.startswith("- "):
        return f"• {_render_inline_telegram_html(line[2:])}"
    return _render_inline_telegram_html(line)


def _render_inline_telegram_html(text: str) -> str:
    parts: list[str] = []
    start = 0
    for match in _INLINE_TOKEN_RE.finditer(text):
        parts.append(escape(text[start:match.start()]))
        link_label, link_url, code_text, italic_text = match.groups()
        if link_label is not None and link_url is not None:
            parts.append(f'<a href="{escape(link_url, quote=True)}">{escape(link_label)}</a>')
        elif code_text is not None:
            parts.append(f"<code>{escape(code_text)}</code>")
        elif italic_text is not None:
            parts.append(f"<i>{escape(italic_text)}</i>")
        start = match.end()
    parts.append(escape(text[start:]))
    return "".join(parts)


def _split_long_markdown_line(line: str, limit: int) -> list[str]:
    prefix = ""
    body = line
    for candidate_prefix in ("### ", "## ", "# ", "> ", "- "):
        if body.startswith(candidate_prefix):
            prefix = candidate_prefix
            body = body[len(candidate_prefix):].strip()
            break

    if not body:
        return [line]

    chunk_size = max(1, limit - 64)
    parts: list[str] = []
    start = 0
    while start < len(body):
        piece = body[start : start + chunk_size].strip()
        if piece:
            parts.append(f"{prefix}{piece}" if prefix else piece)
        start += chunk_size

    return parts or [line]
