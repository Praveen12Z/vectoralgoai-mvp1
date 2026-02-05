from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from polygon import RESTClient

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Correct Polygon tickers (2026)
MARKET_MAP = {
    "NAS100": "I:NDX",
    "US30":   "I:DJI",
    "SPX500": "I:SPX",
    "EURUSD": "C:EURUSD",
    "GBPUSD": "C:GBPUSD",
    "USDJPY": "C:USDJPY",
    "AUDUSD": "C:AUDUSD",
    "USDCAD": "C:USDCAD",
    "EURJPY": "C:EURJPY",
    "GBPJPY": "C:GBPJPY",
    "XAUUSD": "XAUUSD",   # Gold
    "XAGUSD": "XAGUSD",   # Silver
}

@st.cache_data(ttl=3600 * 6, show_spinner="Fetching market data...")
def load_ohlcv(symbol: str, timeframe: str, years: int = 3) -> pd.DataFrame:
    api_key = st.secrets.get("MASSIVE_API_KEY")
    if not api_key:
        st.error("MASSIVE_API_KEY not found in secrets.")
        return pd.DataFrame()

    client = RESTClient(api_key)
    ticker = MARKET_MAP.get(symbol.upper(), symbol.upper())

    # Timeframe mapping
    tf_map = {
        "1m":  (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
        "1h":  (1, "hour"),   "4h": (4, "hour"),   "1d":  (1, "day")
    }
    mult, span = tf_map.get(timeframe.lower(), (1, "hour"))

    from_ = (datetime.utcnow() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
    to_   = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        aggs = list(client.list_aggs(
            ticker=ticker,
            multiplier=mult,
            timespan=span,
            from_=from_,
            to=to_,
            limit=50000,
            adjusted=True
        ))

        if not aggs:
            st.warning(f"No data returned for {symbol} ({ticker})")
            return pd.DataFrame()

        df = pd.DataFrame([{
            "timestamp": pd.to_datetime(a.timestamp, unit="ms"),
            "open": a.open, "high": a.high, "low": a.low,
            "close": a.close, "volume": a.volume
        } for a in aggs])

        df = df.set_index("timestamp").sort_index()
        return df

    except Exception as e:
        st.error(f"Polygon error for {symbol} ({ticker}): {str(e)}")
        return pd.DataFrame()
