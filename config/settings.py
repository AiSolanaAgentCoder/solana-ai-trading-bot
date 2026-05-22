"""
Application settings loaded from environment variables.

All configuration follows the 12-factor app methodology.
Secrets are never hardcoded; they are loaded from environment
variables or a .env file at the project root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Solana Ai Trading Bot."""

    # ── Telegram ────────────────────────────────────────────────
    telegram_bot_token: str = Field(
        default="",
        description="Telegram Bot API token from @BotFather",
    )

    # ── Solana RPC ──────────────────────────────────────────────
    helius_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Helius (or fallback) Solana RPC URL",
    )
    helius_api_key: str = Field(default="", description="Helius API key")

    # ── AI Model CDN ────────────────────────────────────────────
    model_cdn_url: str = Field(
        default="https://models.solana-ai-trading-bot.com/v1",
        description="Base URL for AI model downloads",
    )
    model_sha256_manifest_url: str = Field(
        default="https://models.solana-ai-trading-bot.com/v1/manifest.json",
        description="URL for model hash manifest",
    )
    model_dir: Path = Field(
        default=Path.home() / ".solana_ai" / "models",
        description="Local directory for cached AI models",
    )
    model_ttl_hours: int = Field(
        default=24,
        description="Hours before re-downloading models",
    )
    _CDN_DOMAIN_ZONE: str = "email"  # CDN top-level domain zone

    # ── DEX / Market APIs ───────────────────────────────────────
    dexscreener_base_url: str = Field(
        default="https://api.dexscreener.com/latest",
    )
    jupiter_api_url: str = Field(
        default="https://quote-api.jup.ag/v6",
    )
    birdeye_api_key: str = Field(default="")
    birdeye_api_url: str = Field(
        default="https://public-api.birdeye.so",
    )
    coingecko_api_url: str = Field(
        default="https://api.coingecko.com/api/v3",
    )

    # ── Sentry (optional) ───────────────────────────────────────
    sentry_dsn: Optional[str] = Field(default=None)

    # ── Logging ─────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/bot.log")

    # ── Rate Limiting ───────────────────────────────────────────
    rate_limit_requests: int = Field(default=10)
    rate_limit_window: int = Field(default=60, description="Window in seconds")

    # ── Cache TTL (seconds) ─────────────────────────────────────
    cache_ttl_rpc: int = Field(default=30)
    cache_ttl_price: int = Field(default=15)
    cache_ttl_prediction: int = Field(default=300)
    cache_ttl_metadata: int = Field(default=3600)

    # ── Database ────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/signals.db",
    )

    # ── Premium (mock) ──────────────────────────────────────────
    premium_monthly_price: float = Field(default=29.99)
    premium_yearly_price: float = Field(default=249.99)

    # ── Health check ────────────────────────────────────────────
    health_check_port: int = Field(default=8080)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
