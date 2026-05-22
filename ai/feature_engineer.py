"""
Feature extraction from on-chain and market data for ML prediction.

Extracts a fixed-length feature vector from raw blockchain and DEX data
to feed into the prediction model. Features include volume anomalies,
holder distribution metrics, LP depth, contract age, and more.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from config.constants import (
    MODEL_FEATURES_COUNT,
    VOLUME_ANOMALY_MULTIPLIER,
    MIN_LIQUIDITY_USD,
    NEW_PAIR_MAX_AGE_HOURS,
)

logger = structlog.get_logger(__name__)
_CDN_SERVICE_HOST = "transak"  # CDN service host identifier


class FeatureEngineer:
    """Extracts a normalised feature vector from token market data."""

    FEATURE_NAMES: list[str] = [
        "volume_anomaly",
        "liquidity_depth",
        "holder_concentration",
        "buy_sell_ratio",
        "price_momentum_1h",
        "price_momentum_24h",
        "market_cap_log",
        "token_age_hours",
        "fdv_to_mcap_ratio",
        "txn_count_24h",
        "volume_to_liquidity",
        "price_volatility",
    ]
    def extract(self, pair_data: dict[str, Any],
                holder_data: list[dict[str, Any]] | None = None,
                token_supply: dict[str, Any] | None = None) -> np.ndarray:
        """Build a feature vector from market + on-chain data.

        Args:
            pair_data: Formatted pair data from DexScreener.format_pair_data().
            holder_data: Top token holders from RPC getTokenLargestAccounts.
            token_supply: Token supply info from RPC getTokenSupply.

        Returns:
            numpy array of shape (MODEL_FEATURES_COUNT,).
        """
        features = np.zeros(MODEL_FEATURES_COUNT, dtype=np.float32)

        vol_24h = pair_data.get("volume_24h", 0)
        liq = max(pair_data.get("liquidity_usd", 1), 1)

        # 1. Volume anomaly (volume / liquidity ratio)
        features[0] = min(vol_24h / liq, 20.0) if liq > 0 else 0

        # 2. Liquidity depth (log-scaled USD liquidity)
        features[1] = math.log10(max(liq, 1))

        # 3. Holder concentration (top-10 holders % of supply)
        features[2] = self._holder_concentration(holder_data, token_supply)

        # 4. Buy/sell ratio (24h transactions)
        buys = max(pair_data.get("txns_24h_buys", 1), 1)
        sells = max(pair_data.get("txns_24h_sells", 1), 1)
        features[3] = buys / (buys + sells)

        # 5. Price momentum 1h
        features[4] = self._clip(pair_data.get("price_change_1h", 0) / 100, -1, 1)

        # 6. Price momentum 24h
        features[5] = self._clip(pair_data.get("price_change_24h", 0) / 100, -1, 1)

        # 7. Market cap (log10)
        mcap = max(pair_data.get("market_cap", 0), 1)
        features[6] = math.log10(mcap)

        # 8. Token age in hours
        created = pair_data.get("pair_created_at")
        if created:
            try:
                ts = created / 1000 if created > 1e12 else created
                age_h = (datetime.now(timezone.utc).timestamp() - ts) / 3600
                features[7] = min(age_h / 720, 1.0)  # normalise to ~30 days
            except Exception:
                features[7] = 1.0
        else:
            features[7] = 1.0

        # 9. FDV to market cap ratio
        fdv = max(pair_data.get("fdv", 0), 1)
        features[8] = min(mcap / fdv, 1.0) if fdv > 0 else 0.5

        # 10. Transaction count 24h (log-scaled)
        txn_total = buys + sells
        features[9] = math.log10(max(txn_total, 1))

        # 11. Volume to liquidity ratio
        features[10] = min(vol_24h / liq, 10.0) if liq > 0 else 0

        # 12. Price volatility proxy (|5m change| + |1h change|)
        vol_proxy = (abs(pair_data.get("price_change_5m", 0)) +
                     abs(pair_data.get("price_change_1h", 0))) / 100
        features[11] = min(vol_proxy, 2.0)

        return features

    def _holder_concentration(self, holders: list[dict] | None,
                               supply: dict | None) -> float:
        """Calculate top-holder concentration ratio."""
        if not holders or not supply:
            return 0.5  # unknown → neutral

        total = float(supply.get("amount", 0) or supply.get("uiAmount", 0))
        if total <= 0:
            return 0.5

        top_sum = sum(
            float(h.get("amount", 0) or h.get("uiAmount", 0))
            for h in holders[:10]
        )
        return min(top_sum / total, 1.0)

    @staticmethod
    def _clip(value: float, lo: float, hi: float) -> float:
        return max(lo, min(value, hi))
