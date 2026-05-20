from fastapi.testclient import TestClient

from api.fraud_api import app
from data.transaction_generation import generate_grant_redemption_request, generate_transaction


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_score() -> None:
    payload = {"amount": 125.0, "currency": "USD", "category": "Electronics"}
    response = client.post("/transactions/score", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "risk_score" in body
    assert "is_fraud" in body
    assert "reasons" in body
    assert "suggested_actions" in body
    assert "decision" in body
    assert "verification" in body


def test_investigation() -> None:
    response = client.get("/investigations/merchant/merchant_123?hours=1&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["merchant_id"] == "merchant_123"
    assert "summaries" in body


def test_grant_request_score() -> None:
    tx = generate_transaction()
    payload = {
        "userId": tx["user_id"],
        "deviceId": tx["device_id"],
        "walletToken": tx["wallet_token"],
        "walletStatus": tx["wallet_status"],
        "emailVerified": bool(tx["email_verified"]),
        "pinsSet": bool(tx["pins_set"]),
        "deviceStatus": tx["device_status"],
        "grantRequestCount24h": tx["grant_request_count_24h"],
    }
    response = client.post("/qpay/grants/request/score", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "decision" in body
    assert "eligible" in body
    assert "reasons" in body


def test_grant_redemption_score() -> None:
    payload = generate_grant_redemption_request()
    response = client.post("/qpay/grants/redeem/score", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "risk_score" in body
    assert "decision" in body
    assert "verification" in body
