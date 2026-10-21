"""Borsa erişimi. Modlar:

- dry:     Gerçek piyasa verisi (anahtarsız, public endpoint), emirler sadece simüle edilir.
- testnet: Binance Spot Testnet (https://testnet.binance.vision) — sahte bakiye, gerçek emir akışı.
- live:    Gerçek hesap. ALLOW_LIVE_TRADING=true olmadan kullanılamaz.
"""
import time

import pandas as pd

MODES = ("dry", "testnet", "live")
KLINE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                 "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]


def klines_to_df(klines, now_ms=None) -> pd.DataFrame:
    """Kline listesini DataFrame'e çevirir ve henüz kapanmamış son mumu atar."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    df = pd.DataFrame(klines, columns=KLINE_COLUMNS)
    df = df[df["close_time"].astype("int64") < now_ms]
    df.index = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    return df[["open", "high", "low", "close", "volume"]].astype(float)


class BinanceExchange:
    def __init__(self, mode: str, api_key: str = "", api_secret: str = ""):
        from binance.client import Client  # geç import: testlerde gerek yok

        if mode not in MODES:
            raise ValueError(f"Geçersiz mod: {mode}")
        self.mode = mode
        if mode == "dry":
            self.client = Client(None, None)
        else:
            if not api_key or not api_secret:
                raise RuntimeError(f"{mode} modu için API anahtarları .env içinde tanımlı değil")
            self.client = Client(api_key, api_secret, testnet=(mode == "testnet"))

    def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        # +1: kapanmamış son mum atılacağı için
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=min(limit + 1, 1000))
        return klines_to_df(klines)

    def market_order(self, symbol: str, side: str, quantity: float, ref_price: float) -> dict:
        if self.mode == "dry":
            return {"price": ref_price, "quantity": quantity, "order_id": None, "raw": None}
        order = self.client.create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        executed = float(order.get("executedQty") or 0) or quantity
        quote = float(order.get("cummulativeQuoteQty") or 0)
        price = quote / executed if quote else ref_price
        return {"price": price, "quantity": executed, "order_id": str(order.get("orderId")), "raw": order}
