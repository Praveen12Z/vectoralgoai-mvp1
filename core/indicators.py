import pandas as pd
import numpy as np

def _get_source(df: pd.DataFrame, source: str = "close") -> pd.Series:
    if source not in df.columns:
        raise ValueError(f"Source '{source}' not in DataFrame columns")
    return df[source]

# ───────────────────── INDICATOR FUNCTIONS ─────────────────────

def sma(df: pd.DataFrame, name: str, period: int, source: str = "close"):
    df[name] = _get_source(df, source).rolling(period).mean()
    return df

def ema(df: pd.DataFrame, name: str, period: int, source: str = "close"):
    df[name] = _get_source(df, source).ewm(span=period, adjust=False).mean()
    return df

def rsi(df: pd.DataFrame, name: str, period: int = 14, source: str = "close"):
    delta = _get_source(df, source).diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss + 1e-10)
    df[name] = 100 - (100 / (1 + rs))
    return df

def atr(df: pd.DataFrame, name: str, period: int = 14):
    # ATR does NOT use source — works on high/low/close
    tr = pd.concat([
        (df["high"] - df["low"]).abs(),
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    df[name] = tr.rolling(period).mean()
    return df

def macd(df: pd.DataFrame, name: str, fast=12, slow=26, signal=9, source="close"):
    ema_fast = _get_source(df, source).ewm(span=fast, adjust=False).mean()
    ema_slow = _get_source(df, source).ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    df[name + "_macd"] = macd_line
    df[name + "_signal"] = macd_line.ewm(span=signal, adjust=False).mean()
    df[name + "_hist"] = df[name + "_macd"] - df[name + "_signal"]
    return df

def bbands(df: pd.DataFrame, name: str, period: int = 20, std: float = 2.0, source="close"):
    mid = _get_source(df, source).rolling(period).mean()
    std_dev = _get_source(df, source).rolling(period).std()
    df[name + "_upper"] = mid + std * std_dev
    df[name + "_middle"] = mid
    df[name + "_lower"] = mid - std * std_dev
    return df

def stoch(df: pd.DataFrame, name: str, k=14, d=3):
    low_min = df["low"].rolling(k).min()
    high_max = df["high"].rolling(k).max()
    df[name + "_k"] = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
    df[name + "_d"] = df[name + "_k"].rolling(d).mean()
    return df

def adx(df: pd.DataFrame, name: str, period: int = 14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean()
    up = df["high"] - df["high"].shift()
    dn = df["low"].shift() - df["low"]
    pos_di = 100 * (up.clip(lower=0).rolling(period).mean() / atr_val)
    neg_di = 100 * (dn.clip(lower=0).rolling(period).mean() / atr_val)
    dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di + 1e-10)
    df[name] = dx.rolling(period).mean()
    return df

# ... (keep your other indicators: cci, obv, supertrend, vwap, psar, willr, roc, mfi)

# ──────────────────────────────────────────────────────────────
# REGISTRY – now with source support flag
# ──────────────────────────────────────────────────────────────
INDICATOR_REGISTRY = {
    "sma": sma,
    "ema": ema,
    "rsi": rsi,
    "atr": atr,          # no source
    "macd": macd,
    "bbands": bbands,
    "stoch": stoch,      # no source
    "adx": adx,          # no source
    "cci": cci,          # no source
    "obv": obv,          # no source
    "supertrend": supertrend,  # no source
    "vwap": vwap,        # no source
    "psar": psar,        # no source
    "willr": willr,      # no source
    "roc": roc,          # no source
    "mfi": mfi,          # no source
}

# ──────────────────────────────────────────────────────────────
# FIXED APPLY FUNCTION – only pass source when supported
# ──────────────────────────────────────────────────────────────
def apply_all_indicators(df: pd.DataFrame, cfg):
    df = df.copy()

    # Indicators that accept 'source' parameter
    source_supported = {"sma", "ema", "rsi", "macd", "bbands"}

    for ind in cfg.indicators:
        func = INDICATOR_REGISTRY.get(ind.type.lower())
        if not func:
            st.warning(f"Unknown indicator type: {ind.type}")
            continue

        # Prepare arguments
        kwargs = {"name": ind.name, "period": ind.period}
        if ind.type.lower() in source_supported:
            kwargs["source"] = getattr(ind, "source", "close")

        # Call function safely
        try:
            df = func(df, **kwargs)
        except TypeError as e:
            st.warning(f"Indicator {ind.name} ({ind.type}) failed: {str(e)}. Skipping.")
        except Exception as e:
            st.error(f"Critical error in {ind.name}: {str(e)}")

    return df
