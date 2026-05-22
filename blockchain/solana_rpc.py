"""
Solana RPC client with retry logic and connection pooling.

Wraps Helius / QuickNode / public RPC endpoints for high-throughput
Solana queries. All calls are async and include automatic retry with
exponential backoff via tenacity.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import get_settings
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class SolanaRPCError(Exception):
    """Raised when an RPC call fails after retries."""
    pass


class SolanaRPC:
    """Async Solana JSON-RPC client with caching and retry.

    Args:
        cache: Optional CacheManager for response caching.
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        self._settings = get_settings()
        self._cache = cache
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Create the HTTP client pool."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"Content-Type": "application/json"},
        )
        logger.info("solana_rpc.initialized", url=self._settings.helius_rpc_url[:50])

    async def close(self) -> None:
        """Gracefully close the HTTP client."""
        if self._client:
            await self._client.aclose()
            logger.info("solana_rpc.closed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _call_rpc(self, method: str, params: list[Any] | None = None) -> Any:
        """Execute a JSON-RPC call against the Solana endpoint."""
        if self._client is None:
            await self.initialize()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }

        resp = await self._client.post(self._settings.helius_rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise SolanaRPCError(f"RPC error: {data['error']}")

        return data.get("result")

    async def get_balance(self, address: str) -> float:
        """Return the SOL balance for *address* in SOL (not lamports).

        Args:
            address: Base58-encoded Solana public key.

        Returns:
            Balance in SOL.
        """
        if self._cache:
            cached = await self._cache.get("rpc", f"balance:{address}")
            if cached is not None:
                return cached

        result = await self._call_rpc("getBalance", [address])
        balance_sol = result["value"] / 1e9

        if self._cache:
            await self._cache.set("rpc", f"balance:{address}", balance_sol)

        return balance_sol

    async def get_token_accounts(self, address: str) -> list[dict[str, Any]]:
        """Get all SPL token accounts for a wallet.

        Args:
            address: Wallet public key.

        Returns:
            List of token account dicts with mint, amount, decimals.
        """
        result = await self._call_rpc(
            "getTokenAccountsByOwner",
            [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        )

        accounts = []
        for item in result.get("value", []):
            info = item["account"]["data"]["parsed"]["info"]
            accounts.append(
                {
                    "mint": info["mint"],
                    "amount": int(info["tokenAmount"]["amount"]),
                    "decimals": info["tokenAmount"]["decimals"],
                    "ui_amount": info["tokenAmount"].get("uiAmount", 0),
                }
            )
        return accounts

    async def get_signatures(
        self, address: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get recent transaction signatures for an address.

        Args:
            address: Solana public key.
            limit: Maximum number of signatures to return.

        Returns:
            List of signature dicts.
        """
        result = await self._call_rpc(
            "getSignaturesForAddress",
            [address, {"limit": limit}],
        )
        return result or []

    async def get_transaction(self, signature: str) -> Optional[dict[str, Any]]:
        """Fetch a parsed transaction by signature.

        Args:
            signature: Transaction signature (base58).

        Returns:
            Parsed transaction dict, or None if not found.
        """
        try:
            result = await self._call_rpc(
                "getTransaction",
                [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            )
            return result
        except SolanaRPCError:
            return None

    async def get_slot(self) -> int:
        """Return the current slot number."""
        return await self._call_rpc("getSlot")

    async def get_block_time(self, slot: int) -> Optional[int]:
        """Return the Unix timestamp for a given slot."""
        try:
            return await self._call_rpc("getBlockTime", [slot])
        except SolanaRPCError:
            return None

    async def get_account_info(self, address: str) -> Optional[dict[str, Any]]:
        """Fetch account info for a given address.

        Args:
            address: Solana public key.

        Returns:
            Account info dict, or None.
        """
        if self._cache:
            cached = await self._cache.get("rpc", f"account:{address}")
            if cached is not None:
                return cached

        result = await self._call_rpc(
            "getAccountInfo",
            [address, {"encoding": "jsonParsed"}],
        )

        if result and result.get("value"):
            if self._cache:
                await self._cache.set("rpc", f"account:{address}", result["value"])
            return result["value"]
        return None

    async def get_token_supply(self, mint: str) -> dict[str, Any]:
        """Get the total supply of a token.

        Args:
            mint: Token mint address.

        Returns:
            Dict with amount, decimals, uiAmount.
        """
        result = await self._call_rpc("getTokenSupply", [mint])
        return result.get("value", {})

    async def get_largest_accounts(self, mint: str) -> list[dict[str, Any]]:
        """Get the 20 largest token accounts for a mint.

        Args:
            mint: Token mint address.

        Returns:
            List of {address, amount} dicts, sorted by amount desc.
        """
        if self._cache:
            cached = await self._cache.get("rpc", f"largest:{mint}")
            if cached is not None:
                return cached

        result = await self._call_rpc("getTokenLargestAccounts", [mint])
        accounts = result.get("value", [])

        if self._cache:
            await self._cache.set("rpc", f"largest:{mint}", accounts, ttl=120)

        return accounts
