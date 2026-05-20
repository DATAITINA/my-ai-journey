from __future__ import annotations

import json
import random
from pathlib import Path
import sys
from datetime import datetime, timezone
from typing import Tuple

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.transaction_generation import generate_dataset, set_seed  # noqa: E402


DROP_COLS = {
    "transaction_id",
    "device_id",
    "user_id",
    "ip_address",
    "merchant_id",
    "wallet_token",
    "grant_id",
    "grant_wallet_token",
    "grant_device_id",
    "grant_user_id",
    "signature",
    "grant_signature",
}


def _timestamp_features(ts: str) -> tuple[int, int]:
    dt = datetime.fromisoformat(ts)
    return dt.hour, dt.weekday()


def _build_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    y = df["label"].astype(int)
    X = df.drop(columns=["label"])

    # Replace raw timestamp and high-cardinality identifiers with compact features.
    if "timestamp" in X.columns:
        hours, weekdays = zip(*X["timestamp"].map(_timestamp_features))
        X["tx_hour"] = list(hours)
        X["tx_weekday"] = list(weekdays)
        X = X.drop(columns=["timestamp"])

    X = X.drop(columns=[c for c in DROP_COLS if c in X.columns], errors="ignore")

    # Separate numeric and categorical columns.
    numeric_cols = X.select_dtypes(include=["int64", "float64"]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in numeric_cols]

    X_num = X[numeric_cols]
    X_cat = pd.get_dummies(X[cat_cols], drop_first=False)
    X_all = pd.concat([X_num, X_cat], axis=1)
    return X_all, y


def _train_val_split(
    X: np.ndarray, y: np.ndarray, val_ratio: float = 0.2, seed: int = 42
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    idx = np.arange(X.shape[0])
    rng.shuffle(idx)
    split = int(X.shape[0] * (1 - val_ratio))
    train_idx, val_idx = idx[:split], idx[split:]
    return X[train_idx], y[train_idx], X[val_idx], y[val_idx]


class FraudNet(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(1)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    set_seed(seed)


def train(
    n_samples: int = 8000,
    batch_size: int = 256,
    epochs: int = 10,
    lr: float = 1e-3,
    seed: int = 42,
) -> None:
    _set_seed(seed)
    print(f"Generating synthetic dataset: n_samples={n_samples}")
    data = generate_dataset(n_samples)
    df = pd.DataFrame(data)

    print("Building model features...")
    X_df, y_series = _build_features(df)
    print(f"Feature matrix shape: rows={X_df.shape[0]}, cols={X_df.shape[1]}")
    X = X_df.to_numpy(dtype=np.float32)
    y = y_series.to_numpy(dtype=np.float32)

    X_train, y_train, X_val, y_val = _train_val_split(X, y)

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = FraudNet(input_dim=X.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    last_metrics = {"train_loss": None, "val_loss": None, "val_acc": None}
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * xb.size(0)

        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                logits = model(xb)
                loss = loss_fn(logits, yb)
                val_loss += loss.item() * xb.size(0)
                probs = torch.sigmoid(logits)
                preds = (probs >= 0.5).float()
                correct += (preds == yb).sum().item()
                total += yb.numel()

        train_loss /= len(train_ds)
        val_loss /= len(val_ds)
        val_acc = correct / max(total, 1)
        last_metrics = {"train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc}
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

    model_dir = Path(__file__).parent
    model_dir.mkdir(parents=True, exist_ok=True)

    torch.save(model.state_dict(), model_dir / "fraud_net.pt")
    with open(model_dir / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump({"columns": X_df.columns.tolist()}, f, indent=2)
    with open(model_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "n_samples": n_samples,
                "batch_size": batch_size,
                "epochs": epochs,
                "lr": lr,
                "seed": seed,
                "metrics": last_metrics,
                "feature_count": int(X_df.shape[1]),
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    train()
