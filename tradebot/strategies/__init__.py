from .base import BUY, SELL, Param, Signal, Strategy
from .bollinger import BollingerStrategy
from .combined import CombinedStrategy
from .golden_cross import GoldenCrossStrategy
from .rsi import RSIStrategy

STRATEGIES = {cls.key: cls for cls in (CombinedStrategy, GoldenCrossStrategy, RSIStrategy, BollingerStrategy)}


def get_strategy(key: str) -> type:
    try:
        return STRATEGIES[key]
    except KeyError:
        raise ValueError(f"Bilinmeyen strateji: {key}")


__all__ = ["BUY", "SELL", "Param", "Signal", "Strategy", "STRATEGIES", "get_strategy"]
