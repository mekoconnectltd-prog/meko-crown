from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

RANDOM_SEED = 42
FEATURE_NAMES = [
    "asset_value",
    "deposit",
    "deposit_pct",
    "finance",
    "rate",
    "term",
    "monthly",
    "annual",
    "noi",
    "coverage",
    "credit",
    "battery",
    "age",
]
MODEL_PATH = Path(__file__).with_name("model.pkl")


def generate_data(n: int = 10_000) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []

    for _ in range(n):
        asset_value = rng.uniform(50_000, 2_000_000)
        deposit_pct = rng.uniform(0.05, 0.40)
        deposit = asset_value * deposit_pct
        finance = asset_value - deposit
        rate = rng.uniform(5, 12)
        term = int(rng.choice([36, 48, 60, 72, 84, 120]))
        noi = asset_value * rng.uniform(0.06, 0.35)
        credit = int(rng.integers(550, 800))
        battery = rng.uniform(80, 100)
        age = int(rng.integers(0, 7))

        monthly_rate = rate / 100 / 12
        monthly = (finance * monthly_rate) / (
            1 - (1 + monthly_rate) ** -term
        )
        annual = monthly * 12
        coverage = noi / annual

        default_probability = 0.02
        if coverage < 1.0:
            default_probability += 0.20
        elif coverage < 1.15:
            default_probability += 0.10
        elif coverage < 1.25:
            default_probability += 0.04
        if credit < 650:
            default_probability += 0.10
        if battery < 90:
            default_probability += 0.08
        if deposit_pct < 0.15:
            default_probability += 0.05

        default = int(rng.random() < default_probability)
        rows.append([
            asset_value,
            deposit,
            deposit_pct,
            finance,
            rate,
            term,
            monthly,
            annual,
            noi,
            coverage,
            credit,
            battery,
            age,
            default,
        ])

    return pd.DataFrame(rows, columns=FEATURE_NAMES + ["default"])


def train_model(n: int = 20_000, output_path: Path = MODEL_PATH) -> float:
    df = generate_data(n)
    X = df[FEATURE_NAMES]
    y = df["default"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    predictions = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, predictions)
    joblib.dump(model, output_path)
    return float(auc)


if __name__ == "__main__":
    auc = train_model()
    print(f"ROC AUC: {auc:.4f}")
    print(f"Model saved to {MODEL_PATH}")
