from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import traceback
import uuid

from app.common.config import AppConfig, load_config, load_universe
from app.common.logging import setup_logging
from app.common.schemas import PredictionRecord, RunMeta, StockNarrative
from app.data.fetch_cn import fetch_cn_ohlcv
from app.data.fetch_hk import fetch_hk_ohlcv
from app.data.fetch_us import fetch_us_ohlcv
from app.data.history_store import get_or_update_symbol_history
from app.data.normalize import normalize_symbol, parse_date
from app.llm.base import LLMError
from app.llm.factory import create_llm_client
from app.llm.report_reasoner import generate_market_narrative, generate_stock_narrative
from app.model.predictor import build_predictions
from app.model.qlib_data_builder import build_market_feature_frame, frame_window, save_debug_frames, split_train_predict_frame
from app.model.registry import ModelBundle, load_latest_model, model_is_expired, save_model_bundle
from app.model.trainer import train_market_model
from app.news.aggregator import build_stock_news_queries, search_news_with_fallback
from app.report.market_overview import build_market_snapshot, market_news_query
from app.report.renderer import (
    market_tag,
    render_market_detail_markdown,
    render_summary_markdown,
    render_symbol_detail_markdown,
    write_outputs,
)
from app.report.telegram_sender import TelegramSender

logger = logging.getLogger(__name__)


def _is_en(language: str) -> bool:
    return (language or "").strip().lower() == "en"


def _summary_title(market: str, asof_date: str, language: str) -> str:
    if _is_en(language):
        return f"[{market.upper()}] {asof_date} Daily Summary"
    return f"[{market.upper()}] {asof_date} 日报摘要"


def _failure_title(market: str, asof_date: str, language: str) -> str:
    if _is_en(language):
        return f"[{market.upper()}] {asof_date} Job Failed"
    return f"[{market.upper()}] {asof_date} 任务失败"


def _critical_failure_msg(exc: Exception, language: str) -> str:
    if _is_en(language):
        return f"Critical pipeline failure: {exc}"
    return f"关键链路失败: {exc}"


def _load_symbols(cfg: AppConfig, market: str) -> list[str]:
    universe = load_universe(cfg.project_root)
    symbols = [normalize_symbol(s, market) for s in universe.get(market, [])]
    if len(symbols) > cfg.max_stocks_per_run:
        logger.warning(
            "Universe size=%d exceeds max_stocks_per_run=%d, truncating",
            len(symbols),
            cfg.max_stocks_per_run,
        )
        symbols = symbols[: cfg.max_stocks_per_run]
    return symbols


def _fetch_single_symbol(market: str, symbol: str, start_date, asof_date):
    if market == "cn":
        return fetch_cn_ohlcv(symbol, start_date, asof_date)
    if market == "hk":
        return fetch_hk_ohlcv(symbol, start_date, asof_date)
    if market == "us":
        return fetch_us_ohlcv(symbol, start_date, asof_date)
    raise ValueError(f"Unsupported market: {market}")


def _train_bundle_from_feature_frame(cfg: AppConfig, market: str, asof_date, feature_frame) -> ModelBundle:
    train_frame, _ = split_train_predict_frame(feature_frame, asof_date=asof_date)
    if train_frame.empty:
        raise RuntimeError("No training rows available for retrain fallback")
    window_start, window_end = frame_window(feature_frame)

    from app.model.registry import build_model_version

    model_version = build_model_version(market, asof_date, cfg.project_root)
    bundle = train_market_model(
        train_frame=train_frame,
        model_version=model_version,
        data_window_start=window_start,
        data_window_end=window_end,
    )
    save_model_bundle(cfg.models_root, market, bundle)
    logger.info("Fallback retrain complete model_version=%s", bundle.model_version)
    return bundle


def _resolve_model_bundle(
    cfg: AppConfig,
    market: str,
    asof_date,
    feature_frame,
) -> ModelBundle:
    latest = load_latest_model(cfg.models_root, market)
    if latest and not model_is_expired(latest, asof_date, cfg.model_expire_days):
        logger.info("Use latest model: %s", latest.model_version)
        return latest

    if latest:
        logger.warning("Model expired: %s, retraining", latest.model_version)
    else:
        logger.warning("No model found, retraining")

    return _train_bundle_from_feature_frame(cfg, market, asof_date, feature_frame)


def _send_failure_alert(cfg: AppConfig, market: str, asof_date: str, message: str) -> None:
    sender = TelegramSender(
        bot_token=cfg.telegram_bot_token or "",
        chat_id=cfg.telegram_chat_id or "",
        message_thread_id=cfg.telegram_message_thread_id,
        limit=cfg.detail_message_char_limit,
    )
    if sender.enabled:
        title = _failure_title(market, asof_date, cfg.report_language)
        try:
            sender.send_summary(title, message)
        except Exception as exc:
            logger.error("Failure alert send failed: %s", exc)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run daily report")
    parser.add_argument("--market", choices=["cn", "us", "hk"], required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--no-telegram", action="store_true")
    return parser


def main() -> int:
    setup_logging()
    args = build_arg_parser().parse_args()

    cfg = load_config()
    report_language = cfg.report_language
    llm_model_for_meta = (
        f"gemini:{cfg.gemini_model}"
        if cfg.llm_provider == "gemini"
        else f"ollama:{cfg.ollama_model}"
        if cfg.llm_provider == "ollama"
        else f"openai:{cfg.llm_model}"
        if cfg.llm_provider == "openai"
        else f"{cfg.llm_provider}:{cfg.llm_model}"
    )
    market = args.market
    asof_date = parse_date(args.date)
    asof_str = asof_date.isoformat()

    run_id = uuid.uuid4().hex[:12]
    start_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        symbols = _load_symbols(cfg, market)
        if not symbols:
            raise RuntimeError(f"No symbols configured for market={market}")

        market_data = {}
        failed_symbols: list[str] = []
        for symbol in symbols:
            try:
                market_data[symbol] = get_or_update_symbol_history(
                    cfg=cfg,
                    market=market,
                    symbol=symbol,
                    asof_date=asof_date,
                    fetcher=lambda code, start, end: _fetch_single_symbol(market, code, start, end),
                )
            except Exception as exc:
                logger.warning("Skip symbol %s due to data failure: %s", symbol, exc)
                failed_symbols.append(symbol)

        if not market_data:
            raise RuntimeError("All symbols failed data fetch")

        feature_frame = build_market_feature_frame(market_data)
        train_frame, predict_frame = split_train_predict_frame(feature_frame, asof_date=asof_date)
        if predict_frame.empty:
            raise RuntimeError("No predict rows for asof date")

        save_debug_frames(cfg.outputs_root, market, asof_date, train_frame, predict_frame)

        bundle = _resolve_model_bundle(cfg, market, asof_date, feature_frame)

        predictions = build_predictions(
            market=market,
            asof_date=asof_str,
            bundle=bundle,
            predict_frame=predict_frame,
            top_n=cfg.prediction_top_n,
        )
        if not predictions:
            raise RuntimeError("Prediction result is empty")

        llm_client, llm_model_label = create_llm_client(cfg)

        narratives: dict[str, StockNarrative] = {}
        detail_blocks: list[tuple[str, str]] = []

        # Keep rank order.
        sorted_predictions: list[PredictionRecord] = sorted(predictions, key=lambda x: x.rank)

        for pred in sorted_predictions:
            symbol = pred.symbol
            row = predict_frame[predict_frame["symbol"] == symbol]
            if row.empty:
                failed_symbols.append(symbol)
                continue

            feature_row = row.iloc[-1]
            latest_close = float(feature_row["close"])
            feature_snapshot = {
                "ret_1": float(feature_row["ret_1"]),
                "ret_5": float(feature_row["ret_5"]),
                "ma5_ratio": float(feature_row["ma5_ratio"]),
                "ma10_ratio": float(feature_row["ma10_ratio"]),
                "rsi14": float(feature_row["rsi14"]),
                "macd": float(feature_row["macd"]),
            }

            queries = build_stock_news_queries(market=market, symbol=symbol)
            news_items, provider_used = search_news_with_fallback(
                query=queries,
                tavily_api_key=cfg.tavily_api_key,
                brave_api_key=cfg.brave_api_key,
                max_results=5,
            )

            try:
                narrative = generate_stock_narrative(
                    llm_client=llm_client,
                    market=market,
                    prediction=pred,
                    latest_close=latest_close,
                    feature_snapshot=feature_snapshot,
                    news_items=news_items,
                    provider_used=provider_used,
                    language=report_language,
                )
            except LLMError as exc:
                logger.warning("Skip symbol %s due to LLM failure: %s", symbol, exc)
                failed_symbols.append(symbol)
                continue

            narratives[symbol] = narrative
            detail_blocks.append(
                (
                    symbol,
                    render_symbol_detail_markdown(
                        market=market,
                        asof_date=asof_str,
                        prediction=pred,
                        narrative=narrative,
                        language=report_language,
                    ),
                )
            )

        successful_predictions = [p for p in sorted_predictions if p.symbol in narratives]
        market_summary_text: str | None = None

        # Append one market-level overview after all symbol details.
        market_snapshot = build_market_snapshot(
            market=market,
            market_data=market_data,
            asof_date=asof_date,
            market_index_fetch_enabled=cfg.market_index_fetch_enabled,
        )
        market_news_items, market_news_provider = search_news_with_fallback(
            query=market_news_query(market),
            tavily_api_key=cfg.tavily_api_key,
            brave_api_key=cfg.brave_api_key,
            max_results=6,
        )
        try:
            market_narrative = generate_market_narrative(
                llm_client=llm_client,
                market=market,
                asof_date=asof_str,
                market_snapshot=market_snapshot,
                news_items=market_news_items,
                provider_used=market_news_provider,
                language=report_language,
            )
            market_summary_text = market_narrative.summary
            detail_blocks.append(
                (
                    "MARKET",
                    render_market_detail_markdown(
                        market=market,
                        asof_date=asof_str,
                        market_snapshot=market_snapshot,
                        narrative=market_narrative,
                        language=report_language,
                    ),
                )
            )
        except LLMError as exc:
            if _is_en(report_language):
                market_summary_text = f"{market.upper()} market recap generation failed: {exc}"
            else:
                market_summary_text = f"{market.upper()} 大盘复盘生成失败: {exc}"
            logger.warning("Skip market overview due to LLM failure: %s", exc)

        summary_md = render_summary_markdown(
            market=market,
            asof_date=asof_str,
            predictions=successful_predictions,
            narratives=narratives,
            failed_symbols=failed_symbols,
            market_summary=market_summary_text,
            language=report_language,
        )

        details_md = "\n\n---\n\n".join([detail for _, detail in detail_blocks])

        end_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status = "success"
        if failed_symbols and successful_predictions:
            status = "partial"
        elif not successful_predictions:
            status = "failed"
            if sorted_predictions:
                logger.error(
                    "All symbols failed at narrative stage. predictions=%d failed=%d market=%s",
                    len(sorted_predictions),
                    len(failed_symbols),
                    market,
                )

        run_meta = RunMeta(
            run_id=run_id,
            market=market,
            status=status,
            total_symbols=len(symbols),
            success_symbols=len(successful_predictions),
            failed_symbols=len(failed_symbols),
            failed_list=sorted(set(failed_symbols)),
            model_version=bundle.model_version,
            llm_model=llm_model_label,
            search_provider_primary="tavily",
            search_provider_fallback="brave",
            start_time=start_ts,
            end_time=end_ts,
        )

        output_dir = cfg.outputs_root / market / asof_str
        write_outputs(
            output_dir=output_dir,
            summary_markdown=summary_md,
            details_markdown=details_md,
            predictions=successful_predictions,
            run_meta=run_meta,
        )
        logger.info("Outputs written: %s", output_dir)

        if not args.no_telegram:
            sender = TelegramSender(
                bot_token=cfg.telegram_bot_token or "",
                chat_id=cfg.telegram_chat_id or "",
                message_thread_id=cfg.telegram_message_thread_id,
                limit=cfg.detail_message_char_limit,
            )
            sender.send_report(
                summary_title=_summary_title(market, asof_str, report_language),
                summary_markdown=summary_md,
                market_tag=market_tag(market),
                detail_blocks=detail_blocks,
            )

        return 0 if status in {"success", "partial"} else 1

    except Exception as exc:
        end_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        logger.error("Critical failure: %s", exc)
        logger.debug(traceback.format_exc())
        _send_failure_alert(cfg, market, asof_str, _critical_failure_msg(exc, report_language))

        failed_meta = RunMeta(
            run_id=run_id,
            market=market,
            status="failed",
            total_symbols=0,
            success_symbols=0,
            failed_symbols=0,
            failed_list=[],
            model_version="",
            llm_model=llm_model_for_meta,
            search_provider_primary="tavily",
            search_provider_fallback="brave",
            start_time=start_ts,
            end_time=end_ts,
        )

        output_dir = cfg.outputs_root / market / asof_str
        write_outputs(
            output_dir=output_dir,
            summary_markdown=(
                f"# [{market.upper()}] {asof_str} Daily Report Failed\n\n{exc}"
                if _is_en(report_language)
                else f"# [{market.upper()}] {asof_str} 日报失败\n\n{exc}"
            ),
            details_markdown="",
            predictions=[],
            run_meta=failed_meta,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
