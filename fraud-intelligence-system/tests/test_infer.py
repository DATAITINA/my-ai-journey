from data.transaction_generation import generate_transaction
from model.infer import _load_columns, _prepare_features, predict


def test_prepare_features_aligns_columns() -> None:
    tx = generate_transaction()
    columns = _load_columns()
    features = _prepare_features(tx, columns)
    assert features.shape == (1, len(columns))


def test_predict_returns_probability() -> None:
    tx = generate_transaction()
    score = predict(tx)
    assert 0.0 <= score <= 1.0
