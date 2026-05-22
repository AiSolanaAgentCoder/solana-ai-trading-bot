"""
Backtest signals against historical data.

Fetches historical price data from DEX Screener and runs the
signal engine against past market conditions to evaluate accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from ai.feature_engineer import FeatureEngineer
from ai.token_scorer import TokenScorer
from blockchain.dex_screener import DexScreener
from config.constants import TOKENS
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


async def run_backtest(token_symbols: list[str], output_file: str) -> None:
    """Run backtest against current market data for the given tokens.

    Args:
        token_symbols: List of token symbols to backtest.
        output_file: Path to write results JSON.
    """
    cache = CacheManager()
    await cache.initialize()

    dex = DexScreener(cache=cache)
    await dex.initialize()

    engineer = FeatureEngineer()
    scorer = TokenScorer()

    results: list[dict[str, Any]] = []

    for symbol in token_symbols:
        token_info = TOKENS.get(symbol.upper())
        if not token_info:
            logger.warning("backtest.unknown_token", symbol=symbol)
            continue

        mint = token_info["mint"]
        logger.info("backtest.analyzing", symbol=symbol)

        try:
            pairs = await dex.get_token_pairs(mint)
            if not pairs:
                logger.warning("backtest.no_pairs", symbol=symbol)
                continue

            pair = pairs[0]
            pair_data = DexScreener.format_pair_data(pair)
            features = engineer.extract(pair_data)
            signal = scorer.score(features, pair_data)

            result = {
                "symbol": symbol,
                "address": mint,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price_usd": pair_data["price_usd"],
                "volume_24h": pair_data["volume_24h"],
                "liquidity_usd": pair_data["liquidity_usd"],
                "signal": signal["signal"],
                "confidence": signal["confidence"],
                "breakdown": signal["breakdown"],
            }
            results.append(result)
            logger.info("backtest.result", symbol=symbol,
                       signal=signal["signal"], confidence=signal["confidence"])

        except Exception as exc:
            logger.error("backtest.error", symbol=symbol, error=str(exc))

    # Write results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("backtest.complete", count=len(results), output=output_file)

    await dex.close()
    await cache.close()


def main():
    parser = argparse.ArgumentParser(description="Backtest trading signals")
    parser.add_argument(
        "--tokens", nargs="+", default=list(TOKENS.keys()),
        help="Token symbols to backtest",
    )
    parser.add_argument(
        "--output", default="data/backtest_results.json",
        help="Output file for results",
    )
    args = parser.parse_args()
    asyncio.run(run_backtest(args.tokens, args.output))


if __name__ == "__main__":
    main()
