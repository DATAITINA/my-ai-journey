Fraud Intelligence System Architecture

Components
- `data/transaction_generation.py` generates synthetic QPay-like transaction, offline-grant, and redemption payloads and provides rule-based explanations.
- `model/train.py` builds features, trains `FraudNet`, and writes model artifacts.
- `model/infer.py` loads model artifacts and serves cached inference.
- `api/fraud_api.py` exposes generic scoring plus QPay-specific grant request/redemption scoring endpoints.
- `utils/device_registry.py` tracks trusted devices and accepted counters, optionally backed by Postgres.

Data Flow
1. Synthetic QPay transactions and redemption contexts are generated with labels based on heuristic rules.
2. Training converts timestamps to hour/weekday, drops high-cardinality IDs, and one-hot encodes categoricals.
3. `FraudNet` is trained with BCE loss and saved as `fraud_net.pt`.
4. Inference aligns incoming feature columns to the training schema and returns a sigmoid risk score.
5. Rule checks enforce device trust, counter freshness, wallet status, grant status, grant limits, and merchant readiness before approval.

Artifacts
- `model/fraud_net.pt` model weights
- `model/feature_columns.json` one-hot feature schema
- `model/metadata.json` training metadata and last-run metrics

Runtime Behavior
- The API can auto-train on startup when `FRAUD_AUTO_TRAIN=1` if artifacts are missing.
- Model weights and columns are cached in memory after first load to reduce latency.

Known Constraints
- Data and labels are synthetic and not representative of production fraud patterns.
- Explanations are rule-based heuristics and are not derived from the model.
- Real signature verification and live backend state sync still need production integration with the QPay service.

CONCLUSION
So, basically the Fraud Intelligent System works when a real QPay payment comes in, we arrange its details in the same format the model learned from. Then the model gives a risk score between 0 and 1. Close to 0 means low risk. Close to 1 means high risk.

Even if the model gives a score, some things must be checked directly: is the device trusted, is the QR counter fresh, is the wallet active, is the grant active, is the amount within the grant limit, and is the merchant ready. If any hard rule fails, the payment is rejected before approval.