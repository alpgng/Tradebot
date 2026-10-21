"""Saf pandas ile teknik indikatörler (pandas-ta bağımlılığı olmadan)."""
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # Hiç kayıp yoksa RSI 100'dür.
    out = out.where(avg_loss != 0, 100.0)
    return out.where(avg_gain.notna())


def bollinger(series: pd.Series, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = sma(series, length)
    dev = series.rolling(length).std(ddof=0)
    return pd.DataFrame({"lower": mid - std * dev, "mid": mid, "upper": mid + std * dev})


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(series, fast) - ema(series, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def crossed_above(a: pd.Series, b: pd.Series) -> bool:
    """Son mumda a, b'yi aşağıdan yukarı kesti mi?"""
    if len(a) < 2:
        return False
    prev_a, prev_b, cur_a, cur_b = a.iloc[-2], b.iloc[-2], a.iloc[-1], b.iloc[-1]
    if pd.isna([prev_a, prev_b, cur_a, cur_b]).any():
        return False
    return prev_a <= prev_b and cur_a > cur_b


def crossed_below(a: pd.Series, b: pd.Series) -> bool:
    return crossed_above(b, a)
