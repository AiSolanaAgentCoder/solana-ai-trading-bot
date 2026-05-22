"""Tests for the Solana RPC client."""

from __future__ import annotations

import pytest
import httpx

from blockchain.solana_rpc import SolanaRPC, SolanaRPCError


class TestSolanaRPC:
    @pytest.fixture
    def rpc(self):
        return SolanaRPC(cache=None)

    def test_rpc_initializes(self, rpc):
        assert rpc._client is None
        assert rpc._settings is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self, rpc):
        await rpc.initialize()
        assert rpc._client is not None
        await rpc.close()

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self, rpc):
        await rpc.close()  # Should not raise

    def test_rpc_error_exception(self):
        err = SolanaRPCError("test error")
        assert str(err) == "test error"
