import numpy as np
import pandas as pd
import pytest

from tradebot.config import Settings


def make_df(closes):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1h", tz="UTC")
    return pd.DataFrame({"open": closes, "high": closes * 1.001, "low": closes * 0.999,
                         "close": closes, "volume": 1.0}, index=idx)


@pytest.fixture
def settings(tmp_path):
    return Settings(admin_username="admin", admin_password="pw", secret_key="x" * 32,
                    binance_api_key="", binance_api_secret="", binance_testnet_api_key="",
                    binance_testnet_api_secret="", allow_live_trading=False,
                    database_path=str(tmp_path / "test.db"), resume_bots_on_startup=False,
                    session_https_only=False)
