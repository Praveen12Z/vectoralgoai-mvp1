from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from twelvedata import TDClient

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Twelve Data symbols (2026 standard)
TD_MAP = {
    "NAS100": "NDX",
    "US30":   "DJI",
    "SPX500": "SPX",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
}

@st.cache_data(ttl=3600 * 6, show_spinner="Fetching market data from Twelve Data...")
def load_ohlcv(symbol: str, timeframe: str, years: float = 3) -> pd.DataFrame:
    api_key = st.secrets.get("TWELVE_DATA_API_KEY")
    if not api_key:
        st.error("TWELVE_DATA_API_KEY not found in secrets.")
        return pd.DataFrame()

    client = TDClient(apikey=api_key)
    td_symbol = TD_MAP.get(symbol.upper(), symbol.upper())

    # Timeframe mapping
    tf_map = {
        "1m": "1min", "5m": "5min", "15m": "15min",
        "1h": "1h", "4h": "4h", "1d": "1day"
    }
    interval = tf_map.get(timeframe.lower(), "1h")

    # Date range
    end_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    start_date = (datetime.utcnow() - timedelta(days=int(365 * years))).strftime("%Y-%m-%d %H:%M:%S")

    try:
        ts = client.time_series(
            symbol=td_symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            outputsize=5000,  # max per call
        )

        df = ts.as_pandas()

        if df.empty:
            st.warning(f"No data returned from Twelve Data for {symbol} ({td_symbol})")
            return pd.DataFrame()

        # Standardise columns
        df = df[["open", "high", "low", "close", "volume"]]
        df.index.name = "timestamp"

        # Cache locally (optional)
        cache_path = os.path.join(DATA_DIR, f"{symbol}_{timeframe}.csv")
        df.to_csv(cache_path)

        return df

    except Exception as e:
        st.error(f"Twelve Data error for {symbol}: {str(e)}")
        if "rate limit" in str(e).lower():
            st.error("Rate limit hit. Free tier: 800 calls/day. Wait or upgrade.")
        return pd.DataFrame()
