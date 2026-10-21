import numpy as np
import pytest

from tradebot import indicators as ind
from tradebot.strategies import BUY, SELL, get_strategy
from tests.conftest import make_df


def test_bollinger_bands_not_swapped():
    df = make_df(100 + np.sin(np.arange(100)) * 5)
    bb = ind.bollinger(df["close"], 20, 2).dropna()
    assert (bb["lower"] < bb["mid"]).all() and (bb["mid"] < bb["upper"]).all()


def test_bollinger_strategy_direction():
    s = get_strategy("bollinger")({"length": 20, "std": 2})
    base = list(100 + np.sin(np.arange(60)))
    assert s.evaluate(make_df(base + [80])).action == BUY
    assert s.evaluate(make_df(base + [120])).action == SELL


def test_rsi_bounds():
    r = ind.rsi(make_df(100 + np.cumsum(np.random.default_rng(1).normal(size=300)))["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_golden_cross_fires_only_on_cross_candle():
    s = get_strategy("golden_cross")({"fast": 5, "slow": 20})
    closes = [100.0] * 30 + [100 - i for i in range(1, 21)] + [80 + i * 3 for i in range(1, 30)]
    actions = [s.evaluate(make_df(closes[:n])).action for n in range(25, len(closes) + 1)]
    assert actions.count(BUY) == 1  # eski kod: SMA50>SMA200 olduğu her mumda alım yapardı
    assert actions.count(SELL) == 1


def test_combined_never_buy_and_sell_together():
    s = get_strategy("combined")({"sma_fast": 10, "sma_slow": 30, "min_votes": 1})
    closes = 100 + np.cumsum(np.random.default_rng(7).normal(size=400))
    for n in range(100, 400, 3):
        sig = s.evaluate(make_df(closes[:n]))
        assert sig.action in (None, BUY, SELL)


def test_param_validation():
    cls = get_strategy("golden_cross")
    assert cls.validate_params({}) == {"fast": 50, "slow": 200}
    assert cls.validate_params({"fast": "10"})["fast"] == 10
    with pytest.raises(ValueError):
        cls.validate_params({"fast": 300, "slow": 200})
    with pytest.raises(ValueError):
        cls.validate_params({"bogus": 1})
    with pytest.raises(ValueError):
        cls.validate_params({"fast": 1})
