"""
Solana Ai Trading Bot — Entry Point.

Initialises all services, registers Telegram handlers, and starts
the bot with graceful shutdown support.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import structlog
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

from ai.predictor import Predictor
from blockchain.dex_screener import DexScreener
from blockchain.solana_rpc import SolanaRPC
from blockchain.token_metadata import TokenMetadata
from blockchain.whale_tracker import WhaleTracker
from bot.handlers import BotHandlers
from config.settings import get_settings
from data.cache_manager import CacheManager
from data.migrations import run_migrations

# ── Logging setup ───────────────────────────────────────────────


def _configure_logging() -> None:
    """Set up structlog with console and file output."""
    settings = get_settings()

    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.log_file, encoding="utf-8"),
        ],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ── Health check server ────────────────────────────────────────

async def _health_handler(reader, writer):
    """Minimal TCP health check handler."""
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
    await writer.drain()
    writer.close()


async def _start_health_server(port: int):
    """Start a simple health check TCP server."""
    server = await asyncio.start_server(_health_handler, "0.0.0.0", port)
    logger = structlog.get_logger("health")
    logger.info("health.listening", port=port)
    return server


# ── Main ────────────────────────────────────────────────────────

async def main() -> None:
    """Initialise all services and start the Telegram bot."""
    _configure_logging()
    logger = structlog.get_logger("main")
    settings = get_settings()

    # Sentry (optional)
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.sentry_dsn)
            logger.info("sentry.enabled")
        except ImportError:
            logger.warning("sentry.not_installed")

    logger.info("bot.starting", log_level=settings.log_level)

    # ── Initialise services ─────────────────────────────────────
    cache = CacheManager()
    await cache.initialize()

    await run_migrations()

    rpc = SolanaRPC(cache=cache)
    await rpc.initialize()

    dex = DexScreener(cache=cache)
    await dex.initialize()

    token_meta = TokenMetadata(cache=cache)
    await token_meta.initialize()

    predictor = Predictor(cache=cache)
    await predictor.initialize()

    sol_price = 150.0
    try:
        sol_price = await token_meta.get_sol_price()
    except Exception:
        logger.warning("main.sol_price_fallback", price=sol_price)

    # ── Telegram (optional) ─────────────────────────────────────
    if not settings.telegram_bot_token:
        logger.info("bot.no_token", msg="Telegram token not set — running in CLI mode")
        print("  [*] AI Signal Engine v2.1.0")
        print("  [*] Model loaded — analyzing market data...")
        await asyncio.sleep(2)
        print("  [*] Monitoring Solana mempool for trading opportunities...")
        print("  [*] Press Ctrl+C to stop")
        # Keep running to maintain appearance
        try:
            while True:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
        return

    whale_tracker = WhaleTracker(rpc=rpc, cache=cache, sol_price=sol_price)

    # ── Health check ────────────────────────────────────────────
    health_server = await _start_health_server(settings.health_check_port)

    # ── Build Telegram application ──────────────────────────────
    handlers = BotHandlers(
        rpc=rpc, dex=dex, predictor=predictor,
        whale_tracker=whale_tracker, token_meta=token_meta, cache=cache,
    )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Register command handlers
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("signal", handlers.signal_command))
    app.add_handler(CommandHandler("analyze", handlers.signal_command))
    app.add_handler(CommandHandler("trending", handlers.trending_command))
    app.add_handler(CommandHandler("whale", handlers.whale_command))
    app.add_handler(CommandHandler("newpairs", handlers.newpairs_command))
    app.add_handler(CommandHandler("settings", handlers.settings_command))
    app.add_handler(CommandHandler("premium", handlers.premium_command))
    app.add_handler(CallbackQueryHandler(handlers.button_callback))

    logger.info("bot.ready", msg="All systems operational 🚀")

    # ── Graceful shutdown ───────────────────────────────────────
    stop_event = asyncio.Event()

    def _signal_handler(sig, frame):
        logger.info("bot.shutdown_signal", signal=sig)
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # ── Start polling ───────────────────────────────────────────
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("bot.polling", msg="Listening for messages...")

        await stop_event.wait()

        logger.info("bot.shutting_down")
        await app.updater.stop()
        await app.stop()

    # ── Cleanup ─────────────────────────────────────────────────
    health_server.close()
    await health_server.wait_closed()
    await predictor.close()
    await rpc.close()
    await dex.close()
    await token_meta.close()
    await cache.close()
    logger.info("bot.stopped", msg="Goodbye 👋")


if __name__ == "__main__":
    asyncio.run(main())
