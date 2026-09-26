from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


BASE_DEAL = {
    "asset_value": 1_000_000,
    "deposit": 250_000,
    "finance_amount": 750_000,
    "interest_rate": 6.0,
    "term_months": 240,
    "noi": 90_000,
    "asset_type": "COMMERCIAL_PROPERTY",
}


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "model_loaded" in response.json()


def test_underwrite_approves_low_risk_deal():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "tenant_credit_score": 750,
            "vehicle_age": 2,
        },
    )

    assert response.status_code == 200

    result = response.json()
    assert result["decision"] == "APPROVED"
    assert result["risk_score"] < 40
    assert result["coverage_ratio"] >= 1.25
    assert result["monthly_payment"] > 0
    assert result["annual_payment"] > 0
    assert result["reasons"] == []


def test_underwrite_refers_moderate_risk_deal():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": 80_000,
            "deposit": 150_000,
            "tenant_credit_score": 625,
        },
    )

    assert response.status_code == 200

    result = response.json()
    assert result["decision"] == "REFER"
    assert result["coverage_ratio"] >= 1.15
    assert result["risk_score"] >= 40
    assert "Deposit below 20%" in result["reasons"]
    assert "Below-average credit" in result["reasons"]


def test_underwrite_rejects_high_risk_deal():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": 50_000,
            "deposit": 50_000,
            "tenant_credit_score": 550,
            "asset_type": "EV_FLEET",
            "battery_health": 80,
            "vehicle_age": 8,
        },
    )

    assert response.status_code == 200

    result = response.json()
    assert result["decision"] == "REJECTED"
    assert result["risk_score"] == 100
    assert result["coverage_ratio"] < 1.0
    assert "Coverage ratio below 1.0x" in result["reasons"]
    assert "Deposit below 10%" in result["reasons"]
    assert "Low credit score" in result["reasons"]
    assert "Battery health below 85%" in result["reasons"]
    assert "Asset age above 5 years" in result["reasons"]


def test_ev_battery_penalty_only_applies_to_ev_fleet():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_type": "EQUIPMENT",
            "battery_health": 80,
        },
    )

    assert response.status_code == 200
    assert "Battery health below 85%" not in response.json()["reasons"]


def test_zero_interest_rate_is_supported():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "interest_rate": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["monthly_payment"] == round(
        BASE_DEAL["finance_amount"] / BASE_DEAL["term_months"],
        2,
    )


def test_invalid_request_is_rejected():
    invalid_deal = {
        **BASE_DEAL,
        "finance_amount": "not-a-number",
    }

    response = client.post("/underwrite", json=invalid_deal)

    assert response.status_code == 422


# Edge case: Zero asset value
def test_zero_asset_value():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_value": 0,
            "deposit": 0,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Deposit % should be 0 when asset_value is 0, triggering "Deposit below 10%" penalty
    assert "Deposit below 10%" in result["reasons"]
    assert result["risk_score"] >= 20


# Edge case: Negative asset value
def test_negative_asset_value():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_value": -1_000_000,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Deposit % should be 0 when asset_value is non-positive, triggering penalty
    assert "Deposit below 10%" in result["reasons"]


# Edge case: Negative deposit
def test_negative_deposit():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "deposit": -50_000,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Negative deposit produces negative deposit %, triggers "Deposit below 10%"
    assert "Deposit below 10%" in result["reasons"]


# Edge case: Negative finance amount
def test_negative_finance_amount():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "finance_amount": -750_000,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Negative finance produces negative monthly/annual payments
    assert result["monthly_payment"] < 0
    assert result["annual_payment"] < 0


# Edge case: Zero finance amount
def test_zero_finance_amount():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "finance_amount": 0,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Zero finance produces zero payments and very high coverage
    assert result["monthly_payment"] == 0
    assert result["annual_payment"] == 0
    # Infinite coverage should be clamped or handled gracefully
    assert result["coverage_ratio"] >= 0


# Edge case: Zero NOI
def test_zero_noi():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": 0,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Zero NOI produces zero coverage ratio, should trigger "Coverage ratio below 1.0x"
    assert result["coverage_ratio"] == 0
    assert "Coverage ratio below 1.0x" in result["reasons"]
    assert result["decision"] == "REJECTED"


# Edge case: Negative NOI
def test_negative_noi():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": -10_000,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Negative NOI produces negative coverage, rejected
    assert result["coverage_ratio"] < 0
    assert "Coverage ratio below 1.0x" in result["reasons"]
    assert result["decision"] == "REJECTED"


# Edge case: Zero term months
def test_zero_term_months():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "term_months": 0,
        },
    )

    assert response.status_code == 200
    # Should handle division by zero gracefully in monthly payment calculation
    # Expected behavior: division by zero error or return high monthly payment


# Edge case: Very long loan term
def test_very_long_loan_term():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "term_months": 600,  # 50 years
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Long term should result in lower monthly payments
    assert result["monthly_payment"] > 0
    assert result["monthly_payment"] < BASE_DEAL["finance_amount"] / BASE_DEAL["term_months"]


# Edge case: Very high interest rate
def test_very_high_interest_rate():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "interest_rate": 50.0,  # 50% annual rate
        },
    )

    assert response.status_code == 200
    result = response.json()
    # High interest should produce higher monthly payments
    assert result["monthly_payment"] > BASE_DEAL["finance_amount"] / BASE_DEAL["term_months"]


# Edge case: Credit score exactly at boundary (600)
def test_credit_score_boundary_600():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "tenant_credit_score": 600,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Credit score >= 600 should not trigger "Low credit score" penalty
    assert "Low credit score" not in result["reasons"]
    # But < 650 should trigger "Below-average credit"
    assert "Below-average credit" in result["reasons"]


# Edge case: Credit score exactly at boundary (650)
def test_credit_score_boundary_650():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "tenant_credit_score": 650,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Credit score >= 650 should not trigger "Below-average credit"
    assert "Below-average credit" not in result["reasons"]
    # But < 700 should trigger the minimal penalty
    assert result["risk_score"] >= 5


# Edge case: Battery health exactly at boundary (85)
def test_battery_health_boundary_85():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_type": "EV_FLEET",
            "battery_health": 85,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Battery >= 85 should not trigger "Battery health below 85%"
    assert "Battery health below 85%" not in result["reasons"]


# Edge case: Battery health exactly at boundary (90)
def test_battery_health_boundary_90():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_type": "EV_FLEET",
            "battery_health": 90,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Battery >= 90 should not trigger "Battery health below 90%"
    assert "Battery health below 90%" not in result["reasons"]


# Edge case: Vehicle age exactly at boundary (5)
def test_vehicle_age_boundary_5():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "vehicle_age": 5,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Vehicle age <= 5 should not trigger "Asset age above 5 years"
    assert "Asset age above 5 years" not in result["reasons"]


# Edge case: Deposit exactly at boundary (10%)
def test_deposit_boundary_10_percent():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_value": 1_000_000,
            "deposit": 100_000,  # Exactly 10%
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Deposit >= 10% should not trigger "Deposit below 10%"
    assert "Deposit below 10%" not in result["reasons"]


# Edge case: Deposit exactly at boundary (20%)
def test_deposit_boundary_20_percent():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "asset_value": 1_000_000,
            "deposit": 200_000,  # Exactly 20%
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Deposit >= 20% should not trigger "Deposit below 20%"
    assert "Deposit below 20%" not in result["reasons"]


# Edge case: Coverage ratio exactly at boundary (1.0)
def test_coverage_ratio_boundary_1_0():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": 60_000,  # Produces ~1.0 coverage
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Coverage >= 1.0 should not trigger "Coverage ratio below 1.0x"
    assert "Coverage ratio below 1.0x" not in result["reasons"]


# Edge case: Coverage ratio exactly at boundary (1.25)
def test_coverage_ratio_boundary_1_25():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "noi": 75_000,  # Produces ~1.25 coverage
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Coverage >= 1.25 with low risk should be APPROVED
    if result["risk_score"] < 40:
        assert result["decision"] == "APPROVED"


# Edge case: Missing optional fields
def test_missing_optional_fields():
    deal_without_optional = {
        "asset_value": 1_000_000,
        "deposit": 250_000,
        "finance_amount": 750_000,
        "interest_rate": 6.0,
        "term_months": 240,
        "noi": 90_000,
        "asset_type": "COMMERCIAL_PROPERTY",
    }

    response = client.post("/underwrite", json=deal_without_optional)

    assert response.status_code == 200
    result = response.json()
    # Should process without optional fields
    assert result["decision"] in ["APPROVED", "REFER", "REJECTED"]


# Edge case: Extreme rounding precision
def test_rounding_precision():
    response = client.post(
        "/underwrite",
        json={
            **BASE_DEAL,
            "interest_rate": 6.123456,
            "noi": 90_000.123456,
        },
    )

    assert response.status_code == 200
    result = response.json()
    # Payments and coverage should be rounded to 2 decimal places
    monthly_str = str(result["monthly_payment"])
    assert len(monthly_str.split(".")[-1]) <= 2
