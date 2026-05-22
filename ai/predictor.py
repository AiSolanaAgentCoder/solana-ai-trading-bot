"""
ML prediction engine: orchestrates feature extraction, model inference,
and signal generation. Falls back to heuristic scoring if model unavailable.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import structlog

from ai.feature_engineer import FeatureEngineer
from ai.model_loader import ModelLoader
from ai.token_scorer import TokenScorer
from config.constants import MODEL_FEATURES_COUNT, SIGNAL_BUY_THRESHOLD, SIGNAL_SELL_THRESHOLD
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class Predictor:
    """Main prediction engine that combines ML model with heuristic fallback.

    Args:
        cache: Optional CacheManager for prediction caching.
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._cache = cache
        self._model_loader = ModelLoader()
        self._feature_engineer = FeatureEngineer()
        self._scorer = TokenScorer()
        self._use_model = False

    async def initialize(self) -> None:
        """Initialize the prediction engine and load models."""
        self._use_model = await self._model_loader.initialize()
        mode = "ML model" if self._use_model else "heuristic"
        logger.info("predictor.ready", mode=mode)

    async def predict(self, pair_data: dict[str, Any],
                      holder_data: list[dict] | None = None,
                      token_supply: dict | None = None) -> dict[str, Any]:
        """Generate a trading signal for a token.

        Args:
            pair_data: Formatted pair data from DexScreener.
            holder_data: Top holders from RPC.
            token_supply: Token supply info from RPC.

        Returns:
            Dict with signal, confidence, breakdown, model info.
        """
        token_addr = pair_data.get("address", "unknown")

        # Check cache
        if self._cache:
            cached = await self._cache.get("predictions", token_addr)
            if cached:
                logger.debug("predictor.cache_hit", token=token_addr)
                return cached

        # Extract features
        features = self._feature_engineer.extract(pair_data, holder_data, token_supply)

        # Run prediction
        if self._use_model and self._model_loader.model is not None:
            result = self._ml_predict(features, pair_data)
        else:
            result = self._scorer.score(features, pair_data)

        result["token_address"] = token_addr
        result["token_symbol"] = pair_data.get("symbol", "???")
        result["price_usd"] = pair_data.get("price_usd", 0)

        # Cache result
        if self._cache:
            await self._cache.set("predictions", token_addr, result)

        logger.info("predictor.signal", token=pair_data.get("symbol"),
                    signal=result["signal"], confidence=result["confidence"])

        return result

    def _ml_predict(self, features: np.ndarray,
                     pair_data: dict[str, Any]) -> dict[str, Any]:
        """Run inference using the loaded ML model."""
        try:
            model = self._model_loader.model
            weights = model.get("weights", np.eye(12, 8))
            bias = model.get("bias", np.zeros(8))
            out_w = model.get("output_weights", np.ones((8, 1)))
            out_b = model.get("output_bias", np.zeros(1))

            # Simple forward pass
            hidden = np.tanh(features @ weights + bias)
            raw_score = float(np.sigmoid(hidden @ out_w + out_b)[0]) * 100

            score = max(0, min(100, raw_score))

            if score >= SIGNAL_BUY_THRESHOLD:
                signal = "BUY"
            elif score <= SIGNAL_SELL_THRESHOLD:
                signal = "SELL"
            else:
                signal = "HOLD"

            return {
                "signal": signal,
                "confidence": round(score, 1),
                "breakdown": [f"🧠 ML model prediction: {score:.1f}/100"],
                "model": f"ml_v{self._model_loader._settings.model_cdn_url.split('/')[-1]}",
            }

        except Exception as exc:
            logger.error("predictor.ml_error", error=str(exc), fallback="heuristic")
            return self._scorer.score(features, pair_data)

    async def close(self) -> None:
        """Clean up predictor resources."""
        await self._model_loader.close()
