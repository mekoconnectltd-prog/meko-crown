from pathlib import Path
from typing import List, Optional

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Underwriting AI")

MODEL_PATH = Path(__file__).with_name("model.pkl")
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
MODEL_WEIGHT = 0.30
RULE_WEIGHT = 1.0 - MODEL_WEIGHT

model = None


class DealInput(BaseModel):
    asset_value: float
    deposit: float
    finance_amount: float
    interest_rate: float
    term_months: int
    noi: float
    asset_type: str
    tenant_credit_score: Optional[int] = None
    battery_health: Optional[float] = None
    vehicle_age: Optional[int] = None


class DealOutput(BaseModel):
    monthly_payment: float
    annual_payment: float
    coverage_ratio: float
    risk_score: int
    decision: str
    reasons: List[str]


def monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Calculate a monthly amortizing payment."""
    if term_months == 0:
        raise ValueError("term_months cannot be zero")

    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        return principal / term_months
    return (principal * monthly_rate) / (
        1 - (1 + monthly_rate) ** -term_months
    )


def build_model_features(
    deal: DealInput,
    monthly: float,
    annual: float,
    coverage: float,
) -> pd.DataFrame:
    """Build the exact ordered feature schema used by train_model.py."""
    deposit_pct = deal.deposit / deal.asset_value if deal.asset_value > 0 else 0.0

    # The training data has no missing values. Neutral defaults keep inference
    # deterministic when optional API fields are omitted.
    credit = deal.tenant_credit_score if deal.tenant_credit_score is not None else 700
    battery = (
        deal.battery_health
        if deal.asset_type == "EV_FLEET" and deal.battery_health is not None
        else 100.0
    )
    age = deal.vehicle_age if deal.vehicle_age is not None else 0

    values = [[
        deal.asset_value,
        deal.deposit,
        deposit_pct,
        deal.finance_amount,
        deal.interest_rate,
        deal.term_months,
        monthly,
        annual,
        deal.noi,
        coverage,
        credit,
        battery,
        age,
    ]]
    return pd.DataFrame(values, columns=FEATURE_NAMES)


def model_default_probability(
    deal: DealInput,
    monthly: float,
    annual: float,
    coverage: float,
) -> Optional[float]:
    """Return a validated model probability, or None if no usable model exists."""
    if model is None:
        return None

    try:
        features = build_model_features(deal, monthly, annual, coverage)
        probability = float(model.predict_proba(features)[0][1])
        if not 0 <= probability <= 1:
            return None
        return probability
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def underwrite(deal: DealInput) -> DealOutput:
    monthly = monthly_payment(
        deal.finance_amount,
        deal.interest_rate,
        deal.term_months,
    )
    annual = monthly * 12
    coverage = deal.noi / annual if annual > 0 else 0

    reasons: List[str] = []
    rule_points = 0

    if coverage < 1.0:
        rule_points += 40
        reasons.append("Coverage ratio below 1.0x")
    elif coverage < 1.15:
        rule_points += 25
        reasons.append("Coverage ratio below 1.15x")
    elif coverage < 1.25:
        rule_points += 10
        reasons.append("Coverage ratio below target 1.25x")

    deposit_pct = deal.deposit / deal.asset_value if deal.asset_value > 0 else 0
    if deposit_pct < 0.1:
        rule_points += 20
        reasons.append("Deposit below 10%")
    elif deposit_pct < 0.2:
        rule_points += 10
        reasons.append("Deposit below 20%")

    if deal.tenant_credit_score is not None:
        if deal.tenant_credit_score < 600:
            rule_points += 25
            reasons.append("Low credit score")
        elif deal.tenant_credit_score < 650:
            rule_points += 15
            reasons.append("Below-average credit")
        elif deal.tenant_credit_score < 700:
            rule_points += 5

    if deal.asset_type == "EV_FLEET" and deal.battery_health is not None:
        if deal.battery_health < 85:
            rule_points += 20
            reasons.append("Battery health below 85%")
        elif deal.battery_health < 90:
            rule_points += 10
            reasons.append("Battery health below 90%")

    if deal.vehicle_age is not None and deal.vehicle_age > 5:
        rule_points += 15
        reasons.append("Asset age above 5 years")

    probability = model_default_probability(deal, monthly, annual, coverage)
    if probability is None:
        risk_score = min(100, rule_points)
    else:
        # Blend the deterministic score with the model's default probability.
        risk_score = min(
            100,
            round((rule_points * RULE_WEIGHT) + (probability * 100 * MODEL_WEIGHT)),
        )
        if probability >= 0.5:
            reasons.append("Model-predicted default risk at or above 50%")

    if coverage >= 1.25 and risk_score < 40:
        decision = "APPROVED"
    elif coverage >= 1.15 and risk_score < 60:
        decision = "REFER"
    else:
        decision = "REJECTED"

    return DealOutput(
        monthly_payment=round(monthly, 2),
        annual_payment=round(annual, 2),
        coverage_ratio=round(coverage, 2),
        risk_score=risk_score,
        decision=decision,
        reasons=reasons,
    )


@app.on_event("startup")
async def load_model() -> None:
    global model
    if MODEL_PATH.exists():
        try:
            model = joblib.load(MODEL_PATH)
            print(f"Model loaded from {MODEL_PATH}")
        except Exception as exc:
            model = None
            print(f"Failed to load model: {exc}")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.post("/underwrite", response_model=DealOutput)
def underwrite_deal(deal: DealInput):
    return underwrite(deal)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
