import time

import pytest
from fastapi.testclient import TestClient

from tradebot.api import create_app
from tradebot.db import Database
from tradebot.strategies import BUY, SELL, Signal
from tradebot.worker import BotManager, BotWorker
from tests.conftest import make_df


class FakeExchange:
    def __init__(self):
        self.closes = [100.0] * 300
        self.orders = []

    def get_candles(self, symbol, interval, limit):
        return make_df(self.closes)

    def market_order(self, symbol, side, quantity, ref_price):
        self.orders.append((side, quantity))
        return {"price": ref_price, "quantity": quantity, "order_id": None, "raw": None}


def bot_data(**kw):
    d = dict(name="t", symbol="BTCUSDT", interval="1h", strategy="rsi", params={}, quantity=0.01,
             mode="dry", poll_seconds=60)
    d.update(kw)
    return d


def test_position_tracking(settings, monkeypatch):
    db = Database(settings.database_path)
    ex = FakeExchange()
    manager = BotManager(db, settings, lambda mode: ex)
    bot = db.create_bot(bot_data())
    worker = BotWorker(manager, bot["id"])

    signals = iter([Signal(SELL), Signal(BUY), Signal(BUY), Signal(SELL), Signal(SELL)])
    monkeypatch.setattr("tradebot.strategies.rsi.RSIStrategy.evaluate", lambda self, df: next(signals))
    for i in range(5):
        ex.closes = ex.closes + [100.0 + i]  # her turda yeni kapanmış mum
        worker.tick(db.get_bot(bot["id"]))
    assert ex.orders == [(BUY, 0.01), (SELL, 0.01)]
    assert db.get_bot(bot["id"])["position_qty"] == 0
    assert [o["side"] for o in db.list_orders(bot["id"])] == [SELL, BUY]


def test_same_candle_evaluated_once(settings, monkeypatch):
    db = Database(settings.database_path)
    ex = FakeExchange()
    manager = BotManager(db, settings, lambda mode: ex)
    bot = db.create_bot(bot_data())
    calls = []
    monkeypatch.setattr("tradebot.strategies.rsi.RSIStrategy.evaluate",
                        lambda self, df: calls.append(1) or Signal(None))
    worker = BotWorker(manager, bot["id"])
    worker.tick(db.get_bot(bot["id"]))
    worker.tick(db.get_bot(bot["id"]))
    assert len(calls) == 1


@pytest.fixture
def client(settings):
    ex = FakeExchange()
    app = create_app(settings, exchange_factory=lambda mode: ex)
    with TestClient(app) as c:
        yield c


def login(c):
    assert c.post("/api/login", json={"username": "admin", "password": "pw"}).status_code == 200


def test_auth_required(client):
    assert client.get("/api/bots").status_code == 401
    assert client.post("/api/login", json={"username": "admin", "password": "no"}).status_code == 401
    login(client)
    assert client.get("/api/bots").json() == []
    client.post("/api/logout")
    assert client.get("/api/bots").status_code == 401


def test_bot_crud_and_lifecycle(client):
    login(client)
    r = client.post("/api/bots", json=bot_data(symbol="ethusdt", params={"length": 10}))
    assert r.status_code == 201, r.text
    bot = r.json()
    assert bot["symbol"] == "ETHUSDT" and bot["params"]["length"] == 10

    assert client.post("/api/bots", json=bot_data(params={"oversold": 80})).status_code == 422
    assert client.post("/api/bots", json=bot_data(mode="live")).status_code == 403

    r = client.post(f"/api/bots/{bot['id']}/start")
    assert r.json()["running"] and r.json()["status"] == "running"
    # çalışırken parametre değişebilir, mod değişemez
    assert client.patch(f"/api/bots/{bot['id']}", json={"params": {"length": 21}}).status_code == 200
    assert client.patch(f"/api/bots/{bot['id']}", json={"mode": "testnet"}).status_code == 409
    time.sleep(0.2)
    r = client.post(f"/api/bots/{bot['id']}/stop")
    assert not r.json()["running"] and r.json()["status"] == "stopped"
    logs = client.get(f"/api/bots/{bot['id']}/logs").json()
    assert any("Ayarlar güncellendi" in l["message"] for l in logs)

    assert client.patch(f"/api/bots/{bot['id']}", json={"strategy": "golden_cross"}).json()["params"] == \
        {"fast": 50, "slow": 200}
    assert client.delete(f"/api/bots/{bot['id']}").status_code == 200
    assert client.get(f"/api/bots/{bot['id']}").status_code == 404


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Tradebot Panel" in r.text
