from .. import indicators as ind
from .base import BUY, SELL, Param, Signal, Strategy


class BollingerStrategy(Strategy):
    key = "bollinger"
    name = "Bollinger Bantları"
    description = ("Kapanış alt bandın altındaysa alım, üst bandın üstündeyse satım. "
                   "(Eski kodda alt/üst bant yer değiştirmişti, düzeltildi.)")
    params = [
        Param("length", "int", 20, "Periyot", 2, 200),
        Param("std", "float", 2.0, "Standart sapma çarpanı", 0.5, 5),
    ]

    def min_candles(self):
        return self.p["length"] + 1

    def evaluate(self, df):
        bb = ind.bollinger(df["close"], self.p["length"], self.p["std"]).iloc[-1]
        close = df["close"].iloc[-1]
        if close < bb["lower"]:
            return Signal(BUY, [f"Kapanış {close:.2f} alt bandın ({bb['lower']:.2f}) altında"])
        if close > bb["upper"]:
            return Signal(SELL, [f"Kapanış {close:.2f} üst bandın ({bb['upper']:.2f}) üstünde"])
        return Signal(None)
