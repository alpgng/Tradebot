from .. import indicators as ind
from .base import BUY, SELL, Param, Signal, Strategy


class RSIStrategy(Strategy):
    key = "rsi"
    name = "RSI Aşırı Alım/Satım"
    description = "RSI aşırı satım seviyesinin altına indiğinde alım, aşırı alım seviyesinin üstüne çıktığında satım."
    params = [
        Param("length", "int", 14, "RSI periyodu", 2, 100),
        Param("oversold", "float", 30, "Aşırı satım (alım) seviyesi", 1, 50),
        Param("overbought", "float", 70, "Aşırı alım (satım) seviyesi", 50, 99),
    ]

    @classmethod
    def check(cls, params):
        if params["oversold"] >= params["overbought"]:
            raise ValueError("Aşırı satım seviyesi aşırı alım seviyesinden küçük olmalı")

    def min_candles(self):
        return self.p["length"] * 3

    def evaluate(self, df):
        value = ind.rsi(df["close"], self.p["length"]).iloc[-1]
        if value != value:  # NaN
            return Signal(None)
        if value < self.p["oversold"]:
            return Signal(BUY, [f"RSI {value:.1f} < {self.p['oversold']}"])
        if value > self.p["overbought"]:
            return Signal(SELL, [f"RSI {value:.1f} > {self.p['overbought']}"])
        return Signal(None)
