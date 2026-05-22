"""Tests for the AI prediction engine."""

from __future__ import annotations

import numpy as np
import pytest

from ai.feature_engineer import FeatureEngineer
from ai.token_scorer import TokenScorer
from config.constants import MODEL_FEATURES_COUNT, SIGNAL_BUY_THRESHOLD, SIGNAL_SELL_THRESHOLD


@pytest.fixture
def engineer():
    return FeatureEngineer()


@pytest.fixture
def scorer():
    return TokenScorer()


@pytest.fixture
def sample_pair_data():
    return {
        "name": "TestCoin",
        "symbol": "TEST",
        "address": "TestAddr123",
        "price_usd": 0.001234,
        "volume_24h": 500_000,
        "liquidity_usd": 100_000,
        "price_change_5m": 2.5,
        "price_change_1h": 15.0,
        "price_change_6h": -3.2,
        "price_change_24h": 25.0,
        "pair_address": "PairAddr456",
        "dex": "raydium",
        "pair_created_at": 1700000000000,
        "txns_24h_buys": 1500,
        "txns_24h_sells": 800,
        "fdv": 5_000_000,
        "market_cap": 2_000_000,
    }


class TestFeatureEngineer:
    def test_extract_returns_correct_shape(self, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        assert features.shape == (MODEL_FEATURES_COUNT,)
        assert features.dtype == np.float32

    def test_extract_with_no_holder_data(self, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data, None, None)
        # Holder concentration should be neutral (0.5)
        assert features[2] == pytest.approx(0.5, abs=0.01)

    def test_volume_anomaly_positive(self, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        assert features[0] > 0  # Volume > 0

    def test_buy_sell_ratio(self, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        expected = 1500 / (1500 + 800)
        assert features[3] == pytest.approx(expected, abs=0.01)

    def test_features_are_bounded(self, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        # Most features should be bounded
        assert all(f >= -2 for f in features)
        assert all(f <= 25 for f in features)


class TestTokenScorer:
    def test_score_returns_required_keys(self, scorer, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        result = scorer.score(features, sample_pair_data)
        assert "signal" in result
        assert "confidence" in result
        assert "breakdown" in result
        assert result["signal"] in ("BUY", "SELL", "HOLD")

    def test_confidence_in_range(self, scorer, engineer, sample_pair_data):
        features = engineer.extract(sample_pair_data)
        result = scorer.score(features, sample_pair_data)
        assert 0 <= result["confidence"] <= 100

    def test_low_liquidity_penalized(self, scorer, engineer):
        pair = {
            "symbol": "RUG", "address": "x", "price_usd": 0.0001,
            "volume_24h": 100, "liquidity_usd": 500,
            "price_change_5m": 0, "price_change_1h": 0,
            "price_change_6h": 0, "price_change_24h": 0,
            "txns_24h_buys": 10, "txns_24h_sells": 10,
            "fdv": 1000, "market_cap": 500, "pair_created_at": None,
        }
        features = engineer.extract(pair)
        result = scorer.score(features, pair)
        assert result["confidence"] < 50  # Should be penalized

    def test_strong_buy_signal(self, scorer, engineer):
        pair = {
            "symbol": "MOON", "address": "y", "price_usd": 1.5,
            "volume_24h": 5_000_000, "liquidity_usd": 500_000,
            "price_change_5m": 5, "price_change_1h": 20,
            "price_change_6h": 30, "price_change_24h": 50,
            "txns_24h_buys": 5000, "txns_24h_sells": 1000,
            "fdv": 50_000_000, "market_cap": 30_000_000,
            "pair_created_at": 1600000000000,
        }
        features = engineer.extract(pair)
        result = scorer.score(features, pair)
        assert result["signal"] == "BUY"
        assert result["confidence"] >= SIGNAL_BUY_THRESHOLD
