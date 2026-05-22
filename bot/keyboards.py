"""
Telegram inline keyboard builders for the bot UI.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    buttons = [
        [
            InlineKeyboardButton("📊 Get Signal", callback_data="menu_signal"),
            InlineKeyboardButton("📈 Trending", callback_data="menu_trending"),
        ],
        [
            InlineKeyboardButton("🐋 Whale Alert", callback_data="menu_whale"),
            InlineKeyboardButton("🆕 New Pairs", callback_data="menu_newpairs"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            InlineKeyboardButton("👑 Premium", callback_data="menu_premium"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def signal_detail_keyboard(token_address: str) -> InlineKeyboardMarkup:
    """Build keyboard for a signal detail view."""
    buttons = [
        [
            InlineKeyboardButton(
                "🔄 Refresh Signal",
                callback_data=f"refresh_{token_address}",
            ),
            InlineKeyboardButton(
                "📊 Full Analysis",
                callback_data=f"analyze_{token_address}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔗 DEX Screener",
                url=f"https://dexscreener.com/solana/{token_address}",
            ),
            InlineKeyboardButton(
                "🔗 Birdeye",
                url=f"https://birdeye.so/token/{token_address}?chain=solana",
            ),
        ],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def trending_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for trending tokens view."""
    buttons = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_trending"),
        ],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def settings_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    """Build settings toggle keyboard."""
    whale = "✅" if prefs.get("notify_whale", True) else "❌"
    newpair = "✅" if prefs.get("notify_newpair", True) else "❌"
    signals = "✅" if prefs.get("notify_signals", True) else "❌"

    buttons = [
        [InlineKeyboardButton(f"{whale} Whale Alerts", callback_data="toggle_whale")],
        [InlineKeyboardButton(f"{newpair} New Pairs", callback_data="toggle_newpair")],
        [InlineKeyboardButton(f"{signals} Signal Alerts", callback_data="toggle_signals")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def premium_keyboard() -> InlineKeyboardMarkup:
    """Premium subscription keyboard."""
    buttons = [
        [
            InlineKeyboardButton("💳 Monthly — $29.99", callback_data="premium_monthly"),
            InlineKeyboardButton("💳 Yearly — $249.99", callback_data="premium_yearly"),
        ],
        [
            InlineKeyboardButton("🎁 Redeem Code", callback_data="premium_redeem"),
        ],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def whale_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for whale activity view."""
    buttons = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_whale")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def newpairs_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for new pairs view."""
    buttons = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_newpairs")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)
