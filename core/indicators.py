import pandas as pd
import numpy as np

def _get_source(df: pd.DataFrame, source: str = "close") -> pd.Series:
    if source not in df.columns:
        raise ValueError(f"Source '{source}' not found")
    return df[source]

# ───────────────────── INDICATOR FUNCTIONS ─────────────────────

def sma(df: pd.DataFrame, name: str, period: int, source: str = "close"):
    df[name] = _get_source(df, source).rolling(window=period).mean()
    return df

def ema(df: pd.DataFrame, name: str, period: int, source: str = "close"):
    df[name] = _get_source(df, source).ewm(span=period, adjust=False).mean()
    return df

def rsi(df: pd.DataFrame, name: str, period: int = 14, source: str = "close"):
    delta = _get_source(df, source).diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    df[name] = 100 - (100 / (1 + rs))
    return df

def atr(df: pd.DataFrame, name: str, period: int = 14):
    tr = np.maximum.reduce([
        (df["high"] - df["low"]).abs(),
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ])
    df[name] = pd.Series(tr).rolling(window=period).mean()
    return df

def macd(df: pd.DataFrame, name: str, fast: int = 12, slow: int = 26, signal: int = 9, source: str = "close"):
    ema_fast = _get_source(df, source).ewm(span=fast, adjust=False).mean()
    ema_slow = _get_source(df, source).ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    df[name + "_macd"] = macd_line
    df[name + "_signal"] = macd_line.ewm(span=signal, adjust=False).mean()
    df[name + "_hist"] = df[name + "_macd"] - df[name + "_signal"]
    return df

def bbands(df: pd.DataFrame, name: str, period: int = 20, std: float = 2.0, source: str = "close"):
    mid = _get_source(df, source).rolling(window=period).mean()
    std_dev = _get_source(df, source).rolling(window=period).std()
    df[name + "_upper"] = mid + std * std_dev
    df[name + "_middle"] = mid
    df[name + "_lower"] = mid - std * std_dev
    return df

def stoch(df: pd.DataFrame, name: str, k: int = 14, d: int = 3):
    low_min = df["low"].rolling(window=k).min()
    high_max = df["high"].rolling(window=k).max()
    df[name + "_k"] = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
    df[name + "_d"] = df[name + "_k"].rolling(window=d).mean()
    return df

def adx(df: pd.DataFrame, name: str, period: int = 14):
    tr = np.maximum.reduce([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ])
    atr_val = pd.Series(tr).rolling(window=period).mean()
    up = df["high"] - df["high"].shift()
    dn = df["low"].shift() - df["low"]
    pos_di = 100 * (up.clip(lower=0).rolling(window=period).mean() / atr_val)
    neg_di = 100 * (dn.clip(lower=0).rolling(window=period).mean() / atr_val)
    dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di + 1e-10)
    df[name] = dx.rolling(window=period).mean()
    return df

def cci(df: pd.DataFrame, name: str, period: int = 20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = (tp - sma_tp).abs().rolling(window=period).mean()
    df[name] = (tp - sma_tp) / (0.015 * mad)
    return df

def obv(df: pd.DataFrame, name: str):
    df[name] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    return df

def supertrend(df: pd.DataFrame, name: str, period: int = 10, multiplier: float = 3.0):
    hl2 = (df["high"] + df["low"]) / 2
    atr_val = atr(df.copy(), "atr_temp", period)["atr_temp"]
    upper = hl2 + multiplier * atr_val
    lower = hl2 - multiplier * atr_val
    df[name + "_supertrend"] = np.where(df["close"] > upper.shift(), lower, upper)
    return df

def vwap(df: pd.DataFrame, name: str):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df[name] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return df

def psar(df: pd.DataFrame, name: str, af_start: float = 0.02, af_max: float = 0.2):
    df[name] = df["close"].rolling(10).mean()  # placeholder – full PSAR later
    return df

def willr(df: pd.DataFrame, name: str, period: int = 14):
    hh = df["high"].rolling(period).max()
    ll = df["low"].rolling(period).min()
    df[name] = -100 * (hh - df["close"]) / (hh - ll + 1e-10)
    return df

def roc(df: pd.DataFrame, name: str, period: int = 12):
    df[name] = (df["close"] / df["close"].shift(period) - 1) * 100
    return df

def mfi(df: pd.DataFrame, name: str, period: int = 14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    delta = tp.diff()
    pos_mf = mf.where(delta > 0, 0).rolling(period).sum()
    neg_mf = mf.where(delta < 0, 0).rolling(period).sum()
    mr = pos_mf / neg_mf
    df[name] = 100 - (100 / (1 + mr))
    return df

# ──────────────────────────────────────────────────────────────
# REGISTRY
# ──────────────────────────────────────────────────────────────
INDICATOR_REGISTRY = {
    "sma": sma, "ema": ema, "rsi": rsi, "atr": atr,
    "macd": macd, "bbands": bbands, "stoch": stoch,
    "adx": adx, "cci": cci, "obv": obv, "supertrend": supertrend,
    "vwap": vwap, "psar": psar, "willr": willr, "roc": roc, "mfi": mfi,
}

# ──────────────────────────────────────────────────────────────
# APPLY FUNCTION – returns (df, skipped list)
# ──────────────────────────────────────────────────────────────
def apply_all_indicators(df: pd.DataFrame, cfg):
    df = df.copy()
    source_supported = {"sma", "ema", "rsi", "macd", "bbands"}
    skipped = []

    for ind in cfg.indicators:
        func = INDICATOR_REGISTRY.get(ind.type.lower())
        if not func:
            skipped.append(f"Unknown type: {ind.type}")
            continue

        try:
            if ind.type.lower() in source_supported:
                df = func(df, name=ind.name, period=ind.period, source=getattr(ind, "source", "close"))
            else:
                # For indicators that don't take 'period' or 'source'
                if ind.type.lower() == "macd":
                    df = func(df, name=ind.name, fast=12, slow=26, signal=9)
                else:
                    df = func(df, name=ind.name, period=ind.period)
        except Exception as e:
            skipped.append(f"{ind.name} ({ind.type}): {str(e)}")

    return df, skipped
