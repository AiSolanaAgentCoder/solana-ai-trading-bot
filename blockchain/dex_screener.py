"""
DEX Screener API client for real-time price, volume, and liquidity data.

Wraps the free DEX Screener API (https://docs.dexscreener.com) to
fetch pair information, trending tokens, and newly created pools on Solana.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class DexScreener:
    """Async DEX Screener API client.

    Args:
        cache: Optional CacheManager instance.
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._settings = get_settings()
        self._cache = cache
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = self._settings.dexscreener_base_url

    async def initialize(self) -> None:
        """Create the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            limits=httpx.Limits(max_connections=10),
        )
        logger.info("dex_screener.initialized")

    async def close(self) -> None:
        """Gracefully close connections."""
        if self._client:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _get(self, path: str) -> dict[str, Any]:
        """Perform a GET request to DEX Screener."""
        if self._client is None:
            await self.initialize()
        url = f"{self._base_url}{path}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_pair_by_address(self, pair_address: str) -> Optional[dict[str, Any]]:
        """Fetch a pair's full data by its pair address.

        Args:
            pair_address: DEX pair contract address.

        Returns:
            Pair data dict, or None.
        """
        if self._cache:
            cached = await self._cache.get("prices", f"pair:{pair_address}")
            if cached:
                return cached

        data = await self._get(f"/dex/pairs/solana/{pair_address}")
        pair = data.get("pair") or (data.get("pairs", [None])[0] if data.get("pairs") else None)

        if pair and self._cache:
            await self._cache.set("prices", f"pair:{pair_address}", pair)

        return pair

    async def search_token(self, query: str) -> list[dict[str, Any]]:
        """Search for tokens / pairs by name, symbol, or address.

        Args:
            query: Search query string.

        Returns:
            List of matching pair dicts.
        """
        if self._cache:
            cached = await self._cache.get("prices", f"search:{query}")
            if cached:
                return cached

        data = await self._get(f"/dex/search?q={query}")
        pairs = data.get("pairs", [])

        # Filter Solana pairs only
        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]

        if self._cache:
            await self._cache.set("prices", f"search:{query}", solana_pairs, ttl=30)

        return solana_pairs

    async def get_token_pairs(self, token_address: str) -> list[dict[str, Any]]:
        """Get all trading pairs for a token on Solana.

        Args:
            token_address: Token mint address.

        Returns:
            List of pair data dicts sorted by liquidity desc.
        """
        if self._cache:
            cached = await self._cache.get("prices", f"token_pairs:{token_address}")
            if cached:
                return cached

        data = await self._get(f"/dex/tokens/{token_address}")
        pairs = data.get("pairs", [])

        # Filter Solana and sort by liquidity
        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        solana_pairs.sort(
            key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
            reverse=True,
        )

        if self._cache:
            await self._cache.set("prices", f"token_pairs:{token_address}", solana_pairs)

        return solana_pairs

    async def get_trending_tokens(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get trending Solana tokens based on recent volume and price action.

        Uses the search endpoint for popular memecoins + sorts by volume.

        Args:
            limit: Number of tokens to return.

        Returns:
            Top tokens with price & volume data.
        """
        if self._cache:
            cached = await self._cache.get("prices", "trending")
            if cached:
                return cached[:limit]

        # Query popular Solana tokens
        search_terms = ["SOL", "BONK", "WIF", "JUP", "PYTH", "RAY", "ORCA", "RENDER"]
        all_pairs: list[dict[str, Any]] = []

        tasks = [self.search_token(term) for term in search_terms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_pairs.extend(result)

        # Deduplicate by base token address
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for pair in all_pairs:
            base = pair.get("baseToken", {}).get("address", "")
            if base and base not in seen:
                seen.add(base)
                unique.append(pair)

        # Sort by 24h volume descending
        unique.sort(
            key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0),
            reverse=True,
        )

        result_list = unique[:limit]

        if self._cache:
            await self._cache.set("prices", "trending", result_list, ttl=60)

        return result_list

    async def get_new_pairs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get newly created Solana liquidity pools.

        Args:
            limit: Number of new pairs to return.

        Returns:
            List of new pair dicts sorted by creation time desc.
        """
        if self._cache:
            cached = await self._cache.get("prices", "new_pairs")
            if cached:
                return cached[:limit]

        # DEX Screener's latest pairs endpoint
        try:
            data = await self._get("/dex/pairs/solana")
            pairs = data.get("pairs", [])

            # Sort by creation time, newest first
            pairs.sort(
                key=lambda p: p.get("pairCreatedAt", 0),
                reverse=True,
            )

            result_list = pairs[:limit]

            if self._cache:
                await self._cache.set("prices", "new_pairs", result_list, ttl=60)

            return result_list
        except Exception as exc:
            logger.error("dex_screener.new_pairs_error", error=str(exc))
            return []

    @staticmethod
    def format_pair_data(pair: dict[str, Any]) -> dict[str, Any]:
        """Extract and format key metrics from a pair dict.

        Args:
            pair: Raw pair data from DEX Screener.

        Returns:
            Cleaned dict with price, volume, liquidity, changes.
        """
        base = pair.get("baseToken", {})
        price_usd = float(pair.get("priceUsd", 0) or 0)
        volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        price_change = pair.get("priceChange", {})

        return {
            "name": base.get("name", "Unknown"),
            "symbol": base.get("symbol", "???"),
            "address": base.get("address", ""),
            "price_usd": price_usd,
            "volume_24h": volume_24h,
            "liquidity_usd": liquidity_usd,
            "price_change_5m": float(price_change.get("m5", 0) or 0),
            "price_change_1h": float(price_change.get("h1", 0) or 0),
            "price_change_6h": float(price_change.get("h6", 0) or 0),
            "price_change_24h": float(price_change.get("h24", 0) or 0),
            "pair_address": pair.get("pairAddress", ""),
            "dex": pair.get("dexId", "unknown"),
            "pair_created_at": pair.get("pairCreatedAt"),
            "txns_24h_buys": pair.get("txns", {}).get("h24", {}).get("buys", 0),
            "txns_24h_sells": pair.get("txns", {}).get("h24", {}).get("sells", 0),
            "fdv": float(pair.get("fdv", 0) or 0),
            "market_cap": float(pair.get("marketCap", 0) or 0),
        }
