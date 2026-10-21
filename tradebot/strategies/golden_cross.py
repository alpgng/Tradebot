from .. import indicators as ind
from .base import BUY, SELL, Param, Signal, Strategy


class GoldenCrossStrategy(Strategy):
    key = "golden_cross"
    name = "Golden Cross / Death Cross"
    description = ("Hızlı SMA yavaş SMA'yı yukarı kestiği mumda alım, aşağı kestiği mumda satım. "
                   "(Eski kod 'SMA50 > SMA200' olduğu her saat alım yapıyordu; artık sadece kesişim anında.)")
    params = [
        Param("fast", "int", 50, "Hızlı SMA periyodu", 2, 500),
        Param("slow", "int", 200, "Yavaş SMA periyodu", 3, 1000),
    ]

    @classmethod
    def check(cls, params):
        if params["fast"] >= params["slow"]:
            raise ValueError("Hızlı SMA periyodu yavaş SMA'dan küçük olmalı")

    def min_candles(self):
        return self.p["slow"] + 2

    def evaluate(self, df):
        fast = ind.sma(df["close"], self.p["fast"])
        slow = ind.sma(df["close"], self.p["slow"])
        if ind.crossed_above(fast, slow):
            return Signal(BUY, [f"SMA{self.p['fast']} SMA{self.p['slow']}'ü yukarı kesti (Golden Cross)"])
        if ind.crossed_below(fast, slow):
            return Signal(SELL, [f"SMA{self.p['fast']} SMA{self.p['slow']}'ü aşağı kesti (Death Cross)"])
        return Signal(None)
