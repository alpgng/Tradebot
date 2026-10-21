from .. import indicators as ind
from .base import BUY, SELL, Param, Signal, Strategy


class CombinedStrategy(Strategy):
    """Orijinal TradeCode.py'deki indikatör setinin düzeltilmiş hali.

    Her indikatör bir oy verir; bir yönde en az `min_votes` oy varsa ve karşı yönde
    o kadar oy yoksa işlem yapılır. Eski koddaki gibi aynı turda hem alım hem satım olmaz.
    """

    key = "combined"
    name = "Kombine (Golden Cross + BB + RSI + MACD)"
    description = ("Orijinal botun indikatörleri, oylama ile. Golden Cross ve MACD sadece kesişim anında oy verir, "
                   "Bollinger bantları doğru yönde.")
    params = [
        Param("sma_fast", "int", 50, "Hızlı SMA", 2, 500),
        Param("sma_slow", "int", 200, "Yavaş SMA", 3, 1000),
        Param("bb_length", "int", 20, "Bollinger periyodu", 2, 200),
        Param("bb_std", "float", 2.0, "Bollinger std", 0.5, 5),
        Param("rsi_length", "int", 14, "RSI periyodu", 2, 100),
        Param("rsi_oversold", "float", 30, "RSI aşırı satım", 1, 50),
        Param("rsi_overbought", "float", 70, "RSI aşırı alım", 50, 99),
        Param("macd_fast", "int", 12, "MACD hızlı", 2, 100),
        Param("macd_slow", "int", 26, "MACD yavaş", 3, 200),
        Param("macd_signal", "int", 9, "MACD sinyal", 2, 100),
        Param("min_votes", "int", 2, "İşlem için gereken min. oy", 1, 4),
    ]

    @classmethod
    def check(cls, params):
        if params["sma_fast"] >= params["sma_slow"]:
            raise ValueError("Hızlı SMA periyodu yavaş SMA'dan küçük olmalı")
        if params["macd_fast"] >= params["macd_slow"]:
            raise ValueError("MACD hızlı periyodu yavaş periyottan küçük olmalı")
        if params["rsi_oversold"] >= params["rsi_overbought"]:
            raise ValueError("RSI aşırı satım seviyesi aşırı alım seviyesinden küçük olmalı")

    def min_candles(self):
        return max(self.p["sma_slow"], self.p["macd_slow"] * 3, self.p["bb_length"]) + 2

    def evaluate(self, df):
        close = df["close"]
        p = self.p
        buy, sell = [], []

        fast, slow = ind.sma(close, p["sma_fast"]), ind.sma(close, p["sma_slow"])
        if ind.crossed_above(fast, slow):
            buy.append("Golden Cross")
        elif ind.crossed_below(fast, slow):
            sell.append("Death Cross")

        bb = ind.bollinger(close, p["bb_length"], p["bb_std"]).iloc[-1]
        last = close.iloc[-1]
        if last < bb["lower"]:
            buy.append("Fiyat Bollinger alt bandının altında")
        elif last > bb["upper"]:
            sell.append("Fiyat Bollinger üst bandının üstünde")

        r = ind.rsi(close, p["rsi_length"]).iloc[-1]
        if r == r:
            if r < p["rsi_oversold"]:
                buy.append(f"RSI aşırı satım ({r:.1f})")
            elif r > p["rsi_overbought"]:
                sell.append(f"RSI aşırı alım ({r:.1f})")

        m = ind.macd(close, p["macd_fast"], p["macd_slow"], p["macd_signal"])
        if ind.crossed_above(m["macd"], m["signal"]):
            buy.append("MACD pozitif kesişim")
        elif ind.crossed_below(m["macd"], m["signal"]):
            sell.append("MACD negatif kesişim")

        need = p["min_votes"]
        if len(buy) >= need and len(sell) < need:
            return Signal(BUY, buy)
        if len(sell) >= need and len(buy) < need:
            return Signal(SELL, sell)
        return Signal(None, buy + sell)
