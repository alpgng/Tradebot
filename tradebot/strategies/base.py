from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

BUY = "BUY"
SELL = "SELL"


@dataclass
class Param:
    name: str
    type: str  # "int" | "float"
    default: Any
    label: str
    min: Optional[float] = None
    max: Optional[float] = None

    def coerce(self, value: Any) -> Any:
        try:
            value = int(value) if self.type == "int" else float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{self.name}: sayı olmalı")
        if self.type == "int" and isinstance(value, float):
            value = int(value)
        if self.min is not None and value < self.min:
            raise ValueError(f"{self.name}: en az {self.min} olmalı")
        if self.max is not None and value > self.max:
            raise ValueError(f"{self.name}: en fazla {self.max} olmalı")
        return value

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type, "default": self.default,
                "label": self.label, "min": self.min, "max": self.max}


@dataclass
class Signal:
    action: Optional[str]  # BUY, SELL veya None
    reasons: list = field(default_factory=list)


class Strategy:
    """Tüm stratejilerin temel sınıfı.

    evaluate() yalnızca KAPANMIŞ mumları alır ve tek bir karar döner.
    Pozisyon takibi worker'dadır: BUY sadece pozisyon yokken, SELL sadece pozisyon varken uygulanır.
    """

    key: str = ""
    name: str = ""
    description: str = ""
    params: list = []

    def __init__(self, params: Optional[dict] = None):
        self.p = self.validate_params(params or {})

    @classmethod
    def validate_params(cls, params: dict) -> dict:
        unknown = set(params) - {p.name for p in cls.params}
        if unknown:
            raise ValueError(f"Bilinmeyen parametre(ler): {', '.join(sorted(unknown))}")
        out = {}
        for p in cls.params:
            out[p.name] = p.coerce(params[p.name]) if p.name in params else p.default
        cls.check(out)
        return out

    @classmethod
    def check(cls, params: dict) -> None:
        """Parametreler arası kurallar için alt sınıflar override eder (ValueError fırlatır)."""

    @classmethod
    def schema(cls) -> dict:
        return {"key": cls.key, "name": cls.name, "description": cls.description,
                "params": [p.to_dict() for p in cls.params]}

    def min_candles(self) -> int:
        return 50

    def evaluate(self, df: pd.DataFrame) -> Signal:
        raise NotImplementedError
