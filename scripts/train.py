"""
Train a custom model on historical pump data.

Generates synthetic training data from historical signals and trains
a simple neural network for signal prediction.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import structlog

from config.constants import MODEL_FILENAME, MODEL_FEATURES_COUNT

logger = structlog.get_logger(__name__)


def generate_synthetic_data(n_samples: int = 5000) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data mimicking real market patterns.

    Args:
        n_samples: Number of training samples.

    Returns:
        Tuple of (features, labels) arrays.
    """
    rng = np.random.default_rng(42)
    X = rng.standard_normal((n_samples, MODEL_FEATURES_COUNT)).astype(np.float32)

    # Create labels based on feature patterns
    # High volume + good buy ratio + positive momentum → BUY (1)
    # Low volume + sell pressure + negative momentum → SELL (0)
    signal = (
        0.3 * X[:, 0]  # volume anomaly
        + 0.2 * X[:, 1]  # liquidity
        - 0.15 * X[:, 2]  # holder concentration (lower = better)
        + 0.2 * X[:, 3]  # buy/sell ratio
        + 0.1 * X[:, 4]  # 1h momentum
        + 0.05 * X[:, 5]  # 24h momentum
    )

    # Normalise to 0-1
    y = 1 / (1 + np.exp(-signal))  # sigmoid
    y = y.astype(np.float32)

    return X, y


def train_model(X: np.ndarray, y: np.ndarray,
                epochs: int = 100, lr: float = 0.01) -> dict[str, np.ndarray]:
    """Train a simple 2-layer network.

    Args:
        X: Feature matrix (n_samples, n_features).
        y: Label vector (n_samples,).
        epochs: Training epochs.
        lr: Learning rate.

    Returns:
        Dict of trained weights.
    """
    rng = np.random.default_rng(42)
    n_features = X.shape[1]
    n_hidden = 8

    # Initialize weights
    W1 = rng.standard_normal((n_features, n_hidden)).astype(np.float32) * 0.1
    b1 = np.zeros(n_hidden, dtype=np.float32)
    W2 = rng.standard_normal((n_hidden, 1)).astype(np.float32) * 0.1
    b2 = np.zeros(1, dtype=np.float32)

    for epoch in range(epochs):
        # Forward pass
        hidden = np.tanh(X @ W1 + b1)
        output = 1 / (1 + np.exp(-(hidden @ W2 + b2).flatten()))

        # Loss (MSE)
        loss = np.mean((output - y) ** 2)

        # Backward pass
        d_output = 2 * (output - y) / len(y)
        d_output = d_output.reshape(-1, 1)

        d_W2 = hidden.T @ (d_output * output.reshape(-1, 1) * (1 - output.reshape(-1, 1)))
        d_b2 = np.sum(d_output * output.reshape(-1, 1) * (1 - output.reshape(-1, 1)), axis=0)

        d_hidden = (d_output * output.reshape(-1, 1) * (1 - output.reshape(-1, 1))) @ W2.T
        d_hidden *= (1 - hidden ** 2)

        d_W1 = X.T @ d_hidden
        d_b1 = np.sum(d_hidden, axis=0)

        # Update
        W1 -= lr * d_W1
        b1 -= lr * d_b1
        W2 -= lr * d_W2
        b2 -= lr * d_b2

        if (epoch + 1) % 20 == 0:
            logger.info("train.epoch", epoch=epoch + 1, loss=f"{loss:.6f}")

    return {
        "weights": W1, "bias": b1,
        "output_weights": W2, "output_bias": b2,
    }


def main():
    parser = argparse.ArgumentParser(description="Train signal prediction model")
    parser.add_argument("--samples", type=int, default=5000, help="Training samples")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate")
    parser.add_argument("--output", default=None, help="Output model path")
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

    output_dir = Path.home() / ".solana_ai" / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else output_dir / MODEL_FILENAME

    logger.info("train.start", samples=args.samples, epochs=args.epochs)

    X, y = generate_synthetic_data(args.samples)
    logger.info("train.data_generated", shape=X.shape)

    model = train_model(X, y, epochs=args.epochs, lr=args.lr)

    np.savez(output_path, **model)
    logger.info("train.saved", path=str(output_path))


if __name__ == "__main__":
    main()
