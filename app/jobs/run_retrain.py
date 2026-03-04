from __future__ import annotations

import argparse
import logging

from app.common.config import AppConfig, load_config, load_universe
from app.common.logging import setup_logging
from app.data.fetch_cn import fetch_cn_ohlcv
from app.data.fetch_hk import fetch_hk_ohlcv
from app.data.fetch_us import fetch_us_ohlcv
from app.data.history_store import get_or_update_symbol_history
from app.data.normalize import normalize_symbol, parse_date
from app.model.qlib_data_builder import build_market_feature_frame, frame_window, split_train_predict_frame
from app.model.registry import ModelBundle, build_model_version, save_model_bundle
from app.model.trainer import train_market_model

logger = logging.getLogger(__name__)


def _prepare_symbols(cfg: AppConfig, market: str) -> list[str]:
    universe = load_universe(cfg.project_root)
    raw = universe.get(market, [])
    normalized = [normalize_symbol(s, market) for s in raw]
    if len(normalized) > cfg.max_stocks_per_run:
        logger.warning(
            "Universe size=%d exceeds max_stocks_per_run=%d, truncating",
            len(normalized),
            cfg.max_stocks_per_run,
        )
        normalized = normalized[: cfg.max_stocks_per_run]
    return normalized


def _fetch_single_symbol(market: str, symbol: str, start_date, asof_date):
    if market == "cn":
        return fetch_cn_ohlcv(symbol, start_date, asof_date)
    if market == "hk":
        return fetch_hk_ohlcv(symbol, start_date, asof_date)
    if market == "us":
        return fetch_us_ohlcv(symbol, start_date, asof_date)
    raise ValueError(f"Unsupported market: {market}")


def _fetch_market_data(cfg: AppConfig, market: str, symbols: list[str], asof_date):
    market_data = {}
    failed_symbols: list[str] = []

    for symbol in symbols:
        try:
            history = get_or_update_symbol_history(
                cfg=cfg,
                market=market,
                symbol=symbol,
                asof_date=asof_date,
                fetcher=lambda code, start, end: _fetch_single_symbol(market, code, start, end),
            )
            market_data[symbol] = history
        except Exception as exc:
            logger.warning("Skip symbol %s in retrain due to fetch failure: %s", symbol, exc)
            failed_symbols.append(symbol)

    if failed_symbols:
        logger.warning("Retrain skipped symbols: %s", ",".join(failed_symbols))
    return market_data


def retrain_market(cfg: AppConfig, market: str, asof_date) -> ModelBundle:
    symbols = _prepare_symbols(cfg, market)
    if not symbols:
        raise RuntimeError(f"No symbols configured for market={market}")

    market_data = _fetch_market_data(cfg, market, symbols, asof_date=asof_date)
    if not market_data:
        raise RuntimeError("No market data available after retries")

    feature_frame = build_market_feature_frame(market_data)
    train_frame, _ = split_train_predict_frame(feature_frame, asof_date=asof_date)
    start_window, end_window = frame_window(feature_frame)

    model_version = build_model_version(market, asof_date, cfg.project_root)
    bundle = train_market_model(
        train_frame=train_frame,
        model_version=model_version,
        data_window_start=start_window,
        data_window_end=end_window,
    )
    artifact_dir = save_model_bundle(cfg.models_root, market, bundle)
    logger.info("Model saved: %s", artifact_dir)
    return bundle


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retrain market model")
    parser.add_argument("--market", choices=["cn", "us", "hk"], required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    return parser


def main() -> int:
    setup_logging()
    args = build_arg_parser().parse_args()
    cfg = load_config()
    asof_date = parse_date(args.date)

    retrain_market(cfg, args.market, asof_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
