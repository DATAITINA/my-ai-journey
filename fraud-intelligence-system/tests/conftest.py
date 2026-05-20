from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.infer import artifacts_exist, clear_model_cache  # noqa: E402
from utils.device_registry import clear_registry  # noqa: E402
from model.train import train  # noqa: E402


def pytest_sessionstart() -> None:
    if not artifacts_exist():
        train()
    clear_model_cache()
    clear_registry()
