# Contributing to Solana AI Trading Signals

Thank you for your interest in contributing! This guide will help you
get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/solana-ai-signals.git
cd solana-ai-signals

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys
```

## Code Style

- **Python 3.11+** with type hints on all public functions
- **Docstrings** in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- **Async/await** for all I/O-bound operations
- **structlog** for all logging (no `print()` statements)
- Maximum line length: **100 characters**
- Use `black` for formatting, `ruff` for linting

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_predictor.py -v
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Submit PR with a clear description

## Project Structure

```
solana-ai-signals/
├── bot/          # Telegram bot handlers
├── ai/           # ML prediction engine
├── blockchain/   # Solana RPC & DEX integration
├── data/         # Caching & database
├── config/       # Settings & constants
├── scripts/      # Training & backtesting
└── tests/        # Test suite
```

## Adding a New Command

1. Add the handler method to `bot/handlers.py`
2. Register it in `bot/main.py`
3. Add keyboard buttons in `bot/keyboards.py`
4. Write tests in `tests/`

## Environment Variables

All API keys must come from environment variables. See `.env.example`
for the full list. Never commit secrets to the repository.
