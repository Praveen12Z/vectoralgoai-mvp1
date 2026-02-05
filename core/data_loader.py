from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from polygon import RESTClient

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

@st.cache_data(ttl=3600 * 24, show_spinner="Loading market data...")
def load_ohlcv(symbol: str, timeframe: str, years: int = 3) -> pd.DataFrame:
    """
    Load OHLCV data using Polygon API (via st.secrets).
    Caches result for 24 hours.
    """
    try:
        api_key = st.secrets["MASSIVE_API_KEY"]
    except KeyError:
        st.error("MASSIVE_API_KEY not found in .streamlit/secrets.toml")
        return pd.DataFrame()

    client = RESTClient(api_key)

    MARKET_MAP = {
        "NAS100": "NDX",
        "US30": "DJI",
        "SPX500": "SPX",
        "XAUUSD": "XAUUSD",
        "EURUSD": "EURUSD",
    }
    ticker = MARKET_MAP.get(symbol.upper(), symbol.upper())

    timeframe = timeframe.lower()
    if timeframe == "1h":
        multiplier, timespan = 1, "hour"
    elif timeframe == "4h":
        multiplier, timespan = 4, "hour"
    elif timeframe in ("1d", "d", "1day"):
        multiplier, timespan = 1, "day"
    else:
        st.warning(f"Unsupported timeframe '{timeframe}', falling back to 1h")
        multiplier, timespan = 1, "hour"

    from_ = (datetime.utcnow() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
    to_ = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        aggs = client.list_aggs(
            ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=from_,
            to=to_,
            limit=50000,
            adjusted=True
        )

        data = []
        for agg in aggs:
            data.append({
                "timestamp": pd.to_datetime(agg.timestamp, unit="ms"),
                "open": agg.open,
                "high": agg.high,
                "low": agg.low,
                "close": agg.close,
                "volume": agg.volume
            })

        if not data:
            st.warning("No data returned from Polygon")
            return pd.DataFrame()

        df = pd.DataFrame(data).set_index("timestamp").sort_index()
        
        # Simple cache to disk (optional – helps in development)
        cache_path = os.path.join(DATA_DIR, f"{symbol.upper()}_{timeframe}.csv")
        df.to_csv(cache_path)

        return df

    except Exception as e:
        st.error(f"Polygon API error: {str(e)}")
        return pd.DataFrame()