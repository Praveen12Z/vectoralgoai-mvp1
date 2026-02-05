from __future__ import annotations
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta

# Yahoo tickers (no prefix needed for most)
YAHOO_MAP = {
    "NAS100": "^NDX",
    "US30":   "^DJI",
    "SPX500": "^GSPC",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "XAUUSD": "GC=F",   # Gold futures
    "XAGUSD": "SI=F",   # Silver futures
}

@st.cache_data(ttl=3600 * 6, show_spinner="Fetching market data...")
def load_ohlcv(symbol: str, timeframe: str, years: float = 3) -> pd.DataFrame:
    ticker = YAHOO_MAP.get(symbol.upper(), symbol.upper())

    # Yahoo timeframe mapping (1m only last 7 days, 1h last 730 days, etc.)
    period = f"{int(years * 365)}d" if years <= 2 else "max"  # safe

    try:
        df = yf.download(
            ticker,
            period=period,
            interval=timeframe,
            progress=False,
            auto_adjust=True,
            prepost=False
        )

        if df.empty:
            st.warning(f"No data from Yahoo for {symbol} ({ticker})")
            return pd.DataFrame()

        # Clean columns
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "timestamp"

        return df

    except Exception as e:
        st.error(f"Yahoo Finance error for {symbol}: {str(e)}")
        return pd.DataFrame()
