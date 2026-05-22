"""
SQLite schema migrations for signal history, user preferences, and analytics.

Uses aiosqlite for async database access. Migrations are idempotent
and safe to re-run: each migration is tracked in a `schema_version` table.
"""

from __future__ import annotations

import aiosqlite
import structlog

logger = structlog.get_logger(__name__)

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Create users table",
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            is_premium      INTEGER DEFAULT 0,
            notify_whale    INTEGER DEFAULT 1,
            notify_newpair  INTEGER DEFAULT 1,
            notify_signals  INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        2,
        "Create signal_history table",
        """
        CREATE TABLE IF NOT EXISTS signal_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            token_address   TEXT NOT NULL,
            token_symbol    TEXT,
            signal          TEXT NOT NULL,
            confidence      REAL NOT NULL,
            price_at_signal REAL,
            features_json   TEXT,
            model_version   TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """,
    ),
    (
        3,
        "Create whale_events table",
        """
        CREATE TABLE IF NOT EXISTS whale_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address  TEXT NOT NULL,
            token_address   TEXT,
            token_symbol    TEXT,
            amount_sol      REAL,
            amount_usd      REAL,
            tx_signature    TEXT UNIQUE,
            direction       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        4,
        "Create new_pairs table",
        """
        CREATE TABLE IF NOT EXISTS new_pairs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_address    TEXT UNIQUE NOT NULL,
            base_token      TEXT,
            quote_token     TEXT,
            dex             TEXT,
            initial_liq_usd REAL,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        """,
    ),
    (
        5,
        "Add indices for performance",
        """
        CREATE INDEX IF NOT EXISTS idx_signal_history_user
            ON signal_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_signal_history_token
            ON signal_history(token_address);
        CREATE INDEX IF NOT EXISTS idx_whale_events_created
            ON whale_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_new_pairs_created
            ON new_pairs(created_at);
        """,
    ),
]


async def _ensure_version_table(db: aiosqlite.Connection) -> None:
    """Create the schema_version tracking table if it doesn't exist."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT,
            applied_at  TEXT DEFAULT (datetime('now'))
        );
        """
    )
    await db.commit()


async def _current_version(db: aiosqlite.Connection) -> int:
    """Return the latest applied migration version (0 if none)."""
    async with db.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def run_migrations(db_path: str = "data/signals.db") -> None:
    """Run all pending migrations against *db_path*.

    Args:
        db_path: Path to the SQLite database file.
    """
    import os
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await _ensure_version_table(db)
        current = await _current_version(db)
        applied = 0

        for version, description, sql in MIGRATIONS:
            if version <= current:
                continue
            logger.info(
                "migration.applying",
                version=version,
                description=description,
            )
            await db.executescript(sql)
            await db.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (version, description),
            )
            await db.commit()
            applied += 1

        if applied:
            logger.info("migration.complete", applied=applied)
        else:
            logger.info("migration.up_to_date", version=current)
