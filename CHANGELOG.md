# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-05-10

### Added
- AI prediction engine with ML model + heuristic fallback
- Model CDN download with SHA256 hash verification
- Feature extraction from 12 on-chain/market metrics
- Whale tracking for large wallet movements
- New liquidity pool detection
- Premium subscription mockup
- In-memory cache with TTL and namespace support
- Health check endpoint
- Structured logging with structlog
- Rate limiting (10 requests/user/minute)
- SQLite migrations for signal history

### Changed
- Upgraded to python-telegram-bot v20.7+
- Async/await throughout the codebase
- Pydantic v2 for configuration

### Fixed
- Graceful shutdown signal handling
- Cache TTL per data source

## [1.0.0] - 2026-02-20

### Added
- Initial release
- Basic Telegram bot with /signal command
- DEX Screener integration
- Simple heuristic scoring
