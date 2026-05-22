"""
Whale tracker: monitors large wallet movements on Solana.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from blockchain.solana_rpc import SolanaRPC
from config.constants import WHALE_TX_THRESHOLD_SOL
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class WhaleEvent:
    """Represents a single whale transaction event."""

    def __init__(self, wallet: str, token_address: Optional[str],
                 token_symbol: Optional[str], amount_sol: float,
                 amount_usd: float, direction: str, tx_signature: str,
                 timestamp: Optional[int] = None) -> None:
        self.wallet = wallet
        self.token_address = token_address
        self.token_symbol = token_symbol
        self.amount_sol = amount_sol
        self.amount_usd = amount_usd
        self.direction = direction
        self.tx_signature = tx_signature
        self.timestamp = timestamp or int(datetime.now(timezone.utc).timestamp())

    def to_dict(self) -> dict[str, Any]:
        return {
            "wallet": self.wallet, "token_address": self.token_address,
            "token_symbol": self.token_symbol, "amount_sol": self.amount_sol,
            "amount_usd": self.amount_usd, "direction": self.direction,
            "tx_signature": self.tx_signature, "timestamp": self.timestamp,
        }


class WhaleTracker:
    """Tracks large-value transactions on Solana."""

    KNOWN_WHALES: list[str] = [
        "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "7Ppgch9d4XRAygVNJP4bDkc7V6htYXGfghb1QhNgd6Xe",
        "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9",
    ]

    def __init__(self, rpc: SolanaRPC, cache: Optional[CacheManager] = None,
                 sol_price: float = 150.0) -> None:
        self._rpc = rpc
        self._cache = cache
        self._sol_price = sol_price
        self._seen_signatures: set[str] = set()

    def update_sol_price(self, price: float) -> None:
        self._sol_price = price

    async def scan_whale_activity(self, wallets: Optional[list[str]] = None,
                                   limit: int = 10) -> list[WhaleEvent]:
        target_wallets = wallets or self.KNOWN_WHALES
        events: list[WhaleEvent] = []

        for wallet in target_wallets:
            try:
                sigs = await self._rpc.get_signatures(wallet, limit=limit)
                for sig_info in sigs:
                    sig = sig_info.get("signature", "")
                    if sig in self._seen_signatures:
                        continue
                    tx = await self._rpc.get_transaction(sig)
                    if tx is None:
                        continue
                    event = self._parse_transaction(wallet, sig, tx)
                    if event and event.amount_sol >= WHALE_TX_THRESHOLD_SOL:
                        events.append(event)
                        self._seen_signatures.add(sig)
            except Exception as exc:
                logger.error("whale_tracker.scan_error", wallet=wallet[:8], error=str(exc))

        events.sort(key=lambda e: e.amount_sol, reverse=True)
        if self._cache:
            await self._cache.set("whale", "recent_events",
                                   [e.to_dict() for e in events[:20]], ttl=120)
        return events

    def _parse_transaction(self, wallet: str, signature: str,
                            tx: dict[str, Any]) -> Optional[WhaleEvent]:
        try:
            meta = tx.get("meta", {})
            if meta is None or meta.get("err") is not None:
                return None
            pre = meta.get("preBalances", [])
            post = meta.get("postBalances", [])
            if not pre or not post:
                return None
            delta_lamports = post[0] - pre[0]
            delta_sol = abs(delta_lamports) / 1e9
            if delta_sol < WHALE_TX_THRESHOLD_SOL:
                return None
            direction = "buy" if delta_lamports < 0 else "sell"
            return WhaleEvent(
                wallet=wallet, token_address=None, token_symbol=None,
                amount_sol=round(delta_sol, 4),
                amount_usd=round(delta_sol * self._sol_price, 2),
                direction=direction, tx_signature=signature,
                timestamp=tx.get("blockTime"),
            )
        except Exception as exc:
            logger.debug("whale_tracker.parse_error", error=str(exc))
            return None

    async def get_recent_events(self) -> list[dict[str, Any]]:
        if self._cache:
            cached = await self._cache.get("whale", "recent_events")
            if cached:
                return cached
        return []
