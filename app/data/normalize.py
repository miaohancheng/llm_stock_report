from __future__ import annotations

from datetime import date, datetime


class DataFetchError(RuntimeError):
    pass


def parse_date(value: str | date | datetime | None) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_cn_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.startswith(("SH", "SZ")):
        prefix, code = s[:2], s[2:]
        if code.isdigit() and len(code) == 6:
            return f"{prefix}{code}"
        raise ValueError(f"Invalid CN symbol: {symbol}")
    if s.isdigit() and len(s) == 6:
        prefix = "SH" if s.startswith(("5", "6", "9")) else "SZ"
        return f"{prefix}{s}"
    raise ValueError(f"Invalid CN symbol: {symbol}")


def normalize_us_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s:
        raise ValueError("US symbol cannot be empty")
    return s


def normalize_hk_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.startswith("HK"):
        code = s[2:]
        if code.isdigit() and len(code) == 5:
            return f"HK{code}"
        raise ValueError(f"Invalid HK symbol: {symbol}")
    if s.isdigit():
        if len(s) == 5:
            return f"HK{s}"
        if len(s) == 4:
            return f"HK0{s}"
        if len(s) == 3:
            return f"HK00{s}"
    raise ValueError(f"Invalid HK symbol: {symbol}")


def normalize_symbol(symbol: str, market: str) -> str:
    if market == "cn":
        return normalize_cn_symbol(symbol)
    if market == "us":
        return normalize_us_symbol(symbol)
    if market == "hk":
        return normalize_hk_symbol(symbol)
    raise ValueError(f"Unsupported market: {market}")


def to_akshare_symbol(symbol: str) -> str:
    normalized = normalize_cn_symbol(symbol)
    return normalized[2:]


def to_yfinance_hk_ticker(symbol: str) -> str:
    normalized = normalize_hk_symbol(symbol)
    return f"{normalized[2:]}.HK"
