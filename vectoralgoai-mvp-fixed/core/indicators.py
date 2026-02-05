import pandas as pd


def _get_source(df: pd.DataFrame, source: str = "close") -> pd.Series:
    if source not in df.columns:
        raise ValueError(f"Source column '{source}' not found in DataFrame")
    return df[source]


def ema(df: pd.DataFrame, name: str, period: int, source: str = "close") -> pd.DataFrame:
    src = _get_source(df, source)
    df[name] = src.ewm(span=period, adjust=False).mean()
    return df


def rsi(df: pd.DataFrame, name: str, period: int, source: str = "close") -> pd.DataFrame:
    src = _get_source(df, source)
    delta = src.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    df[name] = 100 - (100 / (1 + rs))
    return df


def atr(df: pd.DataFrame, name: str, period: int) -> pd.DataFrame:
    tr1 = (df["high"] - df["low"]).abs()
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df[name] = tr.rolling(window=period).mean()
    return df


INDICATOR_REGISTRY = {
    "ema": ema,
    "rsi": rsi,
    "atr": atr,
    # add more later if needed (sma, bbands, etc.)
}


def apply_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    for ind in cfg.indicators:
        func = INDICATOR_REGISTRY.get(ind.type)
        if not func:
            st.warning(f"Unknown indicator type: {ind.type}")
            continue
        df = func(df, ind.name, ind.period, getattr(ind, "source", "close"))
    return df