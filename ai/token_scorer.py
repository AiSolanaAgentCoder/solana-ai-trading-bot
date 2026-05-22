"""
Token scorer: heuristic-based scoring when the ML model is unavailable.

Provides a deterministic scoring algorithm based on on-chain metrics
so the bot remains functional even without a trained model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

from config.constants import (
    SIGNAL_BUY_THRESHOLD,
    SIGNAL_SELL_THRESHOLD,
    MIN_LIQUIDITY_USD,
    VOLUME_ANOMALY_MULTIPLIER,
)

logger = structlog.get_logger(__name__)


class TokenScorer:
    """Heuristic scorer for Solana memecoins."""

    @staticmethod
    def score(features: np.ndarray, pair_data: dict[str, Any]) -> dict[str, Any]:
        """Generate a heuristic score and signal from feature vector.

        Args:
            features: Feature array from FeatureEngineer.extract().
            pair_data: Formatted pair data dict.

        Returns:
            Dict with signal, confidence, breakdown.
        """
        score = 50.0  # Start neutral
        breakdown: list[str] = []

        liq = pair_data.get("liquidity_usd", 0)
        vol_24h = pair_data.get("volume_24h", 0)

        # Liquidity check
        if liq < MIN_LIQUIDITY_USD:
            score -= 20
            breakdown.append(f"⚠️ Low liquidity: ${liq:,.0f}")
        elif liq > 100_000:
            score += 10
            breakdown.append(f"✅ Strong liquidity: ${liq:,.0f}")

        # Volume anomaly
        vol_ratio = features[0]
        if vol_ratio > VOLUME_ANOMALY_MULTIPLIER:
            score += 15
            breakdown.append(f"🔥 Volume anomaly: {vol_ratio:.1f}x")
        elif vol_ratio < 0.3:
            score -= 10
            breakdown.append("📉 Low volume activity")

        # Buy/sell ratio
        bs_ratio = features[3]
        if bs_ratio > 0.65:
            score += 12
            breakdown.append(f"🟢 Strong buy pressure: {bs_ratio:.0%}")
        elif bs_ratio < 0.35:
            score -= 12
            breakdown.append(f"🔴 Heavy sell pressure: {bs_ratio:.0%}")

        # Price momentum 1h
        mom_1h = pair_data.get("price_change_1h", 0)
        if mom_1h > 10:
            score += 8
            breakdown.append(f"📈 1h momentum: +{mom_1h:.1f}%")
        elif mom_1h < -10:
            score -= 8
            breakdown.append(f"📉 1h drop: {mom_1h:.1f}%")

        # Price momentum 24h
        mom_24h = pair_data.get("price_change_24h", 0)
        if mom_24h > 20:
            score += 5
            breakdown.append(f"📈 24h gain: +{mom_24h:.1f}%")
        elif mom_24h < -20:
            score -= 5
            breakdown.append(f"📉 24h loss: {mom_24h:.1f}%")

        # Holder concentration
        concentration = features[2]
        if concentration > 0.8:
            score -= 15
            breakdown.append("⚠️ High holder concentration (rug risk)")
        elif concentration < 0.4:
            score += 5
            breakdown.append("✅ Well-distributed holders")

        # Token age
        age_norm = features[7]
        if age_norm < 0.01:  # Very new (< ~7 hours)
            score -= 10
            breakdown.append("🆕 Very new token (high risk)")
        elif age_norm > 0.5:
            score += 3
            breakdown.append("✅ Established token")

        # Volatility
        volatility = features[11]
        if volatility > 1.0:
            score -= 5
            breakdown.append(f"⚡ High volatility: {volatility:.1f}")

        # Clamp score
        score = max(0, min(100, score))

        # Determine signal
        if score >= SIGNAL_BUY_THRESHOLD:
            signal = "BUY"
        elif score <= SIGNAL_SELL_THRESHOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        return {
            "signal": signal,
            "confidence": round(score, 1),
            "breakdown": breakdown,
            "model": "heuristic_v1",
        }
