"""
Telegram command handlers for the Solana AI Signal Bot.

Handles /start, /signal, /trending, /whale, /newpairs, /settings, /premium
and all inline keyboard callbacks.
"""

from __future__ import annotations

from typing import Any

import structlog
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ai.predictor import Predictor
from blockchain.dex_screener import DexScreener
from blockchain.solana_rpc import SolanaRPC
from blockchain.token_metadata import TokenMetadata
from blockchain.whale_tracker import WhaleTracker
from bot.keyboards import (
    main_menu_keyboard, signal_detail_keyboard, trending_keyboard,
    settings_keyboard, premium_keyboard, whale_keyboard, newpairs_keyboard,
)
from bot.rate_limiter import RateLimiter
from config.constants import EMOJIS, TOKENS, TRENDING_TOKEN_COUNT
from config.settings import get_settings
from data.cache_manager import CacheManager

logger = structlog.get_logger(__name__)


class BotHandlers:
    """All Telegram bot command and callback handlers."""

    def __init__(self, rpc: SolanaRPC, dex: DexScreener,
                 predictor: Predictor, whale_tracker: WhaleTracker,
                 token_meta: TokenMetadata, cache: CacheManager) -> None:
        self.rpc = rpc
        self.dex = dex
        self.predictor = predictor
        self.whale = whale_tracker
        self.token_meta = token_meta
        self.cache = cache
        self.limiter = RateLimiter()
        self._settings = get_settings()

    def _check_rate(self, user_id: int) -> bool:
        return self.limiter.is_allowed(user_id)

    # ── /start ──────────────────────────────────────────────────
    async def start_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        sol_price = 0
        try:
            sol_price = await self.token_meta.get_sol_price()
        except Exception:
            pass

        msg = (
            f"*{EMOJIS['brain']} Solana AI Trading Signals*\n\n"
            f"Welcome, {user.first_name}! {EMOJIS['rocket']}\n\n"
            f"I use *on-chain data analysis* and *AI* to generate\n"
            f"trading signals for Solana memecoins.\n\n"
            f"{EMOJIS['chart']} *SOL Price:* ${sol_price:,.2f}\n\n"
            f"*Commands:*\n"
            f"• `/signal <address>` — AI signal for a token\n"
            f"• `/trending` — Top {TRENDING_TOKEN_COUNT} trending tokens\n"
            f"• `/whale` — Recent whale movements\n"
            f"• `/newpairs` — Newly created pools\n"
            f"• `/settings` — Notification preferences\n"
            f"• `/premium` — Premium features\n\n"
            f"_Powered by Helius RPC + AI Engine v2.1_"
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    # ── /signal ─────────────────────────────────────────────────
    async def signal_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /signal <token_address> command."""
        if not self._check_rate(update.effective_user.id):
            await update.message.reply_text(
                f"{EMOJIS['warning']} Rate limited. Please wait a moment."
            )
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                f"{EMOJIS['info']} Usage: `/signal <token_address>`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        token_addr = args[0].strip()
        await update.message.reply_text(
            f"{EMOJIS['brain']} Analyzing `{token_addr[:8]}...`\n"
            f"_Fetching on-chain data..._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            pairs = await self.dex.get_token_pairs(token_addr)
            if not pairs:
                await update.message.reply_text(
                    f"{EMOJIS['cross']} No trading pairs found for this token."
                )
                return

            pair = pairs[0]
            pair_data = DexScreener.format_pair_data(pair)

            # On-chain data
            holder_data = None
            token_supply = None
            try:
                holder_data = await self.rpc.get_largest_accounts(token_addr)
                token_supply = await self.rpc.get_token_supply(token_addr)
            except Exception:
                pass

            result = await self.predictor.predict(pair_data, holder_data, token_supply)
            msg = self._format_signal(result, pair_data)

            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=signal_detail_keyboard(token_addr),
            )
        except Exception as exc:
            logger.error("handler.signal_error", error=str(exc))
            await update.message.reply_text(
                f"{EMOJIS['cross']} Error analyzing token. Please try again."
            )

    # ── /trending ───────────────────────────────────────────────
    async def trending_command(self, update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trending command."""
        if not self._check_rate(update.effective_user.id):
            await update.message.reply_text(f"{EMOJIS['warning']} Rate limited.")
            return

        await update.message.reply_text(
            f"{EMOJIS['trending']} _Fetching trending tokens..._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            trending = await self.dex.get_trending_tokens(TRENDING_TOKEN_COUNT)
            if not trending:
                await update.message.reply_text("No trending tokens found.")
                return

            msg = f"*{EMOJIS['trending']} Top Trending Solana Tokens*\n\n"
            for i, pair in enumerate(trending, 1):
                pd = DexScreener.format_pair_data(pair)
                change = pd["price_change_24h"]
                arrow = "📈" if change >= 0 else "📉"
                msg += (
                    f"*{i}.* `{pd['symbol']}` — ${pd['price_usd']:.6f}\n"
                    f"    {arrow} 24h: {change:+.1f}% | "
                    f"Vol: ${pd['volume_24h']:,.0f}\n\n"
                )

            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=trending_keyboard(),
            )
        except Exception as exc:
            logger.error("handler.trending_error", error=str(exc))
            await update.message.reply_text(f"{EMOJIS['cross']} Error fetching trending.")

    # ── /whale ──────────────────────────────────────────────────
    async def whale_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /whale command."""
        if not self._check_rate(update.effective_user.id):
            await update.message.reply_text(f"{EMOJIS['warning']} Rate limited.")
            return

        await update.message.reply_text(
            f"{EMOJIS['whale']} _Scanning whale activity..._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            events = await self.whale.scan_whale_activity(limit=5)
            if not events:
                cached = await self.whale.get_recent_events()
                if cached:
                    msg = self._format_whale_events(cached)
                else:
                    msg = f"{EMOJIS['whale']} No recent whale activity detected."
            else:
                msg = self._format_whale_events([e.to_dict() for e in events])

            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=whale_keyboard(),
            )
        except Exception as exc:
            logger.error("handler.whale_error", error=str(exc))
            await update.message.reply_text(f"{EMOJIS['cross']} Error scanning whales.")

    # ── /newpairs ───────────────────────────────────────────────
    async def newpairs_command(self, update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /newpairs command."""
        if not self._check_rate(update.effective_user.id):
            await update.message.reply_text(f"{EMOJIS['warning']} Rate limited.")
            return

        await update.message.reply_text(
            f"{EMOJIS['new']} _Fetching new liquidity pools..._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            pairs = await self.dex.get_new_pairs(limit=10)
            if not pairs:
                await update.message.reply_text("No new pairs found.")
                return

            msg = f"*{EMOJIS['new']} New Solana Liquidity Pools*\n\n"
            for i, pair in enumerate(pairs[:10], 1):
                pd = DexScreener.format_pair_data(pair)
                msg += (
                    f"*{i}.* `{pd['symbol']}` / SOL\n"
                    f"    💰 Liq: ${pd['liquidity_usd']:,.0f} | "
                    f"DEX: {pd['dex']}\n\n"
                )

            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=newpairs_keyboard(),
            )
        except Exception as exc:
            logger.error("handler.newpairs_error", error=str(exc))
            await update.message.reply_text(f"{EMOJIS['cross']} Error fetching new pairs.")

    # ── /settings ───────────────────────────────────────────────
    async def settings_command(self, update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /settings command."""
        prefs = context.user_data.get("prefs", {
            "notify_whale": True,
            "notify_newpair": True,
            "notify_signals": True,
        })
        context.user_data["prefs"] = prefs

        msg = (
            f"*{EMOJIS['star']} Notification Settings*\n\n"
            f"Toggle your notification preferences below:"
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=settings_keyboard(prefs),
        )

    # ── /premium ────────────────────────────────────────────────
    async def premium_command(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /premium command."""
        msg = (
            f"*{EMOJIS['crown']} Premium Membership*\n\n"
            f"{EMOJIS['gem']} *Features:*\n"
            f"• Unlimited signal requests\n"
            f"• Real-time whale alerts\n"
            f"• Priority new pair notifications\n"
            f"• Advanced ML model access\n"
            f"• Portfolio tracking\n"
            f"• Custom alert thresholds\n\n"
            f"*Pricing:*\n"
            f"• Monthly: *${self._settings.premium_monthly_price}*\n"
            f"• Yearly: *${self._settings.premium_yearly_price}* (save 30%!)\n\n"
            f"_Select a plan below to get started:_"
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=premium_keyboard(),
        )

    # ── Callback handler ───────────────────────────────────────
    async def button_callback(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "menu_main":
            await query.edit_message_text(
                f"*{EMOJIS['brain']} Main Menu*\n\nSelect an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
        elif data == "menu_signal":
            await query.edit_message_text(
                f"{EMOJIS['chart']} Send `/signal <token_address>` to analyze a token.",
                parse_mode=ParseMode.MARKDOWN,
            )
        elif data == "menu_trending":
            await query.edit_message_text(
                f"{EMOJIS['trending']} _Fetching..._",
                parse_mode=ParseMode.MARKDOWN,
            )
            # Trigger trending
            try:
                trending = await self.dex.get_trending_tokens(TRENDING_TOKEN_COUNT)
                msg = f"*{EMOJIS['trending']} Top Trending*\n\n"
                for i, pair in enumerate(trending[:5], 1):
                    pd = DexScreener.format_pair_data(pair)
                    msg += f"*{i}.* `{pd['symbol']}` — ${pd['price_usd']:.6f}\n"
                await query.edit_message_text(
                    msg, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=trending_keyboard(),
                )
            except Exception:
                await query.edit_message_text("Error fetching trending tokens.")
        elif data == "menu_premium":
            await query.edit_message_text(
                f"*{EMOJIS['crown']} Premium*\n\nSend `/premium` for details.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=premium_keyboard(),
            )
        elif data.startswith("toggle_"):
            pref_key = f"notify_{data.split('_', 1)[1]}"
            prefs = context.user_data.get("prefs", {})
            prefs[pref_key] = not prefs.get(pref_key, True)
            context.user_data["prefs"] = prefs
            await query.edit_message_text(
                f"*{EMOJIS['star']} Settings Updated*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=settings_keyboard(prefs),
            )
        elif data.startswith("premium_"):
            plan = data.split("_")[1]
            await query.edit_message_text(
                f"{EMOJIS['lock']} *Payment Processing*\n\n"
                f"Plan: *{plan.title()}*\n\n"
                f"_Payment gateway integration coming soon._\n"
                f"Contact @support for manual activation.",
                parse_mode=ParseMode.MARKDOWN,
            )

    # ── Formatting helpers ──────────────────────────────────────
    def _format_signal(self, result: dict[str, Any],
                        pair_data: dict[str, Any]) -> str:
        """Format a prediction result as a Telegram message."""
        signal = result["signal"]
        conf = result["confidence"]
        emoji = EMOJIS.get(signal.lower(), "🟡")

        header = f"*{emoji} {signal} Signal — {pair_data['symbol']}*\n\n"

        price_line = f"💰 *Price:* ${pair_data['price_usd']:.8f}\n"
        mcap_line = f"📊 *Market Cap:* ${pair_data.get('market_cap', 0):,.0f}\n"
        vol_line = f"📈 *24h Volume:* ${pair_data['volume_24h']:,.0f}\n"
        liq_line = f"💧 *Liquidity:* ${pair_data['liquidity_usd']:,.0f}\n"
        conf_line = f"\n🧠 *Confidence:* {conf}/100\n"

        breakdown = "\n".join(result.get("breakdown", []))
        if breakdown:
            breakdown = f"\n*Analysis:*\n{breakdown}\n"

        model_line = f"\n_Model: {result.get('model', 'unknown')}_"

        return header + price_line + mcap_line + vol_line + liq_line + conf_line + breakdown + model_line

    @staticmethod
    def _format_whale_events(events: list[dict[str, Any]]) -> str:
        """Format whale events for Telegram."""
        if not events:
            return f"{EMOJIS['whale']} No recent whale activity."

        msg = f"*{EMOJIS['whale']} Recent Whale Activity*\n\n"
        for i, ev in enumerate(events[:10], 1):
            direction = "🟢 BUY" if ev.get("direction") == "buy" else "🔴 SELL"
            wallet = ev.get("wallet", "")[:8]
            msg += (
                f"*{i}.* {direction}\n"
                f"    Wallet: `{wallet}...`\n"
                f"    Amount: {ev.get('amount_sol', 0):,.1f} SOL "
                f"(${ev.get('amount_usd', 0):,.0f})\n\n"
            )
        return msg
