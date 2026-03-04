from __future__ import annotations


TELEGRAM_MARKDOWN_V2_SPECIALS = "_ * [ ] ( ) ~ ` > # + - = | { } . !".split()


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
