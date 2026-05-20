from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Allow running this file directly without PYTHONPATH gymnastics.
    sys.path.insert(0, str(ROOT))

from data.transaction_generation import (
    assess_grant_request,
    explain_transaction,
    generate_grant_redemption_request,
    generate_signed_offline_grant,
    generate_transaction,
    run_fraud_investigation,
    verify_transaction,
)  # noqa: E402
from model.infer import artifacts_exist, predict  # noqa: E402
from model.train import train  # noqa: E402


class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    amount: float = Field(..., ge=0)
    currency: str
    merchant: str | None = None
    merchant_id: str | None = None
    category: str
    timestamp: str | None = None
    device_id: str | None = None
    qr_counter: int | None = None
    qr_age_sec: int | None = None
    qr_ttl_sec: int | None = None
    signature_valid: bool | None = None
    device_status: str | None = None
    merchant_status: str | None = None
    merchant_online: int | None = None


class GrantRequestIn(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    user_id: str | None = Field(default=None, alias="userId")
    device_id: str | None = Field(default=None, alias="deviceId")
    wallet_token: str | None = Field(default=None, alias="walletToken")
    wallet_status: str | None = Field(default=None, alias="walletStatus")
    email_verified: bool | None = Field(default=None, alias="emailVerified")
    pins_set: bool | None = Field(default=None, alias="pinsSet")
    device_status: str | None = Field(default=None, alias="deviceStatus")
    grant_request_count_24h: int | None = Field(default=None, alias="grantRequestCount24h")


class GrantRedemptionIn(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    user_id: str = Field(alias="userId")
    grant_id: str = Field(alias="grantId")
    device_id: str = Field(alias="deviceId")
    wallet_token: str = Field(alias="walletToken")
    amount: float = Field(ge=50000)
    counter: int = Field(ge=1)
    signature: str
    merchant_id: str | None = Field(default=None, alias="merchantId")
    merchant_status: str | None = Field(default=None, alias="merchantStatus")
    merchant_online: int | None = Field(default=None, alias="merchantOnline")
    wallet_status: str | None = Field(default=None, alias="walletStatus")
    grant_status: str | None = Field(default=None, alias="grantStatus")
    grant_remaining_amount: float | None = Field(default=None, alias="grantRemainingAmount")
    grant_max_authorized_amount: float | None = Field(default=None, alias="grantMaxAuthorizedAmount")
    grant_expired: bool | None = Field(default=None, alias="grantExpired")
    signature_valid: bool | None = Field(default=None, alias="signatureValid")


def _startup() -> None:
    if not artifacts_exist():
        if os.getenv("FRAUD_AUTO_TRAIN", "0") == "1":
            train()
        else:
            return
    # Warm model cache on startup.
    try:
        _ = predict(generate_transaction())
    except FileNotFoundError:
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(title="Fraud Intelligence API", version="0.2.0", lifespan=lifespan)


class ScoreOut(BaseModel):
    risk_score: float
    is_fraud: bool
    reasons: list[str]
    suggested_actions : list[str]
    decision: str
    rejection_reason: str | None = None
    risk_level: str | None = None
    needs_review: bool | None = None
    verification: dict[str, bool] | None = None


class GrantAssessmentOut(BaseModel):
    decision: str
    eligible: bool
    reasons: list[str]
    suggested_actions: list[str]


def _score_payload(payload: dict[str, Any]) -> ScoreOut:
    if not payload.get("timestamp"):
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    verification = verify_transaction(payload)
    try:
        risk_score = float(predict(payload))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Model artifacts not found. Run `python model/train.py` first.",
        ) from exc

    explanation = explain_transaction(payload, verification=verification)
    reasons = list(explanation["reasons"])
    suggested_actions = list(explanation["suggested_actions"])
    if risk_score >= 0.7:
        reasons.append("Model score is high")
    if not reasons:
        reasons.append("No rule-based flags")

    decision = verification["decision"]
    rejection_reason = verification["rejection_reason"]
    risk_level = "high" if risk_score >= 0.85 else "medium" if risk_score >= 0.6 else "low"
    needs_review = decision == "approved" and risk_level == "high"

    return ScoreOut(
        risk_score=risk_score,
        is_fraud=risk_score >= 0.7,
        reasons=reasons,
        suggested_actions=suggested_actions,
        decision=decision,
        rejection_reason=rejection_reason,
        risk_level=risk_level,
        needs_review=needs_review,
        verification=verification["verification"],
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/transactions/generate")
def generate() -> dict[str, Any]:
    return generate_transaction()


@app.post("/transactions/score", response_model=ScoreOut)
def score(tx: TransactionIn) -> ScoreOut:
    # Start from a full synthetic transaction so all expected fields exist.
    payload = generate_transaction()
    payload.update(tx.model_dump())
    return _score_payload(payload)


@app.get("/qpay/grants/request/sample")
def sample_grant() -> dict[str, Any]:
    return generate_signed_offline_grant()


@app.get("/qpay/grants/redeem/sample")
def sample_redemption() -> dict[str, Any]:
    return generate_grant_redemption_request()


@app.post("/qpay/grants/request/score", response_model=GrantAssessmentOut)
def score_grant_request(grant: GrantRequestIn) -> GrantAssessmentOut:
    payload = generate_transaction()
    payload.update(grant.model_dump(by_alias=False, exclude_none=True))
    assessment = assess_grant_request(payload)
    return GrantAssessmentOut(**assessment)


@app.post("/qpay/grants/redeem/score", response_model=ScoreOut)
def score_grant_redemption(redemption: GrantRedemptionIn) -> ScoreOut:
    payload = generate_transaction()
    payload.update(redemption.model_dump(by_alias=False, exclude_none=True))
    payload["qr_counter"] = payload["counter"]
    return _score_payload(payload)


@app.get("/investigations/merchant/{merchant_id}")
def investigate(merchant_id: str, hours: int = 24, limit: int = 250) -> dict[str, Any]:
    return run_fraud_investigation(merchant_id, hours=hours, limit=limit)
