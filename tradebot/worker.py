"""Her bot ayrı bir thread'de çalışır. Her turda bot ayarları veritabanından yeniden okunur,
bu sayede panelden değiştirilen parametreler botu durdurmadan bir sonraki turda devreye girer."""
import logging
import threading

from .db import Database, now
from .exchange import BinanceExchange
from .strategies import BUY, SELL, get_strategy

log = logging.getLogger("tradebot")


class BotWorker(threading.Thread):
    def __init__(self, manager: "BotManager", bot_id: int):
        super().__init__(name=f"bot-{bot_id}", daemon=True)
        self.manager = manager
        self.db: Database = manager.db
        self.bot_id = bot_id
        self.stop_event = threading.Event()
        self._exchange = None
        self._exchange_mode = None

    def exchange(self, mode):
        if self._exchange is None or self._exchange_mode != mode:
            self._exchange = self.manager.exchange_factory(mode)
            self._exchange_mode = mode
        return self._exchange

    def run(self):
        self.db.log(self.bot_id, "INFO", "Bot başlatıldı")
        while not self.stop_event.is_set():
            bot = self.db.get_bot(self.bot_id)
            if bot is None:
                break
            try:
                self.tick(bot)
                if bot["last_error"]:
                    self.db.update_bot(self.bot_id, last_error=None)
            except Exception as e:  # bot hatada ölmesin, bir sonraki turda tekrar denesin
                log.exception("bot %s tick hatası", self.bot_id)
                self.db.log(self.bot_id, "ERROR", f"{type(e).__name__}: {e}")
                self.db.update_bot(self.bot_id, last_error=str(e))
            self.stop_event.wait(max(5, int(bot["poll_seconds"])))
        self.db.log(self.bot_id, "INFO", "Bot durduruldu")

    def tick(self, bot: dict):
        if bot["mode"] == "live" and not self.manager.settings.allow_live_trading:
            raise RuntimeError("ALLOW_LIVE_TRADING=false iken live mod çalıştırılamaz")
        strategy = get_strategy(bot["strategy"])(bot["params"])
        exch = self.exchange(bot["mode"])
        need = strategy.min_candles()
        df = exch.get_candles(bot["symbol"], bot["interval"], need + 10)
        self.db.update_bot(self.bot_id, last_run_at=now())
        if len(df) < need:
            self.db.log(self.bot_id, "WARNING", f"Yetersiz veri: {len(df)} mum var, {need} gerekli")
            return

        candle_time = df.index[-1].isoformat()
        if candle_time == bot["last_candle_time"]:
            return  # bu mum zaten değerlendirildi, yeni mum kapanmasını bekle
        self.db.update_bot(self.bot_id, last_candle_time=candle_time)

        signal = strategy.evaluate(df)
        price = float(df["close"].iloc[-1])
        reasons = "; ".join(signal.reasons)
        in_position = bot["position_qty"] > 0

        if signal.action == BUY and not in_position:
            fill = exch.market_order(bot["symbol"], BUY, bot["quantity"], price)
            self.db.add_order(self.bot_id, BUY, fill["quantity"], fill["price"], bot["mode"], reasons,
                              fill["order_id"], fill["raw"])
            self.db.update_bot(self.bot_id, position_qty=fill["quantity"], entry_price=fill["price"])
            self.db.log(self.bot_id, "INFO", f"ALIM {fill['quantity']} @ {fill['price']:.2f} ({reasons})")
        elif signal.action == SELL and in_position:
            fill = exch.market_order(bot["symbol"], SELL, bot["position_qty"], price)
            pnl = (fill["price"] - (bot["entry_price"] or fill["price"])) * fill["quantity"]
            self.db.add_order(self.bot_id, SELL, fill["quantity"], fill["price"], bot["mode"], reasons,
                              fill["order_id"], fill["raw"])
            self.db.update_bot(self.bot_id, position_qty=0, entry_price=None)
            self.db.log(self.bot_id, "INFO",
                        f"SATIM {fill['quantity']} @ {fill['price']:.2f}, K/Z ≈ {pnl:.2f} ({reasons})")
        elif signal.action:
            state = "pozisyon zaten açık" if in_position else "açık pozisyon yok"
            self.db.log(self.bot_id, "INFO", f"{signal.action} sinyali yok sayıldı: {state} ({reasons})")
        else:
            self.db.log(self.bot_id, "DEBUG", f"{candle_time} kapanış {price:.2f}: sinyal yok"
                        + (f" ({reasons})" if reasons else ""))


class BotManager:
    def __init__(self, db: Database, settings, exchange_factory=None):
        self.db = db
        self.settings = settings
        self.exchange_factory = exchange_factory or self._default_exchange
        self.workers: dict[int, BotWorker] = {}
        self._lock = threading.Lock()

    def _default_exchange(self, mode):
        s = self.settings
        if mode == "live":
            return BinanceExchange(mode, s.binance_api_key, s.binance_api_secret)
        if mode == "testnet":
            return BinanceExchange(mode, s.binance_testnet_api_key, s.binance_testnet_api_secret)
        return BinanceExchange("dry")

    def is_running(self, bot_id: int) -> bool:
        w = self.workers.get(bot_id)
        return bool(w and w.is_alive() and not w.stop_event.is_set())

    def start(self, bot_id: int):
        bot = self.db.get_bot(bot_id)
        if bot is None:
            raise KeyError(bot_id)
        if bot["mode"] == "live" and not self.settings.allow_live_trading:
            raise PermissionError("Live mod kapalı. Açmak için .env içinde ALLOW_LIVE_TRADING=true yapın.")
        with self._lock:
            if self.is_running(bot_id):
                return
            worker = BotWorker(self, bot_id)
            self.workers[bot_id] = worker
            self.db.update_bot(bot_id, status="running", last_error=None)
            worker.start()

    def stop(self, bot_id: int, persist: bool = True, wait: float = 5):
        with self._lock:
            worker = self.workers.pop(bot_id, None)
        if worker:
            worker.stop_event.set()
            worker.join(timeout=wait)
        if persist and self.db.get_bot(bot_id):
            self.db.update_bot(bot_id, status="stopped")

    def resume(self):
        for bot in self.db.list_bots():
            if bot["status"] == "running":
                try:
                    self.start(bot["id"])
                except Exception as e:
                    self.db.log(bot["id"], "ERROR", f"Otomatik başlatılamadı: {e}")
                    self.db.update_bot(bot["id"], status="stopped", last_error=str(e))

    def shutdown(self):
        # Durumları "running" bırak ki sunucu yeniden başladığında devam etsinler.
        for bot_id in list(self.workers):
            self.stop(bot_id, persist=False, wait=2)
