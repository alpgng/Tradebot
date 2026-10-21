import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings, load_settings
from .db import Database
from .exchange import MODES
from .strategies import STRATEGIES, get_strategy
from .worker import BotManager

STATIC = Path(__file__).parent / "static"
INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w")


class LoginIn(BaseModel):
    username: str
    password: str


class BotIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    symbol: str = Field(pattern=r"^[A-Za-z0-9]{5,20}$")
    interval: str = "1h"
    strategy: str = "combined"
    params: dict = Field(default_factory=dict)
    quantity: float = Field(gt=0)
    mode: str = "dry"
    poll_seconds: int = Field(default=60, ge=10, le=3600)

    @field_validator("symbol")
    @classmethod
    def upper(cls, v):
        return v.upper()

    @field_validator("interval")
    @classmethod
    def valid_interval(cls, v):
        if v not in INTERVALS:
            raise ValueError(f"interval şunlardan biri olmalı: {', '.join(INTERVALS)}")
        return v

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v):
        if v not in MODES:
            raise ValueError(f"mode şunlardan biri olmalı: {', '.join(MODES)}")
        return v


class BotPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    symbol: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9]{5,20}$")
    interval: Optional[str] = None
    strategy: Optional[str] = None
    params: Optional[dict] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    mode: Optional[str] = None
    poll_seconds: Optional[int] = Field(default=None, ge=10, le=3600)

    @field_validator("symbol")
    @classmethod
    def upper(cls, v):
        return v.upper() if v else v

    @field_validator("interval")
    @classmethod
    def valid_interval(cls, v):
        if v is not None and v not in INTERVALS:
            raise ValueError(f"interval şunlardan biri olmalı: {', '.join(INTERVALS)}")
        return v

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v):
        if v is not None and v not in MODES:
            raise ValueError(f"mode şunlardan biri olmalı: {', '.join(MODES)}")
        return v


def create_app(settings: Optional[Settings] = None, exchange_factory=None) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.database_path)
    manager = BotManager(db, settings, exchange_factory)

    @asynccontextmanager
    async def lifespan(app):
        if settings.resume_bots_on_startup:
            manager.resume()
        else:
            for bot in db.list_bots():
                if bot["status"] == "running":
                    db.update_bot(bot["id"], status="stopped")
        yield
        manager.shutdown()

    app = FastAPI(title="Tradebot Panel", lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="strict",
                       https_only=settings.session_https_only, max_age=7 * 24 * 3600)
    app.state.db = db
    app.state.manager = manager

    def require_user(request: Request):
        if request.session.get("user") != settings.admin_username:
            raise HTTPException(401, "Giriş gerekli")
        return request.session["user"]

    def bot_or_404(bot_id: int) -> dict:
        bot = db.get_bot(bot_id)
        if bot is None:
            raise HTTPException(404, "Bot bulunamadı")
        return bot

    def public(bot: dict) -> dict:
        return {**bot, "running": manager.is_running(bot["id"])}

    def check_params(strategy: str, params: dict) -> dict:
        try:
            return get_strategy(strategy).validate_params(params)
        except ValueError as e:
            raise HTTPException(422, str(e))

    def check_mode(mode: str):
        if mode == "live" and not settings.allow_live_trading:
            raise HTTPException(403, "Live mod kapalı (.env: ALLOW_LIVE_TRADING=true)")

    # --- sayfa ---
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    # --- auth ---
    @app.post("/api/login")
    def login(body: LoginIn, request: Request):
        if not settings.admin_password:
            raise HTTPException(503, "ADMIN_PASSWORD .env içinde tanımlı değil")
        ok_user = hmac.compare_digest(body.username.encode(), settings.admin_username.encode())
        ok_pass = hmac.compare_digest(body.password.encode(), settings.admin_password.encode())
        if not (ok_user and ok_pass):
            time.sleep(1)  # kaba kuvvet denemelerini yavaşlat
            raise HTTPException(401, "Kullanıcı adı veya şifre hatalı")
        request.session["user"] = settings.admin_username
        return {"user": settings.admin_username}

    @app.post("/api/logout")
    def logout(request: Request):
        request.session.clear()
        return {"ok": True}

    @app.get("/api/me")
    def me(user=Depends(require_user)):
        return {"user": user, "allow_live_trading": settings.allow_live_trading,
                "intervals": INTERVALS, "modes": MODES}

    # --- strateji ---
    @app.get("/api/strategies")
    def strategies(user=Depends(require_user)):
        return [cls.schema() for cls in STRATEGIES.values()]

    # --- botlar ---
    @app.get("/api/bots")
    def list_bots(user=Depends(require_user)):
        return [public(b) for b in db.list_bots()]

    @app.post("/api/bots", status_code=201)
    def create_bot(body: BotIn, user=Depends(require_user)):
        check_mode(body.mode)
        data = body.model_dump()
        data["params"] = check_params(body.strategy, body.params)
        return public(db.create_bot(data))

    @app.get("/api/bots/{bot_id}")
    def get_bot(bot_id: int, user=Depends(require_user)):
        return public(bot_or_404(bot_id))

    @app.patch("/api/bots/{bot_id}")
    def update_bot(bot_id: int, body: BotPatch, user=Depends(require_user)):
        bot = bot_or_404(bot_id)
        changes = body.model_dump(exclude_none=True)
        running = manager.is_running(bot_id)
        for key in ("symbol", "mode", "strategy"):
            if key in changes and changes[key] != bot[key]:
                if running:
                    raise HTTPException(409, f"'{key}' değiştirmek için önce botu durdurun")
                if key in ("symbol", "mode") and bot["position_qty"] > 0:
                    raise HTTPException(409, f"Açık pozisyon varken '{key}' değiştirilemez")
        if "mode" in changes:
            check_mode(changes["mode"])
        strategy = changes.get("strategy", bot["strategy"])
        if "params" in changes or "strategy" in changes:
            params = changes.get("params", bot["params"] if strategy == bot["strategy"] else {})
            changes["params"] = check_params(strategy, params)
        if not changes:
            return public(bot)
        updated = db.update_bot(bot_id, **changes)
        db.log(bot_id, "INFO", "Ayarlar güncellendi: " + ", ".join(sorted(changes)))
        return public(updated)

    @app.delete("/api/bots/{bot_id}")
    def delete_bot(bot_id: int, user=Depends(require_user)):
        bot_or_404(bot_id)
        manager.stop(bot_id)
        db.delete_bot(bot_id)
        return {"ok": True}

    @app.post("/api/bots/{bot_id}/start")
    def start_bot(bot_id: int, user=Depends(require_user)):
        bot_or_404(bot_id)
        try:
            manager.start(bot_id)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        return public(db.get_bot(bot_id))

    @app.post("/api/bots/{bot_id}/stop")
    def stop_bot(bot_id: int, user=Depends(require_user)):
        bot_or_404(bot_id)
        manager.stop(bot_id)
        return public(db.get_bot(bot_id))

    @app.post("/api/bots/{bot_id}/reset-position")
    def reset_position(bot_id: int, user=Depends(require_user)):
        """Pozisyon kaydını emir göndermeden sıfırlar (örn. borsada elle kapatıldıysa)."""
        bot_or_404(bot_id)
        db.update_bot(bot_id, position_qty=0, entry_price=None)
        db.log(bot_id, "WARNING", "Pozisyon kaydı elle sıfırlandı (emir gönderilmedi)")
        return public(db.get_bot(bot_id))

    @app.get("/api/bots/{bot_id}/logs")
    def bot_logs(bot_id: int, limit: int = 200, user=Depends(require_user)):
        bot_or_404(bot_id)
        return db.list_logs(bot_id, min(limit, 1000))

    @app.get("/api/bots/{bot_id}/orders")
    def bot_orders(bot_id: int, limit: int = 100, user=Depends(require_user)):
        bot_or_404(bot_id)
        return db.list_orders(bot_id, min(limit, 1000))

    @app.get("/api/orders")
    def all_orders(limit: int = 100, user=Depends(require_user)):
        return db.list_orders(None, min(limit, 1000))

    @app.get("/api/logs")
    def all_logs(limit: int = 200, user=Depends(require_user)):
        return db.list_logs(None, min(limit, 1000))

    return app
