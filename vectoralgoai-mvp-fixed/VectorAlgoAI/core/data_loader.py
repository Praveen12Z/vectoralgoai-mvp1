# core/data_loader.py
from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd

from massive import RESTClient   # Massive/Polygon official client

API_KEY = "H12mN8iRzm7z2yFfQaKCSv3k3ZcqDxJK"
client = RESTClient(API_KEY)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


# -----------------------------------------------------------
# Market mapper (NAS100 → correct Massive symbol)
# -----------------------------------------------------------
MARKET_MAP = {
    "NAS100": "NDX",    # NASDAQ 100 index
    "US30": "DJI",      # Dow Jones
    "SPX500": "SPX",    # S&P 500
    "XAUUSD": "XAUUSD",
    "EURUSD": "EURUSD",
}


def get_symbol(symbol: str) -> str:
    return MARKET_MAP.get(symbol.upper(), symbol.upper())


# -----------------------------------------------------------
# Low-level Massive fetch
# -----------------------------------------------------------
def _fetch_massive(symbol: str, multiplier: int, timespan: str, years: int) -> pd.DataFrame:
    """
    Fetch raw OHLCV bars from Massive/Polygon and return a clean DataFrame.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=365 * years)

    bars = []
    for bar in client.list_aggs(
        symbol,
        multiplier=multiplier,
        timespan=timespan,
        from_=start_date.strftime("%Y-%m-%d"),
        to=end_date.strftime("%Y-%m-%d"),
        limit=50000,
    ):
        bars.append(bar)

    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "timestamp": pd.to_datetime(b.timestamp, unit="ms"),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
    )

    df = (
        df.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .set_index("timestamp")
    )

    return df[["open", "high", "low", "close", "volume"]]


# -----------------------------------------------------------
# Main OHLCV loader
# -----------------------------------------------------------
def load_ohlcv(symbol: str, timeframe: str, years: int = 2) -> pd.DataFrame:
    """
    Load OHLCV candles for given symbol & timeframe.

    Strategy:
      - Always fetch 1h candles from Massive as a base
      - For 4h / 1d, resample from 1h (robust even if Massive doesn't have native 4h)
      - For 15m, try direct fetch; if empty, fall back to 1h and upsample (last resort)
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    timeframe = timeframe.lower()
    mapped_symbol = get_symbol(symbol)

    # Cached path by symbol & timeframe
    cache_path = os.path.join(DATA_DIR, f"{symbol.upper()}_{timeframe}.csv")

    if os.path.exists(cache_path):
        try:
            df_cached = pd.read_csv(cache_path, parse_dates=["timestamp"], index_col="timestamp")
            # Only return if not empty
            if not df_cached.empty:
                return df_cached
        except Exception:
            # If cache is corrupted, ignore and reload
            pass

    # --- Base: always get 1H from Massive ---
    df_1h = _fetch_massive(mapped_symbol, multiplier=1, timespan="hour", years=years)

    if df_1h.empty:
        # If even 1h is empty, we give up
        return df_1h

    # Normalize index frequency
    df_1h = df_1h.sort_index()

    # --- Build requested timeframe from base 1H ---
    if timeframe == "1h":
        df_out = df_1h

    elif timeframe == "4h":
        # Resample 1H → 4H
        df_out = df_1h.resample("4H").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        df_out = df_out.dropna(subset=["open", "high", "low", "close"])

    elif timeframe in ("1d", "1day", "d"):
        # Resample 1H → 1D
        df_out = df_1h.resample("1D").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        df_out = df_out.dropna(subset=["open", "high", "low", "close"])

    elif timeframe == "15m":
        # Try direct 15m from Massive first
        df_15 = _fetch_massive(mapped_symbol, multiplier=15, timespan="minute", years=years)
        if df_15.empty:
            # Last resort: upsample 1h → 15m (not ideal, but avoids total failure)
            df_15 = (
                df_1h.resample("15T")
                .ffill()
            )
        df_out = df_15

    else:
        # Unknown timeframe: fallback to 1h
        df_out = df_1h

    # Final clean + cache
    df_out = df_out.sort_index()
    df_out.index.name = "timestamp"

    try:
        df_out.to_csv(cache_path)
    except Exception:
        # If writing cache fails (e.g. read-only env), ignore
        pass

    return df_out
