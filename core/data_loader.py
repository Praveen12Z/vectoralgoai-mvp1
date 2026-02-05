from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from twelvedata import TDClient

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

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

    tf_map = {
        "1m": "1min", "5m": "5min", "15m": "15min",
        "1h": "1h", "4h": "4h", "1d": "1day"
    }
    interval = tf_map.get(timeframe.lower(), "1h")

    end_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    start_date = (datetime.utcnow() - timedelta(days=int(365 * years))).strftime("%Y-%m-%d %H:%M:%S")

    try:
        ts = client.time_series(
            symbol=td_symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            outputsize=5000,
        )

        df = ts.as_pandas()

        if df.empty:
            st.warning(f"No data returned for {symbol} ({td_symbol})")
            return pd.DataFrame()

        # Standardize columns — volume is optional for forex
        standard_cols = ["open", "high", "low", "close"]
        available_cols = [col.lower() for col in df.columns]
        rename_map = {}
        for col in standard_cols:
            if col in available_cols:
                rename_map[col] = col
            elif col.capitalize() in df.columns:
                rename_map[col.capitalize()] = col

        # Volume if present
        if "volume" in available_cols:
            rename_map["volume"] = "volume"
        elif "Volume" in df.columns:
            rename_map["Volume"] = "volume"

        df = df.rename(columns=rename_map)

        # Keep only available standard columns
        keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[keep_cols]

        df.index.name = "timestamp"

        return df

    except Exception as e:
        st.error(f"Twelve Data error for {symbol} ({td_symbol}): {str(e)}")
        if "rate limit" in str(e).lower():
            st.error("Rate limit hit. Free tier: 800 calls/day. Wait or upgrade.")
        return pd.DataFrame()
