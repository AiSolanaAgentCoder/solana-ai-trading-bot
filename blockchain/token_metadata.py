"""
Token metadata provider using Birdeye, CoinGecko, and on-chain data.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import TOKENS
from config.settings import get_settings
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class TokenMetadata:
    """Fetches and caches token metadata from multiple sources."""

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._settings = get_settings()
        self._cache = cache
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=10),
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def get_known_token(self, symbol_or_mint: str) -> Optional[dict[str, Any]]:
        """Look up a token from the hardcoded list."""
        upper = symbol_or_mint.upper()
        if upper in TOKENS:
            return TOKENS[upper]
        for info in TOKENS.values():
            if info["mint"] == symbol_or_mint:
                return info
        return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_sol_price(self) -> float:
        """Fetch current SOL price from CoinGecko."""
        if self._cache:
            cached = await self._cache.get("prices", "sol_usd")
            if cached is not None:
                return cached

        if self._client is None:
            await self.initialize()

        url = f"{self._settings.coingecko_api_url}/simple/price"
        resp = await self._client.get(url, params={"ids": "solana", "vs_currencies": "usd"})
        resp.raise_for_status()
        price = resp.json().get("solana", {}).get("usd", 0)

        if self._cache and price:
            await self._cache.set("prices", "sol_usd", price, ttl=30)

        return float(price)

    async def get_token_info(self, mint_address: str) -> dict[str, Any]:
        """Get comprehensive token info from Birdeye + fallback."""
        if self._cache:
            cached = await self._cache.get("metadata", f"token:{mint_address}")
            if cached:
                return cached

        # Check known tokens first
        known = None
        for info in TOKENS.values():
            if info["mint"] == mint_address:
                known = info
                break

        info: dict[str, Any] = {
            "address": mint_address,
            "symbol": known["symbol"] if known else "UNKNOWN",
            "name": known["name"] if known else "Unknown Token",
            "decimals": known["decimals"] if known else 9,
        }

        # Try Birdeye API
        if self._settings.birdeye_api_key:
            try:
                birdeye_info = await self._fetch_birdeye(mint_address)
                if birdeye_info:
                    info.update(birdeye_info)
            except Exception as exc:
                logger.debug("token_metadata.birdeye_error", error=str(exc))

        if self._cache:
            await self._cache.set("metadata", f"token:{mint_address}", info)

        return info

    async def _fetch_birdeye(self, mint: str) -> Optional[dict[str, Any]]:
        """Fetch token metadata from Birdeye."""
        if self._client is None:
            await self.initialize()

        url = f"{self._settings.birdeye_api_url}/defi/token_overview"
        headers = {"X-API-KEY": self._settings.birdeye_api_key}
        resp = await self._client.get(url, params={"address": mint}, headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        if not data:
            return None

        return {
            "symbol": data.get("symbol", ""),
            "name": data.get("name", ""),
            "decimals": data.get("decimals", 9),
            "holder_count": data.get("holder", 0),
            "market_cap": data.get("mc", 0),
            "price_usd": data.get("price", 0),
            "volume_24h": data.get("v24hUSD", 0),
            "logo_uri": data.get("logoURI", ""),
        }

    async def get_jupiter_quote(self, input_mint: str, output_mint: str,
                                  amount: int) -> Optional[dict[str, Any]]:
        """Get a swap quote from Jupiter aggregator."""
        if self._client is None:
            await self.initialize()

        try:
            url = f"{self._settings.jupiter_api_url}/quote"
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": "50",
            }
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("token_metadata.jupiter_error", error=str(exc))
            return None
