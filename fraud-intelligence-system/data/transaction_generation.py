import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Iterable

from utils.device_registry import (
    get_device,
    list_device_ids,
    register_device,
    update_device_counter,
)
_COUNTRIES = ["NG", "US", "GB", "KE", "ZA", "DE", "FR", "IN", "BR", "AE"]
_CITIES = ["Lagos", "London", "Nairobi", "Cape Town", "Berlin", "Paris", "Mumbai", "Sao Paulo", "Dubai", "New York"]
# MVP is single-currency; keep a small mix to simulate cross-border risk.
_CURRENCIES = ["NGN", "USD", "GBP"]
_MERCHANTS = ["Amazon", "Walmart", "Target", "Best Buy", "IKEA", "AliExpress", "Apple", "Netflix", "Uber", "Spotify"]
_CATEGORIES = ["Electronics", "Clothing", "Groceries", "Entertainment", "Travel", "Gambling", "Pharmacy", "Fuel"]
_CHANNELS = ["card_present", "card_not_present", "mobile", "web"]
_CARD_TYPES = ["debit", "credit", "prepaid", "virtual"]
_AUTH_METHODS = ["pin", "otp", "biometric", "none"]
_DEVICE_TYPES = ["ios", "android", "web"]
_ISP = ["comcast", "verizon", "vodacom", "bt", "airtel", "mtn", "vodafone", "orange"]
_DEVICE_STATUSES = ["active", "flagged", "revoked"]
_MERCHANT_STATUSES = ["active", "pending", "suspended"]
_KYC_STATUSES = ["verified", "pending", "restricted"]
_RISK_TIERS = ["low", "medium", "high"]
_QR_TTL_SECONDS = [60, 90, 120]
_WALLET_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "FROZEN", "SUSPENDED"]
_GRANT_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "EXPIRED", "REVOKED", "REDEEMED"]
_MERCHANT_IDS = [
    "merchant_123",
    "merchant_234",
    "merchant_345",
    "merchant_456",
    "merchant_567",
]


def set_seed(seed: int) -> None:
    random.seed(seed)


def _random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def _token(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _risk_label(features: dict) -> int:
    # Synthetic label tailored to QPay: hard verification failures are fraud,
    # otherwise score based on risk signals.
    verification = verify_transaction(features, update_registry=False)
    if verification["decision"] == "rejected":
        return 1

    score = 0.0
    if features["amount"] >= 700_000:
        score += 0.25
    if features["category"] in {"Electronics", "Entertainment", "Gambling"} and features["amount"] >= 400_000:
        score += 0.2
    if features["is_new_device"] == 1:
        score += 0.15
    if features["account_age_days"] < 30:
        score += 0.1
    if features["velocity_1h"] >= 5:
        score += 0.1
    if features["previous_chargebacks"] >= 1:
        score += 0.15
    if features["counter_jump"] == 1:
        score += 0.15
    if features["device_status"] == "flagged":
        score += 0.2
    if features["merchant_risk_tier"] == "high":
        score += 0.15
    if features["merchant_kyc_status"] != "verified":
        score += 0.1
    if features["wallet_status"] != "ACTIVE":
        score += 0.2
    if features["grant_status"] != "ACTIVE":
        score += 0.25
    if features["grant_expired"] == 1:
        score += 0.2
    if features["amount_exceeds_grant"] == 1:
        score += 0.25
    if features["wallet_token_match"] == 0:
        score += 0.15
    if features["grant_device_match"] == 0:
        score += 0.2
    if features["grant_user_match"] == 0:
        score += 0.15
    if features["auth_method"] == "none":
        score += 0.1
    if features.get("failed_attempts", 0) >= 3:
        score += 0.1
    if features.get("ip_changes", 0) >= 2:
        score += 0.1
    if features.get("chargeback_ratio_30d", 0.0) >= 0.05:
        score += 0.1
    return 1 if score >= 0.6 else 0


def _determine_rejection_reason(tx: dict) -> str | None:
    if tx.get("device_registered") is False:
        return "Device not registered"
    if tx.get("device_status") == "revoked":
        return "Device inactive"
    if tx.get("merchant_status") != "active":
        return "Merchant inactive"
    if tx.get("wallet_status") != "ACTIVE":
        return "Wallet inactive"
    if tx.get("grant_status") != "ACTIVE":
        return "Grant unavailable"
    if tx.get("grant_expired") == 1:
        return "Grant expired"
    if tx.get("signature_valid") == 0:
        return "Signature invalid"
    if tx.get("wallet_token_match") == 0:
        return "Wallet token mismatch"
    if tx.get("grant_device_match") == 0:
        return "Grant device mismatch"
    if tx.get("grant_user_match") == 0:
        return "Grant user mismatch"
    if tx.get("amount_exceeds_grant") == 1:
        return "Grant amount exceeded"
    if tx.get("qr_expired") == 1:
        return "Expired QR"
    if tx.get("counter_reused") == 1:
        return "Duplicate token"
    if tx.get("sufficient_balance") == 0:
        return "Insufficient balance"
    if tx.get("merchant_online") == 0:
        return "Merchant offline"
    return None


def verify_transaction(tx: dict, update_registry: bool = True) -> dict:
    signature_valid = tx.get("signature_valid")
    if signature_valid is None:
        signature_valid = 1
    qr_expired = tx.get("qr_expired")
    if qr_expired is None:
        qr_expired = 0
    counter_reused = tx.get("counter_reused")
    if counter_reused is None:
        counter_reused = 0
    merchant_online = tx.get("merchant_online")
    if merchant_online is None:
        merchant_online = 1
    sufficient_balance = tx.get("sufficient_balance")
    if sufficient_balance is None:
        sufficient_balance = 1
    wallet_status = tx.get("wallet_status") or "ACTIVE"
    grant_status = tx.get("grant_status") or "ACTIVE"
    grant_expired = tx.get("grant_expired")
    if grant_expired is None:
        grant_expired = 0
    wallet_token_match = tx.get("wallet_token_match")
    if wallet_token_match is None:
        wallet_token_match = 1
    grant_device_match = tx.get("grant_device_match")
    if grant_device_match is None:
        grant_device_match = 1
    grant_user_match = tx.get("grant_user_match")
    if grant_user_match is None:
        grant_user_match = 1
    amount_exceeds_grant = tx.get("amount_exceeds_grant")
    if amount_exceeds_grant is None:
        amount_exceeds_grant = 0

    device_id = tx.get("device_id")
    device_registered = True
    device_status = tx.get("device_status")
    last_counter = None
    counter_reused = tx.get("counter_reused")
    counter_jump = tx.get("counter_jump")
    counter_delta = tx.get("counter_delta")

    if device_id:
        record = get_device(device_id)
        if record is None:
            device_registered = False
        else:
            device_status = record.status
            last_counter = record.last_counter

        tx_counter = tx.get("counter", tx.get("qr_counter"))
        if tx_counter is not None and last_counter is not None:
            counter_delta = tx_counter - last_counter
            counter_reused = 1 if tx_counter <= last_counter else 0
            counter_jump = 1 if counter_delta >= 10 else 0
        elif tx_counter is not None and counter_reused is None:
            counter_reused = 0
            counter_jump = 0

    if device_id is None and device_status is None:
        device_status = "active"

    from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder

    grant_device_id = tx.get("grant_device_id")
    if grant_device_id and device_id:
        grant_device_match = 1 if grant_device_id == device_id else 0

    grant_user_id = tx.get("grant_user_id")
    if grant_user_id and tx.get("user_id"):
        grant_user_match = 1 if grant_user_id == tx.get("user_id") else 0

    grant_wallet_token = tx.get("grant_wallet_token")
    if grant_wallet_token and tx.get("wallet_token"):
        wallet_token_match = 1 if grant_wallet_token == tx.get("wallet_token") else 0

    grant_remaining_amount = tx.get("grant_remaining_amount")
    grant_max_authorized_amount = tx.get("grant_max_authorized_amount")
    amount = tx.get("amount")
    if amount is not None and grant_remaining_amount is not None and amount > grant_remaining_amount:
        amount_exceeds_grant = 1
    if amount is not None and grant_max_authorized_amount is not None and amount > grant_max_authorized_amount:
        amount_exceeds_grant = 1

    verification = {
        "signature_valid": bool(signature_valid),
        "qr_not_expired": not bool(qr_expired),
        "counter_fresh": not bool(counter_reused),
        "device_active": device_status == "active",
        "device_registered": device_registered,
        "merchant_active": tx.get("merchant_status") == "active",
        "merchant_online": bool(merchant_online),
        "sufficient_balance": bool(sufficient_balance),
        "wallet_active": wallet_status == "ACTIVE",
        "grant_active": grant_status == "ACTIVE",
        "grant_not_expired": not bool(grant_expired),
        "wallet_token_match": bool(wallet_token_match),
        "grant_device_match": bool(grant_device_match),
        "grant_user_match": bool(grant_user_match),
        "amount_within_grant": not bool(amount_exceeds_grant),
    }

    tx["device_status"] = device_status
    tx["device_registered"] = device_registered
    tx["wallet_status"] = wallet_status
    tx["grant_status"] = grant_status
    tx["grant_expired"] = int(bool(grant_expired))
    tx["wallet_token_match"] = int(bool(wallet_token_match))
    tx["grant_device_match"] = int(bool(grant_device_match))
    tx["grant_user_match"] = int(bool(grant_user_match))
    tx["amount_exceeds_grant"] = int(bool(amount_exceeds_grant))
    rejection_reason = _determine_rejection_reason(tx)
    decision = "rejected" if rejection_reason else "approved"

    if device_id:
        tx["counter_reused"] = counter_reused if counter_reused is not None else 0
        tx["counter_jump"] = counter_jump if counter_jump is not None else 0
        if counter_delta is not None:
            tx["counter_delta"] = counter_delta
        if decision == "approved" and update_registry:
            tx_counter = tx.get("counter", tx.get("qr_counter"))
            if tx_counter is not None:
                update_device_counter(device_id, int(tx_counter))
    return {
        "verification": verification,
        "rejection_reason": rejection_reason,
        "decision": decision,
    }


def generate_transaction() -> dict:
    now = datetime.now()
    account_age_days = random.randint(1, 2000)
    is_new_device = 1 if random.random() < 0.15 else 0
    velocity_1h = random.randint(0, 10)
    previous_chargebacks = random.randint(0, 3)
    amount = random.randint(50_000, 1_500_000)
    category = random.choice(_CATEGORIES)
    currency = "NGN"
    merchant = random.choice(_MERCHANTS)
    merchant_id = random.choice(_MERCHANT_IDS)
    user_id = str(uuid.uuid4())

    device_status = random.choices(_DEVICE_STATUSES, weights=[0.88, 0.09, 0.03])[0]
    merchant_status = random.choices(_MERCHANT_STATUSES, weights=[0.9, 0.05, 0.05])[0]
    merchant_kyc_status = random.choices(_KYC_STATUSES, weights=[0.85, 0.1, 0.05])[0]
    merchant_risk_tier = random.choices(_RISK_TIERS, weights=[0.6, 0.3, 0.1])[0]
    wallet_status = random.choice(_WALLET_STATUSES)
    grant_status = random.choice(_GRANT_STATUSES)
    email_verified = 1 if random.random() >= 0.04 else 0
    pins_set = 1 if random.random() >= 0.05 else 0

    qr_ttl_sec = random.choice(_QR_TTL_SECONDS)
    qr_age_sec = random.randint(0, 180)
    qr_expired = 1 if qr_age_sec > qr_ttl_sec else 0

    signature_valid = 1 if random.random() >= 0.03 else 0
    merchant_online = 1 if random.random() >= 0.02 else 0

    device_id_pool = list_device_ids()
    reuse_device = bool(device_id_pool) and random.random() < 0.6
    device_id = random.choice(device_id_pool) if reuse_device else str(uuid.uuid4())
    record = get_device(device_id)
    if record is None:
        record = register_device(
            device_id=device_id,
            user_id=user_id,
            status=device_status,
            last_counter=random.randint(1000, 5000),
        )
    else:
        device_status = record.status
        if record.user_id:
            user_id = record.user_id

    last_counter = record.last_counter or random.randint(1000, 5000)
    counter_delta = random.choice([1, 1, 1, 2, 3, 5, 10, -1])
    counter = last_counter + counter_delta
    counter_reused = 1 if counter <= last_counter else 0
    counter_jump = 1 if counter_delta >= 10 else 0

    balance = random.randint(0, 2_500_000)
    sufficient_balance = 1 if balance >= amount else 0
    wallet_token = _token("wallet")
    grant_id = _token("grant")
    grant_expires_in_sec = random.choice([45, 60, 90, 120, 180])
    grant_age_sec = random.randint(0, 240)
    grant_expired = 1 if grant_age_sec > grant_expires_in_sec or grant_status == "EXPIRED" else 0
    grant_remaining_amount = max(amount - random.randint(-150_000, 300_000), 10_000)
    grant_max_authorized_amount = max(grant_remaining_amount, amount + random.randint(0, 250_000))
    amount_exceeds_grant = 1 if amount > grant_remaining_amount or amount > grant_max_authorized_amount else 0
    grant_device_id = device_id if random.random() >= 0.03 else str(uuid.uuid4())
    grant_user_id = user_id if random.random() >= 0.03 else str(uuid.uuid4())
    grant_wallet_token = wallet_token if random.random() >= 0.03 else _token("wallet")
    wallet_token_match = 1 if grant_wallet_token == wallet_token else 0
    grant_device_match = 1 if grant_device_id == device_id else 0
    grant_user_match = 1 if grant_user_id == user_id else 0
    failed_attempts = random.randint(0, 6)
    ip_changes = random.randint(0, 3)
    device_changes = random.randint(0, 2)
    bank_account_status = random.choice(["active", "limited", "closed"])
    chargeback_ratio_30d = round(random.uniform(0, 0.12), 3)

    tx = {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": (now - timedelta(minutes=random.randint(0, 60 * 24))).isoformat(),
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "merchant_id": merchant_id,
        "merchant_status": merchant_status,
        "merchant_kyc_status": merchant_kyc_status,
        "merchant_risk_tier": merchant_risk_tier,
        "merchant_online": merchant_online,
        "category": category,
        "channel": random.choice(_CHANNELS),
        "card_type": random.choice(_CARD_TYPES),
        "auth_method": random.choice(_AUTH_METHODS),
        "device_type": random.choice(_DEVICE_TYPES),
        "device_id": device_id,
        "device_status": device_status,
        "device_trust_score": round(random.uniform(0.2, 0.95), 2),
        "device_model": random.choice(["iPhone 13", "Samsung A15", "Infinix Hot", "Tecno Camon", "Redmi Note"]),
        "user_id": user_id,
        "ip_address": _random_ip(),
        "isp": random.choice(_ISP),
        "country": random.choice(_COUNTRIES),
        "city": random.choice(_CITIES),
        "account_age_days": account_age_days,
        "is_new_device": is_new_device,
        "velocity_1h": velocity_1h,
        "previous_chargebacks": previous_chargebacks,
        "balance": balance,
        "sufficient_balance": sufficient_balance,
        "wallet_token": wallet_token,
        "wallet_status": wallet_status,
        "grant_id": grant_id,
        "grant_status": grant_status,
        "grant_remaining_amount": grant_remaining_amount,
        "grant_max_authorized_amount": grant_max_authorized_amount,
        "grant_expires_in_sec": grant_expires_in_sec,
        "grant_age_sec": grant_age_sec,
        "grant_expired": grant_expired,
        "grant_device_id": grant_device_id,
        "grant_user_id": grant_user_id,
        "grant_wallet_token": grant_wallet_token,
        "wallet_token_match": wallet_token_match,
        "grant_device_match": grant_device_match,
        "grant_user_match": grant_user_match,
        "amount_exceeds_grant": amount_exceeds_grant,
        "qr_counter": counter,
        "counter": counter,
        "highest_redeemed_counter": last_counter,
        "counter_delta": counter_delta,
        "counter_reused": counter_reused,
        "counter_jump": counter_jump,
        "qr_age_sec": qr_age_sec,
        "qr_ttl_sec": qr_ttl_sec,
        "qr_expired": qr_expired,
        "signature_valid": signature_valid,
        "signature": _token("sig"),
        "grant_signature": _token("grantsig"),
        "signature_alg": "Ed25519",
        "signature_kid": "qpay-device-key-v1",
        "email_verified": email_verified,
        "pins_set": pins_set,
        "grant_request_count_24h": random.randint(0, 7),
        "failed_attempts": failed_attempts,
        "ip_changes": ip_changes,
        "device_changes": device_changes,
        "bank_account_status": bank_account_status,
        "chargeback_ratio_30d": chargeback_ratio_30d,
        "payer_offline": 1 if random.random() < 0.7 else 0,
        "is_international": 0,
    }
    tx["label"] = _risk_label(tx)
    if counter_reused == 0:
        update_device_counter(device_id, counter)
    return tx


def generate_dataset(n: int = 1000) -> list[dict]:
    return [generate_transaction() for _ in range(n)]


def generate_signed_offline_grant() -> dict:
    tx = generate_transaction()
    return {
        "payload": {
            "grantId": tx["grant_id"],
            "userId": tx["user_id"],
            "walletToken": tx["wallet_token"],
            "maxAuthorizedAmount": tx["grant_max_authorized_amount"],
            "remainingAmount": tx["grant_remaining_amount"],
            "status": tx["grant_status"],
            "expiresAt": (datetime.now() + timedelta(seconds=tx["grant_expires_in_sec"])).isoformat(),
        },
        "signature": tx["grant_signature"],
        "kid": tx["signature_kid"],
        "alg": tx["signature_alg"],
    }


def generate_grant_redemption_request() -> dict:
    tx = generate_transaction()
    next_counter = int(tx["counter"]) + 1
    return {
        "userId": tx["user_id"],
        "grantId": tx["grant_id"],
        "deviceId": tx["device_id"],
        "walletToken": tx["wallet_token"],
        "amount": tx["amount"],
        "counter": next_counter,
        "signature": tx["signature"],
        "merchantId": tx["merchant_id"],
        "merchantStatus": tx["merchant_status"],
        "merchantOnline": tx["merchant_online"],
        "walletStatus": tx["wallet_status"],
        "grantStatus": tx["grant_status"],
        "grantRemainingAmount": tx["grant_remaining_amount"],
        "grantMaxAuthorizedAmount": tx["grant_max_authorized_amount"],
        "grantExpired": tx["grant_expired"],
        "signatureValid": tx["signature_valid"],
    }


def assess_grant_request(tx: dict) -> dict:
    device_registered = get_device(tx.get("device_id", "")) is not None if tx.get("device_id") else False
    reasons = []
    if not device_registered:
        reasons.append("Device not registered")
    if tx.get("device_status", "active") != "active":
        reasons.append("Device inactive")
    if tx.get("wallet_status", "ACTIVE") != "ACTIVE":
        reasons.append("Wallet inactive")
    if tx.get("email_verified", 1) == 0:
        reasons.append("Email not verified")
    if tx.get("pins_set", 1) == 0:
        reasons.append("PIN setup incomplete")
    if tx.get("grant_request_count_24h", 0) >= 5:
        reasons.append("Unusual grant request velocity")

    eligible = len(reasons) == 0
    return {
        "decision": "approved" if eligible else "rejected",
        "eligible": eligible,
        "reasons": reasons or ["Grant request allowed"],
        "suggested_actions": _suggest_actions(reasons) if reasons else ["Issue signed offline grant"],
    }


def _rng_for_key(key: str) -> random.Random:
    # Deterministic RNG for repeatable investigations.
    return random.Random(key)


def get_transactions_last_hours(merchant_id: str, hours: int = 24, limit: int = 250) -> list[dict]:
    # Simulated transaction database API.
    dataset = generate_dataset(min(limit, 1000))
    cutoff = datetime.now() - timedelta(hours=hours)
    return [
        tx
        for tx in dataset
        if tx["merchant_id"] == merchant_id
        and datetime.fromisoformat(tx["timestamp"]) >= cutoff
    ]


def get_merchant_account(merchant_id: str) -> dict:
    # Simulated merchant account data.
    rng = _rng_for_key(merchant_id)
    return {
        "merchant_id": merchant_id,
        "home_country": rng.choice(_COUNTRIES),
        "risk_tier": rng.choice(["low", "medium", "high"]),
        "kyc_status": rng.choice(["verified", "pending", "restricted"]),
        "payout_hold": rng.choice([True, False, False]),
    }


def get_payment_logs(transaction_id: str) -> dict:
    # Simulated payment logs for a specific transaction.
    rng = _rng_for_key(transaction_id)
    failed_attempts = rng.randint(0, 6)
    return {
        "transaction_id": transaction_id,
        "failed_attempts": failed_attempts,
        "ip_changes": rng.randint(0, 3),
        "device_changes": rng.randint(0, 2),
        "was_3ds_used": rng.choice([True, False]),
    }


def get_banking_status(user_id: str) -> dict:
    # Simulated banking status reports.
    rng = _rng_for_key(user_id)
    return {
        "user_id": user_id,
        "account_status": rng.choice(["active", "limited", "closed"]),
        "recent_returns": rng.randint(0, 2),
        "chargeback_ratio_30d": round(rng.uniform(0, 0.12), 3),
    }


def explain_transaction(tx: dict, verification: dict | None = None) -> dict:
    merchant = get_merchant_account(tx["merchant_id"])
    logs = get_payment_logs(tx["transaction_id"])
    banking = get_banking_status(tx["user_id"])
    verification = verification or verify_transaction(tx, update_registry=False)
    reasons = _explain_suspicion(tx, merchant, logs, banking, verification)
    return {
        "reasons": reasons,
        "suggested_actions": _suggest_actions(reasons),
        "verification": verification,
    }


def _explain_suspicion(
    tx: dict, merchant: dict, logs: dict, banking: dict, verification: dict
) -> list[str]:
    reasons = []
    rejection_reason = verification.get("rejection_reason")
    if rejection_reason:
        reasons.append(rejection_reason)

    if tx["qr_expired"] == 1 and "Expired QR" not in reasons:
        reasons.append("Expired QR")
    if tx["counter_reused"] == 1 and "Duplicate token" not in reasons:
        reasons.append("Duplicate token")
    if tx["counter_jump"] == 1:
        reasons.append("Counter jump detected")
    if tx["device_status"] == "flagged":
        reasons.append("Device flagged for risk")
    if tx.get("wallet_status") != "ACTIVE":
        reasons.append("Wallet inactive")
    if tx.get("grant_status") != "ACTIVE":
        reasons.append("Grant unavailable")
    if tx.get("grant_expired") == 1:
        reasons.append("Grant expired")
    if tx.get("wallet_token_match") == 0:
        reasons.append("Wallet token mismatch")
    if tx.get("grant_device_match") == 0:
        reasons.append("Grant device mismatch")
    if tx.get("grant_user_match") == 0:
        reasons.append("Grant user mismatch")
    if tx.get("amount_exceeds_grant") == 1:
        reasons.append("Grant amount exceeded")
    if tx["signature_valid"] == 0:
        reasons.append("Signature invalid")
    if tx["merchant_status"] != "active":
        reasons.append("Merchant inactive")
    if tx["merchant_online"] == 0:
        reasons.append("Merchant offline")
    if tx.get("email_verified") == 0:
        reasons.append("Email not verified")
    if tx.get("pins_set") == 0:
        reasons.append("PIN setup incomplete")
    if tx.get("grant_request_count_24h", 0) >= 5:
        reasons.append("Unusual grant request velocity")

    if tx["amount"] >= 1000:
        reasons.append("High transaction amount")
    if tx["is_international"] == 1 or tx["country"] != merchant["home_country"]:
        reasons.append("Unusual country or cross-border payment")
    if tx["velocity_1h"] >= 5:
        reasons.append("High transaction velocity in last hour")
    if tx["previous_chargebacks"] >= 1:
        reasons.append("Prior chargebacks on the account")
    if tx["category"] in {"Gambling", "Electronics"} and tx["amount"] >= 400:
        reasons.append("Risky category with elevated amount")
    if tx["is_new_device"] == 1:
        reasons.append("New device for this user")
    if tx["auth_method"] == "none":
        reasons.append("No authentication method used")
    if logs["failed_attempts"] >= 3:
        reasons.append("Multiple failed payment attempts before success")
    if logs["ip_changes"] >= 2:
        reasons.append("Multiple IP changes during payment flow")
    if banking["account_status"] in {"limited", "closed"}:
        reasons.append("Banking account status is not active")
    if banking["chargeback_ratio_30d"] >= 0.05:
        reasons.append("Elevated chargeback ratio in last 30 days")
    if merchant["risk_tier"] == "high" or merchant["kyc_status"] != "verified":
        reasons.append("Merchant risk tier or KYC status is concerning")
    return reasons


def _suggest_actions(reasons: Iterable[str]) -> list[str]:
    actions = []
    reason_set = set(reasons)
    if "Device not registered" in reason_set:
        actions.append("Register device and re-issue credentials before retrying")
    if "Wallet inactive" in reason_set:
        actions.append("Restore wallet status before issuing or redeeming grants")
    if "Grant unavailable" in reason_set:
        actions.append("Issue a fresh active grant before retrying payment")
    if "Grant expired" in reason_set:
        actions.append("Generate a new signed offline grant")
    if "Wallet token mismatch" in reason_set:
        actions.append("Re-sync wallet identity before allowing redemption")
    if "Grant device mismatch" in reason_set:
        actions.append("Bind a new grant to the current verified device")
    if "Grant user mismatch" in reason_set:
        actions.append("Investigate whether the grant has been shared or tampered with")
    if "Grant amount exceeded" in reason_set:
        actions.append("Reduce the redemption amount or issue a larger grant")
    if "Expired QR" in reason_set:
        actions.append("Ask payer to regenerate the QR code")
    if "Duplicate token" in reason_set:
        actions.append("Investigate possible replay and consider revoking device")
    if "Device inactive" in reason_set:
        actions.append("Re-enroll device or contact support to restore access")
    if "Signature invalid" in reason_set:
        actions.append("Revoke device credentials and investigate compromise")
    if "Merchant inactive" in reason_set:
        actions.append("Suspend payouts and contact merchant onboarding")
    if "Merchant offline" in reason_set:
        actions.append("Confirm merchant connectivity before retry")
    if "Counter jump detected" in reason_set:
        actions.append("Review device counter history for tampering")
    if "Insufficient balance" in reason_set:
        actions.append("Prompt payer to fund wallet before retrying")
    if "High transaction amount" in reason_set:
        actions.append("Verify customer identity and funding source")
    if "Unusual country or cross-border payment" in reason_set:
        actions.append("Confirm customer location and device/IP consistency")
    if "Multiple failed payment attempts before success" in reason_set:
        actions.append("Review authentication logs and attempt patterns")
    if "New device for this user" in reason_set:
        actions.append("Trigger step-up authentication for future payments")
    if "Email not verified" in reason_set:
        actions.append("Complete email verification before enabling offline grants")
    if "PIN setup incomplete" in reason_set:
        actions.append("Require app PIN and wallet PIN setup")
    if "Unusual grant request velocity" in reason_set:
        actions.append("Throttle grant issuance and review device activity")
    if "Banking account status is not active" in reason_set:
        actions.append("Hold payout and contact banking partner for details")
    if "Merchant risk tier or KYC status is concerning" in reason_set:
        actions.append("Escalate to merchant onboarding/AML review")
    if not actions:
        actions.append("Manual review by fraud analyst")
    return actions


def find_suspicious_transactions(transactions: list[dict]) -> list[dict]:
    suspicious = []
    for tx in transactions:
        explanation = explain_transaction(tx)
        reasons = explanation["reasons"]
        if reasons:
            suspicious.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "amount": tx["amount"],
                    "currency": tx["currency"],
                    "merchant_id": tx["merchant_id"],
                    "reason": "; ".join(reasons),
                    "suggested_action": "; ".join(explanation["suggested_actions"]),
                }
            )
    return suspicious


def investigation_summary(transactions: list[dict]) -> list[dict]:
    # Structured summaries for reporting.
    return find_suspicious_transactions(transactions)


def render_json_report(summaries: list[dict]) -> str:
    return json.dumps(summaries, indent=2, sort_keys=True)


def render_markdown_table(summaries: list[dict]) -> str:
    if not summaries:
        return "| transaction_id | amount | currency | reason | suggested_action |\n|---|---:|---|---|---|\n"
    header = "| transaction_id | amount | currency | reason | suggested_action |\n|---|---:|---|---|---|\n"
    rows = [
        f"| {s['transaction_id']} | {s['amount']:.2f} | {s['currency']} | {s['reason']} | {s['suggested_action']} |"
        for s in summaries
    ]
    return header + "\n".join(rows)


def run_fraud_investigation(merchant_id: str, hours: int = 24, limit: int = 250) -> dict:
    # Main entry point for the Fraud Investigation Copilot.
    transactions = get_transactions_last_hours(merchant_id, hours=hours, limit=limit)
    summaries = investigation_summary(transactions)
    return {
        "merchant_id": merchant_id,
        "hours": hours,
        "count_reviewed": len(transactions),
        "count_flagged": len(summaries),
        "summaries": summaries,
    }


if __name__ == "__main__":
    for _ in range(10):
        print(generate_transaction())
