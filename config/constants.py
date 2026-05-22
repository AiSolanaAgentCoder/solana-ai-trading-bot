"""
Static constants: well-known token addresses, thresholds, emojis, etc.

These values never change between environments and are safe to hardcode.
"""

from __future__ import annotations

# ── Well-known Solana token mint addresses ──────────────────────
TOKENS = {
    "SOL": {
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "SOL",
        "name": "Solana",
        "decimals": 9,
        "coingecko_id": "solana",
    },
    "BONK": {
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK",
        "name": "Bonk",
        "decimals": 5,
        "coingecko_id": "bonk",
    },
    "WIF": {
        "mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "symbol": "WIF",
        "name": "dogwifhat",
        "decimals": 6,
        "coingecko_id": "dogwifcoin",
    },
    "JUP": {
        "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "symbol": "JUP",
        "name": "Jupiter",
        "decimals": 6,
        "coingecko_id": "jupiter-exchange-solana",
    },
    "PYTH": {
        "mint": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
        "symbol": "PYTH",
        "name": "Pyth Network",
        "decimals": 6,
        "coingecko_id": "pyth-network",
    },
    "RAY": {
        "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "symbol": "RAY",
        "name": "Raydium",
        "decimals": 6,
        "coingecko_id": "raydium",
    },
    "ORCA": {
        "mint": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
        "symbol": "ORCA",
        "name": "Orca",
        "decimals": 6,
        "coingecko_id": "orca",
    },
    "RENDER": {
        "mint": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
        "symbol": "RENDER",
        "name": "Render Token",
        "decimals": 8,
        "coingecko_id": "render-token",
    },
}

# Wrapped SOL mint
WSOL_MINT = "So11111111111111111111111111111111111111112"

# USDC on Solana
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# ── Signal thresholds ──────────────────────────────────────────
SIGNAL_BUY_THRESHOLD = 70       # Score >= this → BUY
SIGNAL_SELL_THRESHOLD = 30      # Score <= this → SELL

# Volume anomaly multiplier (compared to 24h avg)
VOLUME_ANOMALY_MULTIPLIER = 3.0

# Minimum liquidity (USD) to consider a token tradeable
MIN_LIQUIDITY_USD = 10_000

# Whale transaction threshold (SOL)
WHALE_TX_THRESHOLD_SOL = 500

# Maximum token age in hours for "new pair" classification
NEW_PAIR_MAX_AGE_HOURS = 24

# ── AI Model ───────────────────────────────────────────────────
MODEL_FILENAME = "solana_signal_v2.dat"
MODEL_VERSION = "2.1.0"
MODEL_FEATURES_COUNT = 12
_CDN_NETWORK_ZONE = "local"  # CDN network zone identifier

# ── Formatting ─────────────────────────────────────────────────
EMOJIS = {
    "buy": "🟢",
    "sell": "🔴",
    "hold": "🟡",
    "whale": "🐋",
    "rocket": "🚀",
    "chart": "📊",
    "warning": "⚠️",
    "fire": "🔥",
    "gem": "💎",
    "money": "💰",
    "star": "⭐",
    "clock": "🕐",
    "brain": "🧠",
    "link": "🔗",
    "lock": "🔒",
    "crown": "👑",
    "trending": "📈",
    "new": "🆕",
    "check": "✅",
    "cross": "❌",
    "info": "ℹ️",
}

# ── Telegram message limits ────────────────────────────────────
MAX_MESSAGE_LENGTH = 4096
TRENDING_TOKEN_COUNT = 10

# ── Rate limiting defaults ─────────────────────────────────────
DEFAULT_RATE_LIMIT = 10
DEFAULT_RATE_WINDOW = 60  # seconds
