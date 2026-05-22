"""Integration tests for the full signal pipeline."""

from __future__ import annotations

import pytest
import numpy as np

from ai.feature_engineer import FeatureEngineer
from ai.token_scorer import TokenScorer
from blockchain.dex_screener import DexScreener
from bot.rate_limiter import RateLimiter
from config.constants import TOKENS
from data.cache_manager import CacheManager


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed(12345) is True
        assert limiter.is_allowed(12345) is True
        assert limiter.is_allowed(12345) is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed(1) is True
        assert limiter.is_allowed(1) is True
        assert limiter.is_allowed(1) is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed(1) is True
        assert limiter.is_allowed(2) is True
        assert limiter.is_allowed(1) is False

    def test_remaining(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining(1) == 5
        limiter.is_allowed(1)
        assert limiter.remaining(1) == 4

    def test_reset(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed(1)
        assert limiter.is_allowed(1) is False
        limiter.reset(1)
        assert limiter.is_allowed(1) is True


class TestCacheManager:
    @pytest.mark.asyncio
    async def test_in_memory_cache(self):
        cache = CacheManager()
        await cache.initialize()
        await cache.set("test", "key1", {"value": 42}, ttl=60)
        result = await cache.get("test", "key1")
        assert result == {"value": 42}
        await cache.close()

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        cache = CacheManager()
        await cache.initialize()
        result = await cache.get("test", "nonexistent")
        assert result is None
        await cache.close()

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        cache = CacheManager()
        await cache.initialize()
        await cache.set("test", "del_key", "data", ttl=60)
        await cache.delete("test", "del_key")
        result = await cache.get("test", "del_key")
        assert result is None
        await cache.close()


class TestFullPipeline:
    def test_feature_to_signal_pipeline(self):
        """Test the complete feature extraction → scoring pipeline."""
        pair_data = {
            "symbol": "TEST", "address": "addr", "price_usd": 0.01,
            "volume_24h": 1_000_000, "liquidity_usd": 200_000,
            "price_change_5m": 1.5, "price_change_1h": 8.0,
            "price_change_6h": 12.0, "price_change_24h": 15.0,
            "txns_24h_buys": 2000, "txns_24h_sells": 1500,
            "fdv": 10_000_000, "market_cap": 5_000_000,
            "pair_created_at": 1690000000000,
        }

        engineer = FeatureEngineer()
        scorer = TokenScorer()

        features = engineer.extract(pair_data)
        result = scorer.score(features, pair_data)

        assert result["signal"] in ("BUY", "SELL", "HOLD")
        assert 0 <= result["confidence"] <= 100
        assert len(result["breakdown"]) > 0

    def test_known_tokens_exist(self):
        """Verify all known tokens have required fields."""
        for symbol, info in TOKENS.items():
            assert "mint" in info
            assert "symbol" in info
            assert "name" in info
            assert "decimals" in info
            assert len(info["mint"]) > 10
