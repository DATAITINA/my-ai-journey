Fraud Intelligence System

Overview
Synthetic fraud scoring demo with data generation, model training, inference, and a FastAPI service.

QPay Tailoring (Offline QR)
- Payer generates offline QR; merchant must be online to submit.
- Backend verification checks signature validity, QR expiry, counter freshness, device status, merchant status, and balance.
- Human-readable rejection reasons and suggested actions map to QPay UX requirements.
- Fraud scoring now mirrors QPay backend concepts such as `walletToken`, `grantId`, signed offline grants, and merchant-side grant redemption.

API Endpoints
- `GET /health`
- `GET /transactions/generate`
- `POST /transactions/score`
- `GET /qpay/grants/request/sample`
- `GET /qpay/grants/redeem/sample`
- `POST /qpay/grants/request/score`
- `POST /qpay/grants/redeem/score`
- `GET /investigations/merchant/{merchant_id}?hours=24&limit=250`

Example: Score a Transaction
```bash
curl -X POST http://localhost:8000/transactions/score \
  -H "Content-Type: application/json" \
  -d "{\"amount\": 125.0, \"currency\": \"USD\", \"category\": \"Electronics\"}"
```

Quickstart (Docker)
1. Build the image:
   docker build -t fraud-intel .
2. Run the API:
   docker run --rm -p 8000:8000 fraud-intel
3. Check health:
   curl http://localhost:8000/health

Build With Pretrained Artifacts (Docker)
1. Build:
   docker build --build-arg TRAIN_ON_BUILD=1 -t fraud-intel .
2. Run:
   docker run --rm -p 8000:8000 fraud-intel

Local (without Docker)
1. Install dependencies:
   pip install -r requirements.txt
2. Train the model:
   python model/train.py
3. Start the API:
   uvicorn api.fraud_api:app --reload

Environment Variables
- `FRAUD_AUTO_TRAIN=1` trains a model on startup if artifacts are missing.
- `DATABASE_URL=postgresql://user:pass@host:5432/dbname` enables the Postgres-backed device registry.
- `DEVICE_REGISTRY_BACKEND=postgres` forces Postgres even if `DATABASE_URL` is not set (will error).

Artifacts
- `model/fraud_net.pt`
- `model/feature_columns.json`
- `model/metadata.json`

Testing
1. Run tests:
   pytest
