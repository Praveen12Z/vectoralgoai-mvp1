# core/indicators.py
import pandas as pd

# -------------------------------------------------------------
# Helper
# -------------------------------------------------------------
def _get_source(df: pd.DataFrame, source: str) -> pd.Series:
    if source not in df.columns:
        raise ValueError(f"Source column '{source}' not found in price data.")
    return df[source]


# -------------------------------------------------------------
# Indicator implementations
# -------------------------------------------------------------
def ema(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    src = _get_source(df, params.get("source", "close"))
    length = int(params.get("length", 20))
    df[name] = src.ewm(span=length, adjust=False).mean()
    return df


def sma(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    src = _get_source(df, params.get("source", "close"))
    length = int(params.get("length", 20))
    df[name] = src.rolling(length).mean()
    return df


def rsi(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    src = _get_source(df, params.get("source", "close"))
    length = int(params.get("length", 14))

    delta = src.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(length).mean()
    avg_loss = loss.rolling(length).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    df[name] = 100 - (100 / (1 + rs))
    return df


def atr(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    """ATR indicator."""
    length = int(params.get("length", 14))
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df[name] = tr.rolling(length).mean()
    return df


def bbands(df: pd.DataFrame, name: str, params: dict) -> pd.DataFrame:
    src = _get_source(df, params.get("source", "close"))
    length = int(params.get("length", 20))
    std_mult = float(params.get("std", 2.0))
    band = params.get("band", "middle")

    ma = src.rolling(length).mean()
    sd = src.rolling(length).std()

    upper = ma + sd * std_mult
    lower = ma - sd * std_mult

    if band == "upper":
        df[name] = upper
    elif band == "lower":
        df[name] = lower
    else:
        df[name] = ma

    return df


# -------------------------------------------------------------
# Registry
# -------------------------------------------------------------
INDICATOR_REGISTRY = {
    "ema": ema,
    "sma": sma,
    "rsi": rsi,
    "atr": atr,
    "bbands": bbands,
}


# -------------------------------------------------------------
# Generic indicator engine
# -------------------------------------------------------------
def apply_indicators(df: pd.DataFrame, indicator_dicts: list) -> pd.DataFrame:
    df = df.copy()
    for icfg in indicator_dicts:
        name = icfg["name"]
        itype = icfg["type"]
        params = icfg.get("params", {})

        if itype not in INDICATOR_REGISTRY:
            raise ValueError(f"Unknown indicator type: {itype}")

        func = INDICATOR_REGISTRY[itype]
        df = func(df, name, params)
    return df


# -------------------------------------------------------------
# Compatibility bridge for old MVP:
# apply_all_indicators(df, StrategyConfig)
# -------------------------------------------------------------
from core.strategy_config import StrategyConfig

def apply_all_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    indicator_dicts = []
    for ind in cfg.indicators:
        indicator_dicts.append(
            {
                "name": ind.name,
                "type": ind.type,
                "params": {
                    "length": ind.period,
                    "source": getattr(ind, "source", "close"),
                },
            }
        )
    return apply_indicators(df, indicator_dicts)
